from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from backend.app.db import get_db
from backend.app.models.user_session import UserSession
from backend.app.models.question import Question
from backend.app.models.user_answer import UserAnswer
from backend.app.models.policy_item import PolicyItem, ReviewStatus
from backend.app.models.topic import Topic
from backend.app.models.party_position import PartyPosition
from backend.app.schemas.question import QuestionOut
from backend.app.schemas.session import SessionCreate, SessionOut
from backend.app.services.questionnaire import (
    select_next_question,
    QuestionCandidate,
    PartyPositionSlim,
)

router = APIRouter(tags=["questionnaire"])


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
    for answer in answered_rows:
        pi = db.query(PolicyItem).filter(PolicyItem.id == answer.policy_item_id).first()
        if pi:
            topic = db.query(Topic).filter(Topic.id == pi.topic_id).first()
            if topic:
                answered_topic_counts[topic.slug] = (
                    answered_topic_counts.get(topic.slug, 0) + 1
                )

    if len(answered_ids) >= 15:
        return None

    # Build candidates from approved questions not yet answered
    approved_questions = (
        db.query(Question)
        .filter(Question.human_review_status == ReviewStatus.approved)
        .all()
    )

    candidates: list[QuestionCandidate] = []
    for q in approved_questions:
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
    )

    if not best:
        return None

    q = db.query(Question).filter(Question.id == best.question_id).first()
    if not q:
        return None

    topic = db.query(Topic).join(PolicyItem, PolicyItem.topic_id == Topic.id).filter(
        PolicyItem.id == q.policy_item_id
    ).first()

    why_selected = (
        "Our first question covers the topic with most party disagreement."
        if len(answered_ids) == 0
        else "This question best distinguishes between your current top parties."
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
    )

