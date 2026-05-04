import uuid
import datetime
from sqlalchemy import DateTime, func, JSON
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)  # client-generated
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_active_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

