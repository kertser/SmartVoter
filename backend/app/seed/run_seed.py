"""
Seed runner: populates the database with mock data for Phase 1 + Phase 14B.
Run with: uv run python -m backend.app.seed.run_seed

Idempotent: checks if topics already exist before inserting.
"""
import uuid
import sys
from sqlalchemy.exc import IntegrityError

from backend.app.db.session import SessionLocal
from backend.app.db.base import Base
from backend.app.db.session import engine
import backend.app.models  # noqa: F401 — registers all models with Base.metadata

from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.party_instance import PartyInstance, PartyStatus
from backend.app.models.party_lineage_edge import (
    PartyLineageEdge,
    LineageRelationType,
    LineageReviewStatus,
)
from backend.app.models.person import Person
from backend.app.models.person_party_membership import PersonPartyMembership, MembershipRole
from backend.app.models.topic import Topic
from backend.app.models.policy_item import PolicyItem, PolicySourceType, ReviewStatus
from backend.app.models.party_position import PartyPosition
from backend.app.models.question import Question, AnswerScaleType
from backend.app.models.simulation import (
    Pollster, Poll, PollPartyResult,
    HistoricalElectionResult, HistoricalPartyResult,
    CoalitionConstraint,
)
from backend.app.services.volatility import register_mock_volatility

from backend.app.seed.seed_data import (
    POLITICAL_BRANDS,
    PARTY_INSTANCES,
    LINEAGE_EDGES,
    TOPICS,
    POLICY_ITEMS,
    PARTY_POSITIONS_RAW,
    PARTY_VOLATILITY,
    PERSONS,
    MEMBERSHIPS,
    QUESTIONS_DATA,
    # Phase 14B
    POLLSTERS,
    POLLS,
    HISTORICAL_ELECTION,
    COALITION_CONSTRAINTS_RAW,
    # Party UUIDs needed for coalition constraints
    PARTY_LIKUD, PARTY_LABOR, PARTY_UTJ, PARTY_YESH_ATID, PARTY_NEW_HOPE,
    PARTY_MAMLAKHTIT, PARTY_SHAS, PARTY_HATZIONUT, PARTY_BEITEINU,
    PARTY_RAAM, PARTY_HADASH, PARTY_MERETZ,
)


def seed_simulation_only() -> None:
    """Seed only the simulation tables (pollsters, polls, historical election, coalition constraints).
    Safe to run even if core data is already seeded.
    """
    db = SessionLocal()
    try:
        if db.query(Pollster).first():
            print("Simulation data already seeded. Skipping.")
            return

        print("Seeding simulation data...")

        # Pollsters
        for po in POLLSTERS:
            db.add(Pollster(**po))
        db.flush()
        print(f"  ✓ {len(POLLSTERS)} pollsters")

        party_name_to_id: dict[str, uuid.UUID] = {}
        from backend.app.models.party_instance import PartyInstance as _PI
        for pi_row in db.query(_PI).all():
            party_name_to_id[pi_row.official_name] = pi_row.id

        for poll_data in POLLS:
            poll = Poll(
                id=poll_data["id"],
                pollster_id=poll_data["pollster_id"],
                field_end_date=poll_data["field_end_date"],
                sample_size=poll_data["sample_size"],
                quality_score=poll_data["quality_score"],
            )
            db.add(poll)
            db.flush()
            for party_name, share in poll_data["results"]:
                db.add(PollPartyResult(
                    poll_id=poll.id,
                    party_instance_id=party_name_to_id.get(party_name),
                    reported_name=party_name,
                    vote_share_mean=share,
                    seats_mean=round(share / (1 / 120), 1),
                ))
        db.flush()
        print(f"  ✓ {len(POLLS)} polls")

        hist = HistoricalElectionResult(
            id=HISTORICAL_ELECTION["id"],
            election_cycle=HISTORICAL_ELECTION["election_cycle"],
            election_date=HISTORICAL_ELECTION["election_date"],
            turnout=HISTORICAL_ELECTION["turnout"],
            threshold_percent=HISTORICAL_ELECTION["threshold_percent"],
            total_valid_votes=HISTORICAL_ELECTION["total_valid_votes"],
        )
        db.add(hist)
        db.flush()
        for party_name, share, seats, passed in HISTORICAL_ELECTION["results"]:
            db.add(HistoricalPartyResult(
                historical_election_result_id=hist.id,
                party_instance_id=party_name_to_id.get(party_name),
                reported_name=party_name,
                vote_share=share,
                seats=seats,
                passed_threshold=passed,
            ))
        db.flush()
        print(f"  ✓ 1 historical election")

        for src_name, tgt_name, c_type, strength, explanation in COALITION_CONSTRAINTS_RAW:
            src_id = party_name_to_id.get(src_name)
            tgt_id = party_name_to_id.get(tgt_name)
            if not src_id or not tgt_id:
                continue
            db.add(CoalitionConstraint(
                source_party_instance_id=src_id,
                target_party_instance_id=tgt_id,
                constraint_type=c_type,
                strength=strength,
                llm_explanation=explanation,
                confidence=0.90,
                human_review_status="approved",
            ))
        db.flush()
        print(f"  ✓ {len(COALITION_CONSTRAINTS_RAW)} coalition constraints")

        db.commit()
        print("Simulation seeding complete ✓")
    except Exception as e:
        db.rollback()
        print(f"Simulation seeding failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


def patch_party_colors_and_lr() -> None:
    """
    Update existing political_brands with color_hex and party_instances with
    left_right_score from seed data. Safe to run on an already-seeded DB.
    Also inserts new party brands/instances that don't exist yet.
    """
    from sqlalchemy.orm.attributes import flag_modified

    db = SessionLocal()
    try:
        updated_brands = 0
        inserted_brands = 0
        for b in POLITICAL_BRANDS:
            brand = db.query(PoliticalBrand).filter(PoliticalBrand.id == b["id"]).first()
            if not brand:
                db.add(PoliticalBrand(
                    id=b["id"],
                    canonical_name=b["canonical_name"],
                    names_json=b.get("names_json"),
                    description=b.get("description"),
                    color_hex=b.get("color_hex"),
                ))
                inserted_brands += 1
            else:
                if b.get("color_hex") and brand.color_hex != b["color_hex"]:
                    brand.color_hex = b["color_hex"]
                    updated_brands += 1
                # Also update names_json if missing keys
                seed_names = b.get("names_json") or {}
                existing = brand.names_json or {}
                changed = any(
                    seed_names.get(k) and existing.get(k) != seed_names[k]
                    for k in ("he", "ru", "en")
                )
                if changed:
                    brand.names_json = {**existing, **{k: v for k, v in seed_names.items() if v}}
                    flag_modified(brand, "names_json")

        db.flush()
        if inserted_brands:
            print(f"  ✓ Inserted {inserted_brands} new political brands")
        if updated_brands:
            print(f"  ✓ Updated color_hex for {updated_brands} political brands")

        # Party instances
        updated_instances = 0
        inserted_instances = 0
        existing_pids = {str(pi.id) for pi in db.query(PartyInstance).all()}

        for p in PARTY_INSTANCES:
            pid_str = str(p["id"])
            if pid_str not in existing_pids:
                db.add(PartyInstance(
                    id=p["id"],
                    political_brand_id=p["political_brand_id"],
                    official_name=p["official_name"],
                    election_cycle=p.get("election_cycle"),
                    knesset_number=p.get("knesset_number"),
                    start_date=p.get("start_date"),
                    end_date=p.get("end_date"),
                    status=PartyStatus(p["status"]),
                    left_right_score=p.get("left_right_score"),
                ))
                inserted_instances += 1
            else:
                pi_row = db.query(PartyInstance).filter(PartyInstance.id == p["id"]).first()
                if pi_row and p.get("left_right_score") is not None:
                    if pi_row.left_right_score != p["left_right_score"]:
                        pi_row.left_right_score = p["left_right_score"]
                        updated_instances += 1
                if pi_row and p.get("status"):
                    new_status = PartyStatus(p["status"])
                    if pi_row.status != new_status:
                        pi_row.status = new_status

        db.flush()
        if inserted_instances:
            print(f"  ✓ Inserted {inserted_instances} new party instances")
        if updated_instances:
            print(f"  ✓ Updated left_right_score for {updated_instances} party instances")

        db.commit()
        print("patch_party_colors_and_lr complete ✓")
    except Exception as e:
        db.rollback()
        print(f"patch_party_colors_and_lr failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


def patch_simulation_data() -> None:
    """
    Replace/update simulation data (pollsters, polls, historical election, coalition constraints)
    with the current seed data. Drops existing simulation run data first to avoid stale caches.
    Safe to run on a DB that was seeded with old mock data.
    """
    db = SessionLocal()
    try:
        # Clear existing simulation data so new polls trigger fresh runs
        from backend.app.models.simulation import (
            CoalitionScenarioMember, CoalitionScenario, SimulationPartyResult,
            SimulationRun, CoalitionConstraint, HistoricalPartyResult,
            HistoricalElectionResult, PollPartyResult, Poll, Pollster
        )
        print("  Clearing old simulation data...")
        db.query(CoalitionScenarioMember).delete()
        db.query(CoalitionScenario).delete()
        db.query(SimulationPartyResult).delete()
        db.query(SimulationRun).delete()
        db.query(CoalitionConstraint).delete()
        db.query(HistoricalPartyResult).delete()
        db.query(HistoricalElectionResult).delete()
        db.query(PollPartyResult).delete()
        db.query(Poll).delete()
        db.query(Pollster).delete()
        db.flush()

        party_name_to_id: dict[str, uuid.UUID] = {}
        for pi_row in db.query(PartyInstance).all():
            party_name_to_id[pi_row.official_name] = pi_row.id

        # Pollsters
        for po in POLLSTERS:
            db.add(Pollster(**po))
        db.flush()
        print(f"  ✓ {len(POLLSTERS)} pollsters")

        for poll_data in POLLS:
            poll = Poll(
                id=poll_data["id"],
                pollster_id=poll_data["pollster_id"],
                field_end_date=poll_data["field_end_date"],
                sample_size=poll_data["sample_size"],
                quality_score=poll_data["quality_score"],
            )
            db.add(poll)
            db.flush()
            for party_name, share in poll_data["results"]:
                db.add(PollPartyResult(
                    poll_id=poll.id,
                    party_instance_id=party_name_to_id.get(party_name),
                    reported_name=party_name,
                    vote_share_mean=share,
                    seats_mean=round(share * 120, 1),
                ))
        db.flush()
        print(f"  ✓ {len(POLLS)} polls")

        hist = HistoricalElectionResult(
            id=HISTORICAL_ELECTION["id"],
            election_cycle=HISTORICAL_ELECTION["election_cycle"],
            election_date=HISTORICAL_ELECTION["election_date"],
            turnout=HISTORICAL_ELECTION["turnout"],
            threshold_percent=HISTORICAL_ELECTION["threshold_percent"],
            total_valid_votes=HISTORICAL_ELECTION["total_valid_votes"],
        )
        db.add(hist)
        db.flush()
        for party_name, share, seats, passed in HISTORICAL_ELECTION["results"]:
            db.add(HistoricalPartyResult(
                historical_election_result_id=hist.id,
                party_instance_id=party_name_to_id.get(party_name),
                reported_name=party_name,
                vote_share=share,
                seats=seats,
                passed_threshold=passed,
            ))
        db.flush()
        print("  ✓ 1 historical election (25th Knesset, Nov 2022 — real results)")

        for src_name, tgt_name, c_type, strength, explanation in COALITION_CONSTRAINTS_RAW:
            src_id = party_name_to_id.get(src_name)
            tgt_id = party_name_to_id.get(tgt_name)
            if not src_id or not tgt_id:
                print(f"    ⚠ Coalition constraint skipped: {src_name!r} or {tgt_name!r} not in DB")
                continue
            db.add(CoalitionConstraint(
                source_party_instance_id=src_id,
                target_party_instance_id=tgt_id,
                constraint_type=c_type,
                strength=strength,
                llm_explanation=explanation,
                confidence=0.90,
                human_review_status="approved",
            ))
        db.flush()
        print(f"  ✓ {len(COALITION_CONSTRAINTS_RAW)} coalition constraints")

        db.commit()
        print("patch_simulation_data complete ✓")
    except Exception as e:
        db.rollback()
        print(f"patch_simulation_data failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()



    """
    Ensure all seed political brands have up-to-date names_json (he + ru + en).
    Safe to run on an already-seeded DB — only updates if a key is missing or wrong.
    Uses flag_modified so SQLAlchemy detects in-place JSON mutations correctly.
    """
    from sqlalchemy.orm.attributes import flag_modified

    db = SessionLocal()
    try:
        updated = 0
        for b in POLITICAL_BRANDS:
            brand = db.query(PoliticalBrand).filter(PoliticalBrand.id == b["id"]).first()
            if not brand:
                continue
            seed_names = b.get("names_json") or {}
            existing = brand.names_json or {}
            changed = any(
                seed_names.get(k) and existing.get(k) != seed_names[k]
                for k in ("he", "ru", "en")
            )
            if changed:
                # Replace the whole dict; flag_modified ensures SQLAlchemy persists it
                merged = {**existing, **{k: v for k, v in seed_names.items() if v}}
                brand.names_json = merged
                flag_modified(brand, "names_json")
                updated += 1
        if updated:
            db.commit()
            print(f"  ✓ Patched names_json for {updated} political brands")
    except Exception as e:
        db.rollback()
        print(f"patch_brand_names failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


def patch_question_polarity() -> None:
    """
    Update answer_polarity on all existing questions using the seed data as source of truth.
    Safe to run on any already-seeded DB — matching by English text.
    Also clears stale user_answers/recommendation_runs from before the polarity fix was applied
    (since those stored values may be in the wrong direction).
    """
    from backend.app.models.question import Question as _QP

    db = SessionLocal()
    try:
        # Build lookup: english text → answer_polarity
        polarity_map: dict[str, float] = {}
        for q_tuple in QUESTIONS_DATA:
            text_en = q_tuple[1]
            polarity = float(q_tuple[4]) if len(q_tuple) > 4 else 1.0
            polarity_map[text_en] = polarity

        updated = 0
        for q in db.query(_QP).all():
            expected = polarity_map.get(q.question_text_en, 1.0)
            current = getattr(q, "answer_polarity", None)
            if current is None or abs(current - expected) > 0.01:
                q.answer_polarity = expected
                updated += 1

        # Clear stale user_answers since their stored values may be wrong direction
        from backend.app.models.user_answer import UserAnswer as _UA
        from backend.app.models.recommendation_run import RecommendationRun as _RR
        deleted_answers = db.query(_UA).delete()
        deleted_runs = db.query(_RR).delete()

        db.commit()
        print(f"  ✓ patch_question_polarity: updated polarity for {updated} questions")
        if deleted_answers:
            print(f"  ✓ Cleared {deleted_answers} stale user_answers (polarity fix)")
        if deleted_runs:
            print(f"  ✓ Cleared {deleted_runs} stale recommendation_runs")
    except Exception as e:
        db.rollback()
        print(f"patch_question_polarity failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


def patch_question_translations() -> None:
    """
    Backfill question_text_ru (and question_text_he) for existing questions that have
    an empty or NULL translation, using the seed data (questions.json) as the source
    of truth. Matching is done by question_text_en (English text is stable).

    Safe to run on any already-seeded DB — only updates rows where the translation
    field is NULL or empty string.
    """
    from backend.app.models.question import Question as _Q3

    db = SessionLocal()
    try:
        # Build lookup: english text → (he, ru) from seed JSON
        seed_map: dict[str, tuple[str, str]] = {}
        for q_tuple in QUESTIONS_DATA:
            item_slug, text_en, text_he = q_tuple[0], q_tuple[1], q_tuple[2]
            text_ru = q_tuple[3] if len(q_tuple) > 3 else ""
            seed_map[text_en] = (text_he or "", text_ru or "")

        updated = 0
        for q in db.query(_Q3).all():
            if q.question_text_en not in seed_map:
                continue
            he, ru = seed_map[q.question_text_en]
            changed = False
            if ru and not q.question_text_ru:
                q.question_text_ru = ru
                changed = True
            if he and not q.question_text_he:
                q.question_text_he = he
                changed = True
            if changed:
                updated += 1

        if updated:
            db.commit()
            print(f"  ✓ patch_question_translations: filled translations for {updated} questions")
        else:
            print("  patch_question_translations: all translations already present")
    except Exception as e:
        db.rollback()
        print(f"patch_question_translations failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


def seed_missing_topics() -> None:
    """
    Insert any topic from TOPICS that does not yet exist in the database (matched by slug).
    Safe to run on an already-seeded DB — existing topics are untouched.
    Call this to add the 10 new topics without wiping existing data.
    """
    db = SessionLocal()
    try:
        existing_slugs = {t.slug for t in db.query(Topic).all()}
        added = 0
        for t in TOPICS:
            if t["slug"] not in existing_slugs:
                db.add(Topic(**t))
                added += 1
        db.commit()
        if added:
            print(f"  ✓ Added {added} missing topics")
        else:
            print("  All topics already present.")
    except Exception as e:
        db.rollback()
        print(f"seed_missing_topics failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


def seed_missing_policy_items() -> None:
    """
    Insert policy items, party positions, and questions for any policy-item slug
    that does not yet exist in the database. Safe to run on an already-seeded DB.
    """
    from backend.app.models.policy_item import PolicyItem as _PI2
    from backend.app.models.party_position import PartyPosition as _PP2
    from backend.app.models.question import Question as _Q2

    db = SessionLocal()
    try:
        # Build a slug → id map for existing policy items (matched by title)
        existing_titles = {pi.title for pi in db.query(_PI2).all()}

        added_items = 0
        added_positions = 0
        added_questions = 0

        pi_slug_to_id: dict[str, uuid.UUID] = {}

        for item in POLICY_ITEMS:
            if item["title"] in existing_titles:
                # Already in DB — need its id for positions/questions
                matched = db.query(_PI2).filter(_PI2.title == item["title"]).first()
                if matched:
                    pi_slug_to_id[item["slug"]] = matched.id
                continue

            topic_id = item["topic_id"]  # already a UUID from seed_data.py processing

            pi_id = uuid.uuid4()
            pi_slug_to_id[item["slug"]] = pi_id
            from backend.app.models.policy_item import PolicySourceType, ReviewStatus as RS
            db.add(_PI2(
                id=pi_id,
                title=item["title"],
                description=item.get("description"),
                topic_id=topic_id,
                directional_axis=item.get("directional_axis"),
                source_type=PolicySourceType(item["source_type"]),
                llm_confidence=0.85,
                human_review_status=RS.approved,
            ))
            added_items += 1

        db.flush()

        if added_items:
            print(f"  ✓ Added {added_items} missing policy items")
        else:
            print("  All policy items already present.")

        # Add missing party positions
        from backend.app.models.party_position import PartyPosition as _PP3
        existing_positions = {
            (str(pp.party_instance_id), str(pp.policy_item_id))
            for pp in db.query(_PP3).all()
        }

        for (party_id, item_slug), (pos_mean, uncertainty, strength, ev_type) in PARTY_POSITIONS_RAW.items():
            policy_item_id = pi_slug_to_id.get(item_slug)
            if not policy_item_id:
                continue
            key = (str(party_id), str(policy_item_id))
            if key in existing_positions:
                continue
            db.add(_PP3(
                party_instance_id=party_id,
                policy_item_id=policy_item_id,
                position_mean=pos_mean,
                position_uncertainty=uncertainty,
                evidence_strength=strength,
                evidence_type=ev_type,
                llm_explanation=f"Mock position inferred from {ev_type} evidence.",
            ))
            added_positions += 1

        db.flush()
        if added_positions:
            print(f"  ✓ Added {added_positions} missing party positions")

        # Add missing questions
        existing_questions_text = {q.question_text_en for q in db.query(_Q2).all()}
        from backend.app.models.question import AnswerScaleType as AST
        from backend.app.models.policy_item import ReviewStatus as RS2

        # Build lookup of existing questions by English text for translation updates
        existing_question_by_en: dict[str, _Q2] = {
            q.question_text_en: q for q in db.query(_Q2).all()
        }

        for q_tuple in QUESTIONS_DATA:
            item_slug, text_en, text_he = q_tuple[0], q_tuple[1], q_tuple[2]
            text_ru = q_tuple[3] if len(q_tuple) > 3 else None
            answer_polarity = float(q_tuple[4]) if len(q_tuple) > 4 else 1.0
            if text_en in existing_questions_text:
                # Question exists — patch missing translations if needed
                existing_q = existing_question_by_en.get(text_en)
                if existing_q:
                    changed = False
                    if text_ru and not existing_q.question_text_ru:
                        existing_q.question_text_ru = text_ru
                        changed = True
                    if text_he and not existing_q.question_text_he:
                        existing_q.question_text_he = text_he
                        changed = True
                    # Always update polarity (fixes existing incorrect data)
                    if hasattr(existing_q, "answer_polarity") and existing_q.answer_polarity != answer_polarity:
                        existing_q.answer_polarity = answer_polarity
                        changed = True
                    if changed:
                        added_questions += 1  # reuse counter to count patches
                continue
            policy_item_id = pi_slug_to_id.get(item_slug)
            if not policy_item_id:
                continue
            db.add(_Q2(
                policy_item_id=policy_item_id,
                question_text_en=text_en,
                question_text_he=text_he,
                question_text_ru=text_ru,
                answer_scale_type=AST.likert_5,
                neutrality_score=0.82,
                complexity_score=0.45,
                llm_prompt_version="mock-v1",
                answer_polarity=answer_polarity,
                human_review_status=RS2.approved,
            ))
            added_questions += 1

        db.flush()
        if added_questions:
            print(f"  ✓ Added {added_questions} missing questions")

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"seed_missing_policy_items failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


def patch_brand_names() -> None:
    """
    Update political_brands.names_json and color_hex from seed data.
    Safe to run on already-seeded DB — uses canonical_name to look up existing brands.
    """
    db = SessionLocal()
    try:
        updated = 0
        for b in POLITICAL_BRANDS:
            brand = db.query(PoliticalBrand).filter(
                PoliticalBrand.canonical_name == b["canonical_name"]
            ).first()
            if brand is None:
                # Insert missing brand
                db.add(PoliticalBrand(
                    id=b["id"],
                    canonical_name=b["canonical_name"],
                    names_json=b.get("names_json"),
                    description=b.get("description"),
                    color_hex=b.get("color_hex"),
                ))
                updated += 1
            else:
                changed = False
                if b.get("names_json") and brand.names_json != b["names_json"]:
                    brand.names_json = b["names_json"]
                    changed = True
                if b.get("color_hex") and brand.color_hex != b["color_hex"]:
                    brand.color_hex = b["color_hex"]
                    changed = True
                if changed:
                    updated += 1
        db.commit()
        if updated:
            print(f"  ✓ patch_brand_names: updated/inserted {updated} brands")
        else:
            print("  patch_brand_names: all brands up to date")
    except Exception as e:
        db.rollback()
        print(f"patch_brand_names failed: {e}", file=sys.stderr)
    finally:
        db.close()


def patch_party_colors_and_lr() -> None:
    """
    Update party_instances.left_right_score and ensure Raam (and any missing
    English-named party instances) are inserted with correct LR scores and colors.
    """
    db = SessionLocal()
    try:
        updated = 0
        brand_name_to_id: dict[str, uuid.UUID] = {
            b.canonical_name: b.id for b in db.query(PoliticalBrand).all()
        }

        for p in PARTY_INSTANCES:
            # Look up by UUID first (seed has deterministic UUIDs)
            existing = db.query(PartyInstance).filter(PartyInstance.id == p["id"]).first()
            if existing is None:
                # Also check by official_name to avoid duplicate
                existing_by_name = db.query(PartyInstance).filter(
                    PartyInstance.official_name == p["official_name"]
                ).first()
                if existing_by_name is None:
                    # Insert missing party instance
                    brand_id = p.get("political_brand_id") or brand_name_to_id.get(
                        next((b["canonical_name"] for b in POLITICAL_BRANDS
                              if b.get("id") == str(p.get("political_brand_id")) or
                              b.get("id") == p.get("political_brand_id")), None), None
                    )
                    if brand_id:
                        db.add(PartyInstance(
                            id=p["id"],
                            political_brand_id=brand_id if isinstance(brand_id, uuid.UUID)
                                else uuid.UUID(str(brand_id)),
                            official_name=p["official_name"],
                            election_cycle=p.get("election_cycle"),
                            knesset_number=p.get("knesset_number"),
                            start_date=p.get("start_date"),
                            end_date=p.get("end_date"),
                            status=PartyStatus(p["status"]),
                            left_right_score=p.get("left_right_score"),
                        ))
                        updated += 1
            else:
                # Update left_right_score if missing
                if existing.left_right_score is None and p.get("left_right_score") is not None:
                    existing.left_right_score = p["left_right_score"]
                    updated += 1

        db.commit()
        if updated:
            print(f"  ✓ patch_party_colors_and_lr: updated/inserted {updated} party instances")
        else:
            print("  patch_party_colors_and_lr: all party instances up to date")
    except Exception as e:
        db.rollback()
        print(f"patch_party_colors_and_lr failed: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
    finally:
        db.close()


def run_seed() -> None:
    db = SessionLocal()
    try:
        # Idempotency check
        if db.query(Topic).first():
            print("Database already seeded. Checking for updates...")
            db.close()
            patch_brand_names()
            patch_party_colors_and_lr()
            seed_missing_topics()
            seed_missing_policy_items()
            patch_question_translations()
            patch_question_polarity()
            return

        print("Seeding database...")

        # 1. Political Brands
        for b in POLITICAL_BRANDS:
            db.add(PoliticalBrand(
                id=b["id"],
                canonical_name=b["canonical_name"],
                names_json=b.get("names_json"),
                description=b.get("description"),
                color_hex=b.get("color_hex"),
            ))
        db.flush()
        print(f"  ✓ {len(POLITICAL_BRANDS)} political brands")

        # 2. Party Instances
        for p in PARTY_INSTANCES:
            pi = PartyInstance(
                id=p["id"],
                political_brand_id=p["political_brand_id"],
                official_name=p["official_name"],
                election_cycle=p.get("election_cycle"),
                knesset_number=p.get("knesset_number"),
                start_date=p.get("start_date"),
                end_date=p.get("end_date"),
                status=PartyStatus(p["status"]),
                left_right_score=p.get("left_right_score"),
            )
            db.add(pi)
        db.flush()
        print(f"  ✓ {len(PARTY_INSTANCES)} party instances")

        # 3. Lineage Edges
        for edge in LINEAGE_EDGES:
            db.add(
                PartyLineageEdge(
                    from_party_instance_id=edge["from_party_instance_id"],
                    to_party_instance_id=edge["to_party_instance_id"],
                    relation_type=LineageRelationType(edge["relation_type"]),
                    continuity_weight=edge["continuity_weight"],
                    llm_explanation=edge.get("llm_explanation"),
                    human_review_status=LineageReviewStatus(edge.get("human_review_status", "draft")),
                )
            )
        db.flush()
        print(f"  ✓ {len(LINEAGE_EDGES)} lineage edges")

        # 4. Topics
        topic_id_map: dict[str, uuid.UUID] = {}
        for t in TOPICS:
            db.add(Topic(**t))
            topic_id_map[t["slug"]] = t["id"]
        db.flush()
        print(f"  ✓ {len(TOPICS)} topics")

        # 5. Policy Items
        pi_slug_to_id: dict[str, uuid.UUID] = {}
        for item in POLICY_ITEMS:
            pi_id = uuid.uuid4()
            pi_slug_to_id[item["slug"]] = pi_id
            db.add(
                PolicyItem(
                    id=pi_id,
                    title=item["title"],
                    description=item.get("description"),
                    topic_id=item["topic_id"],
                    directional_axis=item.get("directional_axis"),
                    source_type=PolicySourceType(item["source_type"]),
                    llm_confidence=0.85,
                    human_review_status=ReviewStatus.approved,
                )
            )
        db.flush()
        print(f"  ✓ {len(POLICY_ITEMS)} policy items")

        # 6. Party Positions (5 parties × 20 items = 100 rows)
        position_count = 0
        for (party_id, item_slug), (pos_mean, uncertainty, strength, ev_type) in PARTY_POSITIONS_RAW.items():
            policy_item_id = pi_slug_to_id.get(item_slug)
            if not policy_item_id:
                continue
            db.add(
                PartyPosition(
                    party_instance_id=party_id,
                    policy_item_id=policy_item_id,
                    position_mean=pos_mean,
                    position_uncertainty=uncertainty,
                    evidence_strength=strength,
                    evidence_type=ev_type,
                    llm_explanation=f"Mock position inferred from {ev_type} evidence.",
                )
            )
            position_count += 1
        db.flush()
        print(f"  ✓ {position_count} party positions")

        # 7. Persons
        for p in PERSONS:
            db.add(Person(
                id=p["id"],
                name_he=p["name_he"],
                name_en=p["name_en"],
                birth_year=p.get("birth_year"),
            ))
        db.flush()
        print(f"  ✓ {len(PERSONS)} persons")

        # 8. Person Party Memberships
        for m in MEMBERSHIPS:
            db.add(PersonPartyMembership(
                person_id=m["person_id"],
                party_instance_id=m["party_instance_id"],
                role=MembershipRole(m["role"]),
                start_date=m.get("start_date"),
                end_date=m.get("end_date"),
                confidence=0.95,
            ))
        db.flush()
        print(f"  ✓ {len(MEMBERSHIPS)} memberships")

        # 9. Questions (40 total — 2 per policy item)
        q_count = 0
        for q_tuple in QUESTIONS_DATA:
            item_slug, text_en, text_he = q_tuple[0], q_tuple[1], q_tuple[2]
            text_ru = q_tuple[3] if len(q_tuple) > 3 else None
            answer_polarity = float(q_tuple[4]) if len(q_tuple) > 4 else 1.0
            policy_item_id = pi_slug_to_id.get(item_slug)
            if not policy_item_id:
                continue
            db.add(
                Question(
                    policy_item_id=policy_item_id,
                    question_text_en=text_en,
                    question_text_he=text_he,
                    question_text_ru=text_ru,
                    answer_scale_type=AnswerScaleType.likert_5,
                    neutrality_score=0.82,
                    complexity_score=0.45,
                    llm_prompt_version="mock-v1",
                    answer_polarity=answer_polarity,
                    human_review_status=ReviewStatus.approved,
                )
            )
            q_count += 1
        db.flush()
        print(f"  ✓ {q_count} questions")

        # ── Phase 14B: Simulation seed data ──────────────────────────────────

        # 10. Pollsters
        for po in POLLSTERS:
            db.add(Pollster(**po))
        db.flush()
        print(f"  ✓ {len(POLLSTERS)} pollsters")

        # 11. Polls + PollPartyResults
        # Build party_name → party_instance_id map
        party_name_to_id: dict[str, uuid.UUID] = {}
        for pi_row in PARTY_INSTANCES:
            party_name_to_id[pi_row["official_name"]] = pi_row["id"]

        for poll_data in POLLS:
            poll = Poll(
                id=poll_data["id"],
                pollster_id=poll_data["pollster_id"],
                field_end_date=poll_data["field_end_date"],
                sample_size=poll_data["sample_size"],
                quality_score=poll_data["quality_score"],
            )
            db.add(poll)
            db.flush()
            for party_name, share in poll_data["results"]:
                db.add(PollPartyResult(
                    poll_id=poll.id,
                    party_instance_id=party_name_to_id.get(party_name),
                    reported_name=party_name,
                    vote_share_mean=share,
                    seats_mean=round(share / (1 / 120), 1),  # rough estimate
                ))
        db.flush()
        print(f"  ✓ {len(POLLS)} polls with party results")

        # 12. Historical election
        hist = HistoricalElectionResult(
            id=HISTORICAL_ELECTION["id"],
            election_cycle=HISTORICAL_ELECTION["election_cycle"],
            election_date=HISTORICAL_ELECTION["election_date"],
            turnout=HISTORICAL_ELECTION["turnout"],
            threshold_percent=HISTORICAL_ELECTION["threshold_percent"],
            total_valid_votes=HISTORICAL_ELECTION["total_valid_votes"],
        )
        db.add(hist)
        db.flush()
        for party_name, share, seats, passed in HISTORICAL_ELECTION["results"]:
            db.add(HistoricalPartyResult(
                historical_election_result_id=hist.id,
                party_instance_id=party_name_to_id.get(party_name),
                reported_name=party_name,
                vote_share=share,
                seats=seats,
                passed_threshold=passed,
            ))
        db.flush()
        print(f"  ✓ 1 historical election ({HISTORICAL_ELECTION['election_cycle']})")

        # 13. Coalition constraints
        for src_name, tgt_name, c_type, strength, explanation in COALITION_CONSTRAINTS_RAW:
            src_id = party_name_to_id.get(src_name)
            tgt_id = party_name_to_id.get(tgt_name)
            if not src_id or not tgt_id:
                continue
            db.add(CoalitionConstraint(
                source_party_instance_id=src_id,
                target_party_instance_id=tgt_id,
                constraint_type=c_type,
                strength=strength,
                llm_explanation=explanation,
                confidence=0.90,
                human_review_status="approved",
            ))
        db.flush()
        print(f"  ✓ {len(COALITION_CONSTRAINTS_RAW)} coalition constraints")

        db.commit()

        # Register mock volatility for volatility service
        for party_id, score in PARTY_VOLATILITY.items():
            register_mock_volatility(party_id, score)

        print("\nSeeding complete ✓")
        print(f"  Brands: {len(POLITICAL_BRANDS)}, Instances: {len(PARTY_INSTANCES)}, "
              f"Topics: {len(TOPICS)}, Policy Items: {len(POLICY_ITEMS)}, "
              f"Questions: {q_count}, Persons: {len(PERSONS)}, "
              f"Polls: {len(POLLS)}")

    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulation-only", action="store_true", help="Seed only simulation data")
    parser.add_argument("--simulation-reset", action="store_true", help="Reset + reseed simulation data (polls, constraints, historical)")
    parser.add_argument("--topics-only", action="store_true", help="Add missing topics (safe on existing DB)")
    parser.add_argument("--patch-colors", action="store_true", help="Add color_hex and left_right_score to existing DB (safe)")
    parser.add_argument("--patch-translations", action="store_true", help="Fill question_text_ru / question_text_he where empty (safe)")
    parser.add_argument("--patch-polarity", action="store_true", help="Fix answer_polarity for all questions (safe, fixes scoring bug)")
    args = parser.parse_args()
    if args.simulation_only:
        seed_simulation_only()
    elif args.simulation_reset:
        patch_party_colors_and_lr()
        patch_simulation_data()
    elif args.topics_only:
        seed_missing_topics()
    elif args.patch_colors:
        patch_party_colors_and_lr()
    elif args.patch_translations:
        patch_question_translations()
    elif args.patch_polarity:
        patch_question_polarity()
    else:
        run_seed()
        patch_party_colors_and_lr()
        patch_question_translations()
        patch_question_polarity()
        patch_simulation_data()

