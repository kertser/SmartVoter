import uuid
import datetime
from sqlalchemy import ForeignKey, Date, Float, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base
import enum


class MembershipRole(str, enum.Enum):
    mk = "mk"
    candidate = "candidate"
    minister = "minister"
    leader = "leader"
    founder = "founder"


class PersonPartyMembership(Base):
    __tablename__ = "person_party_memberships"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id"), nullable=False, index=True
    )
    party_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("party_instances.id"), nullable=False, index=True
    )
    role: Mapped[MembershipRole] = mapped_column(
        SAEnum(MembershipRole, name="membership_role")
    )
    start_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

