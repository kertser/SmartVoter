"""
CLI entry point for real Knesset data ingestion.
Run with:
  uv run python -m backend.app.seed.ingest_knesset --knesset 25
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --votes-only
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --bills-only
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --no-llm --limit 200

AGENTS.MD Phase 6
"""
import argparse
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest real Knesset data into SmartVoter DB.")
    parser.add_argument("--knesset", type=int, required=True, help="Knesset number (e.g. 25)")
    parser.add_argument("--limit", type=int, default=500, help="Max records per entity type")
    parser.add_argument("--votes-only", action="store_true", help="Import votes only")
    parser.add_argument("--bills-only", action="store_true", help="Import bills only")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM enrichment")
    args = parser.parse_args()

    from backend.app.config import get_settings
    from backend.app.db.session import SessionLocal
    from backend.app.services.ingestion.importers import import_votes, import_bills

    settings = get_settings()
    db = SessionLocal()

    try:
        do_votes = not args.bills_only
        do_bills = not args.votes_only
        enrich = not args.no_llm

        if do_votes:
            logger.info("Importing votes for Knesset %d (limit=%d, llm=%s)…",
                        args.knesset, args.limit, enrich)
            stats = import_votes(db, args.knesset, settings, limit=args.limit, enrich_with_llm=enrich)
            logger.info("Votes: %s", stats)

        if do_bills:
            logger.info("Importing bills for Knesset %d (limit=%d, llm=%s)…",
                        args.knesset, args.limit, enrich)
            stats = import_bills(db, args.knesset, settings, limit=args.limit, enrich_with_llm=enrich)
            logger.info("Bills: %s", stats)

        logger.info("Ingestion complete.")

    except Exception as exc:
        logger.error("Ingestion failed: %s", exc, exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

