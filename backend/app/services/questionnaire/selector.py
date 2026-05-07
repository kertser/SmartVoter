"""
Adaptive questionnaire: next-question selection (AGENTS.MD Section 13.2).
Pure functions; DB access handled by callers.

Design principle: Questions exist to discover what the user GENUINELY VALUES,
not just what policy positions they hold. A user might not know Israeli politics
but will know that they care about cheap childcare, fair military service burden,
or housing affordability. The selector must surface those real priorities.

Salience-driven selection:
- When a user marks an answer as "Very important" (salience=2.0), we assume
  they want to explore this topic more deeply → topic follow-up is prioritised.
- When a user marks an answer as "Not important" (salience=0.5), we assume
  this topic doesn't matter much to them → diversity penalty is steeper.
- Neutral responses (salience=1.0) use the standard diversity penalty.

This ensures the questionnaire acts as a VALUES DISCOVERY engine:
discovering what actually matters to the user, not just measuring
their policy positions on a fixed list of topics.
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


def _topic_interest_factor(
    topic_slug: str,
    topic_count: int,
    user_salience_by_topic: dict[str, float],
) -> float:
    """
    Compute the topic interest factor for a candidate question.

    Combines two signals:
    1. Topic diversity (penalise asking many questions on the same topic)
    2. User salience (if the user said a topic is 'very important', follow up more)

    Formula:
        effective_count = topic_count / max(topic_salience, 0.1)
        diversity_factor = 1 / (1 + effective_count)

    Interpretation:
    - salience=2.0 (Very important): effective_count is halved → slower penalty
      → selector asks up to 2× more questions on this topic.
    - salience=1.0 (Medium): standard diversity penalty.
    - salience=0.5 (Not important): effective_count is doubled → faster penalty
      → selector moves away from this topic quickly.

    This turns the questionnaire into a VALUES DISCOVERY engine: it follows the
    user's expressed interests rather than a rigid fixed topic rotation.
    """
    topic_salience = user_salience_by_topic.get(topic_slug, 1.0)
    effective_count = topic_count / max(topic_salience, 0.1)
    return 1.0 / (1.0 + effective_count)


def select_next_question(
    answered_ids: list[uuid.UUID],
    candidates: list[QuestionCandidate],
    top_party_positions: list[list[PartyPositionSlim]],
    answered_topic_counts: dict[str, int],
    user_salience_by_topic: dict[str, float] | None = None,
) -> QuestionCandidate | None:
    """
    AGENTS.MD Section 13.2 heuristic (enhanced with values-discovery salience):

        question_value = party_separation * evidence_quality
                         * topic_interest_factor * fatigue_penalty

    topic_interest_factor replaces the old simple diversity_penalty:
    it uses the user's expressed salience to decide whether to ask MORE or FEWER
    questions on a given topic. High-salience topics get more follow-up;
    low-salience topics are deprioritised faster.

    Returns the best unasked candidate, or None if all answered or >= 15.
    """
    answered_count = len(answered_ids)
    if answered_count >= 15:
        return None

    answered_set = set(answered_ids)
    unanswered = [c for c in candidates if c.question_id not in answered_set]
    if not unanswered:
        return None

    salience_map = user_salience_by_topic or {}
    fatigue_penalty = math.exp(-answered_count / 15.0)

    scored: list[tuple[float, QuestionCandidate]] = []
    for candidate in unanswered:
        separation = _party_separation_score(candidate.policy_item_id, top_party_positions)
        topic_count = answered_topic_counts.get(candidate.topic_slug, 0)
        interest_factor = _topic_interest_factor(
            candidate.topic_slug, topic_count, salience_map
        )
        # Add a small baseline (0.01) so evidence_quality and interest_factor
        # are always factored in even when party separation data is unavailable.
        value = (
            (separation + 0.01)
            * candidate.evidence_quality
            * interest_factor
            * fatigue_penalty
        )
        scored.append((value, candidate))

    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


def aggregate_salience_by_topic(
    answer_topic_pairs: list[tuple[str, float]],
) -> dict[str, float]:
    """
    Aggregate per-answer salience values into a per-topic salience signal.

    Input: list of (topic_slug, answer_salience) pairs
    Output: dict mapping topic_slug → max salience seen for that topic

    We use MAX rather than MEAN because:
    - If a user rated even one question in a topic as "Very important", we
      should follow up on that topic — even if other questions were neutral.
    - MEAN would dilute the signal when some questions were skimmed quickly.
    """
    result: dict[str, float] = {}
    for topic_slug, salience in answer_topic_pairs:
        if topic_slug not in result or salience > result[topic_slug]:
            result[topic_slug] = salience
    return result


def should_offer_results(answered_count: int, ranking_stability: float) -> bool:
    """AGENTS.MD Section 13.3: offer results when >= 8 answered and stable ranking."""
    return answered_count >= 8 and ranking_stability > 0.8


def force_results(answered_count: int) -> bool:
    """Force results after 15 questions."""
    return answered_count >= 15


