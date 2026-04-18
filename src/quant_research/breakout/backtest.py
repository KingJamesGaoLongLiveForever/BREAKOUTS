"""Event-driven backtest for the Donchian breakout strategy.

This simulator enforces a **single shared capital pool** across every
ticker in the universe.  That matters: if two symbols fire a signal on
the same day, the second trade sees an equity figure that already
reflects the capital committed to the first.  A gross-leverage cap
prevents concurrent positions from implicitly over-committing the book.

Exit priority, checked on every held bar in this order:

1. ``STOP_LOSS``   — intrabar low (long) or high (short) pierces the
   ``entry ± ATR_STOP_MULT·ATR`` stop.  We fill at the stop level
   (conservative fill when stop + target fire on the same bar).
2. ``SUCCESSFUL``  — intrabar high (long) or low (short) reaches the
   ``entry ± PROFIT_TARGET_MULT·ATR`` target.  We fill at the target
   level, creating a clean "successful trade" bucket for the report.
3. ``TIMEOUT``     — holding period reaches ``max_holding_days``.  Fill
   at that bar's close (market-on-close).

Execution: every signal forms on the close of bar *t* and fills on the
**next** bar's open (bar *t+1*), so there is no look-ahead bias.

Equity curve is pure strategy P&L on top of ``initial_capital`` — the
risk-free rate is **not** compounded into the equity, so Sharpe /
Sortino can subtract it explicitly without double-counting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import BreakoutParams, DEFAULT_PARAMS
from .signals import detect_breakouts


LOGGER = logging.getLogger(__name__)


class TradeOutcome(str, Enum):
    STOP_LOSS = "stop_loss"
    SUCCESSFUL = "successful"
    TIMEOUT = "timeout"


@dataclass
class Trade:
    ticker: str
    direction: int  # +1 long, -1 short
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    size: float  # shares (always positive)
    outcome: TradeOutcome
    holding_days: int
    stop_price: float
    target_price: float
    atr_at_entry: float

    @property
    def gross_pnl(self) -> float:
        return self.direction * (self.exit_price - self.entry_price) * self.size

    @property
    def return_pct(self) -> float:
        """Per-trade return as a fraction of notional at entry."""
        return self.direction * (self.exit_price - self.entry_price) / self.entry_price

    def to_row(self, cost_bps_per_side: float) -> dict:
        cost = 2 * (cost_bps_per_side / 1e4) * self.entry_price * self.size
        net = self.gross_pnl - cost
        return {
            "ticker": self.ticker,
            "direction": "long" if self.direction == 1 else "short",
            "entry_date": self.entry_date.date().isoformat(),
            "exit_date": self.exit_date.date().isoformat(),
            "entry_price": round(self.entry_price, 4),
            "exit_price": round(self.exit_price, 4),
            "stop_price": round(self.stop_price, 4),
            "target_price": round(self.target_price, 4),
            "size_shares": int(self.size),
            "atr_at_entry": round(self.atr_at_entry, 4),
            "holding_days": self.holding_days,
            "outcome": self.outcome.value,
            "gross_pnl": round(self.gross_pnl, 2),
            "cost": round(cost, 2),
            "net_pnl": round(net, 2),
            "return_pct": round(self.return_pct, 6),
        }


@dataclass
class _OpenPosition:
    ticker: str
    direction: int
    entry_date: pd.Timestamp
    entry_index: int  # iloc in the ticker's (windowed) price frame
    entry_price: float
    size: int
    stop_price: float
    target_price: float
    atr_at_entry: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _position_size(equity: float, entry_price: float, stop_price: float,
                   risk_per_trade: float, max_position_weight: float) -> int:
    """Fixed-fractional sizing constrained by a weight cap."""

    per_share_risk = abs(entry_price - stop_price)
    if per_share_risk <= 0 or entry_price <= 0 or equity <= 0:
        return 0

    risk_shares = (risk_per_trade * equity) / per_share_risk
    cap_shares = (max_position_weight * equity) / entry_price
    return int(np.floor(max(0.0, min(risk_shares, cap_shares))))


def _evaluate_exit(
    pos: _OpenPosition,
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    j: int,
    params: BreakoutParams,
) -> Optional[Tuple[TradeOutcome, float, int]]:
    """Check if ``pos`` should exit on bar ``j``.

    Returns ``(outcome, exit_price, holding_days)`` or ``None``.  The
    priority is stop-loss → profit target → timeout.
    """

    if j < pos.entry_index:
        return None

    bar = prices.iloc[j]
    holding_days = j - pos.entry_index

    # 1. Stop-loss (intrabar, can fire on the entry bar itself).
    if pos.direction == 1 and bar["low"] <= pos.stop_price:
        return TradeOutcome.STOP_LOSS, pos.stop_price, holding_days
    if pos.direction == -1 and bar["high"] >= pos.stop_price:
        return TradeOutcome.STOP_LOSS, pos.stop_price, holding_days

    # 2. Profit target (intrabar, can fire on the entry bar itself).
    if pos.direction == 1 and bar["high"] >= pos.target_price:
        return TradeOutcome.SUCCESSFUL, pos.target_price, holding_days
    if pos.direction == -1 and bar["low"] <= pos.target_price:
        return TradeOutcome.SUCCESSFUL, pos.target_price, holding_days

    # 3. Timeout — market-on-close when the holding cap is reached.
    if holding_days >= params.max_holding_days:
        return TradeOutcome.TIMEOUT, float(bar["close"]), holding_days

    return None


def _compute_signals(
    prices: pd.DataFrame,
    params: BreakoutParams,
    lookback_overrides: Optional[Dict[pd.Timestamp, int]],
) -> pd.DataFrame:
    """Compute breakout signals on the full history.

    Important: we deliberately do NOT slice ``prices`` here.  The caller
    is responsible for passing full-history prices so rolling windows
    warm up *before* the trading window starts — otherwise walk-forward
    test blocks would begin with ``entry_lookback_days`` bars of NaN
    signals.
    """

    if lookback_overrides:
        return _stitched_signals(prices, params, lookback_overrides)
    return detect_breakouts(
        prices,
        entry_lookback_days=params.entry_lookback_days,
        exit_lookback_days=params.exit_lookback_days,
        atr_lookback_days=params.atr_lookback_days,
        breakout_buffer_pct=params.breakout_buffer_pct,
        min_atr_pct=params.min_atr_pct,
        long_short=params.long_short,
    )


def _stitched_signals(
    prices: pd.DataFrame,
    params: BreakoutParams,
    overrides: Dict[pd.Timestamp, int],
) -> pd.DataFrame:
    """Signal frame that switches entry-lookback at each walk-forward boundary."""

    sorted_dates = sorted(overrides.keys())
    unique_lb = set(overrides.values())
    unique_lb.add(params.entry_lookback_days)

    frames: Dict[int, pd.DataFrame] = {}
    for lb in unique_lb:
        # The trailing-exit channel must be strictly shorter than the
        # entry channel; shrink it if a small grid point would violate
        # the invariant.
        exit_lb = min(params.exit_lookback_days, max(5, lb - 1))
        frames[lb] = detect_breakouts(
            prices,
            entry_lookback_days=lb,
            exit_lookback_days=exit_lb,
            atr_lookback_days=params.atr_lookback_days,
            breakout_buffer_pct=params.breakout_buffer_pct,
            min_atr_pct=params.min_atr_pct,
            long_short=params.long_short,
        )

    out = frames[params.entry_lookback_days].copy()
    for k, start_date in enumerate(sorted_dates):
        end_date = sorted_dates[k + 1] if k + 1 < len(sorted_dates) else None
        lb = overrides[start_date]
        mask = out.index >= pd.Timestamp(start_date)
        if end_date is not None:
            mask &= out.index < pd.Timestamp(end_date)
        out.loc[mask] = frames[lb].loc[mask]
    return out


def _trades_to_frame(trades: List[Trade], params: BreakoutParams) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(columns=[
            "ticker", "direction", "entry_date", "exit_date", "entry_price",
            "exit_price", "stop_price", "target_price", "size_shares", "atr_at_entry",
            "holding_days", "outcome", "gross_pnl", "cost", "net_pnl", "return_pct",
        ])
    rows = [t.to_row(params.cost_bps_per_side) for t in trades]
    df = pd.DataFrame(rows)
    df = df.sort_values("entry_date").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Public driver
# ---------------------------------------------------------------------------

def run_backtest(
    universe: Dict[str, pd.DataFrame],
    params: BreakoutParams = DEFAULT_PARAMS,
    start: Optional[str] = None,
    end: Optional[str] = None,
    lookback_overrides: Optional[Dict[pd.Timestamp, int]] = None,
) -> dict:
    """Single-pool event-driven backtest over a multi-ticker universe.

    Every trade is sized off the same ``equity`` scalar.  Exits are
    processed first on each bar, then new entries — so a liquidating
    trade on day *t* releases capital for another trade opening on the
    very same day.
    """

    start_ts = pd.Timestamp(start) if start is not None else None
    end_ts = pd.Timestamp(end) if end is not None else None

    # --- 1. Pre-compute signals on full history; remember window mask ---
    signals_by_ticker: Dict[str, pd.DataFrame] = {}
    prices_by_ticker: Dict[str, pd.DataFrame] = {}
    window_starts: Dict[str, int] = {}

    min_bars = max(params.entry_lookback_days, params.atr_lookback_days) + 5

    for ticker, raw_prices in universe.items():
        if len(raw_prices) < min_bars:
            continue
        full_signals = _compute_signals(raw_prices, params, lookback_overrides)

        # Restrict to the trading window.  Signals already rolled using
        # pre-window history, so the first in-window bar has a valid
        # upper_entry / lower_entry.
        mask = np.ones(len(raw_prices), dtype=bool)
        if start_ts is not None:
            mask &= raw_prices.index >= start_ts
        if end_ts is not None:
            mask &= raw_prices.index <= end_ts
        if not mask.any():
            continue

        prices_window = raw_prices.loc[mask].copy()
        signals_window = full_signals.loc[mask].copy()
        if len(prices_window) < 2:
            continue

        prices_window.attrs["ticker"] = ticker
        prices_by_ticker[ticker] = prices_window
        signals_by_ticker[ticker] = signals_window
        window_starts[ticker] = 0  # iloc 0 of the windowed frame

    if not prices_by_ticker:
        return _empty_result(params)

    # --- 2. Build a global trading calendar (union of ticker calendars) ---
    calendar = pd.DatetimeIndex([])
    for p in prices_by_ticker.values():
        calendar = calendar.union(p.index)
    calendar = calendar.sort_values()

    # --- 3. Walk the calendar day-by-day with ONE shared equity pool ---
    equity = float(params.initial_capital)
    open_positions: Dict[str, _OpenPosition] = {}
    all_trades: List[Trade] = []
    equity_rows: List[dict] = []

    sorted_tickers = sorted(prices_by_ticker.keys())

    for date in calendar:
        # ---- 3a. Process exits for every open position, in a stable order ----
        for ticker in sorted(open_positions.keys()):
            pos = open_positions[ticker]
            prices = prices_by_ticker[ticker]
            signals = signals_by_ticker[ticker]
            if date not in prices.index:
                continue
            j = prices.index.get_loc(date)
            if isinstance(j, slice):
                j = j.start
            j = int(j)
            if j < pos.entry_index:
                continue

            exit_info = _evaluate_exit(pos, prices, signals, j, params)
            if exit_info is None:
                continue

            outcome, exit_price, holding_days = exit_info
            cost = 2 * (params.cost_bps_per_side / 1e4) * pos.entry_price * pos.size
            gross = pos.direction * (exit_price - pos.entry_price) * pos.size
            equity += gross - cost  # realize P&L into the shared pool

            all_trades.append(Trade(
                ticker=ticker,
                direction=pos.direction,
                entry_date=pos.entry_date,
                exit_date=date,
                entry_price=pos.entry_price,
                exit_price=float(exit_price),
                size=pos.size,
                outcome=outcome,
                holding_days=int(holding_days),
                stop_price=pos.stop_price,
                target_price=pos.target_price,
                atr_at_entry=pos.atr_at_entry,
            ))
            del open_positions[ticker]

        # ---- 3b. Consider new entries ----
        # Stable iteration order for reproducibility.
        for ticker in sorted_tickers:
            if ticker in open_positions:
                continue
            prices = prices_by_ticker[ticker]
            signals = signals_by_ticker[ticker]
            if date not in prices.index:
                continue
            j = prices.index.get_loc(date)
            if isinstance(j, slice):
                j = j.start
            j = int(j)
            if j == 0:
                continue  # need a previous bar to fire a signal

            prev = signals.iloc[j - 1]
            direction = 0
            if bool(prev["long_signal"]):
                direction = 1
            elif bool(prev["short_signal"]):
                direction = -1
            if direction == 0:
                continue

            atr = float(prev["atr"])
            if not np.isfinite(atr) or atr <= 0:
                continue

            entry_price = float(prices.iloc[j]["open"])
            if entry_price <= 0 or not np.isfinite(entry_price):
                continue

            stop_price = entry_price - direction * params.atr_stop_mult * atr
            target_price = entry_price + direction * params.profit_target_mult * atr

            # Check current gross exposure before sizing the new trade.
            gross_exposure = 0.0
            for op_pos in open_positions.values():
                op_prices = prices_by_ticker[op_pos.ticker]
                if date in op_prices.index:
                    px = float(op_prices.loc[date, "close"])
                else:
                    px = op_pos.entry_price
                gross_exposure += op_pos.size * px

            # Size by risk-per-trade, then clip by both the per-name
            # weight cap and the book-wide gross-leverage cap.
            desired_size = _position_size(
                equity=equity,
                entry_price=entry_price,
                stop_price=stop_price,
                risk_per_trade=params.risk_per_trade,
                max_position_weight=params.max_position_weight,
            )
            if desired_size <= 0:
                continue

            leverage_budget = params.max_gross_leverage * equity - gross_exposure
            if leverage_budget <= 0:
                continue
            max_by_leverage = int(np.floor(leverage_budget / entry_price))
            size = min(desired_size, max_by_leverage)
            if size <= 0:
                continue

            open_positions[ticker] = _OpenPosition(
                ticker=ticker,
                direction=direction,
                entry_date=date,
                entry_index=j,
                entry_price=entry_price,
                size=int(size),
                stop_price=float(stop_price),
                target_price=float(target_price),
                atr_at_entry=atr,
            )

        # ---- 3c. Record mark-to-market equity for this day ----
        mtm = equity
        for op_pos in open_positions.values():
            op_prices = prices_by_ticker[op_pos.ticker]
            if date in op_prices.index:
                close_px = float(op_prices.loc[date, "close"])
                mtm += op_pos.direction * (close_px - op_pos.entry_price) * op_pos.size
        equity_rows.append({"date": date, "equity": mtm, "cash_equity": equity})

    # --- 4. Force-close any still-open positions at end of window ---
    last_date = calendar[-1]
    for ticker in list(open_positions.keys()):
        pos = open_positions[ticker]
        prices = prices_by_ticker[ticker]
        valid = prices.index[prices.index <= last_date]
        if len(valid) == 0:
            continue
        j = prices.index.get_loc(valid[-1])
        if isinstance(j, slice):
            j = j.start
        j = int(j)
        if j <= pos.entry_index:
            continue
        exit_price = float(prices.iloc[j]["close"])
        cost = 2 * (params.cost_bps_per_side / 1e4) * pos.entry_price * pos.size
        gross = pos.direction * (exit_price - pos.entry_price) * pos.size
        equity += gross - cost
        all_trades.append(Trade(
            ticker=ticker,
            direction=pos.direction,
            entry_date=pos.entry_date,
            exit_date=valid[-1],
            entry_price=pos.entry_price,
            exit_price=exit_price,
            size=pos.size,
            outcome=TradeOutcome.TIMEOUT,
            holding_days=j - pos.entry_index,
            stop_price=pos.stop_price,
            target_price=pos.target_price,
            atr_at_entry=pos.atr_at_entry,
        ))
        del open_positions[ticker]

    # Update the last equity row to reflect forced-close realizations.
    if equity_rows:
        equity_rows[-1]["equity"] = equity
        equity_rows[-1]["cash_equity"] = equity

    equity_df = pd.DataFrame(equity_rows).set_index("date")
    running_max = equity_df["equity"].cummax()
    equity_df["drawdown"] = equity_df["equity"] / running_max - 1.0
    equity_df["returns"] = equity_df["equity"].pct_change().fillna(0.0)

    trades_frame = _trades_to_frame(all_trades, params)

    return {
        "trades": all_trades,
        "trades_frame": trades_frame,
        "equity_curve": equity_df[["equity", "drawdown", "returns"]],
        "daily_returns": equity_df[["returns"]],
        "params": params.to_dict(),
    }


def _empty_result(params: BreakoutParams) -> dict:
    empty_eq = pd.DataFrame(
        {"equity": [float(params.initial_capital)], "drawdown": [0.0], "returns": [0.0]},
        index=pd.DatetimeIndex([pd.Timestamp.today().normalize()], name="date"),
    )
    return {
        "trades": [],
        "trades_frame": _trades_to_frame([], params),
        "equity_curve": empty_eq,
        "daily_returns": empty_eq[["returns"]],
        "params": params.to_dict(),
    }
