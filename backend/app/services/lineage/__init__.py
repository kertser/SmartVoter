"""Lineage service — Phase 4."""
import uuid
from sqlalchemy.orm import Session

from backend.app.services.lineage.lineage_service import (
    run_lineage_inference,
)

__all__ = ["run_lineage_inference", "get_lineage_prior"]


def get_lineage_prior(party_instance_id: uuid.UUID, db: Session) -> float:
    """
    Returns a continuity weight (0–1) representing how strongly this party
    instance is a continuation of any predecessor party.

    Traverses approved or needs_review party_lineage_edges and returns the
    maximum continuity_weight among incoming edges (i.e., edges that lead
    *to* this party instance).  Falls back to 0.5 if no edges are found.

    This value is used in the new-party scoring formula (AGENTS.MD §9.1):
      position += party_lineage_prior_weight * predecessor_position * continuity_weight
    """
    from backend.app.models.party_lineage_edge import PartyLineageEdge, LineageReviewStatus

    edges = (
        db.query(PartyLineageEdge)
        .filter(
            PartyLineageEdge.to_party_instance_id == party_instance_id,
            PartyLineageEdge.human_review_status.in_([
                LineageReviewStatus.approved,
                LineageReviewStatus.needs_review,
            ]),
        )
        .all()
    )

    if not edges:
        return 0.5  # no lineage known

    # Return the highest incoming continuity weight
    return max(e.continuity_weight for e in edges if e.continuity_weight is not None)

