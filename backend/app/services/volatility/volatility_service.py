"""
Volatility Service — Phase 4 / Gap 6.

Computes candidate and party volatility scores per AGENTS.MD §10.

Candidate volatility (0..1):
  - number of party switches
  - ideological distance between old and new parties
  - recency of switch

Party volatility (0..1):
  - candidate turnover rate
  - leadership changes
  - rename / rebrand count
  - merger / split count
  - proportion of high-volatility candidates

Volatility scores are stored in:
  - Person.external_ids_json["volatility"] (candidate)
  - PartyInstance — returned as a computed dict, NOT stored in DB in MVP
    (the scoring engine reads PARTY_VOLATILITY from seed data or this service)

Usage:
    from backend.app.services.volatility.volatility_service import (
        compute_candidate_volatility,
        compute_party_volatility,
        run_volatility_update,
    )
"""
import logging
import math
import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from backend.app.models.person import Person
from backend.app.models.person_party_membership import PersonPartyMembership
from backend.app.models.party_instance import PartyInstance
from backend.app.models.party_lineage_edge import PartyLineageEdge, LineageRelationType
from backend.app.models.party_position import PartyPosition

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# AGENTS.MD §10.1
_SWITCH_BASE_WEIGHT = 0.25       # per party switch
_HALF_LIFE_YEARS = 4.0           # recency decay
_DISTANCE_SCALE = 0.30           # ideological distance contribution
_MAX_CANDIDATE_VOLATILITY = 1.0

# AGENTS.MD §10.2
_TURNOVER_WEIGHT = 0.30
_LEADERSHIP_CHANGE_WEIGHT = 0.20
_LINEAGE_EVENT_WEIGHT = 0.15     # per rename/merger/split
_HIGH_CANDIDATE_VOLATILITY_WEIGHT = 0.35


# ── Candidate volatility ───────────────────────────────────────────────────────

def compute_candidate_volatility(
    db: Session, person_id: uuid.UUID
) -> float:
    """
    Compute volatility for a single candidate.

    Formula per AGENTS.MD §10.1:
      base = switch_count * SWITCH_BASE_WEIGHT
      recency_factor = exp(-years_since_last_switch / HALF_LIFE_YEARS)
      distance_factor = mean ideological distance between consecutive parties
      volatility = clamp(base * recency_factor + distance_factor, 0, 1)
    """
    memberships = (
        db.query(PersonPartyMembership)
        .filter(PersonPartyMembership.person_id == person_id)
        .order_by(PersonPartyMembership.start_date)
        .all()
    )

    if len(memberships) <= 1:
        return 0.0

    # Count distinct party switches (consecutive different parties)
    party_ids = [m.party_instance_id for m in memberships]
    switches = sum(1 for a, b in zip(party_ids, party_ids[1:]) if a != b)

    if switches == 0:
        return 0.0

    # Recency: years since the most recent switch
    import datetime
    last_switch_date = None
    for m in reversed(memberships[1:]):
        if m.start_date:
            last_switch_date = m.start_date
            break

    years_since = 0.0
    if last_switch_date:
        today = datetime.date.today()
        years_since = (today - last_switch_date).days / 365.25

    recency_factor = math.exp(-years_since / _HALF_LIFE_YEARS)

    # Ideological distance (from party positions if available)
    distance_factor = _mean_ideological_distance(db, party_ids)

    raw = (switches * _SWITCH_BASE_WEIGHT * recency_factor) + (distance_factor * _DISTANCE_SCALE)
    return round(min(_MAX_CANDIDATE_VOLATILITY, raw), 4)


def _mean_ideological_distance(db: Session, party_ids: list[uuid.UUID]) -> float:
    """
    Estimate mean ideological distance between consecutive parties.
    Uses PartyPosition data if available; falls back to 0.5 (neutral).
    """
    if len(party_ids) < 2:
        return 0.0

    distances = []
    for a_id, b_id in zip(party_ids, party_ids[1:]):
        if a_id == b_id:
            distances.append(0.0)
            continue

        # Find policy items both parties have positions on
        a_positions = {p.policy_item_id: p.position_mean
                       for p in db.query(PartyPosition)
                       .filter(PartyPosition.party_instance_id == a_id).all()}
        b_positions = {p.policy_item_id: p.position_mean
                       for p in db.query(PartyPosition)
                       .filter(PartyPosition.party_instance_id == b_id).all()}

        common = set(a_positions.keys()) & set(b_positions.keys())
        if not common:
            distances.append(0.5)  # unknown → medium assumed
            continue

        dist = sum(abs(a_positions[k] - b_positions[k]) for k in common) / len(common)
        distances.append(dist)

    return sum(distances) / len(distances) if distances else 0.0


# ── Party volatility ───────────────────────────────────────────────────────────

def compute_party_volatility(
    db: Session, party_instance_id: uuid.UUID
) -> float:
    """
    Compute volatility for a party instance.

    Inputs (AGENTS.MD §10.2):
    - candidate_turnover: members who left / total members
    - leadership changes: if leader membership ended during the period
    - lineage events: renames, mergers, splits from party_lineage_edges
    - high-volatility candidates ratio

    Returns a float in 0..1.
    """
    party = db.query(PartyInstance).filter(PartyInstance.id == party_instance_id).first()
    if not party:
        return 0.5  # unknown party → moderate assumed

    memberships = (
        db.query(PersonPartyMembership)
        .filter(PersonPartyMembership.party_instance_id == party_instance_id)
        .all()
    )
    total_members = len(memberships)
    if total_members == 0:
        return 0.5

    # 1. Candidate turnover: members who have end_date set (left the party)
    departed = sum(1 for m in memberships if m.end_date is not None)
    turnover_score = min(1.0, departed / total_members)

    # 2. Leadership change: leader roles that ended
    leadership_departed = sum(
        1 for m in memberships
        if m.end_date is not None and m.role.value in ("leader", "founder")
    )
    leadership_score = min(1.0, leadership_departed)

    # 3. Lineage events (higher volatility for splits/mergers)
    lineage_events = (
        db.query(PartyLineageEdge)
        .filter(
            (PartyLineageEdge.from_party_instance_id == party_instance_id)
            | (PartyLineageEdge.to_party_instance_id == party_instance_id)
        )
        .all()
    )
    disruptive_types = {LineageRelationType.split, LineageRelationType.merger}
    disruptive_events = sum(1 for e in lineage_events if e.relation_type in disruptive_types)
    lineage_score = min(1.0, disruptive_events * _LINEAGE_EVENT_WEIGHT)

    # 4. Mean candidate volatility
    candidate_volatilities = []
    for m in memberships:
        v = compute_candidate_volatility(db, m.person_id)
        candidate_volatilities.append(v)
    mean_candidate_vol = (
        sum(candidate_volatilities) / len(candidate_volatilities)
        if candidate_volatilities else 0.0
    )

    volatility = (
        turnover_score * _TURNOVER_WEIGHT
        + leadership_score * _LEADERSHIP_CHANGE_WEIGHT
        + lineage_score
        + mean_candidate_vol * _HIGH_CANDIDATE_VOLATILITY_WEIGHT
    )
    return round(min(1.0, volatility), 4)


# ── Batch runner ───────────────────────────────────────────────────────────────

def run_volatility_update(
    db: Session,
    knesset_number: int | None = None,
) -> dict[str, dict]:
    """
    Compute and cache volatility for all candidates and parties.

    For candidates, caches the score in Person.external_ids_json["volatility"].
    For parties, returns a dict {party_instance_id: volatility_score}.

    Also returns a summary dict for logging/display.
    """
    # Persons
    person_scores: dict[str, float] = {}
    persons = db.query(Person).all()
    for person in persons:
        v = compute_candidate_volatility(db, person.id)
        person_scores[str(person.id)] = v
        # Cache in the person's JSON blob — must rebuild the dict so SQLAlchemy
        # detects the change (it does not track in-place mutations on JSON columns)
        ext = dict(person.external_ids_json or {})
        ext["volatility"] = v
        person.external_ids_json = ext

    # Parties — persist to DB column so scores survive restarts
    party_scores: dict[str, float] = {}
    pi_query = db.query(PartyInstance)
    if knesset_number:
        pi_query = pi_query.filter(PartyInstance.knesset_number == knesset_number)
    parties = pi_query.all()
    for party in parties:
        v = compute_party_volatility(db, party.id)
        party_scores[str(party.id)] = v
        party.volatility_score = v  # persist to DB (avoids in-memory-only loss)

    db.commit()

    logger.info(
        "volatility_update: %d candidates, %d parties",
        len(person_scores), len(party_scores),
    )
    return {
        "candidate_volatility": person_scores,
        "party_volatility": party_scores,
        "summary": {
            "candidates_updated": len(person_scores),
            "parties_updated": len(party_scores),
            "high_volatility_candidates": sum(1 for v in person_scores.values() if v > 0.5),
            "high_volatility_parties": sum(1 for v in party_scores.values() if v > 0.4),
        },
    }

