"""
Quant Manager - Handles LP order management and timeout cancellation.
"""
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"


@dataclass
class LPOrder:
    order_id: str
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    price: float
    created_at: datetime
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0


class QuantManager:
    """Manages LP orders with automatic timeout cancellation."""

    ORDER_TIMEOUT_MINUTES = 30

    def __init__(self):
        self.orders: Dict[str, LPOrder] = {}
        self._running = False

    def add_order(self, order: LPOrder) -> None:
        """Add a new LP order to track."""
        self.orders[order.order_id] = order

    def get_order(self, order_id: str) -> Optional[LPOrder]:
        """Get an order by ID."""
        return self.orders.get(order_id)

    def get_unfilled_orders(self) -> List[LPOrder]:
        """Get all unfilled orders (pending or partially filled)."""
        return [
            order for order in self.orders.values()
            if order.status in (OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED)
        ]

    def get_stale_orders(self) -> List[LPOrder]:
        """Get orders older than timeout threshold that are unfilled."""
        cutoff_time = datetime.now() - timedelta(minutes=self.ORDER_TIMEOUT_MINUTES)
        return [
            order for order in self.get_unfilled_orders()
            if order.created_at < cutoff_time
        ]

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID."""
        order = self.orders.get(order_id)
        if order and order.status in (OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED):
            order.status = OrderStatus.CANCELLED
            return True
        return False

    def cleanup_stale_orders(self) -> List[str]:
        """
        Cancel all LP orders older than 30 minutes if unfilled.
        Returns list of cancelled order IDs.
        """
        cancelled_ids = []
        stale_orders = self.get_stale_orders()

        for order in stale_orders:
            if self.cancel_order(order.order_id):
                cancelled_ids.append(order.order_id)

        return cancelled_ids

    def run_cleanup_loop(self, interval_seconds: float = 60.0) -> None:
        """
        Run continuous cleanup loop that checks order age and cancels stale orders.

        Args:
            interval_seconds: How often to check for stale orders (default: 60s)
        """
        self._running = True

        while self._running:
            cancelled = self.cleanup_stale_orders()
            if cancelled:
                print(f"[QuantManager] Cancelled {len(cancelled)} stale orders: {cancelled}")

            time.sleep(interval_seconds)

    def stop_cleanup_loop(self) -> None:
        """Stop the cleanup loop."""
        self._running = False


if __name__ == "__main__":
    # Example usage
    manager = QuantManager()

    # Add a test order
    test_order = LPOrder(
        order_id="test-001",
        symbol="BTC/USD",
        side="buy",
        quantity=1.0,
        price=50000.0,
        created_at=datetime.now() - timedelta(minutes=35),  # Already stale
    )
    manager.add_order(test_order)

    # Run single cleanup
    cancelled = manager.cleanup_stale_orders()
    print(f"Cancelled orders: {cancelled}")
