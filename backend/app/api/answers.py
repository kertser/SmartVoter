from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from backend.app.db import get_db
from backend.app.models.user_session import UserSession
from backend.app.models.user_answer import UserAnswer
from backend.app.models.question import Question
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

    # Apply answer_polarity: if the question is phrased in the opposite direction to
    # the policy-item axis, flip the stored value so comparisons with party positions
    # are correct.  E.g. "Should Haredim serve?" (support=+1) on axis
    # haredi_service:-1=mandatory,+1=exempt needs polarity=-1 so stored value=-1.
    polarity = 1.0
    if body.question_id:
        q_obj = db.query(Question).filter(Question.id == body.question_id).first()
        if q_obj and q_obj.answer_polarity is not None:
            polarity = q_obj.answer_polarity

    corrected_answer_value = round(body.answer_value * polarity, 4)

    answer = UserAnswer(
        id=uuid.uuid4(),
        session_id=body.session_id,
        question_id=body.question_id,
        policy_item_id=body.policy_item_id,
        answer_value=corrected_answer_value,
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

