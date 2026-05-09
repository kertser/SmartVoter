"""
QuestionExplanation — dedicated cache for LLM-generated question explanations.

Keyed by (question_id, lang). On the first request the LLM is called and the
result is stored here; subsequent requests return the stored text without any
LLM call.

Unlike the generic llm_outputs audit table (which caches by input_hash), this
table is indexed directly by (question_id, lang) so lookups are O(1) and
survive question text edits.
"""
import uuid
import datetime
from sqlalchemy import ForeignKey, String, Text, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class QuestionExplanation(Base):
    __tablename__ = "question_explanations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Language code: "en" | "he" | "ru"
    lang: Mapped[str] = mapped_column(String(10), nullable=False)

    # Explanation fields (mirrors the LLM output schema of explain_question_context)
    background: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_relevant: Mapped[str | None] = mapped_column(Text, nullable=True)
    support_side: Mapped[str | None] = mapped_column(Text, nullable=True)
    oppose_side: Mapped[str | None] = mapped_column(Text, nullable=True)
    everyday_example: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Source: "llm" for fresh generation, "stored" for DB-loaded
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="llm")

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("question_id", "lang", name="uq_question_explanation_lang"),
    )

