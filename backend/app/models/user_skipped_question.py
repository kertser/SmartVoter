import uuid
import datetime
from sqlalchemy import ForeignKey, DateTime, func, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


class UserSkippedQuestion(Base):
    """
    Tracks questions a user has explicitly skipped as "not relevant / outdated".
    These questions are excluded from future question selection for this session.
    (AGENTS.MD Section 14.3 — user control over questionnaire)
    """

    __tablename__ = "user_skipped_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_sessions.id"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id"), nullable=False, index=True
    )
    # Reason the user skipped — "outdated" | "not_relevant" | "other"
    reason: Mapped[str] = mapped_column(String(50), nullable=False, default="outdated")
    skipped_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

