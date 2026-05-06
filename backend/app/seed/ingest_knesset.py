"""
CLI entry point for real Knesset data ingestion and pipeline execution.

AGENTS.MD Phase 6 — Full ingestion pipeline.

Usage examples:
  # Probe whether Knesset 25/26 vote data is available in the OData API:
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --probe-votes
  uv run python -m backend.app.seed.ingest_knesset --knesset 26 --probe-votes

  # Full pipeline for Knesset 25 (no LLM, fast):
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --full --no-llm

  # Full pipeline with LLM enrichment (requires OPENAI_API_KEY in .env):
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --full

  # Step by step:
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --factions
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --votes --limit 500
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --bills --limit 500
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --persons --limit 300
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --vote-results --limit 200
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --policy-items --limit 200
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --party-positions
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --questions --limit 50
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --lineage
  uv run python -m backend.app.seed.ingest_knesset --knesset 25 --volatility
  uv run python -m backend.app.seed.ingest_knesset --migrate-mock

KNOWN LIMITATIONS (as of May 2026):
  - The Knesset Votes.svc OData endpoint (View_vote_rslts_hdr_Approved) historically
    only contained data for Knessets 1-24. Knesset 25 data became partially available
    in 2025. Use --probe-votes to verify availability before a full import.
  - Alternatively Hasadna / Open Knesset (oknesset.org) may have more current vote data.
  - Knesset 26 started in 2025; update party seed data to reflect current parties.
"""
import argparse
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(
        description="SmartVoter: Ingest Knesset data and run analysis pipelines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--knesset", type=int, default=25, help="Knesset number (default: 25)")
    parser.add_argument("--limit", type=int, default=500, help="Max records per entity type")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM enrichment")
    # Multi-Knesset mode: runs the full pipeline for the last N Knessets
    parser.add_argument("--last-n", type=int, default=0, dest="last_n",
                        help=(
                            "Run the full pipeline for the last N Knessets automatically.\n"
                            "E.g. --last-n 2 imports Knessets 24 and 25 (using --current-knesset).\n"
                            "Votes are skipped for Knessets >= --last-knesset-with-votes+1."
                        ))
    parser.add_argument("--current-knesset", type=int, default=None, dest="current_knesset",
                        help="Most recent Knesset number (default: from settings.current_knesset)")

    parser.add_argument("--factions",        action="store_true", help="Import factions/party instances")
    parser.add_argument("--votes",           action="store_true", help="Import plenary votes")
    parser.add_argument("--bills",           action="store_true", help="Import bills")
    parser.add_argument("--persons",         action="store_true", help="Import MKs/candidates")
    parser.add_argument("--vote-results",    action="store_true", dest="vote_results",
                        help="Import per-MK vote results")
    parser.add_argument("--policy-items",    action="store_true", dest="policy_items",
                        help="Run policy item pipeline")
    parser.add_argument("--party-positions", action="store_true", dest="party_positions",
                        help="Run party position pipeline")
    parser.add_argument("--questions",       action="store_true", help="Run question generation")
    parser.add_argument("--lineage",         action="store_true", help="Run lineage inference")
    parser.add_argument("--volatility",      action="store_true", help="Compute volatility scores")
    parser.add_argument("--full",            action="store_true", help="Run all steps in sequence")
    parser.add_argument("--votes-only",      action="store_true", dest="votes_only",
                        help="Shortcut: votes only")
    parser.add_argument("--bills-only",      action="store_true", dest="bills_only",
                        help="Shortcut: bills only")
    parser.add_argument("--migrate-mock",    action="store_true", dest="migrate_mock",
                        help="Remove mock seed data after real data is loaded")
    parser.add_argument("--probe-votes",     action="store_true", dest="probe_votes",
                        help="Check if vote data is available for this Knesset number and exit")

    args = parser.parse_args()

    if args.full:
        args.factions = args.votes = args.bills = True
        args.persons = args.vote_results = True
        args.policy_items = args.party_positions = True
        args.questions = args.lineage = args.volatility = True

    if args.votes_only:
        args.votes = True
    if args.bills_only:
        args.bills = True

    # ── Multi-Knesset mode (--last-n) ────────────────────────────────────────
    if args.last_n > 0:
        from backend.app.config import get_settings as _get_settings
        _settings = _get_settings()
        _current = args.current_knesset or _settings.current_knesset
        _knessets = list(range(_current, _current - args.last_n, -1))  # e.g. [25, 24]
        _last_votes = _settings.last_knesset_with_votes

        print(f"\n{'='*60}")
        print(f"Full pipeline — Knessets: {_knessets} (no-LLM={args.no_llm})")
        print(f"Vote data available up to Knesset {_last_votes}")
        print(f"{'='*60}\n")

        from backend.app.db.session import SessionLocal as _SL
        _db = _SL()

        def _step(label, fn, *a, **kw):
            logger.info("=== %s ===", label.upper())
            try:
                r = fn(*a, **kw)
                logger.info("%s complete: %s", label, r)
                return r
            except Exception as exc:
                logger.error("%s FAILED: %s", label, exc, exc_info=True)
                return None

        try:
            # Phase 1: raw data per Knesset (most recent first)
            for _kn in _knessets:
                print(f"\n--- Knesset {_kn} ---")
                from backend.app.services.ingestion.importers import (
                    import_factions, import_votes, import_bills,
                    import_persons, import_vote_results,
                )
                _step(f"[K{_kn}] factions",      import_factions,      _db, _kn, _settings)
                if _kn <= _last_votes:
                    _step(f"[K{_kn}] votes",     import_votes,         _db, _kn, _settings,
                          limit=args.limit, enrich_with_llm=not args.no_llm)
                    _step(f"[K{_kn}] vote_results", import_vote_results, _db, _kn, _settings,
                          vote_limit=args.limit)
                else:
                    print(f"  ⚠  Knesset {_kn} vote data not yet in Votes.svc — skipping votes+vote_results")
                _step(f"[K{_kn}] bills",          import_bills,         _db, _kn, _settings,
                      limit=args.limit, enrich_with_llm=not args.no_llm)
                _step(f"[K{_kn}] persons",        import_persons,       _db, _kn, _settings,
                      limit=args.limit)

            # Phase 2: analysis pipeline (runs once over all imported data)
            print("\n--- Analysis pipeline ---")
            from backend.app.services.ingestion.policy_item_pipeline import run_policy_item_pipeline
            from backend.app.services.ingestion.party_position_pipeline import run_party_position_pipeline
            from backend.app.services.ingestion.question_pipeline import run_question_pipeline
            from backend.app.services.lineage.lineage_service import run_lineage_inference
            from backend.app.services.volatility.volatility_service import run_volatility_update

            _step("policy_items",    run_policy_item_pipeline,    _db, _settings,
                  knesset_number=None, limit=args.limit, enrich_with_llm=not args.no_llm)
            _step("party_positions", run_party_position_pipeline, _db, _settings,
                  knesset_number=None, enrich_with_llm=not args.no_llm)
            if not args.no_llm:
                _step("questions",   run_question_pipeline, _db, _settings, limit=args.limit)
            _step("lineage",         run_lineage_inference,       _db, _settings,
                  knesset_number=_knessets[0], enrich_with_llm=not args.no_llm)
            _step("volatility",      run_volatility_update,       _db, knesset_number=_knessets[0])

            print(f"\n✅ Full pipeline complete for Knessets {_knessets}")
            logger.info("All requested steps complete.")
        except KeyboardInterrupt:
            logger.warning("Interrupted.")
            sys.exit(130)
        finally:
            _db.close()
        sys.exit(0)
    # ── /end multi-Knesset mode ──────────────────────────────────────────────

    steps_selected = any([
        args.last_n > 0,
        args.factions, args.votes, args.bills, args.persons,
        args.vote_results, args.policy_items, args.party_positions,
        args.questions, args.lineage, args.volatility,
        args.migrate_mock, args.probe_votes,
    ])
    if not steps_selected:
        parser.print_help()
        print("\nError: specify at least one step flag or use --full")
        sys.exit(1)

    from backend.app.config import get_settings
    from backend.app.db.session import SessionLocal

    settings = get_settings()

    # Probe mode: check vote availability and exit
    if args.probe_votes:
        from backend.app.services.ingestion.knesset_odata import probe_votes_availability
        available = probe_votes_availability(settings.knesset_votes_api_base_url, args.knesset)
        if available:
            print(f"✅ Knesset {args.knesset} vote data IS available in the OData API.")
        else:
            print(
                f"❌ Knesset {args.knesset} vote data is NOT available in the OData API.\n"
                f"   Consider: --knesset {args.knesset - 1} for previous Knesset data,\n"
                f"   or use Open Knesset (https://oknesset.org/api/v2/vote/) for current data."
            )
        sys.exit(0 if available else 1)

    db = SessionLocal()

    def run_step(label: str, fn, *a, **kw):
        logger.info("=== %s ===", label.upper())
        try:
            result = fn(*a, **kw)
            logger.info("%s complete: %s", label, result)
            return result
        except Exception as exc:
            logger.error("%s FAILED: %s", label, exc, exc_info=True)
            return None

    try:
        if args.factions:
            from backend.app.services.ingestion.importers import import_factions
            run_step("factions", import_factions, db, args.knesset, settings)

        if args.votes:
            from backend.app.services.ingestion.importers import import_votes
            run_step("votes", import_votes, db, args.knesset, settings,
                     limit=args.limit, enrich_with_llm=not args.no_llm)

        if args.bills:
            from backend.app.services.ingestion.importers import import_bills
            run_step("bills", import_bills, db, args.knesset, settings,
                     limit=args.limit, enrich_with_llm=not args.no_llm)

        if args.persons:
            from backend.app.services.ingestion.importers import import_persons
            run_step("persons", import_persons, db, args.knesset, settings, limit=args.limit)

        if args.vote_results:
            from backend.app.services.ingestion.importers import import_vote_results
            run_step("vote-results", import_vote_results, db, args.knesset, settings,
                     vote_limit=args.limit)

        if args.policy_items:
            from backend.app.services.ingestion.policy_item_pipeline import run_policy_item_pipeline
            run_step("policy-items", run_policy_item_pipeline, db, settings,
                     knesset_number=args.knesset, limit=args.limit,
                     enrich_with_llm=not args.no_llm)

        if args.party_positions:
            from backend.app.services.ingestion.party_position_pipeline import run_party_position_pipeline
            run_step("party-positions", run_party_position_pipeline, db, settings,
                     knesset_number=args.knesset, enrich_with_llm=not args.no_llm)

        if args.questions:
            from backend.app.services.ingestion.question_pipeline import run_question_pipeline
            run_step("questions", run_question_pipeline, db, settings, limit=args.limit)

        if args.lineage:
            from backend.app.services.lineage.lineage_service import run_lineage_inference
            run_step("lineage", run_lineage_inference, db, settings,
                     knesset_number=args.knesset, enrich_with_llm=not args.no_llm)

        if args.volatility:
            from backend.app.services.volatility.volatility_service import run_volatility_update
            run_step("volatility", run_volatility_update, db, knesset_number=args.knesset)

        if args.migrate_mock:
            from backend.app.seed.migrate_mock import migrate_mock_to_real
            run_step("migrate-mock", migrate_mock_to_real, db)

        logger.info("All requested steps complete.")

    except KeyboardInterrupt:
        logger.warning("Interrupted.")
        sys.exit(130)
    finally:
        db.close()


if __name__ == "__main__":
    main()

