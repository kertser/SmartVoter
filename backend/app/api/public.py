"""
Public evidence browser endpoints. (AGENTS.MD Section 14A.12)

GET /api/parties                  — list all party instances
GET /api/parties/{id}             — party profile with positions + members + lineage
GET /api/persons/{id}             — MK/candidate profile with membership history
GET /api/votes/{id}               — vote detail with per-party breakdown
GET /api/bills/{id}               — bill detail
GET /api/parties/{id}/positions/{policy_item_id}/explain
                                  — lazy LLM explanation for EvidenceDrawer
                                    (LLM called only on first request; cached after)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
import logging

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

logger = logging.getLogger(__name__)
router = APIRouter(tags=["public-browser"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _brand_names(brand: PoliticalBrand | None, official_name: str) -> dict:
    names = brand.names_json or {} if brand else {}
    # Strip trailing/leading whitespace from all name strings (Knesset API data often has it)
    def _s(v: str | None) -> str | None:
        return v.strip() if v else None
    he = _s(names.get("he")) or _s(official_name)
    # For Russian, prefer the explicit "ru" translation, then fall back to Hebrew
    # (not official_name, which may be an English transliteration like "HaAvoda")
    ru = _s(names.get("ru")) or _s(names.get("he")) or _s(official_name)
    canonical = _s(brand.canonical_name if brand else official_name)
    return {
        "name": canonical,
        "name_he": he,
        "name_ru": ru,
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
def list_parties(
    group_by_brand: bool = True,
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    Return party instances with brand names.

    group_by_brand=true (default): one entry per political identity.
    Deduplication is two-pass:
      1. By political_brand_id (standard brand linking)
      2. By normalised Hebrew name + knesset_number (catches seed vs. ingested duplicates
         that were created with different brand IDs for the same real-world party)
    When duplicates exist, prefer the instance whose official_name is Hebrew-script.
    """
    import unicodedata

    # Map Hebrew final (sofit) letter forms → their regular equivalents so that
    # רע"ם (final mem) and רע"מ (regular mem) are treated as the same party.
    _SOFIT_MAP = str.maketrans({
        "\u05DA": "\u05DB",  # ך → כ  (final kaf → kaf)
        "\u05DD": "\u05DE",  # ם → מ  (final mem → mem)
        "\u05DF": "\u05E0",  # ן → נ  (final nun → nun)
        "\u05E3": "\u05E4",  # ף → פ  (final pe  → pe)
        "\u05E5": "\u05E6",  # ץ → צ  (final tsadi → tsadi)
    })

    def _norm_he(s: str | None) -> str:
        """Normalise a Hebrew string for comparison: NFC, strip, lowercase,
        and collapse final-letter variants (sofit) to their base form so that
        e.g. רע"ם and רע"מ are treated as duplicates."""
        if not s:
            return ""
        return unicodedata.normalize("NFC", s).translate(_SOFIT_MAP).strip().lower()

    def _is_hebrew(s: str | None) -> bool:
        """Return True if most characters in s are Hebrew script."""
        if not s:
            return False
        he_chars = sum(1 for c in s if "\u05d0" <= c <= "\u05ea")
        return he_chars > len(s) * 0.3

    parties = db.query(PartyInstance).order_by(PartyInstance.knesset_number.desc()).all()
    brand_cache: dict = {}

    if not group_by_brand:
        result = []
        for p in parties:
            brand = brand_cache.setdefault(
                str(p.political_brand_id),
                db.query(PoliticalBrand).filter(PoliticalBrand.id == p.political_brand_id).first(),
            )
            result.append(_party_dict(p, brand))
        return result

    # Pass 1: deduplicate by political_brand_id (keep instance with highest knesset_number)
    by_brand: dict[str, PartyInstance] = {}
    for p in parties:
        key = str(p.political_brand_id) if p.political_brand_id else str(p.id)
        if key not in by_brand:
            by_brand[key] = p
        else:
            # Same brand: keep if Hebrew official_name beats English, or higher knesset_number
            existing = by_brand[key]
            existing_he = _is_hebrew(existing.official_name)
            this_he = _is_hebrew(p.official_name)
            existing_kn = existing.knesset_number or 0
            this_kn = p.knesset_number or 0
            if (not existing_he and this_he) or (this_kn > existing_kn):
                by_brand[key] = p

    # Pass 2: deduplicate by (normalised_he_name, knesset_number)
    # This catches seed 'יש עתיד' vs. ingested 'יש עתיד ' (trailing space, different brand)
    by_he_name: dict[tuple, PartyInstance] = {}
    for p in by_brand.values():
        brand = brand_cache.setdefault(
            str(p.political_brand_id),
            db.query(PoliticalBrand).filter(PoliticalBrand.id == p.political_brand_id).first(),
        )
        names = brand.names_json or {} if brand else {}
        he_name = _norm_he(names.get("he") or p.official_name or "")
        kn = p.knesset_number or 0
        he_key = (he_name, kn)

        if he_name == "":  # no Hebrew name → keep by brand key only
            by_he_name[("__no_he__", id(p))] = p
            continue

        if he_key not in by_he_name:
            by_he_name[he_key] = p
        else:
            # Prefer Hebrew official_name over English; prefer higher knesset if different
            existing = by_he_name[he_key]
            existing_he = _is_hebrew(existing.official_name)
            this_he = _is_hebrew(p.official_name)
            if not existing_he and this_he:
                by_he_name[he_key] = p

    # Sort: active first → knesset_number desc → Hebrew name asc
    def _sort_key(p: PartyInstance):
        brand = brand_cache.get(str(p.political_brand_id))
        names = brand.names_json or {} if brand else {}
        he = _norm_he(names.get("he") or p.official_name or "")
        return (0 if p.status == "active" else 1, -(p.knesset_number or 0), he)

    parties_sorted = sorted(by_he_name.values(), key=_sort_key)

    result = []
    for p in parties_sorted:
        brand = brand_cache.get(str(p.political_brand_id))
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
    hide_procedural: bool = False,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    List votes, optionally filtered by Knesset number.

    hide_procedural=true excludes votes whose titles are purely procedural
    (הסתייגות, committee transfers, etc.) with no substantive information.
    """
    # Titles that are 100 % procedural / uninformative on their own.
    # Without a bill name in the title these convey no policy signal.
    PROCEDURAL_EXACT = {
        "הסתייגות",
        "הצבעה",
        "הצעת ועדה",
        "הצעת ועדת הכנסת",
        # Bill readings — informative only if the bill name is embedded in the title.
        # When stored as a bare word they carry no additional meaning.
        "קריאה שנייה",
        "קריאה ראשונה ושנייה",
        "קריאה ראשונה",
        "אישור החוק",
        "הצעת ועדת הכנסת לסדר היום",
        "הודעת הממשלה",
        "הצעה לסדר היום",
        "בקשה לסדר היום",
        "הצעת הוועדה המסדרת",   # parliamentary rules / agenda-ordering committee — procedural
    }
    # Title prefixes that indicate procedural votes
    PROCEDURAL_PREFIXES = (
        "להעביר את הצעת החוק לוועדה",
        "להעביר את הנושא לוועדה",
        "העברת הנושא לוועדה",
        "לכלול את הנושא בסדר היום",
        "העברת הצעת החוק לוועדה",
        "להחזיר את הצעת החוק",
        "קריאה שנייה ושלישית",
    )

    q = db.query(Vote)
    if knesset_number:
        q = q.filter(Vote.knesset_number == knesset_number)

    if hide_procedural:
        from sqlalchemy import and_, not_, or_
        exact_conds = [Vote.title_he == t for t in PROCEDURAL_EXACT]
        prefix_conds = [Vote.title_he.like(f"{p}%") for p in PROCEDURAL_PREFIXES]
        q = q.filter(not_(or_(*exact_conds, *prefix_conds)))

    votes = q.order_by(Vote.date.desc()).limit(limit).all()

    def _is_procedural(title_he: str | None) -> bool:
        if not title_he:
            return False
        t = title_he.strip()
        if t in PROCEDURAL_EXACT:
            return True
        return any(t.startswith(p) for p in PROCEDURAL_PREFIXES)

    return [
        {
            "id": str(v.id),
            "external_id": v.external_id,
            "title_he": v.title_he,
            "title_en": v.title_en,
            "date": v.date.isoformat() if v.date else None,
            "knesset_number": v.knesset_number,
            "importance_score": v.importance_score,
            "is_procedural_estimate": v.is_procedural_estimate or _is_procedural(v.title_he),
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
def list_persons(
    limit: int = 500,
    current_only: bool = False,
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    List MKs/candidates with current party info.

    current_only=true returns only persons who have at least one open-ended
    membership (end_date IS NULL), i.e. currently active members.
    """
    if current_only:
        # Only persons with an active membership
        active_person_ids = (
            db.query(PersonPartyMembership.person_id)
            .filter(PersonPartyMembership.end_date.is_(None))
            .distinct()
            .all()
        )
        ids = [r[0] for r in active_person_ids]
        q = db.query(Person).filter(Person.id.in_(ids))
    else:
        q = db.query(Person)

    persons = q.limit(limit).all()

    # Filter out obviously mock/seed persons:
    # Real Israeli MKs always have a proper Hebrew name.
    # Seed mock persons use patterns like "MK Changer A" / "MK X".
    import re as _re
    import unicodedata as _ud
    _mock_pattern = _re.compile(r'^MK\s+[A-Z](\s|$)', _re.IGNORECASE)
    persons = [p for p in persons if not (p.name_en and _mock_pattern.match(p.name_en))]

    def _norm(s: str | None) -> str:
        if not s:
            return ""
        return _ud.normalize("NFC", s).strip().lower()

    # Deduplicate:
    # Primary key: Hebrew name (catches seed "בנימין נתניהו" = ingested "בנימין נתניהו")
    # Fallback: English name (when no Hebrew name exists)
    # The old key combined both → missed duplicates where one had name_en and other didn't.
    seen_he: set = set()   # by normalised Hebrew name
    seen_en: set = set()   # by normalised English name (only used when name_he is absent)
    unique_persons = []
    for p in persons:
        he = _norm(p.name_he)
        en = _norm(p.name_en)
        if he:
            if he in seen_he:
                continue
            seen_he.add(he)
        elif en:
            if en in seen_en:
                continue
            seen_en.add(en)
        unique_persons.append(p)

    # Sort by Hebrew name, fallback English
    unique_persons.sort(key=lambda p: (p.name_he or p.name_en or "").lower())

    # Attach current party for each person
    result = []
    for p in unique_persons:
        # Look for the most recent open-ended membership
        current_membership = (
            db.query(PersonPartyMembership)
            .filter(
                PersonPartyMembership.person_id == p.id,
                PersonPartyMembership.end_date.is_(None),
            )
            .order_by(PersonPartyMembership.start_date.desc())
            .first()
        )
        current_party_name = None
        current_party_name_he = None
        current_party_name_ru = None
        current_party_instance_id = None
        if current_membership:
            party = db.query(PartyInstance).filter(PartyInstance.id == current_membership.party_instance_id).first()
            brand = db.query(PoliticalBrand).filter(PoliticalBrand.id == party.political_brand_id).first() if party else None
            n = _brand_names(brand, party.official_name if party else "Unknown")
            current_party_name = n["name"]
            current_party_name_he = n["name_he"]
            current_party_name_ru = n["name_ru"]
            current_party_instance_id = str(current_membership.party_instance_id) if current_membership.party_instance_id else None

        result.append({
            "id": str(p.id),
            "name_en": p.name_en,
            "name_he": p.name_he,
            "birth_year": p.birth_year,
            "current_party_name": current_party_name,
            "current_party_name_he": current_party_name_he,
            "current_party_name_ru": current_party_name_ru,
            "current_party_instance_id": current_party_instance_id,
        })

    return result


# ── Lazy LLM explanation endpoint ─────────────────────────────────────────────

@router.get("/parties/{party_id}/positions/{policy_item_id}/explain")
def explain_party_position(
    party_id: str,
    policy_item_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Returns (or lazily generates) an LLM explanation for why a party holds a
    given position on a policy item. Used by the EvidenceDrawer component.

    Cost optimisation strategy:
    - The party_position_pipeline runs WITHOUT LLM by default (enrich_with_llm=False).
    - The LLM explanation is generated HERE, only when a user actually clicks
      "Show evidence" for a specific party+policy pair.
    - AuditedLLMService caches by input_hash: clicking twice costs nothing extra.

    Response:
        explanation  — LLM-generated 2–3 sentence neutral explanation
        position_mean, evidence_strength, uncertainty — from DB
        from_cache   — true if the explanation was already stored in the DB
    """
    try:
        pid = uuid.UUID(party_id)
        pol_id = uuid.UUID(policy_item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    pos = (
        db.query(PartyPosition)
        .filter(
            PartyPosition.party_instance_id == pid,
            PartyPosition.policy_item_id == pol_id,
        )
        .first()
    )
    if not pos:
        raise HTTPException(status_code=404, detail="Party position not found")

    # If we already have an explanation (from a previous lazy call or manual entry), return it.
    if pos.llm_explanation:
        return {
            "explanation": pos.llm_explanation,
            "position_mean": pos.position_mean,
            "evidence_strength": pos.evidence_strength,
            "uncertainty": pos.position_uncertainty,
            "from_cache": True,
        }

    # Lazy LLM call — generate explanation on demand
    party = db.query(PartyInstance).filter(PartyInstance.id == pid).first()
    policy_item = db.query(PolicyItem).filter(PolicyItem.id == pol_id).first()
    if not party or not policy_item:
        raise HTTPException(status_code=404, detail="Party or policy item not found")

    try:
        from backend.app.config import get_settings
        from backend.app.services.llm import get_llm_provider
        from backend.app.services.llm.audit_service import AuditedLLMService
        from backend.app.services.ingestion.party_position_pipeline import (
            _parse_axis_pole,
        )

        settings = get_settings()
        provider = get_llm_provider(settings)
        svc = AuditedLLMService(provider, db)

        llm_result = svc.infer_party_position(
            {
                "party_name": party.official_name,
                "policy_title": policy_item.title,
                "directional_axis": policy_item.directional_axis or "",
                "negative_pole": _parse_axis_pole(policy_item.directional_axis, "neg"),
                "positive_pole": _parse_axis_pole(policy_item.directional_axis, "pos"),
                "evidence": [
                    {
                        "type": "stored_position",
                        "position_mean": pos.position_mean,
                        "evidence_strength": pos.evidence_strength,
                        "evidence_type": pos.evidence_type or "vote",
                    }
                ],
            },
            entity_id=pol_id,
        )
        explanation = llm_result.get("explanation", "")

        # Persist so the next request is free
        pos.llm_explanation = explanation
        db.commit()

        return {
            "explanation": explanation,
            "position_mean": pos.position_mean,
            "evidence_strength": pos.evidence_strength,
            "uncertainty": pos.position_uncertainty,
            "from_cache": False,
        }

    except Exception as exc:
        logger.warning(
            "Lazy explain failed party=%s policy=%s: %s", party_id, policy_item_id, exc
        )
        raise HTTPException(status_code=503, detail="LLM explanation temporarily unavailable")

