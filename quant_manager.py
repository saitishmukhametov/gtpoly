"""
Quant Manager - Mean reversion trading with momentum confirmation.

Only generates trade signals when z-score AND price momentum align.
"""

import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Signal(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class TradeSignal:
    signal: Signal
    z_score: float
    momentum: float
    reason: str


class QuantManager:
    """Mean reversion strategy with momentum confirmation."""

    def __init__(
        self,
        lookback_period: int = 20,
        z_threshold: float = 2.0,
        momentum_period: int = 10,
    ):
        """
        Initialize the quant manager.

        Args:
            lookback_period: Period for calculating mean and std deviation
            z_threshold: Z-score threshold for mean reversion signals
            momentum_period: Period for calculating price momentum
        """
        self.lookback_period = lookback_period
        self.z_threshold = z_threshold
        self.momentum_period = momentum_period

    def calculate_z_score(self, prices: np.ndarray) -> float:
        """Calculate z-score of the latest price relative to recent history."""
        if len(prices) < self.lookback_period:
            return 0.0

        recent = prices[-self.lookback_period:]
        mean = np.mean(recent)
        std = np.std(recent)

        if std == 0:
            return 0.0

        return (prices[-1] - mean) / std

    def calculate_momentum(self, prices: np.ndarray) -> float:
        """
        Calculate price momentum as rate of change.

        Positive momentum = price trending up
        Negative momentum = price trending down
        """
        if len(prices) < self.momentum_period:
            return 0.0

        return (prices[-1] - prices[-self.momentum_period]) / prices[-self.momentum_period]

    def generate_signal(self, prices: np.ndarray) -> TradeSignal:
        """
        Generate trade signal based on z-score and momentum alignment.

        Mean reversion logic with momentum confirmation:
        - BUY: z-score < -threshold (oversold) AND momentum turning positive
        - SELL: z-score > threshold (overbought) AND momentum turning negative
        - HOLD: z-score and momentum don't align

        Args:
            prices: Array of historical prices (most recent last)

        Returns:
            TradeSignal with signal type, z-score, momentum, and reason
        """
        z_score = self.calculate_z_score(prices)
        momentum = self.calculate_momentum(prices)

        # Mean reversion BUY: price oversold AND momentum confirms reversal
        if z_score < -self.z_threshold and momentum > 0:
            return TradeSignal(
                signal=Signal.BUY,
                z_score=z_score,
                momentum=momentum,
                reason=f"Oversold (z={z_score:.2f}) with positive momentum ({momentum:.4f})",
            )

        # Mean reversion SELL: price overbought AND momentum confirms reversal
        if z_score > self.z_threshold and momentum < 0:
            return TradeSignal(
                signal=Signal.SELL,
                z_score=z_score,
                momentum=momentum,
                reason=f"Overbought (z={z_score:.2f}) with negative momentum ({momentum:.4f})",
            )

        # No trade: z-score and momentum don't align
        return TradeSignal(
            signal=Signal.HOLD,
            z_score=z_score,
            momentum=momentum,
            reason=f"No alignment: z={z_score:.2f}, momentum={momentum:.4f}",
        )
