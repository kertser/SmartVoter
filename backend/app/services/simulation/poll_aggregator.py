"""
Poll aggregator — Phase 14B.
Computes weighted average vote shares from multiple polls.
Per AGENTS.MD Section 14B.5.
"""

import math
from datetime import date


class PollAggregator:
    """
    Aggregate polls into a probabilistic prior over vote shares.

    Weights combine:
     - recency (exponential decay, half_life_days)
     - sample size (sqrt scaling)
     - pollster quality score
    """

    def __init__(self, half_life_days: float = 14.0):
        self.half_life_days = half_life_days

    def aggregate(self, polls: list[dict], reference_date: date | None = None) -> dict[str, dict]:
        """
        Args:
            polls: list of {
                'field_end_date': date,
                'sample_size': int,
                'quality_score': float,
                'party_results': [{'reported_name': str, 'vote_share_mean': float}, …]
            }
            reference_date: today if None

        Returns:
            {party_name: {'vote_share_mean': float, 'vote_share_std': float}}
        """
        if not polls:
            return {}

        today = reference_date or date.today()
        party_data: dict[str, list[tuple[float, float]]] = {}  # {name: [(weighted_share, weight)]}

        for poll in polls:
            days_old = max(0, (today - poll["field_end_date"]).days)
            recency_w = math.exp(-days_old / self.half_life_days)
            sample_w = math.sqrt(poll.get("sample_size", 500)) / 30.0
            quality_w = poll.get("quality_score", 0.7)
            weight = recency_w * sample_w * quality_w

            for pr in poll.get("party_results", []):
                name = pr["reported_name"]
                share = pr.get("vote_share_mean", 0.0)
                party_data.setdefault(name, []).append((share * weight, weight))

        result: dict[str, dict] = {}
        for party, entries in party_data.items():
            total_weight = sum(w for _, w in entries)
            if total_weight <= 0:
                continue
            mean = sum(ws for ws, _ in entries) / total_weight

            if len(entries) > 1:
                variance = sum(w * ((ws / w) - mean) ** 2 for ws, w in entries) / total_weight
                std = math.sqrt(max(0, variance)) + 0.008  # minimum ≈0.8 pp
            else:
                std = 0.025  # 2.5 pp default for single poll

            result[party] = {"vote_share_mean": mean, "vote_share_std": std}

        return result

