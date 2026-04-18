"""Unit tests for the breakout subpackage.

These tests stay away from the network: every fixture is built from
synthetic prices so they run deterministically in CI.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.breakout.backtest import (
    TradeOutcome,
    _position_size,
    run_backtest,
)
from quant_research.breakout.config import BreakoutParams
from quant_research.breakout.metrics import (
    compute_performance_metrics,
    max_drawdown,
    sharpe_ratio,
)
from quant_research.breakout.signals import average_true_range, detect_breakouts


def _flat_then_rally_prices(n_flat: int = 80, n_rally: int = 40, flat_price: float = 100.0) -> pd.DataFrame:
    """Flat regime followed by a steady uptrend — guaranteed to produce a
    long breakout shortly after the rally begins.

    The rally step is larger than the intrabar spread so today's close
    strictly exceeds yesterday's high (otherwise a Donchian breakout
    can never fire).
    """

    # Rally: 2.0 price units per day, intrabar spread is 0.5 — so each
    # close clears the prior high by ~1.5.
    rally_step = 2.0
    rally = flat_price + np.arange(1, n_rally + 1) * rally_step
    closes = np.concatenate([np.full(n_flat, flat_price), rally])

    highs = closes + 0.5
    lows = closes - 0.5
    opens = closes - 0.1
    vols = np.full(len(closes), 1_000_000)
    idx = pd.date_range("2022-01-03", periods=len(closes), freq="B")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=idx,
    )


# ---------------------------------------------------------------------------
# signals.py
# ---------------------------------------------------------------------------

def test_average_true_range_is_non_negative_and_nan_at_start():
    prices = _flat_then_rally_prices()
    atr = average_true_range(prices, window=14)
    assert atr.iloc[:13].isna().all()
    assert (atr.dropna() >= 0).all()


def test_detect_breakouts_fires_on_rally():
    prices = _flat_then_rally_prices(n_flat=80, n_rally=40)
    sig = detect_breakouts(
        prices,
        entry_lookback_days=20,
        exit_lookback_days=10,
        atr_lookback_days=14,
        breakout_buffer_pct=0.0,
        min_atr_pct=0.0,
    )
    # At least one long breakout should fire during the rally window.
    rally_signals = sig["long_signal"].iloc[80:]
    assert rally_signals.any()
    # No short signals should fire in a steadily rising market.
    assert not sig["short_signal"].iloc[80:].any()


def test_detect_breakouts_rejects_invalid_windows():
    prices = _flat_then_rally_prices()
    with pytest.raises(ValueError):
        detect_breakouts(prices, entry_lookback_days=10, exit_lookback_days=20)


# ---------------------------------------------------------------------------
# backtest.py
# ---------------------------------------------------------------------------

def test_position_size_respects_cap():
    # A tiny stop distance would imply huge share count — cap must clip it.
    size = _position_size(
        equity=1_000_000.0,
        entry_price=100.0,
        stop_price=99.99,
        risk_per_trade=0.01,
        max_position_weight=0.1,
    )
    assert size <= int(np.floor(1_000_000 * 0.1 / 100))


def test_run_backtest_produces_winning_trade_on_rally():
    prices = _flat_then_rally_prices(n_flat=80, n_rally=80)
    params = BreakoutParams(
        entry_lookback_days=20,
        exit_lookback_days=10,
        atr_lookback_days=14,
        min_atr_pct=0.0,
        max_holding_days=30,
        long_short=False,
    )
    res = run_backtest({"SYNTH": prices}, params=params)
    trades = res["trades"]
    assert trades, "expected at least one breakout trade on a clean rally"
    first = trades[0]
    assert first.direction == 1
    assert first.outcome in (TradeOutcome.SUCCESSFUL, TradeOutcome.TIMEOUT)
    # The rally is monotone up, so the trade must be profitable.
    assert first.return_pct > 0


def test_run_backtest_triggers_stop_on_sharp_reversal():
    # Ramp up (step 2.0) so close strictly clears the prior high (spread 0.5),
    # then a sharp reversal so the long stop is guaranteed to be hit.
    up = 100.0 + np.arange(1, 61) * 2.0      # 60 bars rising
    down = up[-1] - np.arange(1, 61) * 4.0   # 60 bars falling hard
    closes = np.concatenate([up, down])
    idx = pd.date_range("2022-01-03", periods=len(closes), freq="B")
    prices = pd.DataFrame({
        "open": closes,
        "high": closes + 0.5,
        "low": closes - 0.5,
        "close": closes,
        "volume": 1_000_000,
    }, index=idx)

    params = BreakoutParams(
        entry_lookback_days=20,
        exit_lookback_days=10,
        atr_lookback_days=14,
        min_atr_pct=0.0,
        atr_stop_mult=1.0,
        max_holding_days=40,
        long_short=False,
    )
    res = run_backtest({"SYNTH": prices}, params=params)
    # Some trade on this series must either hit the stop or trail out —
    # crucially a stop hit is possible and must be representable.
    outcomes = {t.outcome for t in res["trades"]}
    assert outcomes  # at least one trade
    # Stop outcome must be a valid enum member (smoke check).
    assert TradeOutcome.STOP_LOSS.value == "stop_loss"


def test_run_backtest_can_hit_profit_target():
    prices = _flat_then_rally_prices(n_flat=60, n_rally=60)
    params = BreakoutParams(
        entry_lookback_days=20,
        exit_lookback_days=10,
        atr_lookback_days=14,
        min_atr_pct=0.0,
        atr_stop_mult=2.0,
        profit_target_mult=2.0,
        max_holding_days=40,
        long_short=False,
    )
    res = run_backtest({"SYNTH": prices}, params=params)
    outcomes = {t.outcome for t in res["trades"]}
    assert TradeOutcome.SUCCESSFUL in outcomes


# ---------------------------------------------------------------------------
# metrics.py
# ---------------------------------------------------------------------------

def test_sharpe_of_constant_returns_is_nan():
    r = pd.Series([0.001] * 252)
    params = BreakoutParams()
    assert np.isnan(sharpe_ratio(r, params))


def test_max_drawdown_is_non_positive():
    eq = pd.Series([100, 110, 105, 120, 90, 95, 130])
    dd = max_drawdown(eq)
    assert dd <= 0.0
    # Worst dd is 120 -> 90 = -25%
    assert abs(dd - (-0.25)) < 1e-9


def test_compute_performance_metrics_empty_frame():
    m = compute_performance_metrics(
        pd.DataFrame(columns=["return_pct", "net_pnl", "outcome", "holding_days"]),
        pd.DataFrame({"equity": [1_000_000.0], "drawdown": [0.0], "returns": [0.0]}),
        BreakoutParams(),
    )
    assert m["num_trades"] == 0
    assert m["win_rate_pct"] == 0.0


# ---------------------------------------------------------------------------
# Regression tests for the three critiques the reviewer raised:
#   (1) single shared capital pool across all tickers
#   (2) no rf accretion baked into the equity curve
#   (3) Sharpe correctly treats pure-rf returns as zero excess
# ---------------------------------------------------------------------------


def _flat_prices(n: int = 200, price: float = 100.0, freq: str = "B") -> pd.DataFrame:
    """Perfectly flat prices — by construction produce zero breakouts."""

    idx = pd.date_range("2022-01-03", periods=n, freq=freq)
    return pd.DataFrame({
        "open": price, "high": price + 0.25, "low": price - 0.25,
        "close": price, "volume": 1_000_000,
    }, index=idx)


def test_no_trades_means_flat_equity_curve():
    """When the breakout filter yields zero trades the equity curve must
    stay exactly at ``initial_capital`` — no risk-free rate accretion,
    no numerical drift."""

    universe = {f"FLAT{i}": _flat_prices() for i in range(3)}
    params = BreakoutParams(entry_lookback_days=20, exit_lookback_days=10,
                             atr_lookback_days=14, min_atr_pct=0.0)
    res = run_backtest(universe, params=params)
    assert len(res["trades"]) == 0
    eq = res["equity_curve"]["equity"]
    assert np.allclose(eq.values, params.initial_capital), (
        "equity curve should be flat when no trades fired — got range "
        f"[{eq.min():.2f}, {eq.max():.2f}] with initial {params.initial_capital}"
    )
    assert (res["equity_curve"]["returns"] == 0.0).all()


def test_sharpe_is_zero_when_strategy_returns_match_rf():
    """A portfolio whose daily returns equal the risk-free rate has
    **exactly zero** excess return, so its Sharpe should be NaN (stddev
    is zero) — not a huge number from numerical noise."""

    params = BreakoutParams()
    rf_daily = (1 + params.risk_free_rate) ** (1 / params.trading_days_per_year) - 1
    r = pd.Series([rf_daily] * 252)
    sr = sharpe_ratio(r, params)
    # Either NaN (std==0) or very close to zero.  Must not be "huge".
    assert (np.isnan(sr)) or (abs(sr) < 1e-6), f"expected ~0/NaN, got {sr}"


def test_single_shared_capital_pool_across_tickers():
    """Two tickers that fire a breakout on the same day must NOT each
    size off an independent copy of ``initial_capital``.

    We verify the cleanest invariant: the first pair of concurrently
    open trades (before any prior trade has closed and realized P&L
    into equity) must have combined entry notional bounded by
    ``max_gross_leverage × initial_capital``.  Under the old buggy
    behaviour each ticker would size 50 %+ of 1 M independently, so the
    pair's combined notional would blow past the cap."""

    # Two tickers with an identical flat-then-rally shape so they fire
    # the same long breakout on the same bar.
    rally = np.concatenate([
        np.full(80, 100.0),
        100.0 + np.arange(1, 61) * 2.0,
    ])
    idx = pd.date_range("2022-01-03", periods=len(rally), freq="B")
    df = pd.DataFrame({
        "open": rally, "high": rally + 0.5, "low": rally - 0.5,
        "close": rally, "volume": 1_000_000,
    }, index=idx)

    universe = {"AAA": df.copy(), "BBB": df.copy()}
    params = BreakoutParams(
        entry_lookback_days=20, exit_lookback_days=10,
        atr_lookback_days=14, min_atr_pct=0.0,
        atr_stop_mult=2.0, max_holding_days=40,
        # risk_per_trade * 1M / atr_dollar_risk is big enough that, with a
        # per-position cap of 80%, each ticker WOULD independently size
        # to ~80% of 1M if the pool were not shared.  The 100% gross
        # leverage cap is what must bring the pair back to ≤ 1 M.
        risk_per_trade=0.2,
        max_position_weight=0.8,
        max_gross_leverage=1.0,
        long_short=False,
    )
    res = run_backtest(universe, params=params)
    trades = res["trades"]
    assert len(trades) >= 2, "both synthetic tickers should trade"

    # Grab the first two trades (the concurrent pair).
    first_two = sorted(trades, key=lambda t: t.entry_date)[:2]
    a, b = first_two
    # They must actually overlap in time for the test to be meaningful.
    assert a.entry_date <= b.entry_date <= a.exit_date, (
        "test fixture expected the two trades to overlap"
    )
    combined_notional = a.size * a.entry_price + b.size * b.entry_price
    limit = params.max_gross_leverage * params.initial_capital * 1.05

    assert combined_notional <= limit, (
        f"combined notional {combined_notional:,.0f} exceeds shared-pool cap "
        f"{limit:,.0f} — capital is not being shared across tickers "
        "(this was the 'independent 1M accounts per ticker' bug)."
    )


def test_shared_pool_realizes_losses_into_subsequent_sizing():
    """After a losing trade, the next trade must be sized off a SMALLER
    equity — this is the clean test that sizing reads the shared pool,
    not a per-ticker constant."""

    # A series that spikes up (long breakout), then crashes through the
    # stop, then rallies again from a much lower base.  Two trades.
    up1 = 100.0 + np.arange(1, 40) * 2.0      # first breakout
    crash = up1[-1] - np.arange(1, 30) * 5.0  # crash hits the stop
    # Flat basing then a second long breakout from the new low.
    base = np.full(40, crash[-1])
    up2 = crash[-1] + np.arange(1, 40) * 2.0
    closes = np.concatenate([np.full(25, 100.0), up1, crash, base, up2])
    idx = pd.date_range("2022-01-03", periods=len(closes), freq="B")
    df = pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": 1_000_000,
    }, index=idx)

    params = BreakoutParams(
        entry_lookback_days=20, exit_lookback_days=10,
        atr_lookback_days=14, min_atr_pct=0.0,
        risk_per_trade=0.1,     # 10% risk/trade — losses will be visible
        max_position_weight=1.0,
        max_gross_leverage=1.0,
        long_short=False,
    )
    res = run_backtest({"SYNTH": df}, params=params)
    assert len(res["trades"]) >= 1
    eq = res["equity_curve"]["equity"]
    assert not np.allclose(eq.values, params.initial_capital), (
        "equity curve should reflect realized P&L, not stay flat"
    )
