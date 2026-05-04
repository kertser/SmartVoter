"""Unit tests for adaptive questionnaire selector (AGENTS.MD Section 13)."""
import uuid
import pytest

from backend.app.services.questionnaire.selector import (
    select_next_question,
    should_offer_results,
    force_results,
    QuestionCandidate,
    PartyPositionSlim,
)


def make_candidate(topic: str = "judiciary", evidence: float = 0.8) -> QuestionCandidate:
    return QuestionCandidate(
        question_id=uuid.uuid4(),
        policy_item_id=uuid.uuid4(),
        topic_slug=topic,
        evidence_quality=evidence,
    )


class TestSelectNextQuestion:
    def test_returns_none_after_15_answers(self):
        candidates = [make_candidate() for _ in range(20)]
        answered_ids = [uuid.uuid4() for _ in range(15)]
        result = select_next_question(
            answered_ids=answered_ids,
            candidates=candidates,
            top_party_positions=[],
            answered_topic_counts={},
        )
        assert result is None

    def test_returns_none_when_all_answered(self):
        c = make_candidate()
        result = select_next_question(
            answered_ids=[c.question_id],
            candidates=[c],
            top_party_positions=[],
            answered_topic_counts={},
        )
        assert result is None

    def test_prefers_high_evidence_quality(self):
        low_ev = make_candidate(evidence=0.1)
        high_ev = make_candidate(evidence=0.9)
        result = select_next_question(
            answered_ids=[],
            candidates=[low_ev, high_ev],
            top_party_positions=[],
            answered_topic_counts={},
        )
        assert result is not None
        assert result.question_id == high_ev.question_id

    def test_diversity_penalty_applied(self):
        """After many questions on same topic, prefer a different topic."""
        same_topic_candidates = [make_candidate(topic="judiciary") for _ in range(3)]
        different_topic = make_candidate(topic="economy_taxes", evidence=0.5)
        # Already answered 3 judiciary questions
        answered_topic_counts = {"judiciary": 3}
        answered_ids = [c.question_id for c in same_topic_candidates[:2]]
        result = select_next_question(
            answered_ids=answered_ids,
            candidates=same_topic_candidates + [different_topic],
            top_party_positions=[],
            answered_topic_counts=answered_topic_counts,
        )
        # The unanswered same-topic has been counted 3x, so diversity_penalty = 1/4 = 0.25
        # different_topic has penalty = 1 / (1+0) = 1.0 — should win despite lower evidence
        assert result is not None
        assert result.topic_slug == "economy_taxes"

    def test_high_party_separation_preferred(self):
        """Questions where parties disagree more should be preferred."""
        item_agree = uuid.uuid4()
        item_disagree = uuid.uuid4()

        candidate_agree = QuestionCandidate(
            question_id=uuid.uuid4(),
            policy_item_id=item_agree,
            topic_slug="security",
            evidence_quality=0.8,
        )
        candidate_disagree = QuestionCandidate(
            question_id=uuid.uuid4(),
            policy_item_id=item_disagree,
            topic_slug="security",
            evidence_quality=0.8,
        )

        # Parties all agree on item_agree (low variance) but disagree on item_disagree (high variance)
        top_party_positions = [
            [PartyPositionSlim(policy_item_id=item_agree, position_mean=0.5),
             PartyPositionSlim(policy_item_id=item_disagree, position_mean=-0.8)],
            [PartyPositionSlim(policy_item_id=item_agree, position_mean=0.5),
             PartyPositionSlim(policy_item_id=item_disagree, position_mean=0.8)],
        ]

        result = select_next_question(
            answered_ids=[],
            candidates=[candidate_agree, candidate_disagree],
            top_party_positions=top_party_positions,
            answered_topic_counts={},
        )
        assert result is not None
        assert result.policy_item_id == item_disagree


class TestStopConditions:
    def test_offer_results_after_8_stable(self):
        assert should_offer_results(8, 0.85) is True

    def test_no_offer_when_unstable(self):
        assert should_offer_results(8, 0.70) is False

    def test_no_offer_before_8_questions(self):
        assert should_offer_results(7, 0.95) is False

    def test_force_results_at_15(self):
        assert force_results(15) is True
        assert force_results(14) is False

