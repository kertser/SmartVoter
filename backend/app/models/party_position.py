import uuid
from sqlalchemy import ForeignKey, Float, Text, String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


class PartyPosition(Base):
    __tablename__ = "party_positions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    party_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("party_instances.id"), nullable=False, index=True
    )
    policy_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policy_items.id"), nullable=False, index=True
    )
    position_mean: Mapped[float] = mapped_column(Float, nullable=False)
    position_uncertainty: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    evidence_strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    evidence_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_refs_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    llm_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

