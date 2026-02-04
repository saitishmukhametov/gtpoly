"""Tests for position tracking and rebalancing."""

import pytest
from rebalancer import Position, PositionTracker, Rebalancer, RebalanceOrder


class TestPosition:
    """Tests for Position dataclass."""

    def test_net_position_long_yes(self):
        pos = Position("m1", yes_position=100, no_position=50)
        assert pos.net_position == 50

    def test_net_position_long_no(self):
        pos = Position("m1", yes_position=30, no_position=70)
        assert pos.net_position == -40

    def test_total_exposure(self):
        pos = Position("m1", yes_position=100, no_position=50)
        assert pos.total_exposure == 150

    def test_skew_positive(self):
        pos = Position("m1", yes_position=100, no_position=50)
        # skew = (100-50)/(100+50) = 50/150 = 0.333
        assert abs(pos.skew - 0.333) < 0.01

    def test_skew_negative(self):
        pos = Position("m1", yes_position=30, no_position=70)
        # skew = (30-70)/(30+70) = -40/100 = -0.4
        assert pos.skew == -0.4

    def test_skew_neutral(self):
        pos = Position("m1", yes_position=50, no_position=50)
        assert pos.skew == 0.0

    def test_skew_empty(self):
        pos = Position("m1")
        assert pos.skew == 0.0

    def test_value(self):
        pos = Position("m1", yes_position=100, no_position=50,
                       yes_price=0.6, no_price=0.4)
        # value = 100*0.6 + 50*0.4 = 60 + 20 = 80
        assert pos.value() == 80


class TestPositionTracker:
    """Tests for PositionTracker."""

    def test_get_nonexistent_position(self):
        tracker = PositionTracker()
        assert tracker.get_position("unknown") is None

    def test_update_creates_position(self):
        tracker = PositionTracker()
        tracker.update_position("m1", "YES", "BUY", 100, 0.5)
        pos = tracker.get_position("m1")
        assert pos is not None
        assert pos.yes_position == 100
        assert pos.no_position == 0

    def test_update_buy_yes(self):
        tracker = PositionTracker()
        tracker.update_position("m1", "YES", "BUY", 100, 0.5)
        pos = tracker.get_position("m1")
        assert pos.yes_position == 100

    def test_update_sell_yes(self):
        tracker = PositionTracker()
        tracker.update_position("m1", "YES", "BUY", 100, 0.5)
        tracker.update_position("m1", "YES", "SELL", 30, 0.55)
        pos = tracker.get_position("m1")
        assert pos.yes_position == 70

    def test_update_buy_no(self):
        tracker = PositionTracker()
        tracker.update_position("m1", "NO", "BUY", 50, 0.45)
        pos = tracker.get_position("m1")
        assert pos.no_position == 50

    def test_update_prices(self):
        tracker = PositionTracker()
        tracker.update_position("m1", "YES", "BUY", 100, 0.5)
        tracker.update_prices("m1", 0.6, 0.4)
        pos = tracker.get_position("m1")
        assert pos.yes_price == 0.6
        assert pos.no_price == 0.4

    def test_all_positions(self):
        tracker = PositionTracker()
        tracker.update_position("m1", "YES", "BUY", 100, 0.5)
        tracker.update_position("m2", "NO", "BUY", 50, 0.4)
        positions = tracker.all_positions()
        assert len(positions) == 2


class TestRebalancer:
    """Tests for Rebalancer."""

    def test_needs_rebalancing_above_threshold(self):
        tracker = PositionTracker()
        tracker.update_position("m1", "YES", "BUY", 100, 0.5)
        tracker.update_position("m1", "NO", "BUY", 50, 0.5)
        # skew = 50/150 = 0.333 > 0.20

        rebalancer = Rebalancer(tracker, skew_threshold=0.20)
        assert rebalancer.needs_rebalancing("m1") is True

    def test_needs_rebalancing_below_threshold(self):
        tracker = PositionTracker()
        tracker.update_position("m1", "YES", "BUY", 55, 0.5)
        tracker.update_position("m1", "NO", "BUY", 45, 0.5)
        # skew = 10/100 = 0.10 < 0.20

        rebalancer = Rebalancer(tracker, skew_threshold=0.20)
        assert rebalancer.needs_rebalancing("m1") is False

    def test_needs_rebalancing_exactly_at_threshold(self):
        tracker = PositionTracker()
        tracker.update_position("m1", "YES", "BUY", 60, 0.5)
        tracker.update_position("m1", "NO", "BUY", 40, 0.5)
        # skew = 20/100 = 0.20 == 0.20 (not > threshold)

        rebalancer = Rebalancer(tracker, skew_threshold=0.20)
        assert rebalancer.needs_rebalancing("m1") is False

    def test_needs_rebalancing_nonexistent(self):
        tracker = PositionTracker()
        rebalancer = Rebalancer(tracker)
        assert rebalancer.needs_rebalancing("unknown") is False

    def test_compute_rebalance_orders_long_yes(self):
        """Long YES position should sell YES and buy NO."""
        tracker = PositionTracker()
        tracker.update_position("m1", "YES", "BUY", 100, 0.55)
        tracker.update_position("m1", "NO", "BUY", 50, 0.45)
        tracker.update_prices("m1", 0.55, 0.45)

        rebalancer = Rebalancer(tracker, skew_threshold=0.20, target_skew=0.0)
        orders = rebalancer.compute_rebalance_orders("m1")

        assert len(orders) == 2

        # Find sell YES order
        sell_yes = [o for o in orders if o.token == "YES" and o.side == "SELL"]
        assert len(sell_yes) == 1
        assert sell_yes[0].size == 25  # Need to sell 25 YES to get to 75

        # Find buy NO order
        buy_no = [o for o in orders if o.token == "NO" and o.side == "BUY"]
        assert len(buy_no) == 1
        assert buy_no[0].size == 25  # Need to buy 25 NO to get to 75

    def test_compute_rebalance_orders_long_no(self):
        """Long NO position should sell NO and buy YES."""
        tracker = PositionTracker()
        tracker.update_position("m1", "YES", "BUY", 50, 0.55)
        tracker.update_position("m1", "NO", "BUY", 100, 0.45)
        tracker.update_prices("m1", 0.55, 0.45)

        rebalancer = Rebalancer(tracker, skew_threshold=0.20, target_skew=0.0)
        orders = rebalancer.compute_rebalance_orders("m1")

        assert len(orders) == 2

        # Find sell NO order
        sell_no = [o for o in orders if o.token == "NO" and o.side == "SELL"]
        assert len(sell_no) == 1
        assert sell_no[0].size == 25

        # Find buy YES order
        buy_yes = [o for o in orders if o.token == "YES" and o.side == "BUY"]
        assert len(buy_yes) == 1
        assert buy_yes[0].size == 25

    def test_compute_rebalance_orders_no_action_needed(self):
        """No orders when below threshold."""
        tracker = PositionTracker()
        tracker.update_position("m1", "YES", "BUY", 55, 0.5)
        tracker.update_position("m1", "NO", "BUY", 45, 0.5)

        rebalancer = Rebalancer(tracker, skew_threshold=0.20)
        orders = rebalancer.compute_rebalance_orders("m1")

        assert len(orders) == 0

    def test_check_all_positions(self):
        """Check all positions returns orders for imbalanced markets."""
        tracker = PositionTracker()
        # m1: skew = 0.333 > 0.20 (needs rebalancing)
        tracker.update_position("m1", "YES", "BUY", 100, 0.5)
        tracker.update_position("m1", "NO", "BUY", 50, 0.5)
        # m2: skew = 0.10 < 0.20 (no rebalancing)
        tracker.update_position("m2", "YES", "BUY", 55, 0.5)
        tracker.update_position("m2", "NO", "BUY", 45, 0.5)

        rebalancer = Rebalancer(tracker, skew_threshold=0.20)
        results = rebalancer.check_all_positions()

        assert "m1" in results
        assert "m2" not in results
        assert len(results["m1"]) == 2


class TestRebalanceOrder:
    """Tests for RebalanceOrder."""

    def test_order_fields(self):
        order = RebalanceOrder(
            condition_id="m1",
            side="SELL",
            token="YES",
            size=25.0,
            price=0.55
        )
        assert order.condition_id == "m1"
        assert order.side == "SELL"
        assert order.token == "YES"
        assert order.size == 25.0
        assert order.price == 0.55


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
