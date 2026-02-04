"""Quant manager for LP spread calculations."""

import math


def calculate_spread(base_spread: float, volume_24h: float) -> float:
    """
    Calculate LP spread adjusted for 24h trading volume.

    High volume = tighter spread (more liquidity, less risk).

    Formula: spread = base - log10(volume/1000) * 0.005

    Args:
        base_spread: Base spread percentage (e.g., 0.03 for 3%)
        volume_24h: 24-hour trading volume in base currency

    Returns:
        Adjusted spread, clamped to minimum of 0.001 (0.1%)
    """
    if volume_24h <= 0:
        return base_spread

    # Avoid log of values less than 1 (which give negative results)
    volume_ratio = max(volume_24h / 1000, 1.0)

    adjustment = math.log10(volume_ratio) * 0.005
    adjusted_spread = base_spread - adjustment

    # Ensure spread doesn't go below minimum
    min_spread = 0.001
    return max(adjusted_spread, min_spread)


class QuantManager:
    """Manages quantitative parameters for liquidity provision."""

    def __init__(self, base_spread: float = 0.03):
        """
        Initialize QuantManager.

        Args:
            base_spread: Default base spread (default 3%)
        """
        self.base_spread = base_spread

    def get_spread(self, volume_24h: float) -> float:
        """
        Get volume-adjusted spread.

        Args:
            volume_24h: 24-hour trading volume

        Returns:
            Volume-weighted spread
        """
        return calculate_spread(self.base_spread, volume_24h)
