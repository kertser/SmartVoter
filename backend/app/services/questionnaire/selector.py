"""
Adaptive questionnaire: next-question selection (AGENTS.MD Section 13.2).
Pure functions; DB access handled by callers.

=== Phase-based selection model ===

Phase 1 — "Topic Survey" (questions 1 … min(n_topics, SURVEY_MAX)):
    One question per topic.  The goal is breadth: discover which topics the
    user cares about before drilling down.  Root questions are always preferred
    within this phase.  The soft rule is:
        - never ask a 2nd question about a topic that already has one answer
          UNLESS all topics are already covered.
        - within that constraint, pick by evidence_quality.

Phase 2 — "Depth Drilling" (questions after survey phase):
    Now the user has told us what matters (via salience).
        - High-salience topics get priority (up to DEPTH_FOLLOW_UPS per topic).
        - Never re-ask the SAME policy_item_id unless the user rated it Very
          Important (salience=2.0) and a second question exists.
        - Prefer questions that best separate currently top-ranked parties.

Convergence / stopping:
    - After MIN_QUESTIONS, offer "see results" if ranking is stable.
    - After HARD_MAX questions, always stop.
    - Ranking stability = Kendall-τ correlation between last two ranked orderings.
"""
import math
import uuid
from dataclasses import dataclass, field

# ──────────────────────────────────────────────────────────────────────────────
# Configuration constants (can be overridden by callers)
# ──────────────────────────────────────────────────────────────────────────────

MIN_QUESTIONS = 8          # earliest point to offer results
HARD_MAX = 40              # absolute maximum questions
SURVEY_MAX_PER_TOPIC = 1   # Phase-1 cap per topic
DEPTH_MAX_PER_TOPIC = 3    # Phase-2 max additional questions per topic
DEPTH_FOLLOW_UPS = 2       # extra questions for Very-Important topics
POLICY_REPEAT_SALIENCE_THRESHOLD = 1.8  # require salience >= this to re-ask same policy_item
CONVERGENCE_THRESHOLD = 0.80  # Kendall-τ above this → ranking stable


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

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
    phase: str,
) -> float:
    """
    Compute the topic interest factor for a candidate question.

    Phase 1 (survey): heavy penalty for topics already asked → enforce breadth.
    Phase 2 (depth):  salience-driven — follow user interest.

    formula (phase 2):
        effective_count = topic_count / max(topic_salience, 0.1)
        diversity_factor = 1 / (1 + effective_count)
    """
    topic_salience = user_salience_by_topic.get(topic_slug, 1.0)

    if phase == "survey":
        # In survey phase: hard preference for uncovered topics.
        # A topic already covered gets an extremely steep penalty.
        if topic_count == 0:
            return 1.0
        return 0.05 / topic_count  # near-zero for already-asked topics

    # Depth phase
    effective_count = topic_count / max(topic_salience, 0.1)
    return 1.0 / (1.0 + effective_count)


def _policy_item_repeat_penalty(
    policy_item_id: uuid.UUID,
    answered_policy_item_counts: dict[uuid.UUID, int],
    salience_by_policy_item: dict[uuid.UUID, float],
) -> float:
    """
    Return a multiplier in [0, 1] that penalises re-asking the same policy item.

    Rules:
    - First question on this policy_item: no penalty (1.0).
    - Second question: only allowed if user rated it Very Important (salience=2.0).
      Otherwise near-zero (0.02).
    - Third or more: always near-zero.
    """
    count = answered_policy_item_counts.get(policy_item_id, 0)
    if count == 0:
        return 1.0
    if count == 1:
        salience = salience_by_policy_item.get(policy_item_id, 1.0)
        if salience >= POLICY_REPEAT_SALIENCE_THRESHOLD:
            return 0.6   # allowed but de-prioritised
        return 0.02      # almost never re-ask
    return 0.01          # three or more times: essentially blocked


def _determine_phase(
    answered_count: int,
    answered_topic_counts: dict[str, int],
    all_topic_slugs: set[str],
) -> str:
    """
    Phase 1 ("survey") until every known topic has been covered at least once
    OR we have answered at least len(all_topic_slugs) questions.
    Phase 2 ("depth") thereafter.
    """
    covered_topics = sum(1 for t in all_topic_slugs if answered_topic_counts.get(t, 0) > 0)
    if covered_topics < len(all_topic_slugs):
        return "survey"
    return "depth"


def _kendall_tau(ranking_a: list[uuid.UUID], ranking_b: list[uuid.UUID]) -> float:
    """
    Kendall-τ rank correlation between two orderings of the same items.
    Returns 1.0 if identical, -1.0 if inverted, 0.0 if no correlation.
    Falls back to 1.0 if rankings are empty or incompatible.
    """
    common = [pid for pid in ranking_a if pid in set(ranking_b)]
    n = len(common)
    if n < 2:
        return 1.0  # nothing to compare yet → treat as stable
    rank_b = {pid: i for i, pid in enumerate(ranking_b)}
    seq = [rank_b[pid] for pid in common]
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            if seq[i] < seq[j]:
                concordant += 1
            elif seq[i] > seq[j]:
                discordant += 1
    total = concordant + discordant
    return (concordant - discordant) / total if total > 0 else 1.0


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def select_next_question(
    answered_ids: list[uuid.UUID],
    candidates: list[QuestionCandidate],
    top_party_positions: list[list[PartyPositionSlim]],
    answered_topic_counts: dict[str, int],
    user_salience_by_topic: dict[str, float] | None = None,
    answered_policy_item_counts: dict[uuid.UUID, int] | None = None,
    salience_by_policy_item: dict[uuid.UUID, float] | None = None,
    all_topic_slugs: set[str] | None = None,
) -> QuestionCandidate | None:
    """
    Phase-aware adaptive question selector.

    Scoring formula:
        question_value = party_separation_score   (how much parties differ)
                       * evidence_quality          (reliability of the evidence)
                       * topic_interest_factor     (breadth in survey / salience in depth)
                       * policy_item_repeat_penalty (avoid asking same policy item twice)
                       * fatigue_penalty            (gentler slow-down over time)

    Phases:
        survey  → cover all topics once; topic_interest_factor is near-zero for
                  topics already asked → strong breadth bias.
        depth   → salience-driven follow-up; repeated topics allowed when the
                  user rated them Very Important.

    Returns the best unasked candidate, or None when the hard maximum is reached
    or no candidates remain.
    """
    answered_count = len(answered_ids)
    if answered_count >= HARD_MAX:
        return None

    answered_set = set(answered_ids)
    unanswered = [c for c in candidates if c.question_id not in answered_set]
    if not unanswered:
        return None

    salience_map = user_salience_by_topic or {}
    pi_count_map = answered_policy_item_counts or {}
    pi_salience_map = salience_by_policy_item or {}
    topic_slugs = all_topic_slugs or {c.topic_slug for c in candidates}

    phase = _determine_phase(answered_count, answered_topic_counts, topic_slugs)
    fatigue_penalty = math.exp(-answered_count / 20.0)  # slower decay than before

    scored: list[tuple[float, QuestionCandidate]] = []
    for candidate in unanswered:
        separation = _party_separation_score(candidate.policy_item_id, top_party_positions)
        topic_count = answered_topic_counts.get(candidate.topic_slug, 0)

        interest_factor = _topic_interest_factor(
            candidate.topic_slug, topic_count, salience_map, phase
        )
        repeat_penalty = _policy_item_repeat_penalty(
            candidate.policy_item_id, pi_count_map, pi_salience_map
        )

        # Small baseline (0.01) so evidence_quality always contributes even
        # when party-separation data is unavailable.
        value = (
            (separation + 0.01)
            * max(candidate.evidence_quality, 0.05)
            * interest_factor
            * repeat_penalty
            * fatigue_penalty
        )
        scored.append((value, candidate))

    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


def compute_ranking_stability(
    prev_ranking: list[uuid.UUID],
    curr_ranking: list[uuid.UUID],
) -> float:
    """
    Return Kendall-τ (0..1) between consecutive top-party rankings.
    1.0 = completely stable, 0.0 = completely random.
    """
    tau = _kendall_tau(prev_ranking, curr_ranking)
    # Map from [-1, 1] to [0, 1]
    return (tau + 1.0) / 2.0


def should_offer_results(
    answered_count: int,
    ranking_stability: float,
    all_topics_covered: bool,
) -> bool:
    """
    Offer "see results now" early exit when:
    - at least MIN_QUESTIONS answered, AND
    - ranking is stable (τ-based), AND
    - all topics have been touched at least once.
    """
    return (
        answered_count >= MIN_QUESTIONS
        and ranking_stability >= CONVERGENCE_THRESHOLD
        and all_topics_covered
    )


def force_results(answered_count: int) -> bool:
    """Absolute hard stop."""
    return answered_count >= HARD_MAX


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
    """
    result: dict[str, float] = {}
    for topic_slug, salience in answer_topic_pairs:
        if topic_slug not in result or salience > result[topic_slug]:
            result[topic_slug] = salience
    return result


def aggregate_salience_by_policy_item(
    answer_pi_pairs: list[tuple[uuid.UUID, float]],
) -> dict[uuid.UUID, float]:
    """Max salience seen per policy_item_id."""
    result: dict[uuid.UUID, float] = {}
    for pi_id, salience in answer_pi_pairs:
        if pi_id not in result or salience > result[pi_id]:
            result[pi_id] = salience
    return result
