"""
Polymarket CLOB client wrapper.
"""

from typing import Optional
from py_clob_client import (
    ClobClient,
    ApiCreds,
    OrderArgs,
    MarketOrderArgs,
    OrderType,
    BookParams,
    BalanceAllowanceParams,
    AssetType,
)
from .config import TradingConfig, get_config


class PolyClient:
    """
    Wrapper around py_clob_client.ClobClient for Polymarket trading.

    Supports three authentication levels:
    - L0: Public endpoints only (no key)
    - L1: Key-based auth (can create orders but not post)
    - L2: Full auth with API creds (can post orders)
    """

    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or get_config()
        self._client: Optional[ClobClient] = None
        self._creds: Optional[ApiCreds] = None

    @property
    def client(self) -> ClobClient:
        """Get or create the ClobClient instance."""
        if self._client is None:
            self._client = ClobClient(
                host=self.config.host,
                chain_id=self.config.chain_id,
                key=self.config.signing_key,
                signature_type=self.config.signature_type,
                funder=self.config.funder,
            )
        return self._client

    def init_l2(self) -> ApiCreds:
        """
        Initialize Level 2 authentication by creating or deriving API credentials.
        Required for posting orders and accessing private endpoints.
        """
        if self._creds is None:
            self._creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(self._creds)
        return self._creds

    @property
    def address(self) -> str:
        """Get the wallet address derived from the signing key."""
        return self.client.get_address()

    # Market data methods (L0)

    def get_markets(self, next_cursor: str = "MA=="):
        """Get all available markets."""
        return self.client.get_markets(next_cursor)

    def get_market(self, condition_id: str):
        """Get a specific market by condition ID."""
        return self.client.get_market(condition_id)

    def get_order_book(self, token_id: str):
        """Get the order book for a token."""
        return self.client.get_order_book(token_id)

    def get_midpoint(self, token_id: str):
        """Get the midpoint price for a token."""
        return self.client.get_midpoint(token_id)

    def get_price(self, token_id: str, side: str):
        """Get the best price for a token and side."""
        return self.client.get_price(token_id, side)

    def get_spread(self, token_id: str):
        """Get the spread for a token."""
        return self.client.get_spread(token_id)

    def get_last_trade_price(self, token_id: str):
        """Get the last trade price for a token."""
        return self.client.get_last_trade_price(token_id)

    # Order methods (L1 for create, L2 for post)

    def create_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        fee_rate_bps: int = 0,
    ):
        """
        Create a signed limit order (L1 auth).

        Args:
            token_id: The token to trade
            price: Price per share (0 < price < 1)
            size: Number of shares
            side: "BUY" or "SELL"
            fee_rate_bps: Fee rate in basis points
        """
        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=side,
            fee_rate_bps=fee_rate_bps,
        )
        return self.client.create_order(order_args)

    def create_market_order(
        self,
        token_id: str,
        amount: float,
        side: str,
        price: float = 0,
    ):
        """
        Create a signed market order (L1 auth).

        Args:
            token_id: The token to trade
            amount: For BUY: dollar amount. For SELL: number of shares.
            side: "BUY" or "SELL"
            price: Optional price limit
        """
        order_args = MarketOrderArgs(
            token_id=token_id,
            amount=amount,
            side=side,
            price=price,
        )
        return self.client.create_market_order(order_args)

    def post_order(self, order, order_type: OrderType = OrderType.GTC):
        """
        Post a signed order to the exchange (L2 auth required).

        Args:
            order: A signed order from create_order or create_market_order
            order_type: GTC (good til cancelled), FOK (fill or kill), GTD (good til date)
        """
        self.init_l2()
        return self.client.post_order(order, order_type)

    def create_and_post_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        order_type: OrderType = OrderType.GTC,
    ):
        """
        Create and post a limit order in one call (L2 auth required).
        """
        self.init_l2()
        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=side,
        )
        return self.client.create_and_post_order(order_args)

    # Order management (L2)

    def get_orders(self, market: str = None, asset_id: str = None):
        """Get open orders."""
        self.init_l2()
        from py_clob_client import OpenOrderParams
        params = OpenOrderParams(market=market, asset_id=asset_id)
        return self.client.get_orders(params)

    def get_order(self, order_id: str):
        """Get a specific order by ID."""
        self.init_l2()
        return self.client.get_order(order_id)

    def cancel_order(self, order_id: str):
        """Cancel a specific order."""
        self.init_l2()
        return self.client.cancel(order_id)

    def cancel_all_orders(self):
        """Cancel all open orders."""
        self.init_l2()
        return self.client.cancel_all()

    # Balance and allowance (L2)

    def get_balance(self, asset_type: AssetType = AssetType.COLLATERAL, token_id: str = None):
        """Get balance and allowance for an asset."""
        self.init_l2()
        params = BalanceAllowanceParams(
            asset_type=asset_type,
            token_id=token_id,
        )
        return self.client.get_balance_allowance(params)

    # Trade history (L2)

    def get_trades(self, market: str = None, asset_id: str = None):
        """Get trade history."""
        self.init_l2()
        from py_clob_client import TradeParams
        params = TradeParams(market=market, asset_id=asset_id)
        return self.client.get_trades(params)
