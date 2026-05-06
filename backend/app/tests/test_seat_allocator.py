"""
Unit tests for the Bader-Ofer seat allocator.
Per AGENTS.MD Section 14B.14 acceptance criteria point 8.
"""
import pytest
from backend.app.services.simulation.seat_allocator import SeatAllocator

THRESHOLD = 3.25
SEATS = 120


@pytest.fixture
def allocator():
    return SeatAllocator(threshold_percent=THRESHOLD, total_seats=SEATS)


class TestThreshold:
    def test_party_below_threshold_gets_zero_seats(self, allocator):
        # large + medium together hold 97% → tiny = 0.001/0.971 ≈ 0.1% < 3.25%
        result = allocator.allocate({"large": 0.90, "medium": 0.07, "tiny": 0.001})
        assert result["tiny"] == 0

    def test_party_exactly_at_threshold_gets_seats(self, allocator):
        # 3.25% of total = at threshold ← should pass
        total = 100.0
        shares = {"A": 60.0, "B": 36.75, "edge": 3.25}
        result = allocator.allocate(shares)
        assert result["edge"] > 0

    def test_all_below_threshold_high_custom_threshold(self):
        # Use a 40% threshold so both A (30%) and B (70%) only A is below
        allocator_high = SeatAllocator(threshold_percent=40.0, total_seats=120)
        result = allocator_high.allocate({"A": 0.30, "B": 0.70})
        assert result["A"] == 0
        assert result["B"] == SEATS  # only B passes

    def test_empty_input(self, allocator):
        assert allocator.allocate({}) == {}


class TestSeatTotal:
    def test_seats_always_sum_to_120(self, allocator):
        shares = {"Likud": 0.25, "Yesh Atid": 0.20, "Shas": 0.10,
                  "National Unity": 0.12, "UTJ": 0.07, "Labor": 0.05,
                  "RA": 0.08, "Hadash": 0.04, "Otzma": 0.03, "tiny": 0.01}
        result = allocator.allocate(shares)
        assert sum(result.values()) == SEATS

    def test_single_party_above_threshold_gets_all_120(self, allocator):
        result = allocator.allocate({"A": 1.0})
        assert result["A"] == SEATS

    def test_two_equal_parties(self, allocator):
        result = allocator.allocate({"A": 0.50, "B": 0.50})
        assert result["A"] + result["B"] == SEATS
        # With Bader-Ofer (d'Hondt) equal parties split evenly
        assert abs(result["A"] - result["B"]) <= 1


class TestBaderOferProperties:
    def test_larger_party_gets_more_seats(self, allocator):
        result = allocator.allocate({"large": 0.40, "small": 0.10})
        assert result["large"] > result["small"]

    def test_proportionality_rough(self, allocator):
        # Large party at 40% should get roughly 40% of seats
        result = allocator.allocate({
            "A": 0.40, "B": 0.30, "C": 0.20, "D": 0.10
        })
        expected_a = round(0.40 * SEATS)
        assert abs(result["A"] - expected_a) <= 2  # within 2 seats

    def test_allocate_from_counts(self, allocator):
        result = allocator.allocate_from_counts({"A": 400000, "B": 300000, "C": 200000, "D": 100000})
        assert sum(result.values()) == SEATS

    def test_unnormalised_shares_give_same_result(self, allocator):
        shares_normalised = {"A": 0.50, "B": 0.30, "C": 0.20}
        shares_unnormalised = {"A": 50.0, "B": 30.0, "C": 20.0}
        r1 = allocator.allocate(shares_normalised)
        r2 = allocator.allocate(shares_unnormalised)
        assert r1 == r2


class TestThresholdPassProbability:
    def test_high_mean_gives_high_probability(self, allocator):
        prob = allocator.threshold_pass_probability(0.15, 0.01)
        assert prob > 0.95

    def test_low_mean_gives_low_probability(self, allocator):
        prob = allocator.threshold_pass_probability(0.01, 0.005)
        assert prob < 0.05

    def test_probability_bounded(self, allocator):
        prob = allocator.threshold_pass_probability(0.05, 0.02)
        assert 0.0 <= prob <= 1.0

    def test_zero_std_deterministic(self, allocator):
        prob_pass = allocator.threshold_pass_probability(0.10, 0.0)
        assert prob_pass == 1.0
        prob_fail = allocator.threshold_pass_probability(0.01, 0.0)
        assert prob_fail == 0.0


class TestSurplusAgreements:
    def test_surplus_partners_both_pass_threshold_pool_remainder(self):
        # Both A and B pass threshold individually.
        # Surplus agreement means their remainder mandates are pooled.
        # With surplus: the group {A+B} competes as a unit in d'Hondt,
        # then seats are split proportionally back to A and B.
        allocator_with = SeatAllocator(surplus_agreements={"A": "B"})
        allocator_without = SeatAllocator()
        shares = {"A": 0.20, "B": 0.15, "C": 0.40, "D": 0.25}
        r_with = allocator_with.allocate(shares)
        r_without = allocator_without.allocate(shares)
        # Both must sum to 120 and all parties above threshold get seats
        assert sum(r_with.values()) == SEATS
        assert sum(r_without.values()) == SEATS
        assert r_with["A"] + r_with["B"] > 0
        # A+B combined should be proportional to their share (35%)
        combined = r_with["A"] + r_with["B"]
        expected = round(0.35 * SEATS)
        assert abs(combined - expected) <= 2

    def test_no_surplus_agreements_matches_simple_allocator(self):
        shares = {"Likud": 0.25, "YA": 0.20, "Shas": 0.10, "NU": 0.12,
                  "UTJ": 0.07, "Labor": 0.05, "RA": 0.08, "Hadash": 0.05,
                  "Otzma": 0.04, "NR": 0.04}
        a1 = SeatAllocator()
        a2 = SeatAllocator(surplus_agreements={})
        r1 = a1.allocate(shares)
        r2 = a2.allocate(shares)
        assert r1 == r2



