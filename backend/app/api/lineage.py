"""
Lineage and party evidence endpoints — Phase 7.
GET /api/lineage          — all lineage nodes + edges for the timeline visualization.
GET /api/parties/{id}/evidence — per-topic evidence for the evidence drawer.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from backend.app.db import get_db
from backend.app.models.party_lineage_edge import PartyLineageEdge
from backend.app.models.party_instance import PartyInstance
from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.party_position import PartyPosition
from backend.app.models.policy_item import PolicyItem
from backend.app.models.topic import Topic

router = APIRouter(tags=["lineage"])


@router.get("/lineage")
def get_lineage(db: Session = Depends(get_db)) -> dict:
    """
    Return all party instances (nodes) and lineage edges for the timeline view.
    Only returns approved edges; nodes include all party instances referenced.
    """
    edges_rows = db.query(PartyLineageEdge).all()

    # Collect all referenced party instance IDs
    party_ids: set[uuid.UUID] = set()
    for edge in edges_rows:
        party_ids.add(edge.from_party_instance_id)
        party_ids.add(edge.to_party_instance_id)

    # Also include all active party instances even if not in an edge
    active_parties = db.query(PartyInstance).filter(PartyInstance.status == "active").all()
    for p in active_parties:
        party_ids.add(p.id)

    # Build node list
    nodes = []
    for pid in party_ids:
        party = db.query(PartyInstance).filter(PartyInstance.id == pid).first()
        if not party:
            continue
        brand = (
            db.query(PoliticalBrand)
            .filter(PoliticalBrand.id == party.political_brand_id)
            .first()
        )
        names = brand.names_json or {} if brand else {}
        nodes.append({
            "id": str(party.id),
            "name": brand.canonical_name if brand else party.official_name,
            "name_he": names.get("he"),
            "name_ru": names.get("ru"),
            "official_name": party.official_name,
            "election_cycle": party.election_cycle,
            "knesset_number": party.knesset_number,
            "status": party.status,
            "start_date": party.start_date.isoformat() if party.start_date else None,
            "end_date": party.end_date.isoformat() if party.end_date else None,
        })

    # Build edge list
    edges = []
    for edge in edges_rows:
        edges.append({
            "id": str(edge.id),
            "from_id": str(edge.from_party_instance_id),
            "to_id": str(edge.to_party_instance_id),
            "relation_type": edge.relation_type.value,
            "continuity_weight": edge.continuity_weight,
            "llm_explanation": edge.llm_explanation,
            "human_review_status": edge.human_review_status.value,
            "source_url": edge.source_url,
        })

    return {"nodes": nodes, "edges": edges}


@router.get("/parties/{party_id}/evidence")
def get_party_evidence(party_id: str, db: Session = Depends(get_db)) -> list[dict]:
    """
    Return per-topic position evidence for a party instance.
    Powers the EvidenceDrawer component.
    """
    try:
        pid = uuid.UUID(party_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid party ID")

    party = db.query(PartyInstance).filter(PartyInstance.id == pid).first()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    positions = (
        db.query(PartyPosition)
        .filter(PartyPosition.party_instance_id == pid)
        .all()
    )

    result = []
    for pos in positions:
        pi = db.query(PolicyItem).filter(PolicyItem.id == pos.policy_item_id).first()
        if not pi:
            continue
        topic = db.query(Topic).filter(Topic.id == pi.topic_id).first() if pi.topic_id else None
        result.append({
            "position_id": str(pos.id),
            "policy_item_id": str(pos.policy_item_id),
            "policy_item_title": pi.title,
            "policy_item_description": pi.description,
            "directional_axis": pi.directional_axis,
            "topic_slug": topic.slug if topic else None,
            "topic_name_en": topic.name_en if topic else None,
            "topic_name_he": topic.name_he if topic else None,
            "topic_name_ru": topic.name_ru if topic else None,
            "position_mean": pos.position_mean,
            "position_uncertainty": pos.position_uncertainty,
            "evidence_strength": pos.evidence_strength,
            "evidence_type": pos.evidence_type or "party_platform",
            "source_refs_json": pos.source_refs_json or [],
            "llm_explanation": pos.llm_explanation,
        })

    # Sort by topic then evidence strength
    result.sort(key=lambda x: (x["topic_slug"] or "", -x["evidence_strength"]))
    return result

