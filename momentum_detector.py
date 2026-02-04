"""Market Momentum Detector

Tracks price velocity across markets. When price moves >2% in 1 minute,
places order in direction of momentum.
"""

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class PricePoint:
    price: float
    timestamp: float


@dataclass
class MarketState:
    prices: list[PricePoint] = field(default_factory=list)

    def add_price(self, price: float, timestamp: float | None = None):
        if timestamp is None:
            timestamp = time.time()
        self.prices.append(PricePoint(price, timestamp))
        self._cleanup_old_prices(timestamp)

    def _cleanup_old_prices(self, current_time: float):
        cutoff = current_time - 120  # Keep 2 minutes of history
        self.prices = [p for p in self.prices if p.timestamp >= cutoff]

    def get_velocity(self, window_seconds: float = 60.0) -> float | None:
        """Calculate price velocity over the given window.

        Returns percentage change per minute, or None if insufficient data.
        """
        if len(self.prices) < 2:
            return None

        current_time = self.prices[-1].timestamp
        window_start = current_time - window_seconds

        # Find oldest price in window
        oldest_in_window = None
        for p in self.prices:
            if p.timestamp >= window_start:
                oldest_in_window = p
                break

        if oldest_in_window is None or oldest_in_window == self.prices[-1]:
            return None

        current_price = self.prices[-1].price
        old_price = oldest_in_window.price

        if old_price == 0:
            return None

        pct_change = ((current_price - old_price) / old_price) * 100
        return pct_change


class MomentumDetector:
    """Detects momentum across markets and triggers orders."""

    MOMENTUM_THRESHOLD = 2.0  # 2% in 1 minute

    def __init__(self, order_callback: Callable[[str, str, float], None] | None = None):
        """
        Args:
            order_callback: Function called when momentum detected.
                           Signature: (market_id, direction, velocity)
                           direction is 'buy' or 'sell'
        """
        self.markets: dict[str, MarketState] = {}
        self.order_callback = order_callback

    def update_price(self, market_id: str, price: float, timestamp: float | None = None):
        """Update price for a market and check for momentum."""
        if market_id not in self.markets:
            self.markets[market_id] = MarketState()

        self.markets[market_id].add_price(price, timestamp)
        self._check_momentum(market_id)

    def _check_momentum(self, market_id: str):
        """Check if momentum threshold is exceeded and trigger order."""
        velocity = self.markets[market_id].get_velocity()

        if velocity is None:
            return

        if abs(velocity) >= self.MOMENTUM_THRESHOLD:
            direction = 'buy' if velocity > 0 else 'sell'
            self._place_order(market_id, direction, velocity)

    def _place_order(self, market_id: str, direction: str, velocity: float):
        """Place order in direction of momentum."""
        if self.order_callback:
            self.order_callback(market_id, direction, velocity)

    def get_all_velocities(self) -> dict[str, float | None]:
        """Get current velocity for all tracked markets."""
        return {
            market_id: state.get_velocity()
            for market_id, state in self.markets.items()
        }


if __name__ == '__main__':
    def on_order(market: str, direction: str, velocity: float):
        print(f"ORDER: {direction.upper()} {market} (velocity: {velocity:+.2f}%)")

    detector = MomentumDetector(order_callback=on_order)

    # Simulate price movement with momentum
    base_time = time.time()
    detector.update_price('BTC-USD', 50000.0, base_time)
    detector.update_price('BTC-USD', 50500.0, base_time + 20)
    detector.update_price('BTC-USD', 51100.0, base_time + 40)  # ~2.2% up in <1min

    print(f"Final velocities: {detector.get_all_velocities()}")
