from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.models.question import Question
from backend.app.models.policy_item import ReviewStatus

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


@admin_router.get("/review/items")
def get_review_items(db: Session = Depends(get_db)) -> list[dict]:
    """Return all questions not yet approved — for admin review."""
    questions = (
        db.query(Question)
        .filter(Question.human_review_status != ReviewStatus.approved)
        .all()
    )
    return [
        {
            "id": str(q.id),
            "question_text_en": q.question_text_en,
            "status": q.human_review_status.value,
            "answer_scale_type": q.answer_scale_type.value,
            "neutrality_score": q.neutrality_score,
        }
        for q in questions
    ]


@admin_router.post("/review/{item_id}/approve")
def approve_item(item_id: str, db: Session = Depends(get_db)) -> dict:
    """Approve a question for public use."""
    import uuid
    q = db.query(Question).filter(Question.id == uuid.UUID(item_id)).first()
    if not q:
        return {"error": "Not found"}
    q.human_review_status = ReviewStatus.approved
    db.commit()
    return {"status": "approved", "id": item_id}


@admin_router.post("/review/{item_id}/reject")
def reject_item(item_id: str, db: Session = Depends(get_db)) -> dict:
    """Reject a question."""
    import uuid
    q = db.query(Question).filter(Question.id == uuid.UUID(item_id)).first()
    if not q:
        return {"error": "Not found"}
    q.human_review_status = ReviewStatus.rejected
    db.commit()
    return {"status": "rejected", "id": item_id}

