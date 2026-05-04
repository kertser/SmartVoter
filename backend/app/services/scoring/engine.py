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
) -> float:
    """
    AGENTS.MD Section 12.2:
    confidence = avg_evidence_strength * coverage * (1 - volatility) * answer_stability
    """
    if not party_positions:
        return 0.0

    avg_evidence = sum(p.evidence_strength for p in party_positions) / len(party_positions)

    if answer_stability is None:
        answer_stability = compute_answer_stability(user_answers, party_positions)

    confidence = (
        avg_evidence
        * coverage_score
        * (1.0 - party_volatility)
        * answer_stability
    )
    return round(min(1.0, max(0.0, confidence)), 4)

