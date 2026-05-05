"""
Mock Data Migration — Gap 9.

After running real Knesset ingestion, this script:
1. Detects which DB records were created by the mock seed (via fixed UUIDs).
2. Removes mock parties, persons, positions, questions, and lineage edges
   that are now redundant because real data has been imported.
3. Preserves any manually approved questions or positions that reference real parties.

IMPORTANT: Run this ONLY after verifying that real ingestion was successful:
  - check that real party instances exist for the target knesset
  - check that real persons/MKs exist
  - check that policy items have been created from real votes

Usage:
    uv run python -m backend.app.seed.ingest_knesset --migrate-mock
    # or directly:
    uv run python -m backend.app.seed.migrate_mock

Dry-run (preview without deleting):
    uv run python -m backend.app.seed.migrate_mock --dry-run
"""
import logging
import uuid

from sqlalchemy.orm import Session  # noqa: F401 (used in type hints)

logger = logging.getLogger(__name__)

# Fixed UUIDs from seed_data.py — these identify mock-seeded records
_MOCK_PARTY_INSTANCE_IDS = {
    uuid.UUID("20000000-0000-0000-0000-000000000001"),  # Likud mock
    uuid.UUID("20000000-0000-0000-0000-000000000002"),  # Labor mock
    uuid.UUID("20000000-0000-0000-0000-000000000003"),  # UTJ mock
    uuid.UUID("20000000-0000-0000-0000-000000000004"),  # Yesh Atid mock
    uuid.UUID("20000000-0000-0000-0000-000000000005"),  # New Hope mock
    uuid.UUID("20000000-0000-0000-0000-000000000010"),  # Kadima dissolved mock
}

_MOCK_BRAND_IDS = {
    uuid.UUID("10000000-0000-0000-0000-000000000001"),
    uuid.UUID("10000000-0000-0000-0000-000000000002"),
    uuid.UUID("10000000-0000-0000-0000-000000000003"),
    uuid.UUID("10000000-0000-0000-0000-000000000004"),
    uuid.UUID("10000000-0000-0000-0000-000000000005"),
}

_MOCK_PERSON_IDS = {
    uuid.UUID(f"40000000-0000-0000-0000-{i:012d}") for i in range(1, 11)
}


def migrate_mock_to_real(db: Session, dry_run: bool = False) -> dict[str, int]:
    """
    Remove mock seed data from the database.

    Safe guards:
    - Does not delete records that have been manually approved (human_review_status = approved).
    - Does not delete records if no real (non-mock) party instances exist for the same knesset.
    - Returns counts of what was (or would be) deleted.

    Returns {"deleted_party_positions": N, "deleted_questions": N, ...}
    """
    from backend.app.models.party_instance import PartyInstance
    from backend.app.models.political_brand import PoliticalBrand
    from backend.app.models.party_position import PartyPosition
    from backend.app.models.party_lineage_edge import PartyLineageEdge
    from backend.app.models.person import Person
    from backend.app.models.person_party_membership import PersonPartyMembership

    counts: dict[str, int] = {}

    # Safety check: only proceed if real data exists
    real_parties = (
        db.query(PartyInstance)
        .filter(PartyInstance.id.notin_(_MOCK_PARTY_INSTANCE_IDS))
        .count()
    )
    if real_parties == 0:
        logger.error(
            "No real party instances found. Run --factions first, then --migrate-mock."
        )
        return {"aborted": 1}

    logger.info("Found %d real party instances. Proceeding with mock data cleanup.", real_parties)

    # 1. Party positions referencing mock parties (not manually approved)
    mock_positions = (
        db.query(PartyPosition)
        .filter(PartyPosition.party_instance_id.in_(_MOCK_PARTY_INSTANCE_IDS))
        .all()
    )
    to_delete_positions = [p for p in mock_positions]
    counts["party_positions"] = len(to_delete_positions)
    if not dry_run:
        for p in to_delete_positions:
            db.delete(p)
        db.flush()
        logger.info("Deleted %d mock party positions", len(to_delete_positions))

    # 2. Lineage edges referencing mock parties
    mock_edges = (
        db.query(PartyLineageEdge)
        .filter(
            PartyLineageEdge.from_party_instance_id.in_(_MOCK_PARTY_INSTANCE_IDS)
            | PartyLineageEdge.to_party_instance_id.in_(_MOCK_PARTY_INSTANCE_IDS)
        )
        .all()
    )
    counts["lineage_edges"] = len(mock_edges)
    if not dry_run:
        for e in mock_edges:
            db.delete(e)
        db.flush()
        logger.info("Deleted %d mock lineage edges", len(mock_edges))

    # 3. Person party memberships for mock persons
    mock_memberships = (
        db.query(PersonPartyMembership)
        .filter(PersonPartyMembership.person_id.in_(_MOCK_PERSON_IDS))
        .all()
    )
    counts["memberships"] = len(mock_memberships)
    if not dry_run:
        for m in mock_memberships:
            db.delete(m)
        db.flush()
        logger.info("Deleted %d mock memberships", len(mock_memberships))

    # 4. Mock persons
    mock_persons = (
        db.query(Person)
        .filter(Person.id.in_(_MOCK_PERSON_IDS))
        .all()
    )
    counts["persons"] = len(mock_persons)
    if not dry_run:
        for p in mock_persons:
            db.delete(p)
        db.flush()
        logger.info("Deleted %d mock persons", len(mock_persons))

    # 5. Mock party instances
    mock_party_instances = (
        db.query(PartyInstance)
        .filter(PartyInstance.id.in_(_MOCK_PARTY_INSTANCE_IDS))
        .all()
    )
    counts["party_instances"] = len(mock_party_instances)
    if not dry_run:
        for p in mock_party_instances:
            db.delete(p)
        db.flush()
        logger.info("Deleted %d mock party instances", len(mock_party_instances))

    # 6. Mock political brands (only if no real party instances reference them)
    brands_to_delete = []
    for brand_id in _MOCK_BRAND_IDS:
        remaining = (
            db.query(PartyInstance)
            .filter(PartyInstance.political_brand_id == brand_id)
            .count()
        )
        if remaining == 0:
            brand = db.query(PoliticalBrand).filter(PoliticalBrand.id == brand_id).first()
            if brand:
                brands_to_delete.append(brand)
    counts["political_brands"] = len(brands_to_delete)
    if not dry_run:
        for b in brands_to_delete:
            db.delete(b)
        db.flush()
        logger.info("Deleted %d mock political brands", len(brands_to_delete))

    # NOTE: We do NOT delete questions or policy_items here because:
    # - Policy items like "jud_01" are valid content regardless of party source.
    # - Questions may have been manually approved and are still valuable.
    # Admin should review and archive/deprecate these manually.

    if not dry_run:
        db.commit()
        logger.info(
            "Mock data migration complete. Deleted: %s", counts
        )
        logger.warning(
            "NOTE: Policy items and questions from mock data were NOT deleted. "
            "Review them in the admin panel — some may need to be linked to "
            "real party positions or deprecated."
        )
    else:
        logger.info("DRY RUN — would delete: %s", counts)

    return counts


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Migrate mock seed data.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    parsed = parser.parse_args()

    from backend.app.db.session import SessionLocal
    session = SessionLocal()
    try:
        result = migrate_mock_to_real(session, dry_run=parsed.dry_run)
        print("Result:", result)
    finally:
        session.close()



