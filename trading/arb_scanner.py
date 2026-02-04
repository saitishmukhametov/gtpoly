"""
Aggressive arbitrage scanner for Polymarket.

Scans all markets for sum-to-one arbitrage opportunities.
If YES_ask + NO_ask < 0.99, executes immediately.
"""

import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

sys.path.insert(0, "/home/sait/gt/gtpoly/polecats/rust/gtpoly/crew/sait")
from trading.client import PolyClient
from trading.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("arb_scanner")


@dataclass
class ArbOpportunity:
    """Represents an arbitrage opportunity."""
    condition_id: str
    question: str
    yes_token_id: str
    no_token_id: str
    yes_ask: float
    no_ask: float
    total_cost: float
    profit_per_share: float


class ArbScanner:
    """
    Aggressive arbitrage scanner.

    Scans markets every interval seconds looking for
    YES_ask + NO_ask < threshold opportunities.
    """

    ARB_THRESHOLD = 0.99  # Execute when YES_ask + NO_ask < this
    SCAN_INTERVAL = 5  # seconds
    MIN_ORDER_SIZE = 5.0  # minimum shares to trade
    MAX_ORDER_SIZE = 100.0  # maximum shares per trade
    MARKET_CACHE_TTL = 300  # refresh market list every 5 minutes
    MAX_WORKERS = 20  # concurrent order book fetches

    def __init__(self, dry_run: bool = False, max_markets: int = None):
        self.poly = PolyClient(get_config())
        self.dry_run = dry_run
        self.max_markets = max_markets
        self.opportunities_found = 0
        self.trades_executed = 0
        self._market_cache = []
        self._cache_time = 0

    def get_all_markets(self, force_refresh: bool = False) -> List[Dict]:
        """Fetch all active markets (cached)."""
        now = time.time()
        if not force_refresh and self._market_cache and (now - self._cache_time) < self.MARKET_CACHE_TTL:
            return self._market_cache

        log.info("Refreshing market list...")
        markets = []
        cursor = "MA=="

        while True:
            response = self.poly.get_markets(cursor)
            data = response.get("data", [])

            if not data:
                break

            for m in data:
                if m.get("active") and not m.get("closed"):
                    # Only include binary YES/NO markets
                    tokens = m.get("tokens", [])
                    if len(tokens) == 2:
                        outcomes = [t.get("outcome", "").lower() for t in tokens]
                        if "yes" in outcomes and "no" in outcomes:
                            markets.append(m)

            cursor = response.get("next_cursor")
            if cursor == "LTE=" or not cursor:
                break

        # Sort by volume (descending) if available
        markets.sort(key=lambda m: float(m.get("volume", 0) or 0), reverse=True)

        self._market_cache = markets
        self._cache_time = now
        log.info(f"Cached {len(markets)} binary markets")
        return markets

    def get_yes_no_tokens(self, market: Dict) -> Optional[Tuple[Dict, Dict]]:
        """Extract YES and NO tokens from a market."""
        tokens = market.get("tokens", [])

        if len(tokens) != 2:
            return None

        yes_token = None
        no_token = None

        for token in tokens:
            outcome = token.get("outcome", "").lower()
            if outcome == "yes":
                yes_token = token
            elif outcome == "no":
                no_token = token

        if yes_token and no_token:
            return (yes_token, no_token)
        return None

    def get_order_book_asks(self, yes_id: str, no_id: str) -> Tuple[Optional[float], Optional[float]]:
        """Get best ask prices for YES and NO tokens."""
        yes_ask = None
        no_ask = None

        try:
            yes_book = self.poly.get_order_book(yes_id)
            if yes_book.asks:
                yes_ask = float(yes_book.asks[0].price)
        except Exception:
            pass

        try:
            no_book = self.poly.get_order_book(no_id)
            if no_book.asks:
                no_ask = float(no_book.asks[0].price)
        except Exception:
            pass

        return yes_ask, no_ask

    def check_market_arb(self, market: Dict) -> Optional[ArbOpportunity]:
        """Check a single market for arbitrage opportunity."""
        tokens = self.get_yes_no_tokens(market)
        if not tokens:
            return None

        yes_token, no_token = tokens
        yes_id = yes_token.get("token_id")
        no_id = no_token.get("token_id")

        yes_ask, no_ask = self.get_order_book_asks(yes_id, no_id)

        if yes_ask is None or no_ask is None:
            return None

        total_cost = yes_ask + no_ask

        if total_cost < self.ARB_THRESHOLD:
            return ArbOpportunity(
                condition_id=market.get("condition_id"),
                question=market.get("question", "Unknown"),
                yes_token_id=yes_id,
                no_token_id=no_id,
                yes_ask=yes_ask,
                no_ask=no_ask,
                total_cost=total_cost,
                profit_per_share=1.0 - total_cost,
            )
        return None

    def execute_arb(self, opp: ArbOpportunity, size: float) -> bool:
        """Execute an arbitrage trade by buying both YES and NO."""
        log.info(f"EXECUTING ARB: {opp.question[:50]}...")
        log.info(f"  YES @ {opp.yes_ask:.4f} + NO @ {opp.no_ask:.4f} = {opp.total_cost:.4f}")
        log.info(f"  Size: {size} shares, Expected profit: ${size * opp.profit_per_share:.2f}")

        if self.dry_run:
            log.info("  [DRY RUN] Would execute trade")
            return True

        try:
            # Buy YES
            yes_order = self.poly.create_and_post_order(
                token_id=opp.yes_token_id,
                price=opp.yes_ask,
                size=size,
                side="BUY",
            )
            log.info(f"  YES order: {yes_order}")

            # Buy NO
            no_order = self.poly.create_and_post_order(
                token_id=opp.no_token_id,
                price=opp.no_ask,
                size=size,
                side="BUY",
            )
            log.info(f"  NO order: {no_order}")

            self.trades_executed += 1
            return True

        except Exception as e:
            log.error(f"  Trade execution failed: {e}")
            return False

    def scan_once(self) -> List[ArbOpportunity]:
        """Perform a single scan of markets using concurrent requests."""
        opportunities = []

        markets = self.get_all_markets()
        scan_markets = markets[:self.max_markets] if self.max_markets else markets
        log.info(f"Scanning {len(scan_markets)} markets...")

        # Use thread pool to check markets concurrently
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {executor.submit(self.check_market_arb, m): m for m in scan_markets}

            for future in as_completed(futures):
                try:
                    opp = future.result()
                    if opp:
                        self.opportunities_found += 1
                        opportunities.append(opp)
                        log.warning(
                            f"ARB FOUND! {opp.question[:40]}... "
                            f"YES:{opp.yes_ask:.3f} + NO:{opp.no_ask:.3f} = {opp.total_cost:.3f} "
                            f"(profit: {opp.profit_per_share:.3f}/share)"
                        )
                except Exception as e:
                    log.debug(f"Error checking market: {e}")

        return opportunities

    def run(self, execute: bool = True, max_iterations: int = None):
        """
        Run the scanner loop.

        Args:
            execute: Whether to execute trades on opportunities found
            max_iterations: Maximum scan iterations (None = infinite)
        """
        log.info("=" * 60)
        log.info("AGGRESSIVE ARB SCANNER STARTING")
        log.info(f"Threshold: {self.ARB_THRESHOLD}")
        log.info(f"Interval: {self.SCAN_INTERVAL}s")
        log.info(f"Max markets: {self.max_markets or 'all'}")
        log.info(f"Dry run: {self.dry_run}")
        log.info(f"Execute: {execute}")
        log.info("=" * 60)

        iteration = 0
        try:
            while max_iterations is None or iteration < max_iterations:
                iteration += 1
                start = time.time()
                log.info(f"\n--- Scan #{iteration} ---")

                opportunities = self.scan_once()

                if opportunities and execute:
                    for opp in opportunities:
                        size = min(self.MAX_ORDER_SIZE, max(self.MIN_ORDER_SIZE, 10))
                        self.execute_arb(opp, size)

                elapsed = time.time() - start
                log.info(
                    f"Scan completed in {elapsed:.1f}s | "
                    f"Total: {self.opportunities_found} opportunities, "
                    f"{self.trades_executed} trades"
                )

                if max_iterations is None or iteration < max_iterations:
                    sleep_time = max(0, self.SCAN_INTERVAL - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)

        except KeyboardInterrupt:
            log.info("\nScanner stopped by user")

        log.info(f"\nFinal stats: {self.opportunities_found} opportunities, {self.trades_executed} trades")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Aggressive arbitrage scanner")
    parser.add_argument("--dry-run", action="store_true", help="Don't execute trades")
    parser.add_argument("--no-execute", action="store_true", help="Scan only, don't trade")
    parser.add_argument("--once", action="store_true", help="Run single scan and exit")
    parser.add_argument("--threshold", type=float, default=0.99, help="Arb threshold")
    parser.add_argument("--max-markets", type=int, default=500, help="Max markets to scan (default 500)")
    args = parser.parse_args()

    scanner = ArbScanner(dry_run=args.dry_run, max_markets=args.max_markets)
    scanner.ARB_THRESHOLD = args.threshold

    scanner.run(
        execute=not args.no_execute,
        max_iterations=1 if args.once else None,
    )


if __name__ == "__main__":
    main()
