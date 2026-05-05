"""Volatility service — Phase 4."""
import uuid
from sqlalchemy.orm import Session

from backend.app.services.volatility.volatility_service import (
    compute_candidate_volatility,
    compute_party_volatility,
    run_volatility_update,
)

__all__ = [
    "compute_candidate_volatility",
    "compute_party_volatility",
    "run_volatility_update",
    "get_party_volatility",
]


def get_party_volatility(party_instance_id: uuid.UUID, db: Session) -> float:
    """
    Returns party volatility score (0..1) for the scoring engine.

    First checks the Party's associated Person memberships for a cached
    volatility score computed by run_volatility_update(). If not available,
    falls back to live computation via compute_party_volatility().

    This is the public interface used by the results API and scoring engine.
    """
    return compute_party_volatility(db, party_instance_id)


