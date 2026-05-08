import uuid
from sqlalchemy import ForeignKey, Float, String, Text, Boolean, Enum as SAEnum
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
    policy_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_items.id"), nullable=True, index=True
    )
    # Root questions are topic-level entry points in the question tree.
    # They have is_root_question=True and topic_id set.
    # Follow-up questions (is_root_question=False) are adaptive and policy-item-level.
    is_root_question: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id"), nullable=True, index=True
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
    # answer_polarity: +1.0 means "Strongly support" on the question = +1 on the policy axis.
    # -1.0 means the question is phrased in the OPPOSITE direction to the axis
    # (e.g. "Should Haredim serve?" → support=+1 but axis is haredi_service: +1=exempt).
    # The answers API multiplies answer_value by answer_polarity before storage.
    answer_polarity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    human_review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="question_review_status"),
        default=ReviewStatus.draft,
    )

