"""
Adaptive questionnaire: next-question selection (AGENTS.MD Section 13.2).
Pure functions; DB access handled by callers.
"""
import math
import uuid
from dataclasses import dataclass


@dataclass
class QuestionCandidate:
    question_id: uuid.UUID
    policy_item_id: uuid.UUID
    topic_slug: str
    evidence_quality: float  # average evidence_strength for this policy_item across parties


@dataclass
class PartyPositionSlim:
    policy_item_id: uuid.UUID
    position_mean: float


def _party_separation_score(
    policy_item_id: uuid.UUID,
    top_party_positions: list[list[PartyPositionSlim]],
) -> float:
    """
    Variance of position_mean across top parties for a given policy item.
    Higher = parties disagree more = more discriminating question.
    """
    positions = [
        pos.position_mean
        for party_pos_list in top_party_positions
        for pos in party_pos_list
        if pos.policy_item_id == policy_item_id
    ]
    if len(positions) < 2:
        return 0.0
    mean = sum(positions) / len(positions)
    variance = sum((p - mean) ** 2 for p in positions) / len(positions)
    return variance


def select_next_question(
    answered_ids: list[uuid.UUID],
    candidates: list[QuestionCandidate],
    top_party_positions: list[list[PartyPositionSlim]],
    answered_topic_counts: dict[str, int],
) -> QuestionCandidate | None:
    """
    AGENTS.MD Section 13.2 heuristic:
    question_value = party_separation * evidence_quality * diversity_penalty * fatigue_penalty

    Returns the best unasked candidate, or None if all answered or >= 15.
    """
    answered_count = len(answered_ids)
    if answered_count >= 15:
        return None

    answered_set = set(answered_ids)
    unanswered = [c for c in candidates if c.question_id not in answered_set]
    if not unanswered:
        return None

    fatigue_penalty = math.exp(-answered_count / 15.0)

    scored: list[tuple[float, QuestionCandidate]] = []
    for candidate in unanswered:
        separation = _party_separation_score(candidate.policy_item_id, top_party_positions)
        topic_count = answered_topic_counts.get(candidate.topic_slug, 0)
        diversity_penalty = 1.0 / (1.0 + topic_count)
        value = (
            separation
            * candidate.evidence_quality
            * diversity_penalty
            * fatigue_penalty
        )
        scored.append((value, candidate))

    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


def should_offer_results(answered_count: int, ranking_stability: float) -> bool:
    """AGENTS.MD Section 13.3: offer results when >= 8 answered and stable ranking."""
    return answered_count >= 8 and ranking_stability > 0.8


def force_results(answered_count: int) -> bool:
    """Force results after 15 questions."""
    return answered_count >= 15

