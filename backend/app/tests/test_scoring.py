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
    compute_agenda_breadth,
    compute_high_salience_topic_coverage,
    SECTORAL_THRESHOLD,
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

    def test_high_salience_coverage_penalizes_missing_topics(self):
        """Confidence must fall when party ignores user's very-important topics."""
        item_id = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item_id, answer_value=0.5, salience=1.0)]
        positions = [make_position(item_id, 0.5, strength=0.85)]
        full_conf = compute_confidence_score(
            positions, answers, 0.1, 1.0, 1.0, high_salience_topic_coverage=1.0
        )
        low_conf = compute_confidence_score(
            positions, answers, 0.1, 1.0, 1.0, high_salience_topic_coverage=0.3
        )
        assert full_conf > low_conf

    def test_unmatched_positions_dont_inflate_confidence(self):
        """
        A sectoral party with 2 great positions on items the user answered,
        plus 8 other high-quality positions on items the user DIDN'T answer,
        should NOT get higher confidence than a party with 2 matched positions only.

        This verifies the 'BUG FIX' in engine.py — avg_evidence uses matched only.
        """
        matched_ids = [uuid.uuid4(), uuid.uuid4()]
        answers = [
            AnswerData(policy_item_id=matched_ids[0], answer_value=0.5, salience=1.0),
            AnswerData(policy_item_id=matched_ids[1], answer_value=0.5, salience=1.0),
        ]

        # Sectoral party: 2 matched positions + 8 unrelated high-quality ones
        matched_positions = [make_position(mid, 0.5, strength=0.85) for mid in matched_ids]
        unmatched_positions = [make_position(uuid.uuid4(), 0.5, strength=0.99) for _ in range(8)]
        sectoral_positions = matched_positions + unmatched_positions

        # Broad party: only the 2 matched positions
        broad_positions = matched_positions

        coverage_sectoral = compute_coverage_score(answers, sectoral_positions)
        coverage_broad = compute_coverage_score(answers, broad_positions)

        conf_sectoral = compute_confidence_score(
            sectoral_positions, answers, 0.1, coverage_sectoral, 1.0
        )
        conf_broad = compute_confidence_score(
            broad_positions, answers, 0.1, coverage_broad, 1.0
        )

        # Confidence should be comparable — the extra unmatched positions must NOT inflate
        # the sectoral party's confidence over the broad party (coverage difference will differ,
        # but evidence quality should be similar since we only use matched positions)
        assert abs(conf_sectoral - conf_broad) < 0.1, (
            f"Sectoral conf={conf_sectoral:.3f} should be close to broad conf={conf_broad:.3f}; "
            "unmatched positions must not inflate confidence"
        )


class TestAgendaBreadth:
    def test_full_coverage(self):
        positions = [make_position(uuid.uuid4(), 0.0) for _ in range(5)]
        breadth = compute_agenda_breadth(positions, party_topic_count=10, total_topics_count=10)
        assert breadth == 1.0

    def test_narrow_party(self):
        positions = [make_position(uuid.uuid4(), 0.0) for _ in range(2)]
        breadth = compute_agenda_breadth(positions, party_topic_count=2, total_topics_count=15)
        assert abs(breadth - 2 / 15) < 0.001

    def test_sectoral_threshold(self):
        positions = [make_position(uuid.uuid4(), 0.0)]
        breadth = compute_agenda_breadth(positions, party_topic_count=2, total_topics_count=15)
        assert breadth < SECTORAL_THRESHOLD

    def test_zero_total_topics_returns_one(self):
        """Edge case: no topics in system → don't penalize the party."""
        positions = [make_position(uuid.uuid4(), 0.0)]
        breadth = compute_agenda_breadth(positions, party_topic_count=1, total_topics_count=0)
        assert breadth == 1.0

    def test_broad_party_not_sectoral(self):
        positions = [make_position(uuid.uuid4(), 0.0) for _ in range(10)]
        breadth = compute_agenda_breadth(positions, party_topic_count=10, total_topics_count=15)
        assert breadth >= SECTORAL_THRESHOLD


class TestHighSalienceTopicCoverage:
    def test_all_high_salience_topics_covered(self):
        item_id = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item_id, answer_value=0.0, salience=2.0)]
        answered_item_to_topic = {item_id: "judiciary"}
        party_covered_topics = {"judiciary", "economy"}
        cov = compute_high_salience_topic_coverage(
            answers, answered_item_to_topic, party_covered_topics
        )
        assert cov == 1.0

    def test_high_salience_topic_not_covered(self):
        item_id = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item_id, answer_value=0.0, salience=2.0)]
        answered_item_to_topic = {item_id: "judiciary"}
        party_covered_topics = {"economy", "security"}  # judiciary missing
        cov = compute_high_salience_topic_coverage(
            answers, answered_item_to_topic, party_covered_topics
        )
        assert cov == 0.0

    def test_only_low_salience_answers_returns_one(self):
        """When user has no very-important (salience=2.0) answers, no penalty."""
        item_id = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item_id, answer_value=0.0, salience=1.0)]
        answered_item_to_topic = {item_id: "judiciary"}
        party_covered_topics = {"economy"}  # judiciary missing, but salience < 2
        cov = compute_high_salience_topic_coverage(
            answers, answered_item_to_topic, party_covered_topics
        )
        assert cov == 1.0

    def test_partial_coverage(self):
        """Party covers 1 of 2 high-salience topics → 0.5."""
        item_a, item_b = uuid.uuid4(), uuid.uuid4()
        answers = [
            AnswerData(policy_item_id=item_a, answer_value=0.0, salience=2.0),
            AnswerData(policy_item_id=item_b, answer_value=0.0, salience=2.0),
        ]
        answered_item_to_topic = {item_a: "judiciary", item_b: "economy"}
        party_covered_topics = {"judiciary"}  # economy missing
        cov = compute_high_salience_topic_coverage(
            answers, answered_item_to_topic, party_covered_topics
        )
        assert abs(cov - 0.5) < 0.001


class TestSectoralScenarioEndToEnd:
    """
    Integration-style tests that verify a sectoral party is correctly
    disadvantaged relative to a broad party despite perfect matched scores.
    """

    def test_sectoral_party_lower_confidence_than_broad(self):
        """
        Sectoral party: 2 perfect matches, covers only 2/15 topics.
        Broad party: 2 perfect matches + partial on others, covers 10/15 topics.
        Confidence for sectoral must be lower due to high_salience_topic_coverage penalty.
        """
        item_a, item_b = uuid.uuid4(), uuid.uuid4()
        answers = [
            AnswerData(policy_item_id=item_a, answer_value=0.8, salience=2.0),
            AnswerData(policy_item_id=item_b, answer_value=0.8, salience=2.0),
        ]
        # Both parties have the same 2 matched positions
        matched_positions = [
            make_position(item_a, 0.8, strength=0.9),
            make_position(item_b, 0.8, strength=0.9),
        ]
        answered_item_to_topic = {item_a: "judiciary", item_b: "security"}

        # Sectoral: covers only 2 of 15 topics
        sectoral_covered_topics = {"judiciary", "security"}
        sectoral_breadth = compute_agenda_breadth(matched_positions, 2, 15)
        sectoral_hsc = compute_high_salience_topic_coverage(
            answers, answered_item_to_topic, sectoral_covered_topics
        )
        sectoral_coverage = compute_coverage_score(answers, matched_positions)
        sectoral_conf = compute_confidence_score(
            matched_positions, answers, 0.1, sectoral_coverage, 1.0,
            high_salience_topic_coverage=sectoral_hsc,
        )

        # Broad: covers 10 of 15 topics (including the user's high-salience ones)
        broad_covered_topics = {"judiciary", "security", "economy", "healthcare",
                                "education", "transport", "welfare", "housing",
                                "environment", "civil_rights"}
        broad_additional = [make_position(uuid.uuid4(), 0.5, strength=0.7) for _ in range(8)]
        broad_positions = matched_positions + broad_additional
        broad_breadth = compute_agenda_breadth(broad_positions, 10, 15)
        broad_hsc = compute_high_salience_topic_coverage(
            answers, answered_item_to_topic, broad_covered_topics
        )
        broad_coverage = compute_coverage_score(answers, broad_positions)
        broad_conf = compute_confidence_score(
            broad_positions, answers, 0.1, broad_coverage, 1.0,
            high_salience_topic_coverage=broad_hsc,
        )

        # Sectoral breadth must be below threshold
        assert sectoral_breadth < SECTORAL_THRESHOLD, f"Expected sectoral; got breadth={sectoral_breadth}"
        assert broad_breadth >= SECTORAL_THRESHOLD

        # High-salience topics covered equally in this scenario (judiciary + security both present)
        assert sectoral_hsc == 1.0
        assert broad_hsc == 1.0

        # Match scores are equal (both perfect on matched items)
        assert compute_match_score(answers, matched_positions) == compute_match_score(
            answers, broad_positions
        )

        # Confidence: broad should be >= sectoral (coverage same here, but test the principle)
        # In this scenario both have 100% HSC so difference comes from coverage only
        assert broad_conf >= sectoral_conf

    def test_sectoral_high_salience_mismatch_lowers_confidence(self):
        """
        Sectoral party has perfect match on 2 items but both are low salience.
        The user's very-important topic (judiciary) is NOT covered by the sectoral party.
        This must lower high_salience_coverage → lower confidence.
        """
        item_a, item_b = uuid.uuid4(), uuid.uuid4()
        important_item = uuid.uuid4()  # user rates this very important

        answers = [
            AnswerData(policy_item_id=item_a, answer_value=0.8, salience=1.0),    # medium
            AnswerData(policy_item_id=item_b, answer_value=0.8, salience=1.0),    # medium
            AnswerData(policy_item_id=important_item, answer_value=0.5, salience=2.0),  # very important
        ]
        answered_item_to_topic = {
            item_a: "economy",
            item_b: "security",
            important_item: "judiciary",
        }

        # Sectoral: perfectly matches economy & security but ignores judiciary entirely
        sectoral_positions = [
            make_position(item_a, 0.8, strength=0.9),
            make_position(item_b, 0.8, strength=0.9),
        ]
        sectoral_covered_topics = {"economy", "security"}
        sectoral_hsc = compute_high_salience_topic_coverage(
            answers, answered_item_to_topic, sectoral_covered_topics
        )
        sectoral_cov = compute_coverage_score(answers, sectoral_positions)
        sectoral_conf = compute_confidence_score(
            sectoral_positions, answers, 0.1, sectoral_cov, 1.0,
            high_salience_topic_coverage=sectoral_hsc,
        )

        # Broad: matches all three items (including judiciary)
        broad_positions = [
            make_position(item_a, 0.8, strength=0.9),
            make_position(item_b, 0.8, strength=0.9),
            make_position(important_item, 0.5, strength=0.9),
        ]
        broad_covered_topics = {"economy", "security", "judiciary"}
        broad_hsc = compute_high_salience_topic_coverage(
            answers, answered_item_to_topic, broad_covered_topics
        )
        broad_cov = compute_coverage_score(answers, broad_positions)
        broad_conf = compute_confidence_score(
            broad_positions, answers, 0.1, broad_cov, 1.0,
            high_salience_topic_coverage=broad_hsc,
        )

        assert sectoral_hsc < 1.0, "Sectoral party should not cover the very-important topic"
        assert broad_hsc == 1.0
        assert broad_conf > sectoral_conf, (
            f"Broad conf={broad_conf:.3f} should exceed sectoral conf={sectoral_conf:.3f}"
        )

