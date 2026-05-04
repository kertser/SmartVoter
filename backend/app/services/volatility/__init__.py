"""Volatility service stub — Phase 1. Phase 4+ computes from candidate turnover etc."""
import uuid
from sqlalchemy.orm import Session

# Mock volatility scores by party UUID (populated from seed data)
_MOCK_VOLATILITY: dict[str, float] = {}


def register_mock_volatility(party_instance_id: uuid.UUID, score: float) -> None:
    _MOCK_VOLATILITY[str(party_instance_id)] = score


def get_party_volatility(party_instance_id: uuid.UUID, db: Session) -> float:
    """Returns party volatility score (0..1). Phase 1: uses seed-registered mock values."""
    return _MOCK_VOLATILITY.get(str(party_instance_id), 0.15)

