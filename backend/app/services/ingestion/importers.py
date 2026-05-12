"""
Importers — orchestrate fetch → upsert → LLM enrichment for Knesset data.
(AGENTS.MD Phase 6)

Usage:
  from backend.app.services.ingestion.importers import (
      import_votes, import_bills, import_factions, import_persons
  )
"""
import logging
import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from backend.app.models.vote import Vote
from backend.app.models.bill import Bill
from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.party_instance import PartyInstance, PartyStatus
from backend.app.models.person import Person
from backend.app.models.person_party_membership import PersonPartyMembership, MembershipRole
from backend.app.models.vote_result import VoteResult, VoteValue
from backend.app.services.ingestion.knesset_odata import (
    fetch_votes, fetch_bills, fetch_factions, fetch_persons, fetch_vote_results,
)
from backend.app.services.ingestion.oknesset import fetch_votes_enriched
from backend.app.services.llm import get_llm_provider
from backend.app.services.llm.audit_service import AuditedLLMService

if TYPE_CHECKING:
    from backend.app.config import Settings

logger = logging.getLogger(__name__)


# ── Votes ──────────────────────────────────────────────────────────────────────

def import_votes(
    db: Session,
    knesset_number: int,
    settings: "Settings",
    limit: int = 500,
    enrich_with_llm: bool = True,
    enrich_english: bool = True,
    probe_availability: bool = True,
) -> dict[str, int]:
    """
    Fetch votes from Knesset OData (Votes.svc), upsert into the DB, optionally
    ask the LLM to produce a plain-language summary and importance score.

    NOTE: The Knesset votes service (View_vote_rslts_hdr_Approved) historically
    only contained data for Knesset 1–24. Knesset 25 data became partially
    available in 2025. For newer Knessets, set probe_availability=True (the default)
    to check availability before making a costly import call.

    When no data is found for knesset_number >= 25, a warning is logged and an
    empty result is returned. Consider using the Open Knesset (Hasadna) API as
    a supplemental source: https://oknesset.org/api/v2/vote/

    Returns {"inserted": N, "updated": N, "skipped": N}.
    """
    raw_votes = fetch_votes(
        settings.knesset_votes_api_base_url,
        knesset_number,
        limit=limit,
        probe_first=probe_availability and knesset_number >= 25,
    )

    # Optionally cross-reference English titles from Open Knesset
    en_titles: dict[str, str] = {}
    if enrich_english:
        try:
            enriched = fetch_votes_enriched(settings.oknesset_api_base_url, limit=limit)
            en_titles = {r["external_id"]: r["title_en"] for r in enriched if r.get("title_en")}
        except Exception as exc:
            logger.warning("Open Knesset enrichment failed (non-fatal): %s", exc)

    llm_raw = get_llm_provider(settings) if enrich_with_llm else None
    llm = AuditedLLMService(llm_raw, db) if llm_raw else None

    inserted = updated = skipped = 0

    for row in raw_votes:
        external_id = row["external_id"]
        existing = db.query(Vote).filter(Vote.external_id == external_id).first()

        title_en = en_titles.get(external_id)
        date_val = _parse_date(row.get("date"))

        if existing:
            # Update English title if we got one
            if title_en and not existing.title_en:
                existing.title_en = title_en
                updated += 1
            else:
                skipped += 1
            continue

        new_vote = Vote(
            id=uuid.uuid4(),
            external_id=external_id,
            title_he=row["title_he"],
            title_en=title_en,
            date=date_val,
            knesset_number=row["knesset_number"],
            vote_type=row.get("vote_type"),
            is_procedural_estimate=False,
            source_url=row.get("source_url"),
            raw_json=row.get("raw_json"),
        )
        db.add(new_vote)
        db.flush()

        # LLM enrichment: importance score + summary
        if llm and row["title_he"]:
            try:
                result = llm.summarize_bill_or_vote(
                    {"title": row["title_he"], "text": "", "metadata": {"knesset": knesset_number, "type": "vote"}},
                    entity_id=new_vote.id,
                )
                new_vote.importance_score = result.get("importance_score")
                new_vote.signal_quality_score = 1.0 - (0.5 if result.get("is_procedural") else 0.0)
            except Exception as exc:
                logger.warning("LLM enrichment failed for vote %s: %s", external_id, exc)

        inserted += 1

    db.commit()
    logger.info(
        "import_votes knesset=%d → inserted=%d updated=%d skipped=%d",
        knesset_number, inserted, updated, skipped,
    )
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


# ── Bills ──────────────────────────────────────────────────────────────────────

def import_bills(
    db: Session,
    knesset_number: int,
    settings: "Settings",
    limit: int = 500,
    enrich_with_llm: bool = True,
) -> dict[str, int]:
    """
    Fetch bills from Knesset OData, upsert into DB, optionally LLM-enrich.
    """
    raw_bills = fetch_bills(settings.knesset_api_base_url, knesset_number, limit=limit)
    llm_raw = get_llm_provider(settings) if enrich_with_llm else None
    llm = AuditedLLMService(llm_raw, db) if llm_raw else None

    inserted = updated = skipped = 0

    for row in raw_bills:
        external_id = row["external_id"]
        existing = db.query(Bill).filter(Bill.external_id == external_id).first()

        if existing:
            skipped += 1
            continue

        date_val = _parse_date(row.get("date_submitted"))

        new_bill = Bill(
            id=uuid.uuid4(),
            external_id=external_id,
            title_he=row["title_he"],
            title_en=row.get("title_en"),
            date_submitted=date_val,
            status=row.get("status"),
            source_url=row.get("source_url"),
            raw_json=row.get("raw_json"),
        )
        db.add(new_bill)
        db.flush()

        if llm and row["title_he"]:
            try:
                result = llm.summarize_bill_or_vote(
                    {"title": row["title_he"], "text": "", "metadata": {"knesset": knesset_number, "type": "bill"}},
                    entity_id=new_bill.id,
                )
                new_bill.summary_he = result.get("plain_summary", "")
                new_bill.summary_en = result.get("plain_summary", "")
            except Exception as exc:
                logger.warning("LLM enrichment failed for bill %s: %s", external_id, exc)

        inserted += 1

    db.commit()
    logger.info(
        "import_bills knesset=%d → inserted=%d skipped=%d",
        knesset_number, inserted, skipped,
    )
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


# ── Factions ───────────────────────────────────────────────────────────────────

def import_factions(
    db: Session,
    knesset_number: int,
    settings: "Settings",
) -> dict[str, int]:
    """
    Fetch all factions for a Knesset from KNS_Faction and upsert them as:
    - PoliticalBrand (one per unique faction name, if not existing)
    - PartyInstance  (one per faction-knesset combination)

    Deduplication key: official_name + knesset_number.

    Returns {"inserted": N, "updated": N, "skipped": N}.
    """
    raw = fetch_factions(settings.knesset_api_base_url, knesset_number)
    inserted = updated = skipped = 0

    for row in raw:
        name_he = row["name_he"]
        faction_id = row["faction_id"]
        source_url = row["source_url"]

        # Find or create PoliticalBrand by canonical_name
        brand = (
            db.query(PoliticalBrand)
            .filter(PoliticalBrand.canonical_name == name_he)
            .first()
        )
        if not brand:
            brand = PoliticalBrand(
                id=uuid.uuid4(),
                canonical_name=name_he,
                names_json={"he": name_he},
                description=f"Auto-imported from Knesset OData (FactionID={faction_id})",
            )
            db.add(brand)
            db.flush()

        # Find or create PartyInstance by official_name + knesset_number
        existing = (
            db.query(PartyInstance)
            .filter(
                PartyInstance.official_name == name_he,
                PartyInstance.knesset_number == knesset_number,
            )
            .first()
        )
        if existing:
            # Update status and dates if changed
            new_status = PartyStatus.active if row["is_current"] else PartyStatus.dissolved
            changed = False
            if existing.status != new_status:
                existing.status = new_status
                changed = True
            if existing.end_date is None and row["end_date"]:
                existing.end_date = _parse_date(row["end_date"])
                changed = True
            if existing.source_url != source_url:
                existing.source_url = source_url
                changed = True
            if changed:
                updated += 1
            else:
                skipped += 1
        else:
            pi = PartyInstance(
                id=uuid.uuid4(),
                political_brand_id=brand.id,
                official_name=name_he,
                election_cycle=str(knesset_number),
                knesset_number=knesset_number,
                start_date=_parse_date(row["start_date"]),
                end_date=_parse_date(row["end_date"]),
                status=PartyStatus.active if row["is_current"] else PartyStatus.dissolved,
                source_url=source_url,
            )
            db.add(pi)
            inserted += 1

    db.commit()
    logger.info(
        "import_factions knesset=%d → inserted=%d updated=%d skipped=%d",
        knesset_number, inserted, updated, skipped,
    )

    # Auto-deduplicate: merge any Hebrew Knesset-imported names that duplicate
    # existing seed/English entries for the same party.
    if inserted > 0 or updated > 0:
        from backend.app.services.ingestion.party_dedup_service import auto_deduplicate_parties
        dedup = auto_deduplicate_parties(
            db,
            api_key=settings.openai_api_key if settings.has_openai else None,
            model=getattr(settings, "openai_model", "gpt-4o-mini"),
        )
        if dedup["merged_count"] > 0:
            logger.info(
                "import_factions: auto-dedup merged %d duplicate party instances (%s)",
                dedup["merged_count"], dedup["source"],
            )

    return {"inserted": inserted, "updated": updated, "skipped": skipped}


# ── Persons ────────────────────────────────────────────────────────────────────

_POSITION_TO_ROLE = {
    43: "mk",   # חבר הכנסת
    61: "mk",   # חברת הכנסת
    48: "leader",  # יו"ר סיעה
    54: "mk",   # חבר/ת סיעה
}


def import_persons(
    db: Session,
    knesset_number: int,
    settings: "Settings",
    limit: int = 500,
) -> dict[str, int]:
    """
    Fetch MKs and faction members from KNS_PersonToPosition and upsert as:
    - Person       (one per unique PersonID)
    - PersonPartyMembership (one per person-faction membership record)

    Dedup keys: Person by external_ids_json["knesset_id"], Membership by person+party+start_date.

    Returns {"persons": {inserted, updated, skipped}, "memberships": {inserted, skipped}}.
    """
    raw = fetch_persons(settings.knesset_api_base_url, knesset_number, limit=limit)

    # Build faction_name → PartyInstance map for this knesset
    party_map: dict[str, uuid.UUID] = {
        pi.official_name: pi.id
        for pi in db.query(PartyInstance)
        .filter(PartyInstance.knesset_number == knesset_number)
        .all()
    }
    # Also map by faction_id stored in source_url (fallback)
    faction_id_map: dict[int, uuid.UUID] = {}
    for pi in db.query(PartyInstance).filter(PartyInstance.knesset_number == knesset_number).all():
        if pi.source_url and "FactionID=" in pi.source_url:
            try:
                fid = int(pi.source_url.split("FactionID=")[-1])
                faction_id_map[fid] = pi.id
            except (ValueError, IndexError):
                pass

    p_inserted = p_updated = p_skipped = 0
    m_inserted = m_skipped = 0

    for row in raw:
        person_id = row["person_id"]
        if not person_id:
            continue

        knesset_id_key = f"knesset_id_{person_id}"

        # Find or create Person
        person = (
            db.query(Person)
            .filter(Person.external_ids_json[("knesset_id",)].as_string() == str(person_id))
            .first()
        )
        # Fallback: search via JSON contains
        if not person:
            for p in db.query(Person).filter(Person.external_ids_json.isnot(None)).all():
                if p.external_ids_json and p.external_ids_json.get("knesset_id") == person_id:
                    person = p
                    break

        if person:
            p_skipped += 1
        else:
            person = Person(
                id=uuid.uuid4(),
                name_he=row["name_he"],
                name_en=row["name_en"],
                external_ids_json={"knesset_id": person_id},
                public_profile_url=row["public_profile_url"],
            )
            db.add(person)
            db.flush()
            p_inserted += 1

        # Resolve party instance
        party_instance_id = (
            faction_id_map.get(row["faction_id"])
            or party_map.get(row["faction_name"] or "")
        )

        if not party_instance_id:
            continue  # Cannot link without known party

        # Find or create PersonPartyMembership
        start_date = _parse_date(row["start_date"])
        existing_mem = (
            db.query(PersonPartyMembership)
            .filter(
                PersonPartyMembership.person_id == person.id,
                PersonPartyMembership.party_instance_id == party_instance_id,
                PersonPartyMembership.start_date == start_date,
            )
            .first()
        )
        if existing_mem:
            m_skipped += 1
        else:
            role_id = row.get("position_id")
            role = MembershipRole(_POSITION_TO_ROLE.get(role_id, "mk"))
            end_date = _parse_date(row["end_date"])
            db.add(PersonPartyMembership(
                person_id=person.id,
                party_instance_id=party_instance_id,
                role=role,
                start_date=start_date,
                end_date=end_date,
                confidence=0.99,
                source_url=row["public_profile_url"],
            ))
            m_inserted += 1

    db.commit()
    stats = {
        "persons": {"inserted": p_inserted, "updated": p_updated, "skipped": p_skipped},
        "memberships": {"inserted": m_inserted, "skipped": m_skipped},
    }
    logger.info("import_persons knesset=%d → %s", knesset_number, stats)
    return stats


# ── Vote Results ────────────────────────────────────────────────────────────────

def import_vote_results(
    db: Session,
    knesset_number: int,
    settings: "Settings",
    vote_limit: int = 500,
    skip_existing: bool = True,
) -> dict[str, int]:
    """
    For each Vote in the DB for this Knesset, fetch per-MK results from
    Votes.svc (vote_rslts_kmmbr_shadow) and upsert into vote_results.

    Resolves kmmbr_id → Person.id via external_ids_json["knesset_id"].
    Resolves faction_name → PartyInstance.id via official_name match.

    NOTE: This makes one API call per vote. Use vote_limit to cap total requests.
    Returns {"inserted": N, "skipped_votes": N, "unknown_person": N}.
    """
    votes = (
        db.query(Vote)
        .filter(Vote.knesset_number == knesset_number, Vote.external_id.isnot(None))
        .limit(vote_limit)
        .all()
    )

    # Build lookup: knesset numeric person ID → internal Person.id
    person_map: dict[int, uuid.UUID] = {}
    for person in db.query(Person).filter(Person.external_ids_json.isnot(None)).all():
        ext = person.external_ids_json or {}
        kid = ext.get("knesset_id")
        if kid is not None:
            try:
                person_map[int(kid)] = person.id
            except (ValueError, TypeError):
                pass

    # Build lookup: faction official_name → PartyInstance.id for this knesset
    party_map: dict[str, uuid.UUID] = {
        pi.official_name: pi.id
        for pi in db.query(PartyInstance)
        .filter(PartyInstance.knesset_number == knesset_number)
        .all()
    }

    inserted = skipped_votes = unknown_person = 0

    for vote in votes:
        if skip_existing:
            existing = db.query(VoteResult).filter(VoteResult.vote_id == vote.id).first()
            if existing:
                skipped_votes += 1
                continue

        try:
            raw_results = fetch_vote_results(
                settings.knesset_votes_api_base_url, vote.external_id
            )
        except Exception as exc:
            logger.warning("fetch_vote_results failed for vote %s: %s", vote.external_id, exc)
            skipped_votes += 1
            continue

        for r in raw_results:
            raw_kid = r.get("person_external_id", "")
            try:
                knesset_id = int(raw_kid)
            except (ValueError, TypeError):
                unknown_person += 1
                continue

            person_id = person_map.get(knesset_id)
            if not person_id:
                unknown_person += 1
                continue

            faction_name = r.get("faction_name") or ""
            party_instance_id = party_map.get(faction_name)

            vote_val_str = r.get("vote_value", "absent")
            try:
                vote_value = VoteValue(vote_val_str)
            except ValueError:
                vote_value = VoteValue.absent

            db.add(VoteResult(
                id=uuid.uuid4(),
                vote_id=vote.id,
                person_id=person_id,
                party_instance_id_at_time=party_instance_id,
                vote_value=vote_value,
                source_url=vote.source_url,
            ))
            inserted += 1

        db.commit()  # commit per-vote to avoid huge transactions

    stats = {"inserted": inserted, "skipped_votes": skipped_votes, "unknown_person": unknown_person}
    logger.info("import_vote_results knesset=%d → %s", knesset_number, stats)
    return stats
