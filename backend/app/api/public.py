"""
Public evidence browser endpoints. (AGENTS.MD Section 14A.12)

GET /api/parties                  — list all party instances
GET /api/parties/{id}             — party profile with positions + members + lineage
GET /api/persons/{id}             — MK/candidate profile with membership history
GET /api/votes/{id}               — vote detail with per-party breakdown
GET /api/bills/{id}               — bill detail
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from backend.app.db import get_db
from backend.app.models.party_instance import PartyInstance
from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.party_lineage_edge import PartyLineageEdge
from backend.app.models.party_position import PartyPosition
from backend.app.models.policy_item import PolicyItem
from backend.app.models.topic import Topic
from backend.app.models.person import Person
from backend.app.models.person_party_membership import PersonPartyMembership
from backend.app.models.vote import Vote
from backend.app.models.vote_result import VoteResult
from backend.app.models.bill import Bill

router = APIRouter(tags=["public-browser"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _brand_names(brand: PoliticalBrand | None, official_name: str) -> dict:
    names = brand.names_json or {} if brand else {}
    return {
        "name": brand.canonical_name if brand else official_name,
        "name_he": names.get("he") or official_name,
        "name_ru": names.get("ru") or official_name,
    }


def _party_dict(party: PartyInstance, brand: PoliticalBrand | None) -> dict:
    n = _brand_names(brand, party.official_name)
    return {
        "id": str(party.id),
        **n,
        "official_name": party.official_name,
        "election_cycle": party.election_cycle,
        "knesset_number": party.knesset_number,
        "status": party.status,
        "start_date": party.start_date.isoformat() if party.start_date else None,
        "end_date": party.end_date.isoformat() if party.end_date else None,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/parties")
def list_parties(db: Session = Depends(get_db)) -> list[dict]:
    """Return all party instances with brand names."""
    parties = db.query(PartyInstance).order_by(PartyInstance.knesset_number.desc()).all()
    result = []
    for p in parties:
        brand = db.query(PoliticalBrand).filter(PoliticalBrand.id == p.political_brand_id).first()
        result.append(_party_dict(p, brand))
    return result


@router.get("/parties/{party_id}")
def get_party(party_id: str, db: Session = Depends(get_db)) -> dict:
    """Full party profile: name, policy positions, members, lineage edges."""
    try:
        pid = uuid.UUID(party_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid party ID")

    party = db.query(PartyInstance).filter(PartyInstance.id == pid).first()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    brand = db.query(PoliticalBrand).filter(PoliticalBrand.id == party.political_brand_id).first()
    base = _party_dict(party, brand)

    # Policy positions
    positions_rows = (
        db.query(PartyPosition).filter(PartyPosition.party_instance_id == pid).all()
    )
    positions = []
    for pos in positions_rows:
        pi = db.query(PolicyItem).filter(PolicyItem.id == pos.policy_item_id).first()
        topic = db.query(Topic).filter(Topic.id == pi.topic_id).first() if pi and pi.topic_id else None
        positions.append({
            "policy_item_id": str(pos.policy_item_id),
            "policy_item_title": pi.title if pi else None,
            "directional_axis": pi.directional_axis if pi else None,
            "topic_slug": topic.slug if topic else None,
            "topic_name_en": topic.name_en if topic else None,
            "topic_name_he": topic.name_he if topic else None,
            "topic_name_ru": topic.name_ru if topic else None,
            "position_mean": pos.position_mean,
            "position_uncertainty": pos.position_uncertainty,
            "evidence_strength": pos.evidence_strength,
            "evidence_type": pos.evidence_type,
            "llm_explanation": pos.llm_explanation,
        })

    # Members
    memberships = (
        db.query(PersonPartyMembership)
        .filter(PersonPartyMembership.party_instance_id == pid)
        .all()
    )
    members = []
    for m in memberships:
        person = db.query(Person).filter(Person.id == m.person_id).first()
        members.append({
            "person_id": str(m.person_id),
            "name_en": person.name_en if person else None,
            "name_he": person.name_he if person else None,
            "role": m.role.value,
            "start_date": m.start_date.isoformat() if m.start_date else None,
            "end_date": m.end_date.isoformat() if m.end_date else None,
            "confidence": m.confidence,
        })

    # Lineage edges (from or to this party)
    edges_from = db.query(PartyLineageEdge).filter(PartyLineageEdge.from_party_instance_id == pid).all()
    edges_to = db.query(PartyLineageEdge).filter(PartyLineageEdge.to_party_instance_id == pid).all()
    lineage = []
    for edge in edges_from + edges_to:
        lineage.append({
            "id": str(edge.id),
            "from_id": str(edge.from_party_instance_id),
            "to_id": str(edge.to_party_instance_id),
            "relation_type": edge.relation_type.value,
            "continuity_weight": edge.continuity_weight,
            "llm_explanation": edge.llm_explanation,
            "human_review_status": edge.human_review_status.value,
        })

    return {
        **base,
        "positions": positions,
        "members": members,
        "lineage": lineage,
    }


@router.get("/persons/{person_id}")
def get_person(person_id: str, db: Session = Depends(get_db)) -> dict:
    """MK/candidate profile with full party membership history."""
    try:
        pid = uuid.UUID(person_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid person ID")

    person = db.query(Person).filter(Person.id == pid).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    memberships = (
        db.query(PersonPartyMembership)
        .filter(PersonPartyMembership.person_id == pid)
        .order_by(PersonPartyMembership.start_date.desc())
        .all()
    )
    memberships_data = []
    for m in memberships:
        party = db.query(PartyInstance).filter(PartyInstance.id == m.party_instance_id).first()
        brand = db.query(PoliticalBrand).filter(PoliticalBrand.id == party.political_brand_id).first() if party else None
        n = _brand_names(brand, party.official_name if party else "Unknown")
        memberships_data.append({
            "party_instance_id": str(m.party_instance_id),
            "party_name": n["name"],
            "party_name_he": n["name_he"],
            "party_name_ru": n["name_ru"],
            "role": m.role.value,
            "start_date": m.start_date.isoformat() if m.start_date else None,
            "end_date": m.end_date.isoformat() if m.end_date else None,
            "confidence": m.confidence,
            "is_current": m.end_date is None,
        })

    return {
        "id": str(person.id),
        "name_en": person.name_en,
        "name_he": person.name_he,
        "birth_year": person.birth_year,
        "public_profile_url": person.public_profile_url,
        "memberships": memberships_data,
    }


@router.get("/votes/{vote_id}")
def get_vote(vote_id: str, db: Session = Depends(get_db)) -> dict:
    """Vote detail with per-person results."""
    try:
        vid = uuid.UUID(vote_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vote ID")

    vote = db.query(Vote).filter(Vote.id == vid).first()
    if not vote:
        raise HTTPException(status_code=404, detail="Vote not found")

    results = db.query(VoteResult).filter(VoteResult.vote_id == vid).all()
    per_person = []
    for r in results:
        person = db.query(Person).filter(Person.id == r.person_id).first()
        per_person.append({
            "person_id": str(r.person_id),
            "name_en": person.name_en if person else None,
            "name_he": person.name_he if person else None,
            "vote_value": r.vote_value.value,
            "party_instance_id_at_time": str(r.party_instance_id_at_time) if r.party_instance_id_at_time else None,
        })

    return {
        "id": str(vote.id),
        "external_id": vote.external_id,
        "title_he": vote.title_he,
        "title_en": vote.title_en,
        "date": vote.date.isoformat() if vote.date else None,
        "knesset_number": vote.knesset_number,
        "vote_type": vote.vote_type,
        "is_procedural_estimate": vote.is_procedural_estimate,
        "importance_score": vote.importance_score,
        "signal_quality_score": vote.signal_quality_score,
        "source_url": vote.source_url,
        "results": per_person,
    }


@router.get("/bills/{bill_id}")
def get_bill(bill_id: str, db: Session = Depends(get_db)) -> dict:
    """Bill detail."""
    try:
        bid = uuid.UUID(bill_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bill ID")

    bill = db.query(Bill).filter(Bill.id == bid).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    return {
        "id": str(bill.id),
        "external_id": bill.external_id,
        "title_he": bill.title_he,
        "title_en": bill.title_en,
        "summary_he": bill.summary_he,
        "summary_en": bill.summary_en,
        "full_text_url": bill.full_text_url,
        "date_submitted": bill.date_submitted.isoformat() if bill.date_submitted else None,
        "status": bill.status,
        "source_url": bill.source_url,
    }


@router.get("/votes")
def list_votes(
    knesset_number: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict]:
    """List votes, optionally filtered by Knesset number."""
    q = db.query(Vote)
    if knesset_number:
        q = q.filter(Vote.knesset_number == knesset_number)
    votes = q.order_by(Vote.date.desc()).limit(limit).all()
    return [
        {
            "id": str(v.id),
            "external_id": v.external_id,
            "title_he": v.title_he,
            "title_en": v.title_en,
            "date": v.date.isoformat() if v.date else None,
            "knesset_number": v.knesset_number,
            "importance_score": v.importance_score,
            "source_url": v.source_url,
        }
        for v in votes
    ]


@router.get("/bills")
def list_bills(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict]:
    """List bills."""
    bills = db.query(Bill).order_by(Bill.date_submitted.desc()).limit(limit).all()
    return [
        {
            "id": str(b.id),
            "external_id": b.external_id,
            "title_he": b.title_he,
            "title_en": b.title_en,
            "date_submitted": b.date_submitted.isoformat() if b.date_submitted else None,
            "status": b.status,
            "source_url": b.source_url,
        }
        for b in bills
    ]


@router.get("/persons")
def list_persons(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    """List MKs/candidates."""
    persons = db.query(Person).limit(limit).all()
    return [
        {
            "id": str(p.id),
            "name_en": p.name_en,
            "name_he": p.name_he,
            "birth_year": p.birth_year,
        }
        for p in persons
    ]

