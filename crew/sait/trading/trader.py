"""
High-level trading operations for Polymarket.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from py_clob_client import OrderType
from .client import PolyClient
from .config import TradingConfig


@dataclass
class Position:
    """Represents a position in a market."""
    token_id: str
    side: str
    size: float
    avg_price: float
    market_price: float

    @property
    def pnl(self) -> float:
        """Unrealized P&L."""
        if self.side == "BUY":
            return (self.market_price - self.avg_price) * self.size
        return (self.avg_price - self.market_price) * self.size


@dataclass
class MarketInfo:
    """Simplified market information."""
    condition_id: str
    question: str
    tokens: List[Dict[str, Any]]
    active: bool
    closed: bool


class Trader:
    """
    High-level trading interface for Polymarket.

    Provides simplified methods for common trading operations.
    """

    def __init__(self, config: Optional[TradingConfig] = None):
        self.poly = PolyClient(config)

    @property
    def address(self) -> str:
        """Get the trader's wallet address."""
        return self.poly.address

    def find_markets(self, query: str = None, limit: int = 10) -> List[MarketInfo]:
        """
        Find markets, optionally filtering by query string.

        Args:
            query: Optional search string to filter markets
            limit: Maximum number of markets to return
        """
        markets = []
        cursor = "MA=="

        while len(markets) < limit:
            response = self.poly.get_markets(cursor)
            data = response.get("data", [])

            if not data:
                break

            for m in data:
                if query is None or query.lower() in m.get("question", "").lower():
                    markets.append(MarketInfo(
                        condition_id=m.get("condition_id"),
                        question=m.get("question"),
                        tokens=m.get("tokens", []),
                        active=m.get("active", False),
                        closed=m.get("closed", False),
                    ))
                    if len(markets) >= limit:
                        break

            cursor = response.get("next_cursor")
            if cursor == "LTE=":
                break

        return markets

    def get_market_price(self, token_id: str) -> Dict[str, float]:
        """
        Get current market prices for a token.

        Returns:
            Dict with 'bid', 'ask', 'mid', 'spread' prices
        """
        book = self.poly.get_order_book(token_id)
        result = {
            "bid": 0.0,
            "ask": 0.0,
            "mid": 0.0,
            "spread": 0.0,
        }

        if book.bids:
            result["bid"] = float(book.bids[0].price)
        if book.asks:
            result["ask"] = float(book.asks[0].price)

        if result["bid"] and result["ask"]:
            result["mid"] = (result["bid"] + result["ask"]) / 2
            result["spread"] = result["ask"] - result["bid"]

        return result

    def buy(
        self,
        token_id: str,
        size: float,
        price: float = None,
        order_type: OrderType = OrderType.GTC,
    ) -> Dict[str, Any]:
        """
        Place a buy order.

        Args:
            token_id: The token to buy
            size: Number of shares to buy
            price: Limit price. If None, uses current ask price.
            order_type: Order type (GTC, FOK, GTD)

        Returns:
            Order response from the exchange
        """
        if price is None:
            prices = self.get_market_price(token_id)
            price = prices["ask"]
            if price == 0:
                raise ValueError("No ask price available")

        return self.poly.create_and_post_order(
            token_id=token_id,
            price=price,
            size=size,
            side="BUY",
            order_type=order_type,
        )

    def sell(
        self,
        token_id: str,
        size: float,
        price: float = None,
        order_type: OrderType = OrderType.GTC,
    ) -> Dict[str, Any]:
        """
        Place a sell order.

        Args:
            token_id: The token to sell
            size: Number of shares to sell
            price: Limit price. If None, uses current bid price.
            order_type: Order type (GTC, FOK, GTD)

        Returns:
            Order response from the exchange
        """
        if price is None:
            prices = self.get_market_price(token_id)
            price = prices["bid"]
            if price == 0:
                raise ValueError("No bid price available")

        return self.poly.create_and_post_order(
            token_id=token_id,
            price=price,
            size=size,
            side="SELL",
            order_type=order_type,
        )

    def buy_market(self, token_id: str, amount: float) -> Dict[str, Any]:
        """
        Place a market buy order.

        Args:
            token_id: The token to buy
            amount: Dollar amount to spend

        Returns:
            Order response from the exchange
        """
        order = self.poly.create_market_order(
            token_id=token_id,
            amount=amount,
            side="BUY",
        )
        return self.poly.post_order(order, OrderType.FOK)

    def sell_market(self, token_id: str, size: float) -> Dict[str, Any]:
        """
        Place a market sell order.

        Args:
            token_id: The token to sell
            size: Number of shares to sell

        Returns:
            Order response from the exchange
        """
        order = self.poly.create_market_order(
            token_id=token_id,
            amount=size,
            side="SELL",
        )
        return self.poly.post_order(order, OrderType.FOK)

    def get_open_orders(self, market: str = None) -> List[Dict[str, Any]]:
        """Get all open orders, optionally filtered by market."""
        return self.poly.get_orders(market=market)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel a specific order."""
        return self.poly.cancel_order(order_id)

    def cancel_all_orders(self) -> Dict[str, Any]:
        """Cancel all open orders."""
        return self.poly.cancel_all_orders()

    def get_balance(self) -> Dict[str, Any]:
        """Get USDC balance and allowance."""
        return self.poly.get_balance()

    def get_trades(self, market: str = None) -> List[Dict[str, Any]]:
        """Get trade history."""
        return self.poly.get_trades(market=market)
