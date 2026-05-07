"""
Question Pipeline — Phase 6 / Gap 4.

Batch-generates Question records for PolicyItems that have no questions yet:

  PolicyItem (approved or needs_review)
    → LLM generate_question  → Question (needs_review)
    → LLM critique_question  → updates neutrality_score

This is the batch runner equivalent of POST /api/admin/llm/generate-questions.
Generated questions ALWAYS require human approval before becoming public.
(AGENTS.MD §7.5, §7.6, §7.7)

Usage:
    from backend.app.services.ingestion.question_pipeline import run_question_pipeline
    stats = run_question_pipeline(db, settings, limit=50)
"""
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from backend.app.models.policy_item import PolicyItem, ReviewStatus
from backend.app.models.question import Question, AnswerScaleType
from backend.app.services.llm import get_llm_provider
from backend.app.services.llm.audit_service import AuditedLLMService
from backend.app.services.llm.question_format import check_question_format

if TYPE_CHECKING:
    from backend.app.config import Settings

logger = logging.getLogger(__name__)

# Minimum neutrality_score required before a question moves to public
PUBLIC_NEUTRALITY_THRESHOLD = 0.75

# Default number of parallel LLM workers for the pipeline
DEFAULT_WORKERS = 6


def run_question_pipeline(
    db: Session,
    settings: "Settings",
    limit: int = 50,
    only_status: str | None = None,
    skip_existing: bool = True,
    max_workers: int = DEFAULT_WORKERS,
) -> dict[str, int]:
    """
    For each PolicyItem with no Question yet (or filtered by status),
    call the LLM to generate + critique a question.

    Runs LLM calls in parallel (max_workers threads), each with its own
    DB session to avoid SQLAlchemy thread-safety issues.

    Questions are created with human_review_status = "needs_review".
    No question becomes public without human approval.

    Args:
        only_status: if set, only process policy items with this review_status value
                     (e.g., "approved"). Default: approved + needs_review.
        skip_existing: skip policy items that already have at least one question.
        max_workers: number of concurrent LLM calls (capped at 15).

    Returns {"processed": N, "created": N, "skipped": N, "errors": N}.
    """
    from backend.app.db.session import SessionLocal

    # Collect IDs to process from the caller's session (read-only query)
    query = db.query(PolicyItem)
    if only_status:
        query = query.filter(PolicyItem.human_review_status == only_status)
    else:
        query = query.filter(
            PolicyItem.human_review_status.in_([
                ReviewStatus.approved,
                ReviewStatus.needs_review,
                ReviewStatus.llm_generated,
            ])
        )
    policy_items = query.limit(limit).all()

    # Pre-filter: skip items that already have a question (done in the main session)
    items_to_process: list[PolicyItem] = []
    skipped = 0
    for pi in policy_items:
        if skip_existing:
            existing = db.query(Question).filter(Question.policy_item_id == pi.id).first()
            if existing:
                skipped += 1
                continue
        items_to_process.append(pi)

    processed = len(items_to_process) + skipped
    created = errors = 0

    if not items_to_process:
        stats = {"processed": processed, "created": created, "skipped": skipped, "errors": errors}
        logger.info("question_pipeline → %s (nothing to do)", stats)
        return stats

    # Snapshot policy-item data so worker threads don't share the caller session
    pi_snapshots = [
        {
            "id": pi.id,
            "title": pi.title,
            "description": pi.description or "",
            "directional_axis": pi.directional_axis or "",
        }
        for pi in items_to_process
    ]

    def _process_one(pi_data: dict) -> dict:
        """Worker: each call gets its own DB session."""
        thread_db = SessionLocal()
        try:
            llm_raw = get_llm_provider(settings)
            llm = AuditedLLMService(llm_raw, thread_db)
            pi_id = pi_data["id"]

            input_data = {
                "title": pi_data["title"],
                "description": pi_data["description"],
                "directional_axis": pi_data["directional_axis"],
            }
            result = llm.generate_question_with_critique(input_data, entity_id=pi_id)

            question_en = result.get("question_en") or result.get("question", "")
            if not question_en:
                logger.warning("LLM returned empty question for policy_item %s", pi_id)
                return {"created": False, "policy_item_id": str(pi_id)}

            # ── Format validation: reject open-ended questions before they reach the DB ──
            fmt = check_question_format(
                question_en=question_en,
                question_he=result.get("question_he", ""),
                question_ru=result.get("question_ru", ""),
            )
            if not fmt["is_valid"]:
                logger.warning(
                    "question_pipeline: open-ended question rejected for policy_item %s — %s",
                    pi_id, fmt["issue"],
                )
                return {
                    "created": False,
                    "format_error": fmt["issue"],
                    "policy_item_id": str(pi_id),
                }

            neutrality_score = float(result.get("neutrality_score", 0.7))

            q = Question(
                id=uuid.uuid4(),
                policy_item_id=pi_id,
                question_text_en=question_en,
                question_text_he=result.get("question_he", ""),
                question_text_ru=result.get("question_ru", ""),
                answer_scale_type=AnswerScaleType.likert_5,
                neutrality_score=neutrality_score,
                llm_prompt_version=result.get("_prompt_version", "v1.0"),
                human_review_status=ReviewStatus.needs_review,
            )
            thread_db.add(q)
            thread_db.commit()
            return {"created": True, "policy_item_id": str(pi_id)}
        except Exception as exc:
            thread_db.rollback()
            logger.error("question_pipeline worker failed for %s: %s", pi_data["id"], exc)
            return {"created": False, "error": str(exc), "policy_item_id": str(pi_data["id"])}
        finally:
            thread_db.close()

    workers = min(max(1, max_workers), 15)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_one, pi_data): pi_data for pi_data in pi_snapshots}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result.get("created"):
                    created += 1
                elif "error" in result:
                    errors += 1
                else:
                    skipped += 1
            except Exception as exc:
                logger.error("question_pipeline future failed: %s", exc)
                errors += 1

    stats = {"processed": processed, "created": created, "skipped": skipped, "errors": errors}
    logger.info("question_pipeline → %s (workers=%d)", stats, workers)
    return stats

