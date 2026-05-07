from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
import logging

from backend.app.db import get_db
from backend.app.models.user_session import UserSession
from backend.app.models.question import Question, AnswerScaleType
from backend.app.models.user_answer import UserAnswer
from backend.app.models.policy_item import PolicyItem, ReviewStatus
from backend.app.models.topic import Topic
from backend.app.models.party_position import PartyPosition
from backend.app.schemas.question import QuestionOut
from backend.app.schemas.session import SessionCreate, SessionOut
from backend.app.services.questionnaire import (
    select_next_question,
    aggregate_salience_by_topic,
    QuestionCandidate,
    PartyPositionSlim,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["questionnaire"])


def _ui_strings() -> dict:
    """Static UI strings for why-selected explanations (i18n-ready placeholder)."""
    return {
        "why_selected": {
            "first_question": (
                "This is the first question. It helps us understand your general priorities."
            ),
            "adaptive_question": (
                "This question helps distinguish between parties that are currently "
                "close in your results."
            ),
            "auto_generated": (
                "This question was automatically generated because no pre-existing "
                "question covered this policy area."
            ),
        }
    }

# ── Statuses that the questionnaire can serve ─────────────────────────────────
# approved  = human-curated seed questions (highest quality)
# llm_generated = auto-generated on-the-fly, pending post-hoc admin review
_SERVABLE_STATUSES = {ReviewStatus.approved, ReviewStatus.llm_generated}


def _auto_generate_question(
    db: Session, best_pi: PolicyItem
) -> Question | None:
    """
    Generate a question for `best_pi` on-the-fly using the LLM provider.
    Stores with status=llm_generated for post-hoc admin review.
    Returns the saved Question, or None if generation fails.
    """
    from backend.app.config import get_settings
    from backend.app.services.llm import get_llm_provider
    from backend.app.services.llm.audit_service import AuditedLLMService

    try:
        settings = get_settings()
        provider = get_llm_provider(settings)
        svc = AuditedLLMService(provider, db)

        input_data = {
            "title": best_pi.title,
            "description": best_pi.description or "",
            "directional_axis": best_pi.directional_axis or "",
        }
        result = svc.generate_question(input_data, entity_id=best_pi.id)

        q = Question(
            policy_item_id=best_pi.id,
            question_text_en=result.get("question_en") or result.get("question", ""),
            question_text_he=result.get("question_he", ""),
            question_text_ru=result.get("question_ru", ""),
            answer_scale_type=AnswerScaleType.likert_5,
            neutrality_score=0.7,
            llm_prompt_version=result.get("_prompt_version", "v1.0-auto"),
            human_review_status=ReviewStatus.llm_generated,
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        logger.info("Auto-generated question %s for policy_item %s", q.id, best_pi.id)
        return q
    except Exception as exc:
        logger.warning("Auto-generation failed for policy_item %s: %s", best_pi.id, exc)
        return None


@router.post("/sessions", response_model=SessionOut)
def create_or_get_session(
    body: SessionCreate, db: Session = Depends(get_db)
) -> SessionOut:
    """Upsert an anonymous session. Client provides UUID or gets a new one."""
    session_id = body.session_id or uuid.uuid4()
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        session = UserSession(id=session_id)
        db.add(session)
        db.commit()
        db.refresh(session)
    return SessionOut(session_id=session.id, created_at=session.created_at)


@router.get("/questions/next", response_model=QuestionOut | None)
def get_next_question(
    session_id: uuid.UUID, db: Session = Depends(get_db)
) -> QuestionOut | None:
    """
    Returns the next adaptive question for a session.
    Returns null when 15 questions have been answered.
    Never exposes party scores. (AGENTS.MD Section 13)
    """
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    answered_rows = (
        db.query(UserAnswer).filter(UserAnswer.session_id == session_id).all()
    )
    answered_ids = [a.question_id for a in answered_rows]
    answered_topic_counts: dict[str, int] = {}
    # Build salience signal: (topic_slug, salience) pairs from all previous answers.
    # Used by select_next_question to follow the user's expressed priorities.
    answer_salience_pairs: list[tuple[str, float]] = []
    for answer in answered_rows:
        pi = db.query(PolicyItem).filter(PolicyItem.id == answer.policy_item_id).first()
        if pi:
            topic = db.query(Topic).filter(Topic.id == pi.topic_id).first()
            if topic:
                answered_topic_counts[topic.slug] = (
                    answered_topic_counts.get(topic.slug, 0) + 1
                )
                answer_salience_pairs.append((topic.slug, answer.salience))
    # Aggregate per-topic salience: use max salience seen for each topic so that
    # a single "Very important" answer drives follow-up even if others were neutral.
    user_salience_by_topic = aggregate_salience_by_topic(answer_salience_pairs)

    if len(answered_ids) >= 15:
        return None

    # Build candidates from servable questions (approved + llm_generated) not yet answered
    servable_questions = (
        db.query(Question)
        .filter(Question.human_review_status.in_(list(_SERVABLE_STATUSES)))
        .all()
    )

    # Root questions (is_root_question=True) are always served first,
    # unless already answered. They cover topics broadly before drilling down.
    unanswered_root_ids = [
        q.id for q in servable_questions
        if q.id not in answered_ids and q.is_root_question
    ]
    # If there are unanswered root questions, serve the first one directly
    # (no need to run the adaptive scoring algorithm yet).
    if unanswered_root_ids:
        root_q = db.query(Question).filter(Question.id == unanswered_root_ids[0]).first()
        if root_q:
            topic = db.query(Topic).filter(Topic.id == root_q.topic_id).first() if root_q.topic_id else None
            why_selected = "This is an opening question that helps us understand your general priorities."
            return QuestionOut(
                id=root_q.id,
                question_text_en=root_q.question_text_en,
                question_text_he=root_q.question_text_he,
                question_text_ru=root_q.question_text_ru,
                answer_scale_type=root_q.answer_scale_type.value,
                policy_item_id=root_q.policy_item_id,
                topic_slug=topic.slug if topic else "unknown",
                topic_name_he=topic.name_he if topic else None,
                topic_name_ru=topic.name_ru if topic else None,
                context_note=None,
                why_selected=why_selected,
            )

    candidates: list[QuestionCandidate] = []
    for q in servable_questions:
        if q.id in answered_ids:
            continue
        pi = db.query(PolicyItem).filter(PolicyItem.id == q.policy_item_id).first()
        if not pi:
            continue
        topic = db.query(Topic).filter(Topic.id == pi.topic_id).first()
        topic_slug = topic.slug if topic else "unknown"

        # Evidence quality = avg evidence_strength across all party positions for this item
        positions = (
            db.query(PartyPosition)
            .filter(PartyPosition.policy_item_id == q.policy_item_id)
            .all()
        )
        avg_evidence = (
            sum(p.evidence_strength for p in positions) / len(positions)
            if positions
            else 0.0
        )

        candidates.append(
            QuestionCandidate(
                question_id=q.id,
                policy_item_id=q.policy_item_id,
                topic_slug=topic_slug,
                evidence_quality=avg_evidence,
            )
        )

    # Top-party positions (stub for Phase 1: use all parties)
    all_positions = db.query(PartyPosition).all()
    party_ids = list({p.party_instance_id for p in all_positions})
    top_party_positions: list[list[PartyPositionSlim]] = []
    for pid in party_ids[:5]:
        party_pos = [
            PartyPositionSlim(
                policy_item_id=p.policy_item_id, position_mean=p.position_mean
            )
            for p in all_positions
            if p.party_instance_id == pid
        ]
        top_party_positions.append(party_pos)

    best = select_next_question(
        answered_ids=answered_ids,
        candidates=candidates,
        top_party_positions=top_party_positions,
        answered_topic_counts=answered_topic_counts,
        user_salience_by_topic=user_salience_by_topic,
    )

    # ── Auto-generate on-the-fly when no pre-existing question is available ──
    if not best:
        # Find policy items that have party positions but no servable question yet
        answered_policy_ids = {a.policy_item_id for a in answered_rows}
        servable_pi_ids = {q.policy_item_id for q in servable_questions}

        candidate_pis = (
            db.query(PolicyItem)
            .filter(PolicyItem.id.notin_(answered_policy_ids | servable_pi_ids))
            .all()
        )

        # Pick the policy item with the best average evidence strength
        best_pi: PolicyItem | None = None
        best_score = -1.0
        for pi in candidate_pis:
            positions = (
                db.query(PartyPosition).filter(PartyPosition.policy_item_id == pi.id).all()
            )
            if not positions:
                continue
            score = sum(p.evidence_strength for p in positions) / len(positions)
            if score > best_score:
                best_score = score
                best_pi = pi

        if best_pi:
            new_q = _auto_generate_question(db, best_pi)
            if new_q:
                # Build the response directly from the newly generated question
                topic = (
                    db.query(Topic)
                    .join(PolicyItem, PolicyItem.topic_id == Topic.id)
                    .filter(PolicyItem.id == best_pi.id)
                    .first()
                )
                return QuestionOut(
                    id=new_q.id,
                    question_text_en=new_q.question_text_en,
                    question_text_he=new_q.question_text_he,
                    question_text_ru=new_q.question_text_ru,
                    answer_scale_type=new_q.answer_scale_type.value,
                    policy_item_id=new_q.policy_item_id,
                    topic_slug=topic.slug if topic else "unknown",
                    topic_name_he=topic.name_he if topic else None,
                    topic_name_ru=topic.name_ru if topic else None,
                    context_note=None,
                    why_selected=_ui_strings()["why_selected"]["auto_generated"],
                )
        return None

    q = db.query(Question).filter(Question.id == best.question_id).first()
    if not q:
        return None

    topic = db.query(Topic).join(PolicyItem, PolicyItem.topic_id == Topic.id).filter(
        PolicyItem.id == q.policy_item_id
    ).first()

    why_selected = (
        _ui_strings()["why_selected"]["first_question"]
        if len(answered_ids) == 0
        else _ui_strings()["why_selected"]["adaptive_question"]
    )

    return QuestionOut(
        id=q.id,
        question_text_en=q.question_text_en,
        question_text_he=q.question_text_he,
        question_text_ru=q.question_text_ru,
        answer_scale_type=q.answer_scale_type.value,
        policy_item_id=q.policy_item_id,
        topic_slug=topic.slug if topic else "unknown",
        topic_name_he=topic.name_he if topic else None,
        topic_name_ru=topic.name_ru if topic else None,
        context_note=None,
        why_selected=why_selected,
        is_root_question=q.is_root_question,
    )

