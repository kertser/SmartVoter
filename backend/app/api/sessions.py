"""
Session management endpoints.
DELETE /api/sessions/{session_id}           — right-to-erasure / privacy endpoint.
DELETE /api/sessions/{session_id}/answers/last — undo the most recent answer (go back).
(AGENTS.MD Section 14C.1)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from backend.app.db import get_db
from backend.app.models.user_session import UserSession
from backend.app.models.user_answer import UserAnswer
from backend.app.models.recommendation_run import RecommendationRun

router = APIRouter(tags=["sessions"])


@router.delete("/sessions/{session_id}")
def delete_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """
    Permanently delete a user session and all associated data.
    Cascade-deletes: user_answers → recommendation_runs → user_session.
    Returns {"deleted": true} whether or not the session existed (idempotent).
    """
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        # Idempotent: if already deleted, return success
        return {"deleted": True, "note": "Session not found (may have already been deleted)"}

    # Delete answers
    db.query(UserAnswer).filter(UserAnswer.session_id == session_id).delete(
        synchronize_session=False
    )
    # Delete recommendation runs
    db.query(RecommendationRun).filter(RecommendationRun.session_id == session_id).delete(
        synchronize_session=False
    )
    # Delete session
    db.delete(session)
    db.commit()

    return {"deleted": True}


@router.delete("/sessions/{session_id}/answers/last")
def undo_last_answer(session_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """
    Remove the most recently submitted answer for this session (go-back feature).
    Returns the question_id of the deleted answer so the frontend knows which
    question to re-show. If no answers exist, returns {"deleted": false}.
    """
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    last_answer = (
        db.query(UserAnswer)
        .filter(UserAnswer.session_id == session_id)
        .order_by(UserAnswer.answered_at.desc())
        .first()
    )
    if not last_answer:
        return {"deleted": False, "question_id": None}

    question_id = str(last_answer.question_id)
    db.delete(last_answer)
    db.commit()
    return {"deleted": True, "question_id": question_id}


