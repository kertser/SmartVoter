import uuid
import datetime
from sqlalchemy import String, Date, JSON, ForeignKey, Integer, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    bill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bills.id"), nullable=True, index=True
    )
    title_he: Mapped[str] = mapped_column(String(500), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    knesset_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vote_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_procedural_estimate: Mapped[bool] = mapped_column(Boolean, default=False)
    importance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

