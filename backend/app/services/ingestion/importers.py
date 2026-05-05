"""
Importers — orchestrate fetch → upsert → LLM enrichment for Knesset data.
(AGENTS.MD Phase 6)

Usage:
  from backend.app.services.ingestion.importers import import_votes, import_bills
  import_votes(db, knesset_number=25, settings=settings)
"""
import logging
import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from backend.app.models.vote import Vote
from backend.app.models.bill import Bill
from backend.app.services.ingestion.knesset_odata import fetch_votes, fetch_bills
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
) -> dict[str, int]:
    """
    Fetch votes from Knesset OData, upsert into the DB, optionally ask the LLM
    to produce a plain-language summary and importance score.

    Returns {"inserted": N, "updated": N, "skipped": N}.
    """
    raw_votes = fetch_votes(settings.knesset_api_base_url, knesset_number, limit=limit)

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






