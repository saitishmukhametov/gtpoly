"""HFT State Manager - Market cache and position tracking.

Caches market metadata to avoid API calls during trading.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Market:
    """Market metadata."""
    market_id: str
    question: str
    yes_token_id: str
    no_token_id: str
    active: bool = True


@dataclass
class Position:
    """Position in a market."""
    market_id: str
    yes_shares: float = 0.0
    no_shares: float = 0.0
    avg_yes_price: float = 0.0
    avg_no_price: float = 0.0


@dataclass
class Fill:
    """Executed trade fill."""
    market_id: str
    token_id: str
    side: str  # 'buy' or 'sell'
    price: float
    size: float
    timestamp: int


class StateManager:
    """Manages HFT state: market cache, positions, and fills."""

    def __init__(self, max_fills: int = 1000):
        self._token_to_market: dict[str, str] = {}
        self._markets: dict[str, Market] = {}
        self._positions: dict[str, Position] = {}
        self._fills: deque[Fill] = deque(maxlen=max_fills)

    def add_market(self, market: Market) -> None:
        """Cache a market and index its tokens."""
        self._markets[market.market_id] = market
        self._token_to_market[market.yes_token_id] = market.market_id
        self._token_to_market[market.no_token_id] = market.market_id

    def get_market(self, market_id: str) -> Optional[Market]:
        """Get market by ID."""
        return self._markets.get(market_id)

    def get_market_by_token(self, token_id: str) -> Optional[Market]:
        """Get market by token ID (yes or no)."""
        market_id = self._token_to_market.get(token_id)
        if market_id:
            return self._markets.get(market_id)
        return None

    def get_tokens(self, market_id: str) -> Optional[tuple[str, str]]:
        """Get (yes_token, no_token) for a market."""
        market = self._markets.get(market_id)
        if market:
            return (market.yes_token_id, market.no_token_id)
        return None

    def is_yes_token(self, token_id: str) -> Optional[bool]:
        """Check if token is yes side. Returns None if unknown."""
        market = self.get_market_by_token(token_id)
        if market:
            return token_id == market.yes_token_id
        return None

    def update_position(self, market_id: str, side: str, is_buy: bool,
                        price: float, size: float) -> None:
        """Update position after a fill."""
        if market_id not in self._positions:
            self._positions[market_id] = Position(market_id=market_id)

        pos = self._positions[market_id]

        if side == 'yes':
            if is_buy:
                total_cost = pos.yes_shares * pos.avg_yes_price + size * price
                pos.yes_shares += size
                pos.avg_yes_price = total_cost / pos.yes_shares if pos.yes_shares > 0 else 0
            else:
                pos.yes_shares -= size
                if pos.yes_shares <= 0:
                    pos.yes_shares = 0
                    pos.avg_yes_price = 0
        else:  # no
            if is_buy:
                total_cost = pos.no_shares * pos.avg_no_price + size * price
                pos.no_shares += size
                pos.avg_no_price = total_cost / pos.no_shares if pos.no_shares > 0 else 0
            else:
                pos.no_shares -= size
                if pos.no_shares <= 0:
                    pos.no_shares = 0
                    pos.avg_no_price = 0

    def get_position(self, market_id: str) -> Optional[Position]:
        """Get position for a market."""
        return self._positions.get(market_id)

    def get_all_positions(self) -> dict[str, Position]:
        """Get all positions."""
        return dict(self._positions)

    def record_fill(self, fill: Fill) -> None:
        """Record a fill and update position."""
        self._fills.append(fill)

        market = self.get_market_by_token(fill.token_id)
        if market:
            is_yes = fill.token_id == market.yes_token_id
            side = 'yes' if is_yes else 'no'
            is_buy = fill.side == 'buy'
            self.update_position(market.market_id, side, is_buy, fill.price, fill.size)

    def get_recent_fills(self, n: Optional[int] = None) -> list[Fill]:
        """Get recent fills, optionally limited to n."""
        if n is None:
            return list(self._fills)
        return list(self._fills)[-n:]

    def clear_market(self, market_id: str) -> None:
        """Remove a market from cache."""
        market = self._markets.pop(market_id, None)
        if market:
            self._token_to_market.pop(market.yes_token_id, None)
            self._token_to_market.pop(market.no_token_id, None)

    @property
    def market_count(self) -> int:
        """Number of cached markets."""
        return len(self._markets)

    @property
    def position_count(self) -> int:
        """Number of positions."""
        return len(self._positions)
