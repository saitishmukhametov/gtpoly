"""
Polymarket Trading Infrastructure

Uses py_clob_client to interact with Polymarket's CLOB.
"""

from .config import TradingConfig, get_config
from .client import PolyClient
from .trader import Trader

__all__ = [
    "TradingConfig",
    "get_config",
    "PolyClient",
    "Trader",
]
