"""
Scoring engine implementing AGENTS.MD Sections 8, 9, 10 and 12.

All functions are pure (no DB access) and fully testable.

Key invariants enforced here (was previously dead code in some places):

1. §8.2 — evidence reliability *priors are caps*. The stored
   `evidence_strength` is taken as the raw observed signal; its effective
   contribution to scoring is bounded above by the §8.2 prior for that
   evidence type. A platform-only row can never contribute more than 0.35,
   no matter what was written into the DB.

2. §9.1 — new-party aggregation. When a party has no direct vote evidence
   on an item, we synthesise a position from candidate history, lineage,
   platform and statements with the spec coefficients
   (0.45 / 0.25 / 0.20 / 0.10).

3. §10.2 — volatility *widens uncertainty and reduces confidence
   multiplicatively*, not additively. A high-volatility party can no longer
   coast on residual confidence weights.

4. §12.1 / §12.2 — match and confidence are computed independently. Match
   uses effective evidence strength as a per-item weight (so unreliable
   evidence still influences the ranking less, exactly as the spec wants);
   confidence aggregates evidence quality, coverage, stability, and
   high-salience-topic coverage, then applies a volatility multiplier.
"""
import uuid
from dataclasses import dataclass

# AGENTS.MD §8.2 — evidence reliability priors (interpreted as ceilings on the
# effective contribution of any single position derived from this source type).
EVIDENCE_WEIGHTS: dict[str, float] = {
    "vote": 1.00,
    "sponsored_bill": 0.80,
    "committee_behavior": 0.70,
    "candidate_past_vote": 0.55,
    "party_lineage": 0.50,
    "coalition_agreement": 0.45,
    "party_platform": 0.35,
    "public_statement": 0.25,
    "media_interview": 0.20,
    # Synthetic source type emitted by §9.1 new-party aggregation.
    # Capped just below platform: we fused multiple weak sources, so it is at
    # most as strong as a candidate-past-vote signal.
    "new_party_synth": 0.55,
}

# Defensive aliases used by older seed data, admin uploads, and ingestion
# pipelines that wrote non-canonical names. They are normalised at scoring
# time so that historical rows do not bypass the §8.2 prior. The dict key
# type is ``str | None`` so that legacy NULL evidence_type is also covered.
EVIDENCE_TYPE_ALIASES: dict[str | None, str] = {
    "bill": "sponsored_bill",
    "bills": "sponsored_bill",
    "platform": "party_platform",
    "platforms": "party_platform",
    "statement": "public_statement",
    "statements": "public_statement",
    "interview": "media_interview",
    "candidate_history": "candidate_past_vote",
    "lineage": "party_lineage",
    "coalition": "coalition_agreement",
    "committee": "committee_behavior",
    None: "party_platform",  # legacy NULL fallback — same as engine default
}

# AGENTS.MD §9.1 — new-party position coefficients
NEW_PARTY_COEFFICIENTS: dict[str, float] = {
    "candidate_history": 0.45,
    "party_lineage": 0.25,
    "platform": 0.20,
    "public_statements": 0.10,
}

# §9.1 also requires an evidence-strength CAP on synthesised positions so that
# a party with no parliamentary record cannot equal a party with rich votes.
NEW_PARTY_EVIDENCE_CAP = 0.40

# §10.2 — multiplier used to widen position_uncertainty proportional to
# party volatility. uncertainty_effective = base + 0.4 * volatility (clipped to 1.0).
VOLATILITY_UNCERTAINTY_MULTIPLIER = 0.4

# §12.2 — multiplicative volatility penalty in confidence:
# confidence_factor = 1 - VOLATILITY_PENALTY_FACTOR * party_volatility.
# At volatility=0.5 → ×0.70. At volatility=1.0 → ×0.40. This is the
# spec-faithful "multiplicative" interpretation; the older additive variant
# only ever subtracted at most 0.10 and was systematically too lenient.
VOLATILITY_PENALTY_FACTOR = 0.6

# Agenda breadth threshold: party is "sectoral" when it covers fewer
# than this fraction of all topics in the system.
SECTORAL_THRESHOLD = 0.35

# Minimum similarity to count as an "agreement" on a topic
AGREEMENT_THRESHOLD = 0.65

# Maximum similarity to count as a "disagreement" on a topic
DISAGREEMENT_THRESHOLD = 0.50


@dataclass
class AnswerData:
    policy_item_id: uuid.UUID
    answer_value: float  # -1.0 to +1.0
    salience: float  # 0.5 | 1.0 | 2.0


@dataclass
class PositionData:
    policy_item_id: uuid.UUID
    position_mean: float  # -1.0 to +1.0
    position_uncertainty: float
    evidence_strength: float
    evidence_type: str  # key in EVIDENCE_WEIGHTS (or alias normalised internally)


# ──────────────────────────────────────────────────────────────────────────────
# §8.2 evidence-type normalisation and effective-strength helpers
# ──────────────────────────────────────────────────────────────────────────────

def normalise_evidence_type(evidence_type: str | None) -> str:
    """
    Map seed/legacy aliases (e.g. ``"platform"``, ``"bill"``, ``None``) to the
    canonical §8.2 keys. Returns the input unchanged if it is already canonical
    or unknown (unknown types are treated as `party_platform` by the prior cap
    via :func:`evidence_type_prior`).
    """
    if evidence_type in EVIDENCE_WEIGHTS:
        return evidence_type
    return EVIDENCE_TYPE_ALIASES.get(evidence_type, evidence_type or "party_platform")


def evidence_type_prior(evidence_type: str | None) -> float:
    """
    §8.2 prior reliability for a (possibly aliased) evidence type. Falls back
    to the platform prior (0.35) for unknown types — the conservative choice.
    """
    canonical = normalise_evidence_type(evidence_type)
    return EVIDENCE_WEIGHTS.get(canonical, EVIDENCE_WEIGHTS["party_platform"])


def effective_evidence_strength(pos: PositionData) -> float:
    """
    Effective contribution of a single party position to scoring.

    Per §8.2 we treat the reliability priors as *ceilings*: stored strength is
    the raw, count-derived signal (already in 0..1) and cannot exceed the
    type's prior. This caps platform/statement-only rows at 0.35 / 0.25 even
    if an admin or LLM wrote a higher number, which is exactly what the spec
    demands ("declared positions are useful, but less reliable than observed
    behavior" — §2.1).
    """
    cap = evidence_type_prior(pos.evidence_type)
    raw = max(0.0, min(1.0, float(pos.evidence_strength)))
    return min(raw, cap)


def effective_position_uncertainty(
    base_uncertainty: float, party_volatility: float
) -> float:
    """
    §10.2 — *Use volatility to widen uncertainty.* Returns the effective
    position uncertainty given the stored ingestion-time uncertainty and the
    current party volatility score (0..1). Clipped to [0, 1].
    """
    base = max(0.0, min(1.0, float(base_uncertainty)))
    vol = max(0.0, min(1.0, float(party_volatility)))
    return min(1.0, base + VOLATILITY_UNCERTAINTY_MULTIPLIER * vol)


# ──────────────────────────────────────────────────────────────────────────────
# §9.1 new-party position aggregator
# ──────────────────────────────────────────────────────────────────────────────

def aggregate_new_party_position(
    *,
    candidate_history_mean: float | None = None,
    lineage_mean: float | None = None,
    platform_mean: float | None = None,
    statements_mean: float | None = None,
    weights: dict[str, float] | None = None,
    evidence_cap: float = NEW_PARTY_EVIDENCE_CAP,
) -> tuple[float, float]:
    """
    AGENTS.MD §9.1 — synthesise a position for a party with no direct
    parliamentary evidence on a given policy item.

    Returns ``(position_mean, evidence_strength)``. ``evidence_strength`` is
    capped at ``evidence_cap`` (default 0.40) and scaled by the fraction of
    the four signal slots that were actually supplied. A new party with only
    a platform plank thus contributes ~0.20 * cap, while one with all four
    sources approaches the cap.

    All means are expected in [-1, +1]. Missing signals (None) are skipped
    and their weights redistributed proportionally across the present ones.
    """
    coeffs = weights or NEW_PARTY_COEFFICIENTS
    sources: list[tuple[float, float]] = []  # (value, weight)
    if candidate_history_mean is not None:
        sources.append((candidate_history_mean, coeffs["candidate_history"]))
    if lineage_mean is not None:
        sources.append((lineage_mean, coeffs["party_lineage"]))
    if platform_mean is not None:
        sources.append((platform_mean, coeffs["platform"]))
    if statements_mean is not None:
        sources.append((statements_mean, coeffs["public_statements"]))

    if not sources:
        return 0.0, 0.0

    total_weight = sum(w for _, w in sources)
    position_mean = sum(v * w for v, w in sources) / total_weight

    # The "presence factor" is the proportion of full §9.1 weight actually
    # accounted for. A platform-only new party (0.20 of 1.0) gets 0.20.
    presence = total_weight / sum(coeffs.values())
    evidence_strength = round(min(evidence_cap, evidence_cap * presence + 0.05), 4)

    return round(max(-1.0, min(1.0, position_mean)), 4), evidence_strength


# ──────────────────────────────────────────────────────────────────────────────
# §12.1 match score
# ──────────────────────────────────────────────────────────────────────────────

def compute_match_score(
    user_answers: list[AnswerData],
    party_positions: list[PositionData],
) -> float:
    """
    AGENTS.MD §12.1:
        distance = abs(user_pos - party_pos)
        similarity = 1 - distance / 2
        weighted_similarity = similarity * salience * effective_evidence_strength
        match_score = sum(weighted_sim) / sum(salience * effective_evidence_strength)

    Effective evidence strength applies the §8.2 type ceiling, so a perfectly
    aligned platform-only position cannot dominate a vote-derived one with
    the same raw stored strength. This is the desired behaviour:
    *observed behaviour outranks declared positions* (§2.1).

    Only policy items present in BOTH user answers AND party positions
    contribute. Returns 0.0 when no overlap or when denominator is zero.
    """
    position_map = {p.policy_item_id: p for p in party_positions}

    numerator = 0.0
    denominator = 0.0

    for answer in user_answers:
        pos = position_map.get(answer.policy_item_id)
        if pos is None:
            continue
        # Defensive clamp on answer value — schema validates, but engine
        # must never produce negative similarities or > 1.
        ans_val = max(-1.0, min(1.0, float(answer.answer_value)))
        pos_val = max(-1.0, min(1.0, float(pos.position_mean)))
        distance = abs(ans_val - pos_val)
        similarity = 1.0 - distance / 2.0
        weight = answer.salience * effective_evidence_strength(pos)
        numerator += similarity * weight
        denominator += weight

    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def compute_coverage_score(
    user_answers: list[AnswerData],
    party_positions: list[PositionData],
) -> float:
    """
    Fraction of answered policy items that have evidence for this party.
    High-salience answers are weighted more in coverage check.

    This measures how much of the USER's answered questions the party covers.
    Distinct from agenda_breadth which measures the party's overall topic spread.
    """
    if not user_answers:
        return 0.0

    position_ids = {p.policy_item_id for p in party_positions}
    covered_weight = 0.0
    total_weight = 0.0

    for answer in user_answers:
        total_weight += answer.salience
        if answer.policy_item_id in position_ids:
            covered_weight += answer.salience

    if total_weight == 0:
        return 0.0
    return round(covered_weight / total_weight, 4)


def compute_agenda_breadth(
    party_positions: list[PositionData],
    party_topic_count: int,
    total_topics_count: int,
) -> float:
    """
    Fraction of all topics in the system that this party has at least one
    position on.  party_topic_count must be pre-computed by the caller
    who has access to topic metadata.

    Returns 0..1. A party covering 3 of 15 topics returns 0.20.
    WARNING: is_sectoral if this value < SECTORAL_THRESHOLD.
    """
    if total_topics_count == 0:
        return 1.0
    return round(min(1.0, party_topic_count / total_topics_count), 4)


def compute_high_salience_topic_coverage(
    user_answers: list[AnswerData],
    answered_item_to_topic: dict[uuid.UUID, str],
    party_covered_topics: set[str],
) -> float:
    """
    Fraction of topics where the user has VERY IMPORTANT (salience=2.0) answers
    that the party actually covers with at least one position.

    If the user has no high-salience answers, returns 1.0 (no penalty).
    This penalizes parties that ignore the user's most important concerns.

    answered_item_to_topic: mapping policy_item_id → topic_slug (caller provides)
    party_covered_topics: set of topic slugs the party has at least one position on
    """
    high_sal_topics: set[str] = set()
    for answer in user_answers:
        if answer.salience >= 2.0:
            topic = answered_item_to_topic.get(answer.policy_item_id)
            if topic:
                high_sal_topics.add(topic)

    if not high_sal_topics:
        return 1.0  # user has no very-important answers → no penalty

    covered = high_sal_topics & party_covered_topics
    return round(len(covered) / len(high_sal_topics), 4)


def compute_answer_stability(
    user_answers: list[AnswerData],
    party_positions: list[PositionData],
) -> float:
    """
    Leave-one-out ranking stability: how much does the match score change
    when each answer is removed? High stability → score is robust.
    Returns score in 0..1 (1 = perfectly stable).
    """
    if len(user_answers) <= 1:
        return 1.0

    base_score = compute_match_score(user_answers, party_positions)
    deviations = []

    for i in range(len(user_answers)):
        subset = user_answers[:i] + user_answers[i + 1:]
        score = compute_match_score(subset, party_positions)
        deviations.append(abs(score - base_score))

    mean_deviation = sum(deviations) / len(deviations)
    stability = max(0.0, 1.0 - mean_deviation * 5)  # scale: 0.2 deviation → 0 stability
    return round(stability, 4)


# ──────────────────────────────────────────────────────────────────────────────
# §12.2 confidence score (multiplicative volatility — spec-faithful)
# ──────────────────────────────────────────────────────────────────────────────

def compute_confidence_score(
    party_positions: list[PositionData],
    user_answers: list[AnswerData],
    party_volatility: float,
    coverage_score: float,
    answer_stability: float | None = None,
    high_salience_topic_coverage: float = 1.0,
) -> float:
    """
    AGENTS.MD §12.2 — confidence = base_quality_signal × volatility_factor.

    base_quality_signal (weighted sum, components in [0, 1]):
        0.40 * avg_effective_evidence_strength (matched positions only)
        0.25 * coverage_score
        0.15 * answer_stability
        0.20 * high_salience_topic_coverage

    volatility_factor = 1 − VOLATILITY_PENALTY_FACTOR × party_volatility
        (multiplicative — a volatile party with churning candidates and
        unstable lineage cannot achieve high confidence regardless of
        evidence quality on the items the user happened to answer).

    Notes:

    * `avg_effective_evidence_strength` is computed only over positions that
      overlap with the user's answered items (so a sectoral party cannot pad
      confidence by holding strong positions on items the user never reached).
    * `effective_evidence_strength` applies the §8.2 type ceiling.
    * The combination respects the §2.3 invariant: confidence is computed
      *separately* from match — match never sees `party_volatility`.
    """
    if not party_positions:
        return 0.0

    answered_ids = {a.policy_item_id for a in user_answers}

    matched_positions = [p for p in party_positions if p.policy_item_id in answered_ids]
    if matched_positions:
        avg_evidence = sum(
            effective_evidence_strength(p) for p in matched_positions
        ) / len(matched_positions)
    else:
        avg_evidence = sum(
            effective_evidence_strength(p) for p in party_positions
        ) / len(party_positions)

    if answer_stability is None:
        answer_stability = compute_answer_stability(user_answers, party_positions)

    base_signal = (
        0.40 * avg_evidence
        + 0.25 * coverage_score
        + 0.15 * answer_stability
        + 0.20 * high_salience_topic_coverage
    )
    volatility = max(0.0, min(1.0, float(party_volatility)))
    volatility_factor = max(0.0, 1.0 - VOLATILITY_PENALTY_FACTOR * volatility)

    confidence = base_signal * volatility_factor
    return round(min(1.0, max(0.0, confidence)), 4)

