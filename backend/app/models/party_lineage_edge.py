import uuid
from sqlalchemy import ForeignKey, Float, String, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base
import enum


class LineageRelationType(str, enum.Enum):
    rename = "rename"
    split = "split"
    merger = "merger"
    successor = "successor"
    alliance = "alliance"
    rebrand = "rebrand"


class LineageReviewStatus(str, enum.Enum):
    draft = "draft"
    needs_review = "needs_review"
    approved = "approved"
    rejected = "rejected"


class PartyLineageEdge(Base):
    __tablename__ = "party_lineage_edges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    from_party_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("party_instances.id"), nullable=False, index=True
    )
    to_party_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("party_instances.id"), nullable=False, index=True
    )
    relation_type: Mapped[LineageRelationType] = mapped_column(
        SAEnum(LineageRelationType, name="lineage_relation_type")
    )
    continuity_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    llm_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_review_status: Mapped[LineageReviewStatus] = mapped_column(
        SAEnum(LineageReviewStatus, name="lineage_review_status"),
        default=LineageReviewStatus.draft,
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

