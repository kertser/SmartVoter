"""
Methodology-invariant tests for AGENTS.MD §§8, 9, 10, 12.

These tests guard the spec rules that historically were either dead code
or partially implemented:

* §8.2 — evidence-type priors are CEILINGS on effective strength.
* §9.1 — new-party position aggregator uses 0.45/0.25/0.20/0.10.
* §10.2 — volatility widens uncertainty AND multiplicatively reduces confidence.
* §11/§12.1 — salience 2.0 carries 4× the weight of salience 0.5.

Any change that breaks these tests should also update AGENTS.MD.
"""
import uuid

import pytest

from backend.app.services.scoring.engine import (
    AnswerData,
    PositionData,
    aggregate_new_party_position,
    compute_confidence_score,
    compute_match_score,
    effective_evidence_strength,
    effective_position_uncertainty,
    evidence_type_prior,
    normalise_evidence_type,
    EVIDENCE_WEIGHTS,
    NEW_PARTY_COEFFICIENTS,
    NEW_PARTY_EVIDENCE_CAP,
)


def _pos(item_id, mean=0.5, strength=0.9, etype="vote"):
    return PositionData(
        policy_item_id=item_id,
        position_mean=mean,
        position_uncertainty=0.15,
        evidence_strength=strength,
        evidence_type=etype,
    )


# ──────────────────────────────────────────────────────────────────────────────
# §8.2 — evidence-type priors are ceilings
# ──────────────────────────────────────────────────────────────────────────────

class TestEvidenceTypePrior:
    def test_canonical_keys_unchanged(self):
        assert evidence_type_prior("vote") == 1.0
        assert evidence_type_prior("party_platform") == 0.35
        assert evidence_type_prior("public_statement") == 0.25

    def test_aliases_normalised(self):
        # Seed JSON used 'platform', 'bill', 'statement'.
        assert normalise_evidence_type("platform") == "party_platform"
        assert normalise_evidence_type("bill") == "sponsored_bill"
        assert normalise_evidence_type("statement") == "public_statement"
        assert normalise_evidence_type(None) == "party_platform"

    def test_alias_priors_match_canonical(self):
        assert evidence_type_prior("platform") == EVIDENCE_WEIGHTS["party_platform"]
        assert evidence_type_prior("bill") == EVIDENCE_WEIGHTS["sponsored_bill"]
        assert evidence_type_prior("statement") == EVIDENCE_WEIGHTS["public_statement"]

    def test_unknown_type_falls_back_to_platform_prior(self):
        # Conservative fallback: unknown evidence type cannot exceed the
        # platform prior of 0.35.
        assert evidence_type_prior("inscrutable_oracle") == 0.35

    def test_effective_strength_caps_inflated_platform_row(self):
        """
        A seed/admin row that wrote evidence_strength=0.95 with type
        'platform' must be clipped to the §8.2 ceiling of 0.35.
        """
        pos = _pos(uuid.uuid4(), strength=0.95, etype="platform")
        assert effective_evidence_strength(pos) == pytest.approx(0.35)

    def test_effective_strength_passes_through_when_below_cap(self):
        pos = _pos(uuid.uuid4(), strength=0.20, etype="public_statement")
        assert effective_evidence_strength(pos) == pytest.approx(0.20)

    def test_vote_row_unaffected(self):
        pos = _pos(uuid.uuid4(), strength=0.80, etype="vote")
        assert effective_evidence_strength(pos) == pytest.approx(0.80)


# ──────────────────────────────────────────────────────────────────────────────
# §11 / §12.1 — salience is linear; 2.0 weighs 4× more than 0.5
# ──────────────────────────────────────────────────────────────────────────────

class TestSalienceWeighting:
    def test_salience_2_dominates_salience_05(self):
        """
        Item A (perfect agreement, salience 2.0) and item B (perfect
        disagreement, salience 0.5) → final score is 4× weighted toward A.

        Expected: (1.0 * 2.0 * w + 0.0 * 0.5 * w) / (2.5 * w) = 0.80.
        """
        a, b = uuid.uuid4(), uuid.uuid4()
        answers = [
            AnswerData(policy_item_id=a, answer_value=1.0, salience=2.0),
            AnswerData(policy_item_id=b, answer_value=-1.0, salience=0.5),
        ]
        positions = [_pos(a, 1.0, 0.9, "vote"), _pos(b, 1.0, 0.9, "vote")]
        score = compute_match_score(answers, positions)
        assert score == pytest.approx(0.80, abs=0.005)


# ──────────────────────────────────────────────────────────────────────────────
# §9.1 — new-party aggregator
# ──────────────────────────────────────────────────────────────────────────────

class TestNewPartyAggregator:
    def test_full_four_signal_aggregation(self):
        """
        candidate=+0.6, lineage=+0.4, platform=-0.2, statements=-0.6
            ⇒ 0.45*0.6 + 0.25*0.4 + 0.20*(-0.2) + 0.10*(-0.6)
            = 0.27 + 0.10 - 0.04 - 0.06 = 0.27
        """
        mean, strength = aggregate_new_party_position(
            candidate_history_mean=0.6,
            lineage_mean=0.4,
            platform_mean=-0.2,
            statements_mean=-0.6,
        )
        assert mean == pytest.approx(0.27, abs=0.01)
        # All four sources present → strength close to (but at most) the cap.
        assert strength <= NEW_PARTY_EVIDENCE_CAP + 1e-6
        assert strength >= NEW_PARTY_EVIDENCE_CAP * 0.9

    def test_platform_only_party_has_low_strength(self):
        """A new party with ONLY a platform plank cannot exceed ~0.20 of cap."""
        mean, strength = aggregate_new_party_position(platform_mean=0.5)
        assert mean == pytest.approx(0.5, abs=0.001)
        # presence = 0.20 / 1.0 = 0.20  ⇒  strength = 0.40*0.20 + 0.05 = 0.13
        assert strength <= 0.20

    def test_no_signals_returns_zero(self):
        assert aggregate_new_party_position() == (0.0, 0.0)

    def test_strength_capped(self):
        """Strength can never exceed NEW_PARTY_EVIDENCE_CAP."""
        _, strength = aggregate_new_party_position(
            candidate_history_mean=0.0,
            lineage_mean=0.0,
            platform_mean=0.0,
            statements_mean=0.0,
            evidence_cap=0.40,
        )
        assert strength <= 0.40

    def test_coefficients_sum_to_one(self):
        assert sum(NEW_PARTY_COEFFICIENTS.values()) == pytest.approx(1.0)


# ──────────────────────────────────────────────────────────────────────────────
# §10.2 — volatility widens uncertainty and reduces confidence multiplicatively
# ──────────────────────────────────────────────────────────────────────────────

class TestVolatilityEffects:
    def test_volatility_widens_uncertainty(self):
        base = effective_position_uncertainty(0.1, 0.0)
        mid = effective_position_uncertainty(0.1, 0.5)
        high = effective_position_uncertainty(0.1, 1.0)
        assert base == pytest.approx(0.10)
        assert mid == pytest.approx(0.30)
        assert high == pytest.approx(0.50)

    def test_uncertainty_clipped_to_one(self):
        assert effective_position_uncertainty(0.9, 1.0) == pytest.approx(1.0)

    def test_volatility_multiplicative_in_confidence(self):
        """
        Two parties identical except for volatility (0.1 vs 0.8) — the high-
        volatility party must score substantially lower in confidence.

        With evidence=0.8, coverage=stab=hsc=1.0:
            base = 0.40*0.8 + 0.25 + 0.15 + 0.20 = 0.92
            low_vol  = 0.92 * (1 - 0.6*0.1) = 0.92*0.94 ≈ 0.865
            high_vol = 0.92 * (1 - 0.6*0.8) = 0.92*0.52 ≈ 0.478
            Δ ≈ 0.39 (well above the spec-required 0.20).
        """
        item = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item, answer_value=0.5, salience=1.0)]
        positions = [_pos(item, 0.5, 0.85, "vote")]

        low_conf = compute_confidence_score(positions, answers, 0.10, 1.0, 1.0)
        high_conf = compute_confidence_score(positions, answers, 0.80, 1.0, 1.0)

        assert low_conf - high_conf >= 0.20

    def test_zero_volatility_no_penalty(self):
        item = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item, answer_value=0.5, salience=1.0)]
        positions = [_pos(item, 0.5, 1.0, "vote")]
        # evidence=1.0, all components 1.0 → base=1.0; vol=0 → factor=1
        conf = compute_confidence_score(positions, answers, 0.0, 1.0, 1.0)
        assert conf == pytest.approx(1.0)


# ──────────────────────────────────────────────────────────────────────────────
# §2.3 — match and confidence are independent (no leakage)
# ──────────────────────────────────────────────────────────────────────────────

class TestMatchVsConfidenceIndependence:
    def test_match_unaffected_by_volatility(self):
        """
        match_score does not see volatility (volatility lives only in
        confidence). Two parties with identical positions must produce the
        same match_score regardless of their volatility.
        """
        item = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item, answer_value=0.5, salience=1.0)]
        positions = [_pos(item, 0.5, 0.9, "vote")]
        # Match score is a pure function of (answers, positions); volatility
        # is not even an argument. This is a structural assertion.
        score = compute_match_score(answers, positions)
        assert 0.0 <= score <= 1.0


# ──────────────────────────────────────────────────────────────────────────────
# §8.2 + §12.1 — platform-only party can rank but is appropriately downweighted
# ──────────────────────────────────────────────────────────────────────────────

class TestPlatformOnlyParty:
    def test_platform_party_match_meaningful_but_evidence_capped(self):
        """
        A new platform-only party with perfect alignment still gets a
        meaningful match score (the spec says new parties must NOT be
        excluded), but its effective evidence on a single item is at most
        0.35 — i.e. it cannot dominate a vote-derived alternative on the
        same item with similar alignment.
        """
        item = uuid.uuid4()
        answers = [AnswerData(policy_item_id=item, answer_value=0.8, salience=1.0)]
        platform_party = [_pos(item, 0.8, strength=0.95, etype="platform")]
        # Match score on a single item is the similarity itself (denominator
        # cancels), so this should be 1.0 — perfect alignment IS perfect
        # alignment regardless of source.
        assert compute_match_score(answers, platform_party) == pytest.approx(1.0)

        # But effective evidence (which DRIVES confidence) is capped at 0.35.
        eff = effective_evidence_strength(platform_party[0])
        assert eff == pytest.approx(0.35)

    def test_two_party_ranking_vote_over_platform_when_tied_alignment(self):
        """
        Two parties both perfectly aligned on item A and both perfectly
        anti-aligned on item B. Party V uses votes for both (high effective
        strength on both). Party P uses platforms for both (effective 0.35
        on each). Final match score is identical (perfect cancellation), but
        when one item is mismatched between the two, the vote-based party
        should pull more of the user's score weight.

        Concretely: user agrees on A, disagrees on B (both salience 1.0).
        V: vote/0.95 on A (effective 0.95), vote/0.95 on B (effective 0.95)
        P: platform/0.95 on A (effective 0.35), platform/0.95 on B (eff 0.35)
        Both score 0.5 on match. The point is they CAN both be scored.
        """
        a, b = uuid.uuid4(), uuid.uuid4()
        answers = [
            AnswerData(policy_item_id=a, answer_value=1.0, salience=1.0),
            AnswerData(policy_item_id=b, answer_value=-1.0, salience=1.0),
        ]
        v_party = [_pos(a, 1.0, 0.95, "vote"), _pos(b, 1.0, 0.95, "vote")]
        p_party = [_pos(a, 1.0, 0.95, "platform"), _pos(b, 1.0, 0.95, "platform")]

        v_match = compute_match_score(answers, v_party)
        p_match = compute_match_score(answers, p_party)
        # Same alignment on both items → same balance of agree/disagree.
        assert v_match == pytest.approx(p_match)

        # But confidence diverges: vote-based avg_evidence ≈ 0.95, platform
        # avg_evidence ≈ 0.35.
        v_conf = compute_confidence_score(v_party, answers, 0.1, 1.0, 1.0)
        p_conf = compute_confidence_score(p_party, answers, 0.1, 1.0, 1.0)
        assert v_conf > p_conf + 0.20


