"""
Monte Carlo Knesset simulator — Phase 14B.
Per AGENTS.MD Section 14B.6 and 14B.7.

IMPORTANT: All outputs are probabilistic SCENARIOS, not predictions.
Never convert simulation output to voting advice.
"""

import random
import statistics
from backend.app.services.simulation.seat_allocator import SeatAllocator


class KnessetSimulator:
    """
    Run Monte Carlo simulations over vote share distributions and produce
    probabilistic seat-count statistics for each party.
    """

    def __init__(self, n_iterations: int = 5000):
        self.n_iterations = n_iterations
        self.allocator = SeatAllocator()

    def run(
        self,
        poll_aggregate: dict[str, dict],
        party_volatility: dict[str, float] | None = None,
        volatility_multiplier: float = 0.5,
    ) -> dict[str, dict]:
        """
        Args:
            poll_aggregate: {party_name: {vote_share_mean, vote_share_std}}
            party_volatility: optional {party_name: 0..1} to widen uncertainty
            volatility_multiplier: how much volatility widens the std

        Returns:
            {party_name: {seats_mean, seats_median, seats_p10, seats_p25,
                           seats_p75, seats_p90, threshold_pass_probability,
                           vote_share_mean}}
        """
        party_volatility = party_volatility or {}
        parties = list(poll_aggregate.keys())
        seat_draws: dict[str, list[int]] = {p: [] for p in parties}

        for _ in range(self.n_iterations):
            sampled: dict[str, float] = {}
            for p in parties:
                agg = poll_aggregate[p]
                base_std = agg["vote_share_std"]
                vol = party_volatility.get(p, 0.0)
                adj_std = base_std * (1.0 + vol * volatility_multiplier)
                raw = agg["vote_share_mean"] + random.gauss(0, adj_std)
                sampled[p] = max(0.0, raw)

            seats = self.allocator.allocate(sampled)
            for p in parties:
                seat_draws[p].append(seats.get(p, 0))

        results: dict[str, dict] = {}
        for p in parties:
            draws = sorted(seat_draws[p])
            n = len(draws)
            above = sum(1 for s in draws if s > 0)
            results[p] = {
                "party_name": p,
                "seats_mean": round(statistics.mean(draws), 2),
                "seats_median": draws[n // 2],
                "seats_p10": draws[int(n * 0.10)],
                "seats_p25": draws[int(n * 0.25)],
                "seats_p75": draws[int(n * 0.75)],
                "seats_p90": draws[int(n * 0.90)],
                "threshold_pass_probability": round(above / n, 3),
                "vote_share_mean": poll_aggregate[p]["vote_share_mean"],
            }

        return results

