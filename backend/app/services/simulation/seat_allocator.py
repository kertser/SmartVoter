"""
Seat allocation engine — Phase 14B.

Implements the Bader-Ofer method (official Israeli law since 1992).
Bader-Ofer is a highest-averages method where parties may enter surplus-vote
agreements (hasdamat odafot) that cause their votes to be pooled when computing
the final highest-averages round.

For MVP we implement the base Bader-Ofer without surplus agreements, which is
equivalent to d'Hondt applied to the above-threshold parties.  Surplus-vote
agreements are tracked in the `surplus_agreements` parameter for future support.

Per AGENTS.MD Section 14B.4.
"""

import math
import random

THRESHOLD_PERCENT = 3.25   # Israel: 3.25%
TOTAL_SEATS = 120


class SeatAllocator:
    """
    Deterministic seat allocation using Bader-Ofer (d'Hondt variant),
    the official Israeli seat allocation law (Elections Law, Section 69a).

    Args:
        threshold_percent: electoral threshold (default 3.25%).
        total_seats: Knesset size (default 120).
        surplus_agreements: mapping of {party_name: partner_name} for
            paired surplus-vote (hasdamat odafot) agreements.  Partners'
            votes are pooled in the final highest-averages round.
            Defaults to empty (no agreements).
    """

    def __init__(
        self,
        threshold_percent: float = THRESHOLD_PERCENT,
        total_seats: int = TOTAL_SEATS,
        surplus_agreements: dict[str, str] | None = None,
    ):
        self.threshold_percent = threshold_percent
        self.total_seats = total_seats
        # Normalise surplus agreements to canonical pairs: smaller name → larger name
        self._surplus: dict[str, str] = {}
        for a, b in (surplus_agreements or {}).items():
            self._surplus[a] = b
            self._surplus[b] = a

    # ── Public API ────────────────────────────────────────────────────────────

    def allocate(self, vote_shares: dict[str, float]) -> dict[str, int]:
        """
        Allocate 120 Knesset seats using Bader-Ofer (d'Hondt).

        Args:
            vote_shares: {party_name: share_0_to_1}  (unnormalised OK)

        Returns:
            {party_name: seats}  (parties below threshold → 0)
        """
        total = sum(vote_shares.values())
        if total <= 0:
            return {p: 0 for p in vote_shares}

        threshold_frac = self.threshold_percent / 100.0
        passed = {p: v for p, v in vote_shares.items() if v / total >= threshold_frac}
        failed = {p: 0 for p in vote_shares if p not in passed}

        if not passed:
            return {**failed}

        seats = self._bader_ofer(passed)
        return {**seats, **failed}

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
        Monte Carlo estimate of P(party passes threshold).
        """
        if vote_share_std <= 0:
            return 1.0 if vote_share_mean * 100 >= self.threshold_percent else 0.0
        passes = sum(
            1 for _ in range(n_samples)
            if (vote_share_mean + random.gauss(0, vote_share_std)) * 100
            >= self.threshold_percent
        )
        return passes / n_samples

    # ── Bader-Ofer (d'Hondt) implementation ──────────────────────────────────

    def _bader_ofer(self, votes: dict[str, float]) -> dict[str, int]:
        """
        Pure d'Hondt / Bader-Ofer allocation (without surplus pooling for now).

        The d'Hondt method iteratively awards each seat to the party with the
        highest quotient  votes[p] / (seats_so_far[p] + 1).

        This is mathematically equivalent to Bader-Ofer without surplus agreements.
        When surplus_agreements are provided, partners' vote totals are first
        summed and allocated together, then split back proportionally —
        a simplified version of the statutory procedure.
        """
        seats: dict[str, int] = {p: 0 for p in votes}

        if self._surplus:
            seats = self._bader_ofer_with_surplus(votes)
        else:
            for _ in range(self.total_seats):
                # Highest quotient
                winner = max(votes, key=lambda p: votes[p] / (seats[p] + 1))
                seats[winner] += 1

        return seats

    def _bader_ofer_with_surplus(self, votes: dict[str, float]) -> dict[str, int]:
        """
        Bader-Ofer with surplus-vote agreements.
        1. Allocate seats to agreement *groups* (treating partners as one entity).
        2. Split the group's seats back to constituent parties proportionally.
        """
        # Build groups
        visited: set[str] = set()
        groups: list[list[str]] = []
        for p in votes:
            if p in visited:
                continue
            partner = self._surplus.get(p)
            if partner and partner in votes:
                groups.append([p, partner])
                visited.add(p)
                visited.add(partner)
            else:
                groups.append([p])
                visited.add(p)

        group_votes = {
            "_".join(sorted(g)): sum(votes[p] for p in g)
            for g in groups
        }
        group_seats: dict[str, int] = {gk: 0 for gk in group_votes}

        for _ in range(self.total_seats):
            winner = max(group_votes, key=lambda g: group_votes[g] / (group_seats[g] + 1))
            group_seats[winner] += 1

        # Split group seats back
        seats: dict[str, int] = {p: 0 for p in votes}
        for g in groups:
            gk = "_".join(sorted(g))
            total_g = sum(votes[p] for p in g) or 1.0
            n = group_seats[gk]
            # Proportional split with largest-remainder residual
            raw = {p: votes[p] / total_g * n for p in g}
            base = {p: math.floor(v) for p, v in raw.items()}
            remainder = n - sum(base.values())
            for p in sorted(raw, key=lambda x: raw[x] - math.floor(raw[x]), reverse=True)[
                :remainder
            ]:
                base[p] += 1
            for p in g:
                seats[p] = base[p]

        return seats

