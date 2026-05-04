from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from backend.app.db import get_db
from backend.app.models.user_session import UserSession
from backend.app.models.user_answer import UserAnswer
from backend.app.schemas.question import AnswerIn, AnswerOut

router = APIRouter(tags=["answers"])


@router.post("/answers", response_model=AnswerOut)
def submit_answer(body: AnswerIn, db: Session = Depends(get_db)) -> AnswerOut:
    """
    Record a user's answer. Does NOT return party scores — scores only
    available at GET /results/{session_id}. (AGENTS.MD Section 13.3)
    """
    session = db.query(UserSession).filter(UserSession.id == body.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    answer = UserAnswer(
        id=uuid.uuid4(),
        session_id=body.session_id,
        question_id=body.question_id,
        policy_item_id=body.policy_item_id,
        answer_value=body.answer_value,
        salience=body.salience,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return AnswerOut(
        id=answer.id,
        session_id=answer.session_id,
        answered_at=answer.answered_at,
    )

