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
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from backend.app.models.policy_item import PolicyItem, ReviewStatus
from backend.app.models.question import Question, AnswerScaleType
from backend.app.services.llm import get_llm_provider
from backend.app.services.llm.audit_service import AuditedLLMService

if TYPE_CHECKING:
    from backend.app.config import Settings

logger = logging.getLogger(__name__)

# Minimum neutrality_score required before a question moves to public
PUBLIC_NEUTRALITY_THRESHOLD = 0.75


def run_question_pipeline(
    db: Session,
    settings: "Settings",
    limit: int = 50,
    only_status: str | None = None,
    skip_existing: bool = True,
) -> dict[str, int]:
    """
    For each PolicyItem with no Question yet (or filtered by status),
    call the LLM to generate + critique a question.

    Questions are created with human_review_status = "needs_review".
    No question becomes public without human approval.

    Args:
        only_status: if set, only process policy items with this review_status value
                     (e.g., "approved"). Default: approved + needs_review.
        skip_existing: skip policy items that already have at least one question.

    Returns {"processed": N, "created": N, "skipped": N, "errors": N}.
    """
    llm_raw = get_llm_provider(settings)
    llm = AuditedLLMService(llm_raw, db)

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

    processed = created = skipped = errors = 0

    for pi in policy_items:
        processed += 1

        if skip_existing:
            existing = db.query(Question).filter(Question.policy_item_id == pi.id).first()
            if existing:
                skipped += 1
                continue

        try:
            q = _generate_question_for_item(db, llm, pi)
            if q:
                db.commit()
                created += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.error("question_pipeline failed for policy_item %s: %s", pi.id, exc)
            db.rollback()
            errors += 1

    stats = {"processed": processed, "created": created, "skipped": skipped, "errors": errors}
    logger.info("question_pipeline → %s", stats)
    return stats


def _generate_question_for_item(
    db: Session,
    llm: AuditedLLMService,
    pi: PolicyItem,
) -> Question | None:
    """
    Generate + critique a single question for a PolicyItem in one LLM call.
    Returns the created Question row (not yet committed), or None.
    """
    input_data = {
        "title": pi.title,
        "description": pi.description or "",
        "directional_axis": pi.directional_axis or "",
    }

    # Single combined call: generate + critique (1 LLM call instead of 2)
    result = llm.generate_question_with_critique(input_data, entity_id=pi.id)

    question_en = result.get("question_en") or result.get("question", "")
    if not question_en:
        logger.warning("LLM returned empty question for policy_item %s", pi.id)
        return None

    # neutrality_score already computed inside generate_question_with_critique
    neutrality_score = float(result.get("neutrality_score", 0.7))

    q = Question(
        id=uuid.uuid4(),
        policy_item_id=pi.id,
        question_text_en=question_en,
        question_text_he=result.get("question_he", ""),
        question_text_ru=result.get("question_ru", ""),
        answer_scale_type=AnswerScaleType.likert_5,
        neutrality_score=neutrality_score,
        llm_prompt_version=result.get("_prompt_version", "v1.0"),
        human_review_status=ReviewStatus.needs_review,
    )
    db.add(q)
    db.flush()
    return q

