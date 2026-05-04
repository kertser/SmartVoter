"""Lineage service stub — Phase 1."""
import uuid
from sqlalchemy.orm import Session


def get_lineage_prior(party_instance_id: uuid.UUID, db: Session) -> float:
    """Returns a lineage-based position prior weight (0–1).
    Phase 1: stub returning 0.5. Phase 4+ will traverse party_lineage_edges."""
    return 0.5

