"""Breakout detection.

The breakout definition used here is the classic *Donchian channel* rule,
popularised by the Turtle Traders in the 1980s:

* **Long breakout**: today's close exceeds the highest close of the prior
  ``entry_lookback_days`` sessions (optionally by a small buffer).
* **Short breakout**: today's close falls below the lowest close of the
  prior ``entry_lookback_days`` sessions (optionally by a small buffer).

An auxiliary *trailing exit* channel (``exit_lookback_days``, typically
shorter than the entry channel) is returned so the backtester can close
trades as soon as momentum fades.  We also pre-compute the Average True
Range (ATR) on the same frame so stop placement is trivial downstream.

All tunable thresholds live in :mod:`quant_research.breakout.config` and
are surfaced as keyword arguments here.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .config import (
    ATR_LOOKBACK_DAYS,
    BREAKOUT_BUFFER_PCT,
    ENTRY_LOOKBACK_DAYS,
    EXIT_LOOKBACK_DAYS,
    MIN_ATR_PCT,
)


def average_true_range(prices: pd.DataFrame, window: int = ATR_LOOKBACK_DAYS) -> pd.Series:
    """Wilder-style ATR computed with a simple rolling mean.

    Using a simple mean instead of Wilder's smoothing keeps the computation
    deterministic and makes the first ``window`` bars exactly NaN — handy
    for unit tests.
    """

    high = prices["high"]
    low = prices["low"]
    prev_close = prices["close"].shift(1)

    true_range = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return true_range.rolling(window=window, min_periods=window).mean()


def detect_breakouts(
    prices: pd.DataFrame,
    entry_lookback_days: int = ENTRY_LOOKBACK_DAYS,
    exit_lookback_days: int = EXIT_LOOKBACK_DAYS,
    atr_lookback_days: int = ATR_LOOKBACK_DAYS,
    breakout_buffer_pct: float = BREAKOUT_BUFFER_PCT,
    min_atr_pct: float = MIN_ATR_PCT,
    long_short: bool = True,
) -> pd.DataFrame:
    """Return a per-bar breakout signal frame.

    Parameters
    ----------
    prices:
        Daily OHLCV frame indexed by date.  Columns ``open``, ``high``,
        ``low``, ``close`` are required.
    entry_lookback_days:
        Donchian entry channel length (days).
    exit_lookback_days:
        Donchian trailing exit channel length (days).  Must be < entry.
    atr_lookback_days:
        ATR window used for stop placement and volatility filtering.
    breakout_buffer_pct:
        Minimum fractional breach of the entry channel (e.g. ``0.001`` is
        10bp).  Zero means any break counts.
    min_atr_pct:
        If ATR/price falls below this, suppress signals for that bar.
    long_short:
        If ``False``, short breakout signals are zeroed out.

    Returns
    -------
    pd.DataFrame
        Columns:

        * ``close``        — raw close (passthrough, convenient for plots)
        * ``upper_entry``  — prior-N high (the long breakout line)
        * ``lower_entry``  — prior-N low  (the short breakout line)
        * ``upper_exit``   — prior-M high (used as short trailing stop)
        * ``lower_exit``   — prior-M low  (used as long trailing stop)
        * ``atr``          — ATR on the ``atr_lookback_days`` window
        * ``long_signal``  — bool, True on bars where we open a new long
        * ``short_signal`` — bool, True on bars where we open a new short
    """

    if exit_lookback_days >= entry_lookback_days:
        raise ValueError(
            "exit_lookback_days must be strictly shorter than entry_lookback_days "
            "(trailing exit must tighten faster than entry extends)."
        )

    close = prices["close"]
    high = prices["high"]
    low = prices["low"]

    # Use .shift(1) so that today's signal only depends on *prior* bars —
    # no lookahead.  "Is today's close > yesterday's 55-day high?" etc.
    upper_entry = high.rolling(entry_lookback_days).max().shift(1)
    lower_entry = low.rolling(entry_lookback_days).min().shift(1)
    upper_exit = high.rolling(exit_lookback_days).max().shift(1)
    lower_exit = low.rolling(exit_lookback_days).min().shift(1)

    atr = average_true_range(prices, window=atr_lookback_days)

    # Buffered breakout thresholds — a 10bp buffer means the close has to
    # clear the prior high by 0.1 % of the channel width, not just touch it.
    channel_width = (upper_entry - lower_entry).abs()
    buffer = (breakout_buffer_pct * channel_width).fillna(0.0)

    long_signal = close > (upper_entry + buffer)
    short_signal = close < (lower_entry - buffer)

    # Volatility filter — skip dead markets.
    atr_pct = atr / close
    alive = atr_pct >= min_atr_pct
    long_signal &= alive
    short_signal &= alive

    if not long_short:
        short_signal = pd.Series(False, index=close.index)

    out = pd.DataFrame(
        {
            "close": close,
            "upper_entry": upper_entry,
            "lower_entry": lower_entry,
            "upper_exit": upper_exit,
            "lower_exit": lower_exit,
            "atr": atr,
            "long_signal": long_signal.fillna(False).astype(bool),
            "short_signal": short_signal.fillna(False).astype(bool),
        }
    )
    return out


def first_crossing_index(values: pd.Series, threshold: pd.Series, above: bool) -> Optional[pd.Timestamp]:
    """Return the first date where ``values`` crosses ``threshold``.

    Used by the backtester when it needs to know when a trailing stop was
    breached inside a held window.  Exposed here so it can be unit-tested.
    """

    if above:
        hit = values >= threshold
    else:
        hit = values <= threshold
    hit = hit[hit]
    if hit.empty:
        return None
    return hit.index[0]
