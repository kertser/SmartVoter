import uuid
import datetime
from sqlalchemy import String, DateTime, func, Date, ForeignKey, Integer, Enum as SAEnum, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base
import enum


class PartyStatus(str, enum.Enum):
    active = "active"
    dissolved = "dissolved"
    merged = "merged"
    split = "split"
    renamed = "renamed"


class PartyInstance(Base):
    __tablename__ = "party_instances"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    political_brand_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("political_brands.id"), nullable=False, index=True
    )
    official_name: Mapped[str] = mapped_column(String(255), nullable=False)
    election_cycle: Mapped[str | None] = mapped_column(String(50), nullable=True)
    knesset_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[PartyStatus] = mapped_column(
        SAEnum(PartyStatus, name="party_status"), default=PartyStatus.active
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # Persisted volatility score (0..1). NULL = not yet computed.
    volatility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Left-right political axis score: -1.0 (far left) .. +1.0 (far right). NULL = not yet computed.
    left_right_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # High-level political bloc for grouping/display: right | center-right | center | left | arab
    political_bloc: Mapped[str | None] = mapped_column(String(20), nullable=True)


