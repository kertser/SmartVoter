import uuid
from sqlalchemy import String, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name_he: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    external_ids_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    public_profile_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

