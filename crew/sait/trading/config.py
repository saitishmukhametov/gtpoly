"""
Trading configuration for Polymarket.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TradingConfig:
    signing_key: str
    funder: str
    signature_type: int
    host: str
    chain_id: int


# Polygon mainnet
POLYGON_CHAIN_ID = 137
CLOB_HOST = "https://clob.polymarket.com"


def get_config() -> TradingConfig:
    """Get the trading configuration."""
    return TradingConfig(
        signing_key="0xdeb8bd100077f42d5a7ee9578b6ba09970a8ab028d30a44515de2b7b4a44837a",
        funder="0x9d3347c6637c6481c664e51038aaa449dbad74ed",
        signature_type=1,  # POLY_PROXY
        host=CLOB_HOST,
        chain_id=POLYGON_CHAIN_ID,
    )
