"""
Policy Item Pipeline — Phase 6 / Gap 2.

Converts imported Votes and Bills into normalised PolicyItem records:

  Vote/Bill  →  LLM classify topic  →  LLM extract axis  →  PolicyItem (needs_review)

Deduplication rule (MVP): one PolicyItem per source vote/bill.
Admins can later merge duplicates or assign multiple-source references.

Usage:
    from backend.app.services.ingestion.policy_item_pipeline import run_policy_item_pipeline
    stats = run_policy_item_pipeline(db, settings, knesset_number=25, limit=200)
"""
import logging
import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from backend.app.models.vote import Vote
from backend.app.models.bill import Bill
from backend.app.models.topic import Topic
from backend.app.models.policy_item import PolicyItem, PolicySourceType, ReviewStatus
from backend.app.services.llm import get_llm_provider
from backend.app.services.llm.audit_service import AuditedLLMService

if TYPE_CHECKING:
    from backend.app.config import Settings

logger = logging.getLogger(__name__)

# Maps LLM topic slug → canonical Topic slug stored in DB
_TOPIC_SLUG_ALIASES: dict[str, list[str]] = {
    "security":              ["security"],
    "judiciary":             ["judiciary"],
    "religion_state":        ["religion_state"],
    "settlements":           ["security"],          # sub-topic → parent
    "economy_taxes":         ["economy_taxes"],
    "healthcare":            ["healthcare"],
    "education":             ["education"],
    "civil_rights":          ["civil_rights"],
    "housing":               ["housing"],
    "welfare":               ["welfare"],
    "military_service":      ["military_service"],
    "governance_corruption": ["governance_corruption"],
    "environment":           ["environment"],
    "transport":             ["transport"],
    "cost_of_living":        ["cost_of_living"],
}


def _resolve_topic(db: Session, llm_primary_topic: str) -> uuid.UUID | None:
    """Resolve LLM topic slug → Topic.id, trying canonical aliases."""
    candidates = _TOPIC_SLUG_ALIASES.get(llm_primary_topic, [llm_primary_topic])
    for slug in candidates:
        topic = db.query(Topic).filter(Topic.slug == slug).first()
        if topic:
            return topic.id
    # Fallback: any topic
    fallback = db.query(Topic).first()
    return fallback.id if fallback else None


def _already_has_policy_item(db: Session, source_type: str, source_id: str) -> bool:
    """Return True if a PolicyItem with this source ref already exists."""
    ref_marker = f"{source_type}:{source_id}"
    # Quick text search in source_refs_json (MVP: linear scan)
    for pi in db.query(PolicyItem).filter(PolicyItem.source_type == source_type).all():
        if pi.source_refs_json and any(
            (r.get("id") == source_id if isinstance(r, dict) else r == ref_marker)
            for r in pi.source_refs_json
        ):
            return True
    return False


def run_policy_item_pipeline(
    db: Session,
    settings: "Settings",
    knesset_number: int | None = None,
    limit: int = 200,
    min_importance: float = 0.5,
    skip_procedural: bool = True,
    enrich_with_llm: bool = True,
) -> dict[str, int]:
    """
    Scan Votes (and Bills) in the DB and create PolicyItem records for those
    that pass quality filters and don't already have a PolicyItem.

    Steps per vote/bill:
    1. LLM classify_policy_item  → topic + confidence
    2. LLM extract_policy_axis   → directional_axis
    3. Insert PolicyItem with human_review_status = "needs_review"

    Without LLM (enrich_with_llm=False): creates stubs in "draft" status
    with empty axis, using the vote title as the policy item title.

    Returns {"votes_processed": N, "bills_processed": N, "created": N, "skipped": N}.
    """
    llm_raw = get_llm_provider(settings) if enrich_with_llm else None
    llm = AuditedLLMService(llm_raw, db) if llm_raw else None

    votes_processed = bills_processed = created = skipped = 0

    # Process votes
    vote_query = db.query(Vote).filter(Vote.is_procedural_estimate.is_(False) if skip_procedural else True)
    if knesset_number:
        vote_query = vote_query.filter(Vote.knesset_number == knesset_number)
    if min_importance > 0:
        vote_query = vote_query.filter(
            (Vote.importance_score >= min_importance) | Vote.importance_score.is_(None)
        )
    votes = vote_query.limit(limit).all()

    for vote in votes:
        votes_processed += 1
        if _already_has_policy_item(db, "vote", str(vote.id)):
            skipped += 1
            continue

        title = vote.title_en or vote.title_he
        result = _create_policy_item_from_source(
            db, llm, title,
            description=vote.title_he,
            source_type=PolicySourceType.vote,
            source_id=str(vote.id),
            source_url=vote.source_url,
        )
        if result:
            created += 1

    # Process bills
    bills = db.query(Bill).limit(limit).all()
    for bill in bills:
        bills_processed += 1
        if _already_has_policy_item(db, "bill", str(bill.id)):
            skipped += 1
            continue

        title = bill.title_en or bill.title_he
        result = _create_policy_item_from_source(
            db, llm, title,
            description=bill.summary_en or bill.summary_he or "",
            source_type=PolicySourceType.bill,
            source_id=str(bill.id),
            source_url=bill.source_url,
        )
        if result:
            created += 1

    db.commit()
    stats = {
        "votes_processed": votes_processed,
        "bills_processed": bills_processed,
        "created": created,
        "skipped": skipped,
    }
    logger.info("policy_item_pipeline → %s", stats)
    return stats


def _create_policy_item_from_source(
    db: Session,
    llm: AuditedLLMService | None,
    title: str,
    description: str,
    source_type: PolicySourceType,
    source_id: str,
    source_url: str | None,
) -> PolicyItem | None:
    """
    Create a PolicyItem from a single vote or bill source.
    Uses LLM to classify topic and extract directional axis.
    Returns the created PolicyItem, or None on error.
    """
    if not title or title.strip() == "—":
        return None

    # Default topic fallback (use first topic in DB)
    topic_id: uuid.UUID | None = None
    directional_axis: str | None = None
    llm_confidence: float | None = None
    review_status = ReviewStatus.draft

    if llm:
        # Single combined call: classify topic + extract axis (1 LLM call instead of 2)
        try:
            combined = llm.classify_and_extract(
                {"title": title, "description": description}
            )
            primary_topic = combined.get("primary_topic", "")
            llm_confidence = combined.get("classification_confidence")
            topic_id = _resolve_topic(db, primary_topic)
            review_status = ReviewStatus.needs_review

            neg = combined.get("negative_pole", "")
            pos = combined.get("positive_pole", "")
            axis_name = combined.get("axis_name", "")
            if axis_name or neg or pos:
                directional_axis = f"{axis_name}: -1={neg}, +1={pos}"
        except Exception as exc:
            logger.warning("classify_and_extract failed for '%s': %s", title[:80], exc)

    # Fallback: use any topic
    if not topic_id:
        fallback = db.query(Topic).first()
        topic_id = fallback.id if fallback else None

    if not topic_id:
        logger.error("No topics in DB — cannot create policy item for '%s'", title[:80])
        return None

    pi = PolicyItem(
        id=uuid.uuid4(),
        title=title[:500],
        description=description[:2000] if description else None,
        topic_id=topic_id,
        directional_axis=directional_axis,
        source_type=source_type,
        source_refs_json=[{"type": source_type.value, "id": source_id, "url": source_url}],
        llm_confidence=llm_confidence,
        human_review_status=review_status,
    )
    db.add(pi)
    db.flush()
    return pi

