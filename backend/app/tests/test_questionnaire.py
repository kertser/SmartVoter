"""
Unit tests for the adaptive questionnaire selector (AGENTS.MD Section 13).

Core design principle being tested:
    The questionnaire is a VALUES DISCOVERY engine. It must help users discover
    what they GENUINELY CARE ABOUT, not just what policy positions they hold.

    A user who says "cost of living is very important" should get more follow-up
    questions about cost-of-living specifics (subsidies? VAT? rent control?),
    because their stated salience tells us what topics matter most to them.

    The selector must use salience (expressed importance) to drive topic selection —
    not just party separation and evidence quality.

Phase-based selection (new in Phase 8+):
    Phase 1 "survey": covers all topics once before drilling down.
    Phase 2 "depth": salience-driven follow-up, avoids same policy_item repeats.
"""
import uuid
import pytest

from backend.app.services.questionnaire.selector import (
    select_next_question,
    should_offer_results,
    force_results,
    aggregate_salience_by_topic,
    _topic_interest_factor,
    QuestionCandidate,
    PartyPositionSlim,
    HARD_MAX,
    MIN_QUESTIONS,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_candidate(
    topic: str = "judiciary",
    evidence: float = 0.8,
    policy_item_id: uuid.UUID | None = None,
) -> QuestionCandidate:
    return QuestionCandidate(
        question_id=uuid.uuid4(),
        policy_item_id=policy_item_id or uuid.uuid4(),
        topic_slug=topic,
        evidence_quality=evidence,
    )


# ── Section 1: Basic selector behaviour ───────────────────────────────────────

class TestSelectNextQuestionBasics:
    def test_returns_none_after_hard_max_answers(self):
        """No question should be returned once HARD_MAX answers have been given."""
        candidates = [make_candidate() for _ in range(HARD_MAX + 5)]
        answered_ids = [uuid.uuid4() for _ in range(HARD_MAX)]
        result = select_next_question(
            answered_ids=answered_ids,
            candidates=candidates,
            top_party_positions=[],
            answered_topic_counts={},
        )
        assert result is None

    def test_returns_none_when_all_answered(self):
        """If every candidate has been answered, return None."""
        c = make_candidate()
        result = select_next_question(
            answered_ids=[c.question_id],
            candidates=[c],
            top_party_positions=[],
            answered_topic_counts={},
        )
        assert result is None

    def test_returns_none_when_no_candidates(self):
        """Empty candidate list → None."""
        result = select_next_question(
            answered_ids=[],
            candidates=[],
            top_party_positions=[],
            answered_topic_counts={},
        )
        assert result is None

    def test_returns_candidate_when_unanswered_exist(self):
        """At least one unanswered candidate should be returned."""
        c = make_candidate()
        result = select_next_question(
            answered_ids=[],
            candidates=[c],
            top_party_positions=[],
            answered_topic_counts={},
        )
        assert result is not None
        assert result.question_id == c.question_id

    def test_hard_max_is_40(self):
        """Hard max should be 40 (not 15)."""
        assert HARD_MAX == 40

    def test_min_questions_is_8(self):
        """Min questions before offering results should be 8."""
        assert MIN_QUESTIONS == 8


# ── Section 2: Evidence quality preference ────────────────────────────────────

class TestEvidenceQualityPreference:
    def test_prefers_high_evidence_quality(self):
        """
        Questions backed by stronger parliamentary evidence provide more reliable
        party-position signals. The selector should prefer them.
        """
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

    def test_evidence_quality_breaks_tie(self):
        """When party separation is equal, evidence quality decides."""
        item_a = uuid.uuid4()
        item_b = uuid.uuid4()
        low_ev = QuestionCandidate(
            question_id=uuid.uuid4(), policy_item_id=item_a,
            topic_slug="economy", evidence_quality=0.2,
        )
        high_ev = QuestionCandidate(
            question_id=uuid.uuid4(), policy_item_id=item_b,
            topic_slug="economy", evidence_quality=0.9,
        )
        # Same positions for both items (no separation) — evidence quality decides
        positions = [
            [PartyPositionSlim(policy_item_id=item_a, position_mean=0.5),
             PartyPositionSlim(policy_item_id=item_b, position_mean=0.5)],
            [PartyPositionSlim(policy_item_id=item_a, position_mean=0.5),
             PartyPositionSlim(policy_item_id=item_b, position_mean=0.5)],
        ]
        result = select_next_question(
            answered_ids=[],
            candidates=[low_ev, high_ev],
            top_party_positions=positions,
            answered_topic_counts={},
        )
        assert result is not None
        assert result.question_id == high_ev.question_id


# ── Section 3: Party separation preference ────────────────────────────────────

class TestPartySeparationPreference:
    def test_high_party_separation_preferred(self):
        """
        Questions where parties DISAGREE most are the most informative — they best
        distinguish between parties that are close in the current match scores.
        This is essential for understanding the user's real political alignment.
        """
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

        # Parties all agree on item_agree (low variance) but disagree strongly on item_disagree
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


# ── Section 4: Topic diversity ────────────────────────────────────────────────

class TestTopicDiversity:
    def test_basic_diversity_penalty_applied(self):
        """
        Without any salience signal, having answered 3 judiciary questions should
        make a different-topic question more attractive — even at lower evidence quality.
        """
        same_topic_candidates = [make_candidate(topic="judiciary") for _ in range(3)]
        different_topic = make_candidate(topic="economy_taxes", evidence=0.5)
        answered_topic_counts = {"judiciary": 3}
        answered_ids = [c.question_id for c in same_topic_candidates[:2]]
        result = select_next_question(
            answered_ids=answered_ids,
            candidates=same_topic_candidates + [different_topic],
            top_party_positions=[],
            answered_topic_counts=answered_topic_counts,
        )
        # Unanswered judiciary: diversity_factor = 1/(1+3) = 0.25, evidence=0.8
        # economy_taxes: diversity_factor = 1/(1+0) = 1.0, evidence=0.5
        # 0.5 * 1.0 = 0.5 > 0.8 * 0.25 = 0.2 → economy wins
        assert result is not None
        assert result.topic_slug == "economy_taxes"


# ── Section 5: Salience-driven selection (VALUES DISCOVERY) ───────────────────

class TestSalienceDrivenSelection:
    """
    These tests verify the core values-discovery behaviour.

    The app's purpose: understand what the user GENUINELY VALUES.
    If a user says "military service equality is VERY IMPORTANT to me",
    the questionnaire should ask more follow-up questions about military
    service specifics (length, Haredi service, universal obligation).

    This is what separates SmartVoter from a simple political quiz:
    it learns the user's priorities and drills down accordingly.
    """

    def test_high_salience_topic_gets_follow_up_despite_diversity_penalty(self):
        """
        When a user rates a topic as VERY IMPORTANT (salience=2.0), the selector
        should prefer follow-up questions on that topic, even after having already
        asked one question there.

        This test verifies that at count=1 with high salience (2.0), judiciary
        is NOT as harshly penalised as at neutral salience (1.0) in depth phase.
        """
        from backend.app.services.questionnaire.selector import _topic_interest_factor
        factor_neutral = _topic_interest_factor("judiciary", 1, {"judiciary": 1.0}, "depth")
        factor_high = _topic_interest_factor("judiciary", 1, {"judiciary": 2.0}, "depth")
        assert factor_high > factor_neutral, (
            "High-salience topic should be less penalised after 1 answer "
            "than a neutral-salience topic."
        )

    def test_low_salience_topic_deprioritized_faster(self):
        """
        When a user rates a topic as NOT IMPORTANT (salience=0.5), the diversity
        penalty should be STEEPER — we should move away from it more quickly.

        Scenario:
        - User answered 1 environment question with salience=0.5 (not important)
        - Next candidates: 1 more environment Q (evidence=0.9) vs security Q (evidence=0.5)
        - With salience: env effective_count = 1 / 0.5 = 2.0 → factor = 1/(1+2) ≈ 0.333
          security factor = 1/(1+0) = 1.0
          env score: 0.9 * 0.333 ≈ 0.30
          security score: 0.5 * 1.0 = 0.50 → security wins despite lower evidence
        """
        env_q = make_candidate(topic="environment", evidence=0.9)
        security_q = make_candidate(topic="security", evidence=0.5)

        result = select_next_question(
            answered_ids=[],
            candidates=[env_q, security_q],
            top_party_positions=[],
            answered_topic_counts={"environment": 1},
            user_salience_by_topic={"environment": 0.5},  # Not important
        )
        assert result is not None
        assert result.topic_slug == "security", (
            "Low-salience topic should be deprioritised — user said it doesn't matter much."
        )

    def test_neutral_salience_is_standard_diversity(self):
        """
        In depth phase, neutral salience (1.0) should produce exactly the same
        result as the old diversity penalty: 1 / (1 + topic_count).
        """
        factor_with_salience = _topic_interest_factor("judiciary", 2, {"judiciary": 1.0}, "depth")
        factor_without_salience = 1.0 / (1.0 + 2)  # old formula
        assert abs(factor_with_salience - factor_without_salience) < 1e-9

    def test_salience_doubles_follow_up_budget(self):
        """
        Very important (salience=2.0) at topic_count=2 should produce the same
        interest factor as neutral (salience=1.0) at topic_count=1.
        This means high-salience topics get roughly 2× the follow-up budget.
        """
        # salience=2.0, count=2: effective_count=1, factor = 1/(1+1) = 0.5
        factor_high_salience = _topic_interest_factor("judiciary", 2, {"judiciary": 2.0}, "depth")
        # salience=1.0, count=1: effective_count=1, factor = 1/(1+1) = 0.5
        factor_neutral = _topic_interest_factor("judiciary", 1, {"judiciary": 1.0}, "depth")
        assert abs(factor_high_salience - factor_neutral) < 1e-9

    def test_no_salience_map_falls_back_to_standard_diversity(self):
        """
        When user_salience_by_topic is None (not provided), the selector
        must behave identically to the old diversity-only formula.
        """
        same_topic_candidates = [make_candidate(topic="judiciary") for _ in range(3)]
        different_topic = make_candidate(topic="economy_taxes", evidence=0.5)
        answered_topic_counts = {"judiciary": 3}
        answered_ids = [c.question_id for c in same_topic_candidates[:2]]

        # Without salience map
        result_no_salience = select_next_question(
            answered_ids=answered_ids,
            candidates=same_topic_candidates + [different_topic],
            top_party_positions=[],
            answered_topic_counts=answered_topic_counts,
            user_salience_by_topic=None,
        )
        # With neutral salience map (all 1.0)
        result_neutral = select_next_question(
            answered_ids=answered_ids,
            candidates=same_topic_candidates + [different_topic],
            top_party_positions=[],
            answered_topic_counts=answered_topic_counts,
            user_salience_by_topic={"judiciary": 1.0, "economy_taxes": 1.0},
        )
        assert result_no_salience is not None
        assert result_neutral is not None
        assert result_no_salience.question_id == result_neutral.question_id


# ── Section 6: Topic interest factor (unit tests) ─────────────────────────────

class TestTopicInterestFactor:
    """Unit tests for the _topic_interest_factor helper function."""

    def test_zero_count_returns_one(self):
        """Never-answered topic should have interest factor = 1.0 in survey phase."""
        factor = _topic_interest_factor("judiciary", 0, {}, "survey")
        assert factor == 1.0

    def test_high_count_reduces_factor(self):
        """More answers on a topic → lower interest factor (depth phase)."""
        factor_1 = _topic_interest_factor("judiciary", 1, {}, "depth")
        factor_3 = _topic_interest_factor("judiciary", 3, {}, "depth")
        assert factor_1 > factor_3

    def test_high_salience_slows_decay(self):
        """High salience keeps factor higher even after multiple answers (depth)."""
        factor_neutral = _topic_interest_factor("judiciary", 2, {"judiciary": 1.0}, "depth")
        factor_high = _topic_interest_factor("judiciary", 2, {"judiciary": 2.0}, "depth")
        assert factor_high > factor_neutral

    def test_low_salience_accelerates_decay(self):
        """Low salience makes factor drop faster with each answer (depth)."""
        factor_neutral = _topic_interest_factor("judiciary", 1, {"judiciary": 1.0}, "depth")
        factor_low = _topic_interest_factor("judiciary", 1, {"judiciary": 0.5}, "depth")
        assert factor_low < factor_neutral

    def test_factor_always_positive(self):
        """Interest factor must always be positive (no zero/negative scores)."""
        for count in range(10):
            for salience in [0.5, 1.0, 2.0]:
                factor = _topic_interest_factor("test", count, {"test": salience}, "depth")
                assert factor > 0.0

    def test_factor_at_most_one_for_unvisited(self):
        """Unvisited topics should have factor exactly 1.0 in survey phase."""
        factor = _topic_interest_factor("judiciary", 0, {"judiciary": 2.0}, "survey")
        assert factor == 1.0, "Zero questions answered should give factor=1.0 regardless of salience"

    def test_factor_ordering_by_salience(self):
        """At the same topic_count, the ordering must be: high > neutral > low (depth)."""
        count = 2
        factor_high = _topic_interest_factor("t", count, {"t": 2.0}, "depth")
        factor_neutral = _topic_interest_factor("t", count, {"t": 1.0}, "depth")
        factor_low = _topic_interest_factor("t", count, {"t": 0.5}, "depth")
        assert factor_high > factor_neutral > factor_low

    def test_survey_phase_already_covered_topic_near_zero(self):
        """In survey phase, topic already asked once should get near-zero factor."""
        factor_covered = _topic_interest_factor("judiciary", 1, {}, "survey")
        factor_uncovered = _topic_interest_factor("economy", 0, {}, "survey")
        assert factor_uncovered == 1.0
        assert factor_covered < 0.1  # near-zero to enforce breadth


# ── Section 7: Salience aggregation ───────────────────────────────────────────

class TestAggregateSalienceByTopic:
    """
    Tests for the aggregate_salience_by_topic helper.

    We use MAX aggregation because a single "Very important" answer on a topic
    should drive follow-up — even if other answers on that topic were neutral.
    This prevents diluting strong preference signals.
    """

    def test_single_topic_single_answer(self):
        result = aggregate_salience_by_topic([("judiciary", 2.0)])
        assert result == {"judiciary": 2.0}

    def test_max_is_kept_not_mean(self):
        """
        If user marked judiciary very important once and neutral twice,
        the max (2.0) should dominate — driving follow-up on judiciary.
        """
        pairs = [("judiciary", 2.0), ("judiciary", 1.0), ("judiciary", 1.0)]
        result = aggregate_salience_by_topic(pairs)
        assert result["judiciary"] == 2.0

    def test_multiple_topics_aggregated_separately(self):
        pairs = [
            ("security", 2.0),
            ("economy", 0.5),
            ("security", 1.0),
            ("economy", 1.0),
        ]
        result = aggregate_salience_by_topic(pairs)
        assert result["security"] == 2.0
        assert result["economy"] == 1.0

    def test_empty_input_returns_empty(self):
        assert aggregate_salience_by_topic([]) == {}

    def test_not_important_preserved(self):
        """
        If ALL answers on a topic are "not important", the aggregated max
        should be 0.5, correctly flagging this topic as low priority.
        """
        pairs = [("environment", 0.5), ("environment", 0.5)]
        result = aggregate_salience_by_topic(pairs)
        assert result["environment"] == 0.5

    def test_very_important_single_overrides_multiple_neutrals(self):
        """
        One "very important" answer on cost_of_living should drive follow-up
        even if the user was neutral on three other cost_of_living questions.
        This is the core 'values discovery' mechanism.
        """
        pairs = [
            ("cost_of_living", 1.0),
            ("cost_of_living", 1.0),
            ("cost_of_living", 1.0),
            ("cost_of_living", 2.0),  # user said "this specific aspect is very important"
        ]
        result = aggregate_salience_by_topic(pairs)
        assert result["cost_of_living"] == 2.0

    def test_unknown_topic_returns_no_entry(self):
        """Topics with no answers must not appear in the result."""
        result = aggregate_salience_by_topic([("security", 1.0)])
        assert "judiciary" not in result


# ── Section 8: Stop conditions ────────────────────────────────────────────────

class TestStopConditions:
    def test_offer_results_after_8_stable_all_covered(self):
        """Results offered when stable AND all topics covered AND min answered."""
        assert should_offer_results(8, 0.85, True) is True

    def test_no_offer_when_unstable(self):
        """Not offered when ranking unstable."""
        assert should_offer_results(8, 0.70, True) is False

    def test_no_offer_before_8_questions(self):
        """Not offered before MIN_QUESTIONS even if stable."""
        assert should_offer_results(7, 0.95, True) is False

    def test_force_results_at_hard_max(self):
        """Force results at HARD_MAX (40)."""
        assert force_results(HARD_MAX) is True
        assert force_results(HARD_MAX - 1) is False

    def test_no_offer_when_topics_not_covered(self):
        """Not offered when not all topics covered yet."""
        assert should_offer_results(8, 0.85, False) is False

    def test_offer_requires_all_three_conditions(self):
        """All three conditions (count, stability, coverage) must hold."""
        # CONVERGENCE_THRESHOLD = 0.80 — must be >= to trigger
        assert should_offer_results(8, 0.80, True) is True    # exactly at threshold → offered
        assert should_offer_results(8, 0.79, True) is False   # just below threshold → not offered
        assert should_offer_results(8, 0.81, True) is True
        assert should_offer_results(8, 0.81, False) is False  # topics not covered


# ── Section 9: End-to-end values discovery scenario ──────────────────────────

class TestValuesDiscoveryScenario:
    """
    Simulate a realistic questionnaire session where the user reveals
    their genuine priorities through the salience signals they provide.

    Scenario: "Sasha" cares deeply about cost of living and military service
    equality, but not much about environmental policy.
    The questionnaire should discover these priorities and drill accordingly.
    """

    def test_sasha_scenario_cost_of_living_prioritized_over_low_salience(self):
        """
        After Sasha says cost_of_living is 'Very important' (salience=2.0)
        and environment is 'Not important' (salience=0.5),
        the next question should be another cost_of_living question — not
        environment, even though env has higher evidence quality.
        """
        cost_q2 = make_candidate(topic="cost_of_living", evidence=0.75)
        env_q = make_candidate(topic="environment", evidence=0.9)

        answered_topic_counts = {"cost_of_living": 1, "environment": 1}
        user_salience_by_topic = {
            "cost_of_living": 2.0,   # Very important
            "environment": 0.5,      # Not important
        }

        result = select_next_question(
            answered_ids=[],
            candidates=[cost_q2, env_q],
            top_party_positions=[],
            answered_topic_counts=answered_topic_counts,
            user_salience_by_topic=user_salience_by_topic,
        )
        # cost_q2: factor=1/(1+1/2.0)=1/1.5≈0.667, score=0.75*0.667≈0.50
        # env_q: factor=1/(1+1/0.5)=1/3≈0.333, score=0.9*0.333≈0.30
        # cost_q2 should win
        assert result is not None
        assert result.topic_slug == "cost_of_living", (
            "Questionnaire should drill deeper into cost_of_living because "
            "Sasha said it's very important — even though env has higher evidence."
        )

    def test_military_high_salience_stays_competitive_vs_unvisited(self):
        """
        With salience=2.0 and count=1 in depth phase, military's factor is 0.667.
        An unvisited economy topic has factor=1.0.
        With equal evidence, economy wins — but military is NOT dropped.
        This tests that high-salience topics remain in the running.
        """
        mil_factor = _topic_interest_factor("military_service", 1, {"military_service": 2.0}, "depth")
        eco_factor = _topic_interest_factor("economy_taxes", 0, {}, "depth")

        # Check military is still reasonably competitive (factor > 0.5)
        assert mil_factor > 0.5, (
            "High-salience topic after 1 answer should still have interest factor > 0.5"
        )
        assert eco_factor == 1.0

    def test_session_flow_values_discovery(self):
        """
        Simulate a complete session flow where salience accumulates and shapes
        the questionnaire trajectory.

        Flow:
        1. Empty session → all topics at neutral
        2. User answers judiciary Q (salience=2.0) → judiciary becomes priority
        3. Security Q (salience=1.0) → neutral
        4. Environment Q (salience=0.5) → deprioritised

        After these 3 answers, the next question should come from judiciary
        (still has high interest due to salience=2.0) NOT environment
        (deprioritised due to salience=0.5), assuming equal evidence quality.
        """
        # Step 1: Before any answers, evidence quality is the tiebreaker
        jud_q1 = make_candidate(topic="judiciary", evidence=0.8)
        sec_q1 = make_candidate(topic="security", evidence=0.6)
        env_q1 = make_candidate(topic="environment", evidence=0.7)

        result_first = select_next_question(
            answered_ids=[],
            candidates=[jud_q1, sec_q1, env_q1],
            top_party_positions=[],
            answered_topic_counts={},
        )
        assert result_first is not None
        assert result_first.topic_slug == "judiciary"  # highest evidence wins

        # Step 2: After 3 answers establishing salience signals
        jud_q2 = make_candidate(topic="judiciary", evidence=0.75)
        env_q2 = make_candidate(topic="environment", evidence=0.78)

        answered_topic_counts = {"judiciary": 1, "security": 1, "environment": 1}
        user_salience_by_topic = {
            "judiciary": 2.0,    # Very important
            "security": 1.0,     # Neutral
            "environment": 0.5,  # Not important
        }

        result_after = select_next_question(
            answered_ids=[jud_q1.question_id, sec_q1.question_id, env_q1.question_id],
            candidates=[jud_q2, env_q2],
            top_party_positions=[],
            answered_topic_counts=answered_topic_counts,
            user_salience_by_topic=user_salience_by_topic,
        )
        # jud_q2: factor = 1/(1+1/2) = 1/1.5 ≈ 0.667, score = 0.75*0.667 ≈ 0.500
        # env_q2: factor = 1/(1+1/0.5) = 1/3 ≈ 0.333, score = 0.78*0.333 ≈ 0.260
        # judiciary wins
        assert result_after is not None
        assert result_after.topic_slug == "judiciary", (
            "After establishing that judiciary is very important (salience=2.0), "
            "the next question should drill deeper into judiciary — "
            "this is the values discovery at work."
        )
