"""
Order Book Depth Analysis

Analyzes CLOB (Central Limit Order Book) depth before placing orders.
Helps avoid thin books and prefer markets with sufficient liquidity.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderLevel:
    """A single price level in the order book."""
    price: float
    size: float

    @property
    def value(self) -> float:
        """Total value at this price level."""
        return self.price * self.size


@dataclass
class OrderBook:
    """Represents an order book with bids and asks."""
    bids: list[OrderLevel]  # Sorted descending by price (best bid first)
    asks: list[OrderLevel]  # Sorted ascending by price (best ask first)

    @property
    def best_bid(self) -> Optional[OrderLevel]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[OrderLevel]:
        return self.asks[0] if self.asks else None

    @property
    def spread(self) -> Optional[float]:
        """Bid-ask spread as a percentage of mid price."""
        if not self.best_bid or not self.best_ask:
            return None
        mid = (self.best_bid.price + self.best_ask.price) / 2
        return (self.best_ask.price - self.best_bid.price) / mid * 100


@dataclass
class DepthAnalysis:
    """Results of order book depth analysis."""
    bid_depth: float  # Total value on bid side
    ask_depth: float  # Total value on ask side
    is_sufficient: bool  # Whether depth meets minimum requirements
    spread_pct: Optional[float]  # Bid-ask spread percentage
    reason: str  # Human-readable explanation


class OrderBookAnalyzer:
    """
    Analyzes order book depth to determine if markets are suitable for trading.

    Avoids thin books by requiring minimum liquidity on both sides.
    """

    def __init__(
        self,
        min_depth_per_side: float = 1000.0,
        max_spread_pct: float = 1.0,
        depth_levels: int = 10
    ):
        """
        Initialize the analyzer.

        Args:
            min_depth_per_side: Minimum USD value required on each side
            max_spread_pct: Maximum acceptable spread as percentage
            depth_levels: Number of price levels to consider for depth
        """
        self.min_depth_per_side = min_depth_per_side
        self.max_spread_pct = max_spread_pct
        self.depth_levels = depth_levels

    def calculate_side_depth(self, levels: list[OrderLevel]) -> float:
        """Calculate total depth (value) for one side of the book."""
        return sum(level.value for level in levels[:self.depth_levels])

    def analyze(self, order_book: OrderBook) -> DepthAnalysis:
        """
        Analyze order book depth and determine if it's suitable for trading.

        Returns:
            DepthAnalysis with depth metrics and suitability assessment
        """
        bid_depth = self.calculate_side_depth(order_book.bids)
        ask_depth = self.calculate_side_depth(order_book.asks)
        spread = order_book.spread

        # Check if depth is sufficient on both sides
        reasons = []
        is_sufficient = True

        if bid_depth < self.min_depth_per_side:
            is_sufficient = False
            reasons.append(
                f"Bid depth ${bid_depth:.2f} below minimum ${self.min_depth_per_side:.2f}"
            )

        if ask_depth < self.min_depth_per_side:
            is_sufficient = False
            reasons.append(
                f"Ask depth ${ask_depth:.2f} below minimum ${self.min_depth_per_side:.2f}"
            )

        if spread is not None and spread > self.max_spread_pct:
            is_sufficient = False
            reasons.append(
                f"Spread {spread:.2f}% exceeds maximum {self.max_spread_pct:.2f}%"
            )

        if is_sufficient:
            reason = (
                f"Sufficient depth: bids ${bid_depth:.2f}, asks ${ask_depth:.2f}"
            )
        else:
            reason = "; ".join(reasons)

        return DepthAnalysis(
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            is_sufficient=is_sufficient,
            spread_pct=spread,
            reason=reason
        )

    def should_trade(self, order_book: OrderBook) -> bool:
        """Quick check if order book has sufficient depth for trading."""
        return self.analyze(order_book).is_sufficient


def analyze_depth(
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
    min_depth: float = 1000.0
) -> DepthAnalysis:
    """
    Convenience function to analyze order book depth.

    Args:
        bids: List of (price, size) tuples, best bid first
        asks: List of (price, size) tuples, best ask first
        min_depth: Minimum required depth per side in USD

    Returns:
        DepthAnalysis with results
    """
    order_book = OrderBook(
        bids=[OrderLevel(price=p, size=s) for p, s in bids],
        asks=[OrderLevel(price=p, size=s) for p, s in asks]
    )
    analyzer = OrderBookAnalyzer(min_depth_per_side=min_depth)
    return analyzer.analyze(order_book)
