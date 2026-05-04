import uuid
from sqlalchemy import ForeignKey, Float, String, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base
from backend.app.models.policy_item import ReviewStatus
import enum


class AnswerScaleType(str, enum.Enum):
    likert_5 = "likert_5"
    binary = "binary"
    tradeoff = "tradeoff"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    policy_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policy_items.id"), nullable=False, index=True
    )
    question_text_he: Mapped[str] = mapped_column(Text, nullable=False)
    question_text_en: Mapped[str] = mapped_column(Text, nullable=False)
    question_text_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_scale_type: Mapped[AnswerScaleType] = mapped_column(
        SAEnum(AnswerScaleType, name="answer_scale_type"),
        default=AnswerScaleType.likert_5,
    )
    neutrality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    complexity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    human_review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="question_review_status"),
        default=ReviewStatus.draft,
    )

