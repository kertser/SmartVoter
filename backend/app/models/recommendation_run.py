import uuid
import datetime
from sqlalchemy import ForeignKey, DateTime, func, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_sessions.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    scoring_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(50), default="0.1.0")

