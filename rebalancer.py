"""Position tracking and rebalancing module.

Tracks positions and rebalances when skew exceeds threshold.
Sells overweight side, buys underweight side.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Position:
    """Represents a position in a two-sided market."""

    condition_id: str
    yes_position: float = 0.0
    no_position: float = 0.0
    yes_price: float = 0.5
    no_price: float = 0.5

    @property
    def net_position(self) -> float:
        """Net position: positive = long YES, negative = long NO."""
        return self.yes_position - self.no_position

    @property
    def total_exposure(self) -> float:
        """Total gross exposure."""
        return self.yes_position + self.no_position

    @property
    def skew(self) -> float:
        """Position skew as ratio. Range: [-1, 1]."""
        if self.total_exposure == 0:
            return 0.0
        return self.net_position / self.total_exposure

    def value(self) -> float:
        """Current position value."""
        return (self.yes_position * self.yes_price +
                self.no_position * self.no_price)


@dataclass
class RebalanceOrder:
    """Order to execute for rebalancing."""

    condition_id: str
    side: str  # "BUY" or "SELL"
    token: str  # "YES" or "NO"
    size: float
    price: float


class PositionTracker:
    """Tracks positions across multiple markets."""

    def __init__(self):
        self._positions: dict[str, Position] = {}

    def get_position(self, condition_id: str) -> Optional[Position]:
        """Get position for a market."""
        return self._positions.get(condition_id)

    def update_position(
        self,
        condition_id: str,
        token: str,
        side: str,
        size: float,
        price: float
    ) -> Position:
        """Update position after a trade.

        Args:
            condition_id: Market identifier
            token: "YES" or "NO"
            side: "BUY" or "SELL"
            size: Trade size
            price: Trade price

        Returns:
            Updated position
        """
        if condition_id not in self._positions:
            self._positions[condition_id] = Position(condition_id=condition_id)

        pos = self._positions[condition_id]

        # Update position based on trade
        delta = size if side == "BUY" else -size

        if token == "YES":
            pos.yes_position += delta
        else:
            pos.no_position += delta

        return pos

    def update_prices(
        self,
        condition_id: str,
        yes_price: float,
        no_price: float
    ) -> None:
        """Update market prices for a position."""
        if condition_id in self._positions:
            self._positions[condition_id].yes_price = yes_price
            self._positions[condition_id].no_price = no_price

    def all_positions(self) -> list[Position]:
        """Return all tracked positions."""
        return list(self._positions.values())


class Rebalancer:
    """Rebalances positions when skew exceeds threshold.

    When skew exceeds the threshold (default 20%):
    - Sells the overweight side
    - Buys the underweight side
    """

    def __init__(
        self,
        tracker: PositionTracker,
        skew_threshold: float = 0.20,
        target_skew: float = 0.0
    ):
        """Initialize rebalancer.

        Args:
            tracker: Position tracker instance
            skew_threshold: Trigger rebalancing when |skew| > threshold (default 20%)
            target_skew: Target skew after rebalancing (default 0 = neutral)
        """
        self.tracker = tracker
        self.skew_threshold = skew_threshold
        self.target_skew = target_skew

    def needs_rebalancing(self, condition_id: str) -> bool:
        """Check if position needs rebalancing.

        Returns True if |skew| > threshold.
        """
        pos = self.tracker.get_position(condition_id)
        if pos is None:
            return False
        return abs(pos.skew) > self.skew_threshold

    def compute_rebalance_orders(
        self,
        condition_id: str
    ) -> list[RebalanceOrder]:
        """Compute orders to rebalance a position.

        Sells overweight side, buys underweight side to reach target skew.

        Returns:
            List of orders to execute (may be empty if no rebalancing needed)
        """
        pos = self.tracker.get_position(condition_id)
        if pos is None or not self.needs_rebalancing(condition_id):
            return []

        orders = []
        current_skew = pos.skew

        # Calculate target positions
        # Target: (yes - no) / (yes + no) = target_skew
        # If target_skew = 0, then yes = no
        total = pos.total_exposure
        target_yes = total * (1 + self.target_skew) / 2
        target_no = total * (1 - self.target_skew) / 2

        yes_delta = target_yes - pos.yes_position
        no_delta = target_no - pos.no_position

        # Generate orders
        # Positive delta = need to buy, negative = need to sell

        if current_skew > 0:
            # Long YES (overweight) -> sell YES, buy NO
            if yes_delta < 0:
                orders.append(RebalanceOrder(
                    condition_id=condition_id,
                    side="SELL",
                    token="YES",
                    size=abs(yes_delta),
                    price=pos.yes_price
                ))
            if no_delta > 0:
                orders.append(RebalanceOrder(
                    condition_id=condition_id,
                    side="BUY",
                    token="NO",
                    size=abs(no_delta),
                    price=pos.no_price
                ))
        else:
            # Long NO (overweight) -> sell NO, buy YES
            if no_delta < 0:
                orders.append(RebalanceOrder(
                    condition_id=condition_id,
                    side="SELL",
                    token="NO",
                    size=abs(no_delta),
                    price=pos.no_price
                ))
            if yes_delta > 0:
                orders.append(RebalanceOrder(
                    condition_id=condition_id,
                    side="BUY",
                    token="YES",
                    size=abs(yes_delta),
                    price=pos.yes_price
                ))

        return orders

    def check_all_positions(self) -> dict[str, list[RebalanceOrder]]:
        """Check all positions and return rebalancing orders needed.

        Returns:
            Dict mapping condition_id to list of rebalance orders
        """
        result = {}
        for pos in self.tracker.all_positions():
            orders = self.compute_rebalance_orders(pos.condition_id)
            if orders:
                result[pos.condition_id] = orders
        return result


# Example usage
if __name__ == "__main__":
    # Create tracker and rebalancer
    tracker = PositionTracker()
    rebalancer = Rebalancer(tracker, skew_threshold=0.20)

    # Simulate some trades that create an imbalanced position
    market_id = "market_001"

    # Buy more YES than NO -> creates positive skew
    tracker.update_position(market_id, "YES", "BUY", 100, 0.55)
    tracker.update_position(market_id, "NO", "BUY", 50, 0.45)
    tracker.update_prices(market_id, 0.55, 0.45)

    pos = tracker.get_position(market_id)
    print(f"Position: YES={pos.yes_position}, NO={pos.no_position}")
    print(f"Skew: {pos.skew:.2%}")
    print(f"Needs rebalancing: {rebalancer.needs_rebalancing(market_id)}")

    # Get rebalance orders
    orders = rebalancer.compute_rebalance_orders(market_id)
    print("\nRebalance orders:")
    for order in orders:
        print(f"  {order.side} {order.size:.2f} {order.token} @ {order.price}")
