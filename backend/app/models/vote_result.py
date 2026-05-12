import uuid
from sqlalchemy import ForeignKey, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base
import enum


class VoteValue(str, enum.Enum):
    for_ = "for"
    against = "against"
    abstain = "abstain"
    absent = "absent"
    unknown = "unknown"


class VoteResult(Base):
    __tablename__ = "vote_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vote_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("votes.id"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id"), nullable=False, index=True
    )
    party_instance_id_at_time: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("party_instances.id"), nullable=True, index=True
    )
    vote_value: Mapped[VoteValue] = mapped_column(
        SAEnum(
            VoteValue,
            name="vote_value",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        )
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

