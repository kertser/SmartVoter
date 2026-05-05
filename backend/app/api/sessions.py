"""
Session management endpoints.
DELETE /api/sessions/{session_id} — right-to-erasure / privacy endpoint.
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

