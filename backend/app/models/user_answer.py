import uuid
import datetime
from sqlalchemy import ForeignKey, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


class UserAnswer(Base):
    __tablename__ = "user_answers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_sessions.id"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id"), nullable=False, index=True
    )
    policy_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_items.id"), nullable=True, index=True
    )
    answer_value: Mapped[float] = mapped_column(Float, nullable=False)  # -1 to +1
    salience: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)  # 0.5|1.0|2.0
    answered_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

