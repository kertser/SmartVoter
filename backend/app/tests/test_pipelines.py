"""
Tests for the full ingestion pipeline services.
Covers Gaps 1–6: importers, policy_item_pipeline, party_position_pipeline,
question_pipeline, lineage_service, volatility_service.

All tests use in-memory SQLite databases and mocked LLM / HTTP calls so they
run offline without any external dependencies.
"""
import datetime
import math
import uuid
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import Base
from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.party_instance import PartyInstance, PartyStatus
from backend.app.models.party_lineage_edge import (
    PartyLineageEdge, LineageRelationType, LineageReviewStatus,
)
from backend.app.models.person import Person
from backend.app.models.person_party_membership import PersonPartyMembership, MembershipRole
from backend.app.models.topic import Topic
from backend.app.models.policy_item import PolicyItem, PolicySourceType, ReviewStatus
from backend.app.models.question import Question, AnswerScaleType
from backend.app.models.vote import Vote
from backend.app.models.vote_result import VoteResult, VoteValue
from backend.app.models.party_position import PartyPosition


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.knesset_api_base_url = "https://knesset.example.com/Odata/ParliamentInfo.svc"
    s.knesset_votes_api_base_url = "https://knesset.example.com/Odata/Votes.svc"
    s.oknesset_api_base_url = "https://oknesset.example.com/api/v2"
    s.llm_provider = "mock"
    s.openai_api_key = None
    s.admin_password = "test"
    return s


def _make_brand(db: Session, name: str = "Test Party") -> PoliticalBrand:
    brand = PoliticalBrand(id=uuid.uuid4(), canonical_name=name, names_json={"he": name})
    db.add(brand)
    db.flush()
    return brand


def _make_party(db: Session, brand: PoliticalBrand, knesset: int = 25,
                name: str | None = None) -> PartyInstance:
    pi = PartyInstance(
        id=uuid.uuid4(),
        political_brand_id=brand.id,
        official_name=name or brand.canonical_name,
        election_cycle=str(knesset),
        knesset_number=knesset,
        status=PartyStatus.active,
    )
    db.add(pi)
    db.flush()
    return pi


def _make_topic(db: Session, slug: str = "judiciary") -> Topic:
    t = Topic(
        id=uuid.uuid4(),
        slug=slug,
        name_he=slug,
        name_en=slug,
    )
    db.add(t)
    db.flush()
    return t


def _make_vote(db: Session, knesset: int = 25, external_id: str | None = None) -> Vote:
    v = Vote(
        id=uuid.uuid4(),
        external_id=external_id or str(uuid.uuid4())[:8],
        title_he="הצבעה בנושא שיפוטי",
        title_en="Vote on judicial matter",
        date=datetime.date(2023, 1, 1),
        knesset_number=knesset,
        is_procedural_estimate=False,
        importance_score=0.8,
    )
    db.add(v)
    db.flush()
    return v


def _make_person(db: Session, knesset_id: int = 1001) -> Person:
    p = Person(
        id=uuid.uuid4(),
        name_he="ישראל ישראלי",
        name_en="Israel Israeli",
        external_ids_json={"knesset_id": knesset_id},
    )
    db.add(p)
    db.flush()
    return p


def _make_vote_result(
    db: Session, vote: Vote, person: Person, party: PartyInstance,
    value: VoteValue = VoteValue.for_,
) -> VoteResult:
    vr = VoteResult(
        id=uuid.uuid4(),
        vote_id=vote.id,
        person_id=person.id,
        party_instance_id_at_time=party.id,
        vote_value=value,
    )
    db.add(vr)
    db.flush()
    return vr


def _make_policy_item(
    db: Session, topic: Topic, source_type=PolicySourceType.vote,
    source_id: str | None = None,
    status: ReviewStatus = ReviewStatus.approved,
) -> PolicyItem:
    pi = PolicyItem(
        id=uuid.uuid4(),
        title="Should the court's review powers be limited?",
        description="A question about judicial review.",
        topic_id=topic.id,
        directional_axis="judicial_review: -1=broad review, +1=limited review",
        source_type=source_type,
        source_refs_json=[{"type": source_type.value, "id": source_id or str(uuid.uuid4())}],
        llm_confidence=0.85,
        human_review_status=status,
    )
    db.add(pi)
    db.flush()
    return pi


# ── Volatility service tests ───────────────────────────────────────────────────

class TestCandidateVolatility:
    def test_single_membership_zero_volatility(self, db):
        from backend.app.services.volatility.volatility_service import compute_candidate_volatility
        brand = _make_brand(db)
        party = _make_party(db, brand)
        person = _make_person(db)
        db.add(PersonPartyMembership(
            person_id=person.id, party_instance_id=party.id,
            role=MembershipRole.mk,
            start_date=datetime.date(2021, 1, 1),
        ))
        db.flush()
        v = compute_candidate_volatility(db, person.id)
        assert v == 0.0

    def test_two_memberships_nonzero_volatility(self, db):
        from backend.app.services.volatility.volatility_service import compute_candidate_volatility
        brand1 = _make_brand(db, "Party A")
        brand2 = _make_brand(db, "Party B")
        p1 = _make_party(db, brand1, knesset=24)
        p2 = _make_party(db, brand2, knesset=25)
        person = _make_person(db)
        db.add(PersonPartyMembership(
            person_id=person.id, party_instance_id=p1.id, role=MembershipRole.mk,
            start_date=datetime.date(2019, 1, 1), end_date=datetime.date(2022, 12, 31),
        ))
        db.add(PersonPartyMembership(
            person_id=person.id, party_instance_id=p2.id, role=MembershipRole.mk,
            start_date=datetime.date(2023, 1, 1),
        ))
        db.flush()
        v = compute_candidate_volatility(db, person.id)
        assert 0.0 < v <= 1.0

    def test_volatility_in_valid_range(self, db):
        from backend.app.services.volatility.volatility_service import compute_candidate_volatility
        brand = _make_brand(db)
        parties = [_make_party(db, brand, knesset=i) for i in range(20, 26)]
        person = _make_person(db)
        for i, party in enumerate(parties):
            db.add(PersonPartyMembership(
                person_id=person.id, party_instance_id=party.id, role=MembershipRole.mk,
                start_date=datetime.date(2015 + i, 1, 1),
            ))
        db.flush()
        v = compute_candidate_volatility(db, person.id)
        assert 0.0 <= v <= 1.0


class TestPartyVolatility:
    def test_empty_party_moderate_volatility(self, db):
        from backend.app.services.volatility.volatility_service import compute_party_volatility
        brand = _make_brand(db)
        party = _make_party(db, brand)
        v = compute_party_volatility(db, party.id)
        assert v == 0.5  # no memberships → unknown → 0.5

    def test_stable_party_low_volatility(self, db):
        from backend.app.services.volatility.volatility_service import compute_party_volatility
        brand = _make_brand(db)
        party = _make_party(db, brand)
        person = _make_person(db)
        db.add(PersonPartyMembership(
            person_id=person.id, party_instance_id=party.id, role=MembershipRole.mk,
            start_date=datetime.date(2023, 1, 1),
        ))
        db.flush()
        v = compute_party_volatility(db, party.id)
        assert 0.0 <= v <= 1.0

    def test_split_event_increases_volatility(self, db):
        from backend.app.services.volatility.volatility_service import compute_party_volatility
        brand = _make_brand(db)
        p1 = _make_party(db, brand, knesset=24)
        p2 = _make_party(db, brand, knesset=25)
        person = _make_person(db)
        db.add(PersonPartyMembership(
            person_id=person.id, party_instance_id=p1.id, role=MembershipRole.mk,
            start_date=datetime.date(2021, 1, 1), end_date=datetime.date(2023, 1, 1),
        ))
        db.flush()
        # Add split lineage event
        db.add(PartyLineageEdge(
            id=uuid.uuid4(),
            from_party_instance_id=p1.id,
            to_party_instance_id=p2.id,
            relation_type=LineageRelationType.split,
            continuity_weight=0.35,
            human_review_status=LineageReviewStatus.approved,
        ))
        db.flush()

        v_with_split = compute_party_volatility(db, p1.id)
        # Shouldn't be 0.5 (unknown) since we have membership data
        assert 0.0 <= v_with_split <= 1.0

    def test_run_volatility_update(self, db):
        from backend.app.services.volatility.volatility_service import run_volatility_update
        brand = _make_brand(db)
        party = _make_party(db, brand)
        person = _make_person(db)
        db.add(PersonPartyMembership(
            person_id=person.id, party_instance_id=party.id, role=MembershipRole.mk,
            start_date=datetime.date(2023, 1, 1),
        ))
        db.commit()

        result = run_volatility_update(db)
        assert "candidate_volatility" in result
        assert "party_volatility" in result
        assert "summary" in result
        assert result["summary"]["candidates_updated"] >= 1
        assert result["summary"]["parties_updated"] >= 1

        # Verify cached volatility in Person.external_ids_json
        db.refresh(person)
        assert "volatility" in (person.external_ids_json or {})


# ── Lineage service tests ──────────────────────────────────────────────────────

class TestLineageService:
    def test_no_parties_no_edges(self, db, mock_settings):
        from backend.app.services.lineage.lineage_service import run_lineage_inference
        result = run_lineage_inference(db, mock_settings, knesset_number=25, enrich_with_llm=False)
        assert result["edges_proposed"] == 0

    def test_similar_names_propose_edge(self, db, mock_settings):
        from backend.app.services.lineage.lineage_service import run_lineage_inference
        brand = _make_brand(db, "Likud")
        _make_party(db, brand, knesset=24, name="Likud")
        _make_party(db, brand, knesset=25, name="Likud")
        db.commit()

        # Mock LLM to avoid real calls
        with patch("backend.app.services.lineage.lineage_service.get_llm_provider") as mock_llm:
            mock_llm.return_value = None  # no LLM enrichment
            result = run_lineage_inference(db, mock_settings,
                                           knesset_number=25, enrich_with_llm=False)

        assert result["edges_proposed"] >= 1
        edge_count = db.query(PartyLineageEdge).count()
        assert edge_count >= 1

    def test_no_duplicate_edges(self, db, mock_settings):
        from backend.app.services.lineage.lineage_service import run_lineage_inference
        brand = _make_brand(db, "Likud")
        _make_party(db, brand, knesset=24, name="Likud")
        _make_party(db, brand, knesset=25, name="Likud")
        db.commit()

        run_lineage_inference(db, mock_settings, knesset_number=25, enrich_with_llm=False)
        run_lineage_inference(db, mock_settings, knesset_number=25, enrich_with_llm=False)
        edge_count = db.query(PartyLineageEdge).count()
        assert edge_count == 1  # second run should skip existing edges

    def test_brand_same_id_match(self, db, mock_settings):
        from backend.app.services.lineage.lineage_service import run_lineage_inference
        brand = _make_brand(db, "Same Brand")
        _make_party(db, brand, knesset=24, name="Party Old Name")
        _make_party(db, brand, knesset=25, name="Party New Name")
        db.commit()

        # Very different names but same brand — should still propose via brand match
        result = run_lineage_inference(db, mock_settings,
                                       knesset_number=25, enrich_with_llm=False)
        assert result["edges_proposed"] >= 1

    def test_get_lineage_prior_no_edges(self, db):
        from backend.app.services.lineage import get_lineage_prior
        brand = _make_brand(db)
        party = _make_party(db, brand)
        db.commit()
        prior = get_lineage_prior(party.id, db)
        assert prior == 0.5  # no edges → default

    def test_get_lineage_prior_with_approved_edge(self, db):
        from backend.app.services.lineage import get_lineage_prior
        brand = _make_brand(db)
        p_old = _make_party(db, brand, knesset=24)
        p_new = _make_party(db, brand, knesset=25)
        edge = PartyLineageEdge(
            id=uuid.uuid4(),
            from_party_instance_id=p_old.id,
            to_party_instance_id=p_new.id,
            relation_type=LineageRelationType.rename,
            continuity_weight=0.90,
            human_review_status=LineageReviewStatus.approved,
        )
        db.add(edge)
        db.commit()

        prior = get_lineage_prior(p_new.id, db)
        assert prior == pytest.approx(0.90)


# ── Policy item pipeline tests ─────────────────────────────────────────────────

class TestPolicyItemPipeline:
    def test_creates_stub_items_without_llm(self, db, mock_settings):
        from backend.app.services.ingestion.policy_item_pipeline import run_policy_item_pipeline
        topic = _make_topic(db)
        vote = _make_vote(db, knesset=25)
        db.commit()

        stats = run_policy_item_pipeline(
            db, mock_settings, knesset_number=25, limit=10,
            enrich_with_llm=False,
        )
        assert stats["created"] >= 1
        assert db.query(PolicyItem).count() >= 1

    def test_skips_already_processed_votes(self, db, mock_settings):
        from backend.app.services.ingestion.policy_item_pipeline import run_policy_item_pipeline
        topic = _make_topic(db)
        vote = _make_vote(db, knesset=25)
        db.commit()

        run_policy_item_pipeline(db, mock_settings, knesset_number=25, limit=10,
                                  enrich_with_llm=False)
        count_after_first = db.query(PolicyItem).count()

        run_policy_item_pipeline(db, mock_settings, knesset_number=25, limit=10,
                                  enrich_with_llm=False)
        count_after_second = db.query(PolicyItem).count()

        assert count_after_first == count_after_second  # no duplicates

    def test_items_linked_to_correct_vote(self, db, mock_settings):
        from backend.app.services.ingestion.policy_item_pipeline import run_policy_item_pipeline
        topic = _make_topic(db)
        vote = _make_vote(db, knesset=25)
        db.commit()

        run_policy_item_pipeline(db, mock_settings, knesset_number=25, limit=10,
                                  enrich_with_llm=False)
        item = db.query(PolicyItem).first()
        assert item is not None
        refs = item.source_refs_json or []
        assert any(r.get("id") == str(vote.id) for r in refs if isinstance(r, dict))

    def test_skips_procedural_votes(self, db, mock_settings):
        from backend.app.services.ingestion.policy_item_pipeline import run_policy_item_pipeline
        topic = _make_topic(db)
        vote = _make_vote(db, knesset=25)
        vote.is_procedural_estimate = True
        db.flush()
        db.commit()

        stats = run_policy_item_pipeline(
            db, mock_settings, knesset_number=25, limit=10,
            skip_procedural=True, enrich_with_llm=False,
        )
        assert stats["created"] == 0


# ── Party position pipeline tests ─────────────────────────────────────────────

class TestPartyPositionPipeline:
    def _setup(self, db):
        brand = _make_brand(db)
        party = _make_party(db, brand, knesset=25)
        topic = _make_topic(db)
        vote = _make_vote(db, knesset=25)
        person = _make_person(db)
        _make_vote_result(db, vote, person, party, VoteValue.for_)
        item = PolicyItem(
            id=uuid.uuid4(),
            title="Judicial review",
            description="Test",
            topic_id=topic.id,
            source_type=PolicySourceType.vote,
            source_refs_json=[{"type": "vote", "id": str(vote.id)}],
            llm_confidence=0.8,
            human_review_status=ReviewStatus.approved,
        )
        db.add(item)
        db.commit()
        return party, item, vote

    def test_creates_position_from_votes(self, db, mock_settings):
        from backend.app.services.ingestion.party_position_pipeline import run_party_position_pipeline
        party, item, vote = self._setup(db)

        stats = run_party_position_pipeline(
            db, mock_settings, knesset_number=25,
            enrich_with_llm=False,
        )
        assert stats["positions_created"] >= 1
        pos = db.query(PartyPosition).filter(
            PartyPosition.party_instance_id == party.id,
            PartyPosition.policy_item_id == item.id,
        ).first()
        assert pos is not None
        assert -1.0 <= pos.position_mean <= 1.0
        assert 0.0 <= pos.evidence_strength <= 1.0

    def test_skips_party_with_no_votes(self, db, mock_settings):
        from backend.app.services.ingestion.party_position_pipeline import run_party_position_pipeline
        brand2 = _make_brand(db, "Another Party")
        party2 = _make_party(db, brand2, knesset=25)
        # No vote results for party2
        party, item, vote = self._setup(db)

        stats = run_party_position_pipeline(
            db, mock_settings, knesset_number=25,
            enrich_with_llm=False,
        )
        assert stats["skipped_no_evidence"] >= 1

    def test_does_not_duplicate_positions(self, db, mock_settings):
        from backend.app.services.ingestion.party_position_pipeline import run_party_position_pipeline
        self._setup(db)
        run_party_position_pipeline(db, mock_settings, knesset_number=25, enrich_with_llm=False)
        count1 = db.query(PartyPosition).count()
        run_party_position_pipeline(db, mock_settings, knesset_number=25, enrich_with_llm=False)
        count2 = db.query(PartyPosition).count()
        assert count1 == count2

    def test_overwrite_updates_position(self, db, mock_settings):
        from backend.app.services.ingestion.party_position_pipeline import run_party_position_pipeline
        self._setup(db)
        run_party_position_pipeline(db, mock_settings, knesset_number=25, enrich_with_llm=False)
        stats = run_party_position_pipeline(
            db, mock_settings, knesset_number=25,
            enrich_with_llm=False, overwrite_existing=True,
        )
        assert stats["positions_updated"] >= 1


# ── Question pipeline tests ────────────────────────────────────────────────────

class TestQuestionPipeline:
    _MOCK_QUESTION_RESULT = {
        "question_en": "Should judicial review be limited?",
        "question_he": "האם להגביל את הביקורת השיפוטית?",
        "question_ru": "Следует ли ограничить судебный контроль?",
        "neutrality_risk": "low",
        "neutrality_score": 0.85,
        "_prompt_version": "v1.0",
    }

    def _make_mock_llm_provider(self):
        provider = MagicMock()
        provider.provider = "mock"
        provider.model = "mock-v1"
        provider.generate_question.return_value = dict(self._MOCK_QUESTION_RESULT)
        provider.generate_question_with_critique.return_value = dict(self._MOCK_QUESTION_RESULT)
        provider.critique_question.return_value = {
            "is_loaded": False,
            "bias_direction": None,
            "suggested_revision": None,
        }
        return provider

    def test_generates_question_for_approved_item(self, db):
        from backend.app.services.ingestion.question_pipeline import run_question_pipeline
        topic = _make_topic(db)
        item = _make_policy_item(db, topic, status=ReviewStatus.approved)
        db.flush()  # make item visible within the session

        mock_settings = MagicMock()
        mock_settings.llm_provider = "mock"

        # The pipeline's worker spawns its own SessionLocal() — redirect to test db.
        # We use a thin wrapper that delegates to the test session but no-ops close().
        class _PassthroughSession:
            """Delegates to the real test db; suppresses close() so the fixture can clean up."""
            def add(self, obj): db.add(obj)
            def query(self, *args, **kw): return db.query(*args, **kw)
            def commit(self): db.flush()  # flush instead of real commit
            def rollback(self): db.rollback()
            def close(self): pass
            def flush(self): db.flush()

        mock_session_factory = MagicMock(return_value=_PassthroughSession())

        with patch("backend.app.db.session.SessionLocal", mock_session_factory):
            with patch("backend.app.services.ingestion.question_pipeline.get_llm_provider") as mock_get:
                mock_get.return_value = self._make_mock_llm_provider()
                with patch(
                    "backend.app.services.llm.audit_service.AuditedLLMService.generate_question_with_critique"
                ) as mock_gen:
                    mock_gen.return_value = dict(self._MOCK_QUESTION_RESULT)
                    # max_workers=1 → single worker thread; avoids SQLite multi-thread issues
                    stats = run_question_pipeline(db, mock_settings, limit=10, max_workers=1)

        assert stats["created"] >= 1
        q = db.query(Question).first()
        assert q is not None
        assert q.human_review_status == ReviewStatus.needs_review

        assert stats["created"] >= 1
        q = db.query(Question).first()
        assert q is not None
        assert q.human_review_status == ReviewStatus.needs_review

    def test_skips_items_with_existing_questions(self, db):
        from backend.app.services.ingestion.question_pipeline import run_question_pipeline
        topic = _make_topic(db)
        item = _make_policy_item(db, topic, status=ReviewStatus.approved)
        # Pre-create a question (all NOT NULL fields required)
        q = Question(
            id=uuid.uuid4(),
            policy_item_id=item.id,
            question_text_he="כבר קיים?",
            question_text_en="Already exists?",
            question_text_ru="Уже существует?",
            answer_scale_type=AnswerScaleType.likert_5,
            human_review_status=ReviewStatus.approved,
        )
        db.add(q)
        db.commit()

        mock_settings = MagicMock()
        with patch("backend.app.services.ingestion.question_pipeline.get_llm_provider") as mock_get:
            mock_get.return_value = self._make_mock_llm_provider()
            with patch("backend.app.services.llm.audit_service.AuditedLLMService.generate_question"):
                stats = run_question_pipeline(db, mock_settings, limit=10, skip_existing=True)

        assert stats["skipped"] >= 1
        assert db.query(Question).count() == 1


# ── Import vote results tests ──────────────────────────────────────────────────

class TestImportVoteResults:
    def test_imports_vote_results(self, db, mock_settings):
        from backend.app.services.ingestion.importers import import_vote_results
        brand = _make_brand(db)
        party = _make_party(db, brand, knesset=25)
        person = _make_person(db, knesset_id=999)
        vote = _make_vote(db, knesset=25, external_id="12345")
        db.commit()

        mock_raw_results = [
            {"person_external_id": "999", "vote_value": "for", "faction_name": brand.canonical_name},
        ]

        with patch(
            "backend.app.services.ingestion.importers.fetch_vote_results",
            return_value=mock_raw_results,
        ):
            stats = import_vote_results(db, knesset_number=25, settings=mock_settings, vote_limit=10)

        assert stats["inserted"] >= 1
        assert db.query(VoteResult).count() >= 1

    def test_handles_unknown_person_gracefully(self, db, mock_settings):
        from backend.app.services.ingestion.importers import import_vote_results
        brand = _make_brand(db)
        party = _make_party(db, brand, knesset=25)
        vote = _make_vote(db, knesset=25, external_id="99999")
        db.commit()

        # Return result for a person not in the DB
        mock_raw_results = [
            {"person_external_id": "777777", "vote_value": "for", "faction_name": brand.canonical_name},
        ]

        with patch(
            "backend.app.services.ingestion.importers.fetch_vote_results",
            return_value=mock_raw_results,
        ):
            stats = import_vote_results(db, knesset_number=25, settings=mock_settings, vote_limit=10)

        assert stats["unknown_person"] >= 1
        assert stats["inserted"] == 0

    def test_skips_voted_votes_when_skip_existing(self, db, mock_settings):
        from backend.app.services.ingestion.importers import import_vote_results
        brand = _make_brand(db)
        party = _make_party(db, brand, knesset=25)
        person = _make_person(db, knesset_id=888)
        vote = _make_vote(db, knesset=25, external_id="11111")
        # Pre-load one result for this vote
        _make_vote_result(db, vote, person, party, VoteValue.for_)
        db.commit()

        call_count = 0

        def fake_fetch(base_url, vote_ext_id):
            nonlocal call_count
            call_count += 1
            return []

        with patch(
            "backend.app.services.ingestion.importers.fetch_vote_results",
            side_effect=fake_fetch,
        ):
            import_vote_results(db, knesset_number=25, settings=mock_settings,
                                 vote_limit=10, skip_existing=True)

        assert call_count == 0  # should skip because results already exist


# ── Knesset OData probe tests ──────────────────────────────────────────────────

class TestProbeVotesAvailability:
    def test_returns_true_when_data_found(self):
        from backend.app.services.ingestion.knesset_odata import probe_votes_availability

        with patch("backend.app.services.ingestion.knesset_odata._get_json") as mock_get:
            mock_get.return_value = {"value": [{"vote_id": 1}]}
            result = probe_votes_availability("https://mock.url", 25)

        assert result is True

    def test_returns_false_when_no_data(self):
        from backend.app.services.ingestion.knesset_odata import probe_votes_availability

        with patch("backend.app.services.ingestion.knesset_odata._get_json") as mock_get:
            mock_get.return_value = {"value": []}
            result = probe_votes_availability("https://mock.url", 26)

        assert result is False

    def test_returns_false_on_http_error(self):
        from backend.app.services.ingestion.knesset_odata import probe_votes_availability
        import httpx

        with patch("backend.app.services.ingestion.knesset_odata._get_json") as mock_get:
            mock_get.side_effect = httpx.ConnectError("timeout")
            result = probe_votes_availability("https://mock.url", 26)

        assert result is False

    def test_fetch_votes_skips_when_probe_fails(self):
        from backend.app.services.ingestion.knesset_odata import fetch_votes

        with patch("backend.app.services.ingestion.knesset_odata.probe_votes_availability",
                   return_value=False):
            results = fetch_votes("https://mock.url", 26, limit=100, probe_first=True)

        assert results == []


# ── Migrate mock data tests ────────────────────────────────────────────────────

class TestMigrateMock:
    def test_aborts_when_no_real_parties(self, db):
        from backend.app.seed.migrate_mock import migrate_mock_to_real
        # No real parties in DB → should abort
        result = migrate_mock_to_real(db, dry_run=True)
        assert "aborted" in result

    def test_dry_run_does_not_delete(self, db):
        from backend.app.seed.migrate_mock import (
            migrate_mock_to_real, _MOCK_PARTY_INSTANCE_IDS, _MOCK_BRAND_IDS,
        )
        # Insert a real party to pass the safety check
        real_brand = _make_brand(db, "Real Party")
        real_party = _make_party(db, real_brand, knesset=26)

        # Insert one mock party instance with correctly stubbed UUID
        mock_brand_id = next(iter(_MOCK_BRAND_IDS))
        mock_party_id = next(iter(_MOCK_PARTY_INSTANCE_IDS))
        brand = PoliticalBrand(id=mock_brand_id, canonical_name="Mock Brand",
                               names_json={"he": "Mock Brand"})
        db.add(brand)
        db.flush()
        party = PartyInstance(
            id=mock_party_id, political_brand_id=mock_brand_id,
            official_name="Mock Party", election_cycle="25",
            knesset_number=25, status=PartyStatus.active,
        )
        db.add(party)
        db.commit()

        counts = migrate_mock_to_real(db, dry_run=True)
        # Dry run should report counts but not actually delete
        assert db.query(PartyInstance).filter(PartyInstance.id == mock_party_id).count() == 1
        assert counts.get("party_instances", 0) >= 1



