import uuid
from sqlalchemy import String, ForeignKey, JSON, Text, Float, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base
import enum


class PolicySourceType(str, enum.Enum):
    vote = "vote"
    bill = "bill"
    platform = "platform"
    statement = "statement"
    candidate_history = "candidate_history"


class ReviewStatus(str, enum.Enum):
    draft = "draft"
    llm_generated = "llm_generated"
    needs_review = "needs_review"
    approved = "approved"
    rejected = "rejected"
    deprecated = "deprecated"


class PolicyItem(Base):
    __tablename__ = "policy_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id"), nullable=False, index=True
    )
    directional_axis: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_type: Mapped[PolicySourceType] = mapped_column(
        SAEnum(PolicySourceType, name="policy_source_type")
    )
    source_refs_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    llm_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="policy_review_status"),
        default=ReviewStatus.draft,
    )

