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

    Priority order:
    1. Persisted `volatility_score` column on PartyInstance (set by run_volatility_update)
    2. In-memory mock cache (set during seeding via register_mock_volatility)
    3. Live computation via compute_party_volatility()
    """
    # 1. Check persisted DB value (avoids losing scores on restart)
    try:
        from backend.app.models.party_instance import PartyInstance

        party = db.query(PartyInstance).filter(PartyInstance.id == party_instance_id).first()
        if party and party.volatility_score is not None:
            return party.volatility_score
    except Exception:
        pass  # Fall through to cache / live computation

    # 2. In-memory mock cache (seed data)
    if party_instance_id in _mock_volatility_cache:
        return _mock_volatility_cache[party_instance_id]

    # 3. Live computation
    return compute_party_volatility(db, party_instance_id)

