import uuid
import datetime
from sqlalchemy import String, Date, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    title_he: Mapped[str] = mapped_column(String(500), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary_he: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    date_submitted: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

