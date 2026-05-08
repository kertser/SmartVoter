"""
Scoring engine implementing AGENTS.MD Sections 8 and 12.

All functions are pure (no DB access) and fully testable.
"""
import math
import uuid
from dataclasses import dataclass

# AGENTS.MD Section 8.2 — evidence reliability priors
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
}

# AGENTS.MD Section 9.1 — new-party position coefficients
NEW_PARTY_COEFFICIENTS: dict[str, float] = {
    "candidate_history": 0.45,
    "party_lineage": 0.25,
    "platform": 0.20,
    "public_statements": 0.10,
}

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
    evidence_type: str  # key in EVIDENCE_WEIGHTS


def compute_match_score(
    user_answers: list[AnswerData],
    party_positions: list[PositionData],
) -> float:
    """
    AGENTS.MD Section 12.1:
    distance = abs(user_pos - party_pos)
    similarity = 1 - distance / 2
    weighted_similarity = similarity * salience * evidence_strength
    match_score = sum(weighted_sim) / sum(salience * evidence_strength)

    Only policy items present in BOTH user answers AND party positions contribute.
    Returns 0.0 when no overlap or when denominator is zero.
    """
    position_map = {p.policy_item_id: p for p in party_positions}

    numerator = 0.0
    denominator = 0.0

    for answer in user_answers:
        pos = position_map.get(answer.policy_item_id)
        if pos is None:
            continue
        distance = abs(answer.answer_value - pos.position_mean)
        similarity = 1.0 - distance / 2.0
        weight = answer.salience * pos.evidence_strength
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


def compute_confidence_score(
    party_positions: list[PositionData],
    user_answers: list[AnswerData],
    party_volatility: float,
    coverage_score: float,
    answer_stability: float | None = None,
    high_salience_topic_coverage: float = 1.0,
) -> float:
    """
    AGENTS.MD Section 12.2 — weighted hybrid confidence formula.

    Replaces the original fully-multiplicative formula which collapsed too
    aggressively when any single factor was low (e.g. a new party with
    platform-only evidence would show <10% confidence even when the match
    score itself was meaningful).

    New formula (weighted sum of components):
        confidence =
              0.40 * avg_evidence_strength   (primary: data quality)
            + 0.25 * coverage_score          (secondary: question coverage)
            + 0.15 * answer_stability        (tertiary: ranking robustness)
            + 0.10 * (1 - party_volatility)  (stability penalty)
            + 0.10 * high_salience_coverage  (important-topic coverage)

    avg_evidence_strength is computed ONLY over positions that overlap with
    the user's answered items (prevents sectoral parties from padding confidence
    via high-quality evidence on items the user never answered).

    The resulting score is in 0..1.  A party with average evidence across all
    dimensions scores ~0.65; a party with many votes and high coverage can
    reach ~0.85; a new platform-only party with limited coverage scores ~0.35.
    """
    if not party_positions:
        return 0.0

    answered_ids = {a.policy_item_id for a in user_answers}

    # Evidence quality — computed only over MATCHED positions (answered items)
    matched_positions = [p for p in party_positions if p.policy_item_id in answered_ids]
    if matched_positions:
        avg_evidence = sum(p.evidence_strength for p in matched_positions) / len(matched_positions)
    else:
        avg_evidence = sum(p.evidence_strength for p in party_positions) / len(party_positions)

    if answer_stability is None:
        answer_stability = compute_answer_stability(user_answers, party_positions)

    volatility_factor = max(0.0, 1.0 - party_volatility)

    confidence = (
        0.40 * avg_evidence
        + 0.25 * coverage_score
        + 0.15 * answer_stability
        + 0.10 * volatility_factor
        + 0.10 * high_salience_topic_coverage
    )
    return round(min(1.0, max(0.0, confidence)), 4)

