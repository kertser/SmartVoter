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


def run_seed() -> None:
    db = SessionLocal()
    try:
        # Idempotency check
        if db.query(Topic).first():
            print("Database already seeded. Checking for missing topics...")
            db.close()
            seed_missing_topics()
            return

        print("Seeding database...")

        # 1. Political Brands
        for b in POLITICAL_BRANDS:
            db.add(PoliticalBrand(**b))
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
    parser.add_argument("--topics-only", action="store_true", help="Add missing topics (safe on existing DB)")
    args = parser.parse_args()
    if args.simulation_only:
        seed_simulation_only()
    elif args.topics_only:
        seed_missing_topics()
    else:
        run_seed()
        seed_simulation_only()

