"""
Coalition scenario generator — Phase 14B.
Per AGENTS.MD Section 14B.9 and 14B.10.

Outputs are CONDITIONAL SCENARIOS, never voting advice.
"""

from itertools import combinations


MINIMUM_MAJORITY = 61   # Knesset majority


class CoalitionSimulator:
    """
    Given a seat distribution, enumerate numerically viable coalitions
    and score them for feasibility, stability, and coherence.
    """

    def __init__(self, constraints: list[dict] | None = None):
        """
        constraints: [{'source': name, 'target': name, 'type': 'refuses'|'prefers',
                        'strength': 'hard'|'soft'}]
        """
        self.constraints = constraints or []
        # Pre-index hard refuses as frozensets (bidirectional)
        self._hard_refuses: set[frozenset[str]] = set()
        self._soft_refuses: set[frozenset[str]] = set()
        for c in self.constraints:
            pair = frozenset([c["source"], c["target"]])
            if c.get("type") == "refuses":
                if c.get("strength") == "hard":
                    self._hard_refuses.add(pair)
                else:
                    self._soft_refuses.add(pair)

    def generate_viable_coalitions(
        self,
        seat_distribution: dict[str, float],
        max_scenarios: int = 10,
    ) -> list[dict]:
        """
        Enumerate viable majority coalitions from mean seat counts.

        Args:
            seat_distribution: {party_name: mean_seats}  (parties below ~3 ignored)
            max_scenarios: return at most this many scenarios

        Returns:
            list of scenario dicts, sorted by probability estimate descending
        """
        # Only consider parties likely to have seats
        parties = [(p, s) for p, s in seat_distribution.items() if s >= 3.0]
        parties.sort(key=lambda x: -x[1])  # largest first

        scenarios: list[dict] = []

        for size in range(2, min(7, len(parties) + 1)):
            for combo in combinations(parties, size):
                members = [p for p, _ in combo]
                total_seats = sum(s for _, s in combo)

                if total_seats < MINIMUM_MAJORITY:
                    continue

                # Hard constraint check
                if any(
                    frozenset([members[i], members[j]]) in self._hard_refuses
                    for i in range(len(members))
                    for j in range(i + 1, len(members))
                ):
                    continue

                score = self._score(members, total_seats)
                scenarios.append({
                    "members": members,
                    "seat_mean": round(total_seats, 1),
                    "seat_p10": round(total_seats * 0.88, 1),
                    "seat_p90": round(total_seats * 1.12, 1),
                    **score,
                })

        scenarios.sort(key=lambda x: -x["probability_estimate"])
        return scenarios[:max_scenarios]

    def _score(self, members: list[str], total_seats: float) -> dict:
        seat_margin = (total_seats - MINIMUM_MAJORITY) / 60.0  # 0=bare, 1=supermajority

        soft_conflicts = sum(
            1 for i in range(len(members))
            for j in range(i + 1, len(members))
            if frozenset([members[i], members[j]]) in self._soft_refuses
        )

        feasibility = min(1.0, max(0.05, 0.70 + seat_margin * 0.30 - soft_conflicts * 0.15))
        stability   = min(1.0, max(0.05, 0.82 - (len(members) - 2) * 0.10 + seat_margin * 0.18))
        coherence   = min(1.0, max(0.05, 0.78 - soft_conflicts * 0.20))
        probability = round(feasibility * stability * coherence, 3)

        # Produce a non-editorial explanation
        parts = [f"{', '.join(members)}: {total_seats:.0f} seats"]
        if total_seats < 65:
            parts.append("Narrow majority — sensitive to party defections.")
        if soft_conflicts:
            parts.append(f"{soft_conflicts} soft constraint(s) between members.")

        return {
            "feasibility_score": round(feasibility, 3),
            "stability_score":   round(stability, 3),
            "ideological_coherence_score": round(coherence, 3),
            "probability_estimate": probability,
            "explanation": " ".join(parts),
        }

