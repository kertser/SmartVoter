from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.models.topic import Topic
from backend.app.schemas.topic import TopicOut

router = APIRouter(tags=["topics"])


@router.get("/topics", response_model=list[TopicOut])
def list_topics(db: Session = Depends(get_db)) -> list[TopicOut]:
    """Return all topics ordered by slug."""
    topics = db.query(Topic).order_by(Topic.slug).all()
    return [TopicOut.model_validate(t) for t in topics]

