"""Tests for market momentum detector."""

import time
from momentum_detector import MomentumDetector, MarketState, PricePoint


def test_market_state_velocity():
    """Test velocity calculation."""
    state = MarketState()
    base_time = 1000.0

    state.add_price(100.0, base_time)
    state.add_price(102.0, base_time + 60)  # 2% up in 1 minute

    velocity = state.get_velocity()
    assert velocity is not None
    assert abs(velocity - 2.0) < 0.01


def test_market_state_insufficient_data():
    """Test that velocity returns None with insufficient data."""
    state = MarketState()
    assert state.get_velocity() is None

    state.add_price(100.0, 1000.0)
    assert state.get_velocity() is None  # Only one point


def test_momentum_detector_triggers_buy():
    """Test that detector triggers buy on upward momentum."""
    orders = []

    def on_order(market, direction, velocity):
        orders.append((market, direction, velocity))

    detector = MomentumDetector(order_callback=on_order)
    base_time = 1000.0

    detector.update_price('ETH-USD', 2000.0, base_time)
    detector.update_price('ETH-USD', 2050.0, base_time + 60)  # 2.5% up

    assert len(orders) == 1
    assert orders[0][0] == 'ETH-USD'
    assert orders[0][1] == 'buy'
    assert orders[0][2] > 2.0


def test_momentum_detector_triggers_sell():
    """Test that detector triggers sell on downward momentum."""
    orders = []

    def on_order(market, direction, velocity):
        orders.append((market, direction, velocity))

    detector = MomentumDetector(order_callback=on_order)
    base_time = 1000.0

    detector.update_price('BTC-USD', 50000.0, base_time)
    detector.update_price('BTC-USD', 48500.0, base_time + 60)  # -3% down

    assert len(orders) == 1
    assert orders[0][0] == 'BTC-USD'
    assert orders[0][1] == 'sell'
    assert orders[0][2] < -2.0


def test_no_trigger_below_threshold():
    """Test that detector doesn't trigger below 2% threshold."""
    orders = []

    def on_order(market, direction, velocity):
        orders.append((market, direction, velocity))

    detector = MomentumDetector(order_callback=on_order)
    base_time = 1000.0

    detector.update_price('SOL-USD', 100.0, base_time)
    detector.update_price('SOL-USD', 101.5, base_time + 60)  # 1.5% - below threshold

    assert len(orders) == 0


def test_multiple_markets():
    """Test tracking multiple markets simultaneously."""
    detector = MomentumDetector()
    base_time = 1000.0

    detector.update_price('BTC-USD', 50000.0, base_time)
    detector.update_price('ETH-USD', 2000.0, base_time)
    detector.update_price('BTC-USD', 51000.0, base_time + 60)
    detector.update_price('ETH-USD', 1950.0, base_time + 60)

    velocities = detector.get_all_velocities()
    assert 'BTC-USD' in velocities
    assert 'ETH-USD' in velocities
    assert velocities['BTC-USD'] > 0  # Up
    assert velocities['ETH-USD'] < 0  # Down


def test_old_prices_cleaned_up():
    """Test that old prices are cleaned up."""
    state = MarketState()
    base_time = 1000.0

    state.add_price(100.0, base_time)
    state.add_price(101.0, base_time + 60)
    state.add_price(102.0, base_time + 150)  # 2.5 minutes after first

    # First price should be cleaned up (>2 min old)
    assert len(state.prices) == 2


if __name__ == '__main__':
    test_market_state_velocity()
    test_market_state_insufficient_data()
    test_momentum_detector_triggers_buy()
    test_momentum_detector_triggers_sell()
    test_no_trigger_below_threshold()
    test_multiple_markets()
    test_old_prices_cleaned_up()
    print("All tests passed!")
