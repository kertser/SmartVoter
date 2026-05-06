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
    "register_mock_volatility",
]

# In-memory cache for mock/seed volatility scores keyed by party_instance_id
_mock_volatility_cache: dict[uuid.UUID, float] = {}


def register_mock_volatility(party_id: uuid.UUID, score: float) -> None:
    """Register a mock volatility score for a party instance.

    Called during seeding so that get_party_volatility() can return
    pre-computed mock values without hitting the DB computation path.
    """
    _mock_volatility_cache[party_id] = score


def get_party_volatility(party_instance_id: uuid.UUID, db: Session) -> float:
    """
    Returns party volatility score (0..1) for the scoring engine.

    Checks the mock cache first (populated during seeding via
    register_mock_volatility()), then falls back to live computation
    via compute_party_volatility().

    This is the public interface used by the results API and scoring engine.
    """
    if party_instance_id in _mock_volatility_cache:
        return _mock_volatility_cache[party_instance_id]
    return compute_party_volatility(db, party_instance_id)


