"""
Deploy full capital to high-volume LP orders.

Task: Deploy $24.92 USDC to top 5 volume markets with tight 1-cent spreads.
Goal: Maximize fill rate.
"""

import sys
import time

# Add crew/sait to path for imports
sys.path.insert(0, '/home/sait/gt/gtpoly/crew/sait')

from py_clob_client import OrderType
from trading.client import PolyClient
from trading.config import get_config
from trading.mm.scanner import MarketScanner


def deploy_lp(capital: float = 24.92, spread: float = 0.01, num_markets: int = 5):
    """
    Deploy capital to LP orders on high-volume markets.

    Args:
        capital: Total USDC to deploy
        spread: Spread in dollars (0.01 = 1 cent)
        num_markets: Number of markets to deploy to
    """
    MIN_ORDER_SIZE = 5.0  # Polymarket minimum

    print("=" * 60)
    print(f"DEPLOYING ${capital:.2f} TO {num_markets} HIGH-VOLUME MARKETS")
    print(f"Spread: ${spread:.2f} (tight for max fill rate)")
    print("=" * 60)

    # Init client
    poly = PolyClient(get_config())
    poly.init_l2()

    # Check balance
    bal = poly.get_balance()
    usdc_balance = int(bal['balance']) / 1e6
    print(f"\nCurrent USDC balance: ${usdc_balance:.2f}")

    if usdc_balance < capital:
        print(f"WARNING: Balance ${usdc_balance:.2f} < requested ${capital:.2f}")
        capital = usdc_balance

    # Cancel any existing orders first
    print("\nCancelling existing orders...")
    try:
        poly.cancel_all_orders()
        print("  ✓ Cancelled all existing orders")
    except Exception as e:
        print(f"  ✗ Cancel failed: {e}")

    # Scan for top volume markets
    print(f"\nScanning for top {num_markets} volume markets...")
    scanner = MarketScanner()
    markets = scanner.scan_markets(limit=50)

    # Filter: price between 0.35 and 0.65 (balanced range where both sides
    # can meet minimum order size efficiently)
    viable = [m for m in markets if 0.35 <= m.gamma_yes_price <= 0.65]

    # Sort by volume and take top N
    viable.sort(key=lambda m: -m.volume_24h)
    top_markets = viable[:num_markets]

    if len(top_markets) < num_markets:
        print(f"  ⚠ Only found {len(top_markets)} viable markets in 0.35-0.65 range")

    # Calculate capital allocation with minimum order sizes
    # With min 5 shares at ~$0.50 = $2.50 per order, 2 orders per market = $5 per market
    # So for 5 markets = $25 minimum. We have ~$25, so this should work.
    capital_per_market = capital / len(top_markets)

    print(f"\nCapital allocation:")
    print(f"  ${capital_per_market:.2f} per market")
    print(f"  Min order size: {MIN_ORDER_SIZE} shares")

    # Deploy to each market
    print(f"\n{'='*60}")
    print("DEPLOYING ORDERS")
    print("=" * 60)

    orders_placed = 0
    total_deployed = 0.0
    half_spread = spread / 2

    for i, market in enumerate(top_markets, 1):
        mid = market.gamma_yes_price

        # Calculate prices with tight spread
        yes_bid = round(mid - half_spread, 3)
        no_bid = round((1 - mid) - half_spread, 3)

        # Ensure valid prices
        yes_bid = max(0.01, min(0.98, yes_bid))
        no_bid = max(0.01, min(0.98, no_bid))

        # Calculate max sizes that fit in budget while meeting minimum
        # Allocate proportionally based on price, ensuring both get at least min
        yes_cost_per_share = yes_bid
        no_cost_per_share = no_bid
        total_cost_per_share = yes_cost_per_share + no_cost_per_share

        # Size = capital / price, but ensure minimum
        yes_size = max(MIN_ORDER_SIZE, round((capital_per_market * 0.5) / yes_bid, 1))
        no_size = max(MIN_ORDER_SIZE, round((capital_per_market * 0.5) / no_bid, 1))

        print(f"\n{i}. {market.question[:50]}...")
        print(f"   Volume 24h: ${market.volume_24h:,.0f}")
        print(f"   Mid price: {mid:.2f}")
        print(f"   YES bid: {yes_size:.1f} @ ${yes_bid:.3f} (${yes_size * yes_bid:.2f})")
        print(f"   NO bid: {no_size:.1f} @ ${no_bid:.3f} (${no_size * no_bid:.2f})")

        # Place YES order
        try:
            result = poly.create_and_post_order(
                token_id=market.yes_token_id,
                price=yes_bid,
                size=yes_size,
                side='BUY',
                order_type=OrderType.GTC,
            )
            order_id = result.get('id') or result.get('orderID', 'N/A')
            print(f"   ✓ YES order: {order_id[:16]}...")
            orders_placed += 1
            total_deployed += yes_size * yes_bid
        except Exception as e:
            print(f"   ✗ YES failed: {e}")

        # Place NO order
        try:
            result = poly.create_and_post_order(
                token_id=market.no_token_id,
                price=no_bid,
                size=no_size,
                side='BUY',
                order_type=OrderType.GTC,
            )
            order_id = result.get('id') or result.get('orderID', 'N/A')
            print(f"   ✓ NO order: {order_id[:16]}...")
            orders_placed += 1
            total_deployed += no_size * no_bid
        except Exception as e:
            print(f"   ✗ NO failed: {e}")

        # Small delay between markets
        time.sleep(0.3)

    # Summary
    print(f"\n{'='*60}")
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    print(f"Markets: {len(top_markets)}")
    print(f"Orders placed: {orders_placed}")
    print(f"Total deployed: ${total_deployed:.2f}")
    print(f"Spread: ${spread:.2f} (1 cent)")

    # Verify orders
    print(f"\nVerifying open orders...")
    try:
        open_orders = poly.get_orders()
        print(f"  Open orders: {len(open_orders)}")

        total_value = 0.0
        for order in open_orders:
            price = float(order.get('price', 0))
            size = float(order.get('original_size', 0) or order.get('size', 0))
            total_value += price * size

        print(f"  Total order value: ${total_value:.2f}")
    except Exception as e:
        print(f"  ✗ Verification failed: {e}")

    return orders_placed


if __name__ == "__main__":
    deploy_lp(capital=24.92, spread=0.01, num_markets=5)
