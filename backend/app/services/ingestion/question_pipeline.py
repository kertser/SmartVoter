"""
Question Pipeline — Phase 6 / Gap 4.

Batch-generates Question records for PolicyItems that have no questions yet:

  PolicyItem (approved or needs_review)
    → LLM generate_question  → Question (needs_review)
    → LLM critique_question  → updates neutrality_score

This is the batch runner equivalent of POST /api/admin/llm/generate-questions.
Generated questions ALWAYS require human approval before becoming public.
(AGENTS.MD §7.5, §7.6, §7.7)

Also provides run_niche_discovery_pipeline() which specifically generates
questions for policy items where non-mainstream parties have strong, distinctive
legislative positions — enabling the adaptive questionnaire to surface unexpected
party matches (AGENTS.MD §14A concept: niche discovery).

Usage:
    from backend.app.services.ingestion.question_pipeline import (
        run_question_pipeline,
        run_niche_discovery_pipeline,
    )
    stats = run_question_pipeline(db, settings, limit=50)
    discovery_stats = run_niche_discovery_pipeline(db, settings, limit=20)
"""
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from backend.app.models.party_position import PartyPosition
from backend.app.models.policy_item import PolicyItem, ReviewStatus, PolicySourceType
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


# ─────────────────────────────────────────────────────────────────────────────
# Discovery question pipeline
# ─────────────────────────────────────────────────────────────────────────────

# Thresholds for "strong outsider position" — must both be met
DISCOVERY_MIN_POSITION_ABS = 0.45   # |position_mean| must be >= this
DISCOVERY_MIN_EVIDENCE = 0.55       # evidence_strength must be >= this


def run_niche_discovery_pipeline(
    db: Session,
    settings: "Settings",
    limit: int = 20,
    max_workers: int = 4,
    evidence_types: tuple[str, ...] = ("vote", "sponsored_bill"),
) -> dict[str, int]:
    """
    Generate questions specifically for NICHE policy items where a non-mainstream
    party has a distinctive, evidence-backed legislative position.

    Selection criteria for a "discovery" policy item:
      1. source_type is a legislative action (vote, bill) — real behavior, not just
         declared platform.
      2. At least one party position has |position_mean| >= DISCOVERY_MIN_POSITION_ABS
         AND evidence_strength >= DISCOVERY_MIN_EVIDENCE.
      3. No existing approved or llm_generated question covers this policy item.

    These questions are generated with the 'discovery_question_from_niche' prompt
    and tagged with llm_prompt_version='discovery-v1.3'. They start as
    human_review_status='needs_review' and require admin approval before going live.

    The resulting question pool feeds the adaptive questionnaire's discovery
    blend phase, which progressively surfaces potential outsider-party matches
    that the user hasn't considered.

    Returns {"processed": N, "created": N, "skipped": N, "errors": N}.
    """
    from backend.app.db.session import SessionLocal

    # --- Step 1: Find policy items that pass the discovery criteria ---
    eligible_pis: list[PolicyItem] = []
    seen_ids: set[uuid.UUID] = set()

    # Only legislative source types (strongest evidence; real behavior)
    source_type_filter = [PolicySourceType.vote, PolicySourceType.bill]

    pis = (
        db.query(PolicyItem)
        .filter(PolicyItem.source_type.in_(source_type_filter))
        .filter(PolicyItem.human_review_status.in_([
            ReviewStatus.approved,
            ReviewStatus.needs_review,
            ReviewStatus.llm_generated,
        ]))
        .limit(limit * 5)  # over-fetch, filter below
        .all()
    )

    for pi in pis:
        if pi.id in seen_ids:
            continue
        # Skip if question already exists
        existing = db.query(Question).filter(Question.policy_item_id == pi.id).first()
        if existing:
            continue
        # Check if any party has a strong distinctive position
        positions = (
            db.query(PartyPosition)
            .filter(PartyPosition.policy_item_id == pi.id)
            .all()
        )
        has_strong_outsider = any(
            abs(p.position_mean) >= DISCOVERY_MIN_POSITION_ABS
            and p.evidence_strength >= DISCOVERY_MIN_EVIDENCE
            for p in positions
        )
        if not has_strong_outsider:
            continue
        eligible_pis.append(pi)
        seen_ids.add(pi.id)
        if len(eligible_pis) >= limit:
            break

    if not eligible_pis:
        stats = {"processed": 0, "created": 0, "skipped": 0, "errors": 0}
        logger.info("niche_discovery_pipeline → %s (no eligible items)", stats)
        return stats

    # Snapshot data for worker threads
    pi_snapshots = []
    for pi in eligible_pis:
        positions = (
            db.query(PartyPosition)
            .filter(PartyPosition.policy_item_id == pi.id)
            .all()
        )
        # Build a short evidence context summary (anonymous — no party names)
        strong_positions = [
            p for p in positions
            if abs(p.position_mean) >= DISCOVERY_MIN_POSITION_ABS
            and p.evidence_strength >= DISCOVERY_MIN_EVIDENCE
        ]
        n_strong = len(strong_positions)
        avg_pos = (
            sum(abs(p.position_mean) for p in strong_positions) / n_strong
            if n_strong > 0 else 0.0
        )
        direction = "strongly support" if avg_pos > 0 else "strongly oppose"
        evidence_context = (
            f"{n_strong} parties have {direction} this policy "
            f"(average position strength: {avg_pos:.2f}). "
            f"Evidence is primarily from {pi.source_type.value} records."
        )

        pi_snapshots.append({
            "id": pi.id,
            "title": pi.title,
            "description": pi.description or "",
            "directional_axis": pi.directional_axis or "",
            "evidence_context": evidence_context,
        })

    processed = len(pi_snapshots)
    created = skipped = errors = 0

    def _process_one(pi_data: dict) -> dict:
        thread_db = SessionLocal()
        try:
            llm_raw = get_llm_provider(settings)
            llm = AuditedLLMService(llm_raw, thread_db)
            pi_id = pi_data["id"]

            input_data = {
                "title": pi_data["title"],
                "description": pi_data["description"],
                "directional_axis": pi_data["directional_axis"],
                "evidence_context": pi_data["evidence_context"],
            }

            # Use the dedicated discovery prompt
            result = llm.generate_discovery_question(
                input_data,
                entity_id=pi_id,
            )

            question_en = result.get("question_en") or result.get("question", "")
            if not question_en:
                logger.warning(
                    "niche_discovery_pipeline: LLM returned empty question for %s", pi_id
                )
                return {"created": False, "policy_item_id": str(pi_id)}

            fmt = check_question_format(
                question_en=question_en,
                question_he=result.get("question_he", ""),
                question_ru=result.get("question_ru", ""),
            )
            if not fmt["is_valid"]:
                logger.warning(
                    "niche_discovery_pipeline: rejected open-ended question for %s — %s",
                    pi_id, fmt["issue"],
                )
                return {
                    "created": False,
                    "format_error": fmt["issue"],
                    "policy_item_id": str(pi_id),
                }

            neutrality_score = float(result.get("neutrality_score", 0.70))

            q = Question(
                id=uuid.uuid4(),
                policy_item_id=pi_id,
                question_text_en=question_en,
                question_text_he=result.get("question_he", ""),
                question_text_ru=result.get("question_ru", ""),
                answer_scale_type=AnswerScaleType.likert_5,
                neutrality_score=neutrality_score,
                llm_prompt_version="discovery-v1.3",
                human_review_status=ReviewStatus.needs_review,
            )
            thread_db.add(q)
            thread_db.commit()
            logger.info(
                "niche_discovery_pipeline: created question %s for policy_item %s",
                q.id, pi_id,
            )
            return {"created": True, "policy_item_id": str(pi_id)}
        except Exception as exc:
            thread_db.rollback()
            logger.error(
                "niche_discovery_pipeline worker failed for %s: %s",
                pi_data["id"], exc,
            )
            return {
                "created": False,
                "error": str(exc),
                "policy_item_id": str(pi_data["id"]),
            }
        finally:
            thread_db.close()

    workers = min(max(1, max_workers), 10)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_one, snap): snap for snap in pi_snapshots}
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
                logger.error("niche_discovery_pipeline future failed: %s", exc)
                errors += 1

    stats = {"processed": processed, "created": created, "skipped": skipped, "errors": errors}
    logger.info("niche_discovery_pipeline → %s (workers=%d)", stats, workers)
    return stats


