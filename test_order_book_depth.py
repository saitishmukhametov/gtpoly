"""Tests for order book depth analysis."""

from order_book_depth import (
    OrderLevel,
    OrderBook,
    OrderBookAnalyzer,
    analyze_depth,
)


def test_order_level_value():
    """Test OrderLevel value calculation."""
    level = OrderLevel(price=100.0, size=10.0)
    assert level.value == 1000.0


def test_order_book_spread():
    """Test spread calculation."""
    book = OrderBook(
        bids=[OrderLevel(price=99.0, size=10.0)],
        asks=[OrderLevel(price=101.0, size=10.0)]
    )
    # Mid = 100, spread = 2, spread_pct = 2%
    assert book.spread == 2.0


def test_sufficient_depth():
    """Test that sufficient depth passes analysis."""
    book = OrderBook(
        bids=[OrderLevel(price=100.0, size=20.0)],  # $2000 depth
        asks=[OrderLevel(price=101.0, size=20.0)]   # $2020 depth
    )
    analyzer = OrderBookAnalyzer(min_depth_per_side=1000.0, max_spread_pct=2.0)
    result = analyzer.analyze(book)

    assert result.is_sufficient
    assert result.bid_depth == 2000.0
    assert result.ask_depth == 2020.0


def test_thin_book_rejected():
    """Test that thin books are rejected."""
    book = OrderBook(
        bids=[OrderLevel(price=100.0, size=5.0)],   # $500 depth (too thin)
        asks=[OrderLevel(price=101.0, size=20.0)]   # $2020 depth
    )
    analyzer = OrderBookAnalyzer(min_depth_per_side=1000.0)
    result = analyzer.analyze(book)

    assert not result.is_sufficient
    assert "Bid depth" in result.reason


def test_wide_spread_rejected():
    """Test that wide spreads are rejected."""
    book = OrderBook(
        bids=[OrderLevel(price=95.0, size=20.0)],   # $1900 depth
        asks=[OrderLevel(price=105.0, size=20.0)]   # $2100 depth
    )
    # Spread = 10/100 = 10%
    analyzer = OrderBookAnalyzer(min_depth_per_side=1000.0, max_spread_pct=1.0)
    result = analyzer.analyze(book)

    assert not result.is_sufficient
    assert "Spread" in result.reason


def test_analyze_depth_convenience():
    """Test the convenience function."""
    result = analyze_depth(
        bids=[(100.0, 15.0), (99.0, 20.0)],
        asks=[(101.0, 15.0), (102.0, 20.0)],
        min_depth=1000.0
    )

    assert result.is_sufficient
    assert result.bid_depth == 3480.0  # 100*15 + 99*20
    assert result.ask_depth == 3555.0  # 101*15 + 102*20


def test_empty_book():
    """Test handling of empty order book."""
    book = OrderBook(bids=[], asks=[])
    analyzer = OrderBookAnalyzer(min_depth_per_side=1000.0)
    result = analyzer.analyze(book)

    assert not result.is_sufficient
    assert result.bid_depth == 0.0
    assert result.ask_depth == 0.0


if __name__ == "__main__":
    test_order_level_value()
    test_order_book_spread()
    test_sufficient_depth()
    test_thin_book_rejected()
    test_wide_spread_rejected()
    test_analyze_depth_convenience()
    test_empty_book()
    print("All tests passed!")
