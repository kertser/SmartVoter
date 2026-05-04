"""Unit tests for the scoring engine (AGENTS.MD Sections 8 and 12)."""
import uuid
import pytest

from backend.app.services.scoring.engine import (
    AnswerData,
    PositionData,
    compute_match_score,
    compute_confidence_score,
    compute_coverage_score,
    compute_answer_stability,
)


def make_answer(value: float, salience: float = 1.0) -> AnswerData:
    return AnswerData(policy_item_id=uuid.uuid4(), answer_value=value, salience=salience)


def make_position(item_id: uuid.UUID, mean: float, strength: float = 0.8) -> PositionData:
    return PositionData(
        policy_item_id=item_id,
        position_mean=mean,
        position_uncertainty=0.15,
        evidence_strength=strength,
        evidence_type="vote",
    )


class TestMatchScore:
    def test_perfect_agreement(self):
        """User and party are identical → score ≈ 1.0"""
        item_id = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item_id, answer_value=0.8, salience=1.0)]
        positions = [make_position(item_id, 0.8)]
        score = compute_match_score(answers, positions)
        assert abs(score - 1.0) < 0.001

    def test_complete_disagreement(self):
        """User at -1, party at +1 → score = 0.0"""
        item_id = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item_id, answer_value=-1.0, salience=1.0)]
        positions = [make_position(item_id, 1.0)]
        score = compute_match_score(answers, positions)
        assert abs(score - 0.0) < 0.001

    def test_salience_weighting(self):
        """High-salience issues should count more."""
        item_a = uuid.uuid4()
        item_b = uuid.uuid4()
        # Agree on high-salience item, disagree on low-salience item
        answers = [
            AnswerData(policy_item_id=item_a, answer_value=1.0, salience=2.0),
            AnswerData(policy_item_id=item_b, answer_value=-1.0, salience=0.5),
        ]
        positions = [
            make_position(item_a, 1.0, 0.9),  # agree
            make_position(item_b, 1.0, 0.9),  # disagree
        ]
        score = compute_match_score(answers, positions)
        # Should be above 0.5 because the agreement is high salience
        assert score > 0.5

    def test_no_matched_items_returns_zero(self):
        """If no policy items match, score = 0."""
        answers = [AnswerData(policy_item_id=uuid.uuid4(), answer_value=0.5, salience=1.0)]
        positions = [make_position(uuid.uuid4(), 0.5)]
        score = compute_match_score(answers, positions)
        assert score == 0.0

    def test_evidence_strength_matters(self):
        """Two identical answers; one with higher evidence strength should dominate."""
        item_a = uuid.uuid4()
        item_b = uuid.uuid4()
        answers = [
            AnswerData(policy_item_id=item_a, answer_value=1.0, salience=1.0),
            AnswerData(policy_item_id=item_b, answer_value=-1.0, salience=1.0),
        ]
        positions = [
            make_position(item_a, 1.0, strength=0.9),   # agree, high evidence
            make_position(item_b, 1.0, strength=0.1),   # disagree, low evidence
        ]
        score = compute_match_score(answers, positions)
        assert score > 0.5  # high-evidence agreement dominates


class TestCoverageScore:
    def test_full_coverage(self):
        item_id = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item_id, answer_value=0.0, salience=1.0)]
        positions = [make_position(item_id, 0.0)]
        assert compute_coverage_score(answers, positions) == 1.0

    def test_no_coverage(self):
        answers = [AnswerData(policy_item_id=uuid.uuid4(), answer_value=0.0, salience=1.0)]
        positions = [make_position(uuid.uuid4(), 0.0)]
        assert compute_coverage_score(answers, positions) == 0.0

    def test_empty_answers(self):
        positions = [make_position(uuid.uuid4(), 0.0)]
        assert compute_coverage_score([], positions) == 0.0


class TestConfidenceScore:
    def test_new_party_lower_confidence(self):
        """New party (low evidence_strength) should have lower confidence."""
        item_id = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item_id, answer_value=0.5, salience=1.0)]

        established_positions = [make_position(item_id, 0.5, strength=0.90)]
        new_party_positions = [make_position(item_id, 0.5, strength=0.28)]

        established_conf = compute_confidence_score(
            established_positions, answers, 0.1, 1.0, 1.0
        )
        new_party_conf = compute_confidence_score(
            new_party_positions, answers, 0.55, 0.8, 0.9
        )
        assert established_conf > new_party_conf

    def test_high_volatility_reduces_confidence(self):
        item_id = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item_id, answer_value=0.5, salience=1.0)]
        positions = [make_position(item_id, 0.5, strength=0.85)]
        low_vol = compute_confidence_score(positions, answers, 0.05, 1.0, 1.0)
        high_vol = compute_confidence_score(positions, answers, 0.80, 1.0, 1.0)
        assert low_vol > high_vol

    def test_confidence_in_range(self):
        item_id = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item_id, answer_value=0.0, salience=1.0)]
        positions = [make_position(item_id, 0.0, strength=0.85)]
        conf = compute_confidence_score(positions, answers, 0.1, 0.9, 0.95)
        assert 0.0 <= conf <= 1.0

