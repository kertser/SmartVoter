"""
Seed runner: populates the database with mock data for Phase 1.
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
)


def run_seed() -> None:
    db = SessionLocal()
    try:
        # Idempotency check
        if db.query(Topic).first():
            print("Database already seeded. Skipping.")
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
        for item_slug, text_en, text_he in QUESTIONS_DATA:
            policy_item_id = pi_slug_to_id.get(item_slug)
            if not policy_item_id:
                continue
            db.add(
                Question(
                    policy_item_id=policy_item_id,
                    question_text_en=text_en,
                    question_text_he=text_he,
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

        db.commit()

        # Register mock volatility for volatility service
        for party_id, score in PARTY_VOLATILITY.items():
            register_mock_volatility(party_id, score)

        print("\nSeeding complete ✓")
        print(f"  Brands: {len(POLITICAL_BRANDS)}, Instances: {len(PARTY_INSTANCES)}, "
              f"Topics: {len(TOPICS)}, Policy Items: {len(POLICY_ITEMS)}, "
              f"Questions: {q_count}, Persons: {len(PERSONS)}")

    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()

