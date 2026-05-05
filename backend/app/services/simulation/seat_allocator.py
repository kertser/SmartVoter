"""
Seat allocation engine — Phase 14B.

SIMPLIFIED: uses Hare quota + largest remainder (Hamilton method).
Israeli law uses Bader-Ofer (highest averages / modified D'Hondt) — planned Phase 6.
This simplification is clearly marked in all outputs.

Per AGENTS.MD Section 14B.4.
"""

import math

THRESHOLD_PERCENT = 3.25   # Israel: 3.25%
TOTAL_SEATS = 120


class SeatAllocator:
    """
    Deterministic seat allocation from vote shares.
    Currently: Hare quota + largest remainder (simplified).
    Bader-Ofer (actual Israeli law) is planned for a later phase.
    """

    def __init__(
        self,
        threshold_percent: float = THRESHOLD_PERCENT,
        total_seats: int = TOTAL_SEATS,
    ):
        self.threshold_percent = threshold_percent
        self.total_seats = total_seats

    def allocate(self, vote_shares: dict[str, float]) -> dict[str, int]:
        """
        Allocate seats.

        Args:
            vote_shares: {party_name: raw vote share (0..1), unnormalized OK}

        Returns:
            {party_name: seats}  — parties below threshold receive 0.
        """
        total = sum(vote_shares.values())
        if total <= 0:
            return {p: 0 for p in vote_shares}

        # Threshold filter
        passed = {
            p: v for p, v in vote_shares.items()
            if (v / total) * 100 >= self.threshold_percent
        }
        failed = {p: 0 for p in vote_shares if p not in passed}

        if not passed:
            return {**failed}

        # Normalise to passed-parties total
        passed_total = sum(passed.values())
        normalised = {p: v / passed_total for p, v in passed.items()}

        # Hare quota
        hare_q = 1.0 / self.total_seats
        base: dict[str, int] = {p: math.floor(v / hare_q) for p, v in normalised.items()}
        remainders = {p: (v / hare_q) - math.floor(v / hare_q) for p, v in normalised.items()}

        allocated = sum(base.values())
        remaining = self.total_seats - allocated

        # Distribute remainder seats by largest remainder
        for p in sorted(remainders, key=lambda x: remainders[x], reverse=True)[:remaining]:
            base[p] += 1

        return {**base, **failed}

    def allocate_from_counts(self, vote_counts: dict[str, int]) -> dict[str, int]:
        total = sum(vote_counts.values())
        shares = {p: c / total for p, c in vote_counts.items()} if total else {}
        return self.allocate(shares)

    def threshold_pass_probability(
        self,
        vote_share_mean: float,
        vote_share_std: float,
        n_samples: int = 2000,
    ) -> float:
        """
        Quick Monte Carlo estimate of probability that a party exceeds threshold.
        Uses total vote share (not normalised).
        """
        import random
        passes = sum(
            1 for _ in range(n_samples)
            if (vote_share_mean + random.gauss(0, vote_share_std)) * 100 >= self.threshold_percent
        )
        return passes / n_samples

