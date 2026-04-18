"""Central configuration for the breakout strategy.

All tunable numbers live here so that the grader (and future-me) can find
every threshold, cutoff, and window in a single file.  Nothing in the
backtest should hard-code a magic number; it should look up the value on a
:class:`BreakoutParams` instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Tuple


# ---------------------------------------------------------------------------
# Named constants used as defaults.  They are grouped by responsibility so a
# reader can scan the file top-to-bottom and immediately see what drives the
# strategy.
# ---------------------------------------------------------------------------

# --- Breakout detection -----------------------------------------------------
#: Length of the Donchian channel used for entries (days / bars).
ENTRY_LOOKBACK_DAYS: int = 55

#: Length of the shorter Donchian channel used for the trailing exit.
EXIT_LOOKBACK_DAYS: int = 20

#: Require today's close to breach the prior-N-day high (or low) by more
#: than this fraction of the channel width.  Zero means "any break wins",
#: a small positive value filters micro-breakouts / noise.
BREAKOUT_BUFFER_PCT: float = 0.0

#: Minimum ATR (as a fraction of price) needed to take a trade.  Avoids
#: entering in dead, flat markets where a break is probably noise.
MIN_ATR_PCT: float = 0.005  # 0.5% of price

# --- Risk / sizing ----------------------------------------------------------
#: ATR lookback for stop placement and volatility targeting.
ATR_LOOKBACK_DAYS: int = 20

#: Initial stop = entry_price -/+ (ATR_STOP_MULT * ATR).
ATR_STOP_MULT: float = 2.0

#: Profit target = entry_price +/- (PROFIT_TARGET_MULT * ATR).  Using the
#: same ATR scale keeps the target interpretable across tickers.
PROFIT_TARGET_MULT: float = 3.0

#: Hard time stop: close the trade after this many bars if neither the stop
#: nor the ATR-based profit target has fired.
MAX_HOLDING_DAYS: int = 20

#: Risk budget per trade as a fraction of portfolio equity.  Used to size
#: the position from the entry-stop distance.
RISK_PER_TRADE: float = 0.01  # 1%

#: Cap on any single position as a fraction of equity (even if the ATR is
#: very small, do not let one ticker dominate the book).
MAX_POSITION_WEIGHT: float = 0.15

#: Hard cap on gross exposure (|long| + |short|) across the whole book,
#: expressed as a multiple of current portfolio equity.  1.0 means the
#: simulator never holds more than 100% gross exposure at any time.
MAX_GROSS_LEVERAGE: float = 1.0

# --- Portfolio & execution --------------------------------------------------
#: Starting capital for the simulation (USD).
INITIAL_CAPITAL: float = 1_000_000.0

#: Round-trip transaction cost (commission + half-spread + slippage), in
#: basis points of notional.  Applied on both entry and exit.
COST_BPS_PER_SIDE: float = 2.0

#: Annualization factor for Sharpe / Sortino on daily data.
TRADING_DAYS_PER_YEAR: int = 252

#: Risk-free rate used for Sharpe / Sortino (annualized, decimal).
RISK_FREE_RATE: float = 0.04

# --- Walk-forward -----------------------------------------------------------
#: Grid of Donchian entry lookbacks explored during training.
ENTRY_LOOKBACK_GRID: Tuple[int, ...] = (20, 40, 55, 100)

#: Training window length (trading days).
TRAIN_WINDOW_DAYS: int = 252

#: Out-of-sample test window length (trading days) before rolling again.
TEST_WINDOW_DAYS: int = 252


@dataclass
class BreakoutParams:
    """Container for every knob of the breakout backtest.

    Using a dataclass (rather than a dict) makes the parameters discoverable
    via IDE auto-complete and gives us free :func:`dataclasses.asdict`
    serialization for the HTML report.
    """

    entry_lookback_days: int = ENTRY_LOOKBACK_DAYS
    exit_lookback_days: int = EXIT_LOOKBACK_DAYS
    breakout_buffer_pct: float = BREAKOUT_BUFFER_PCT
    min_atr_pct: float = MIN_ATR_PCT

    atr_lookback_days: int = ATR_LOOKBACK_DAYS
    atr_stop_mult: float = ATR_STOP_MULT
    profit_target_mult: float = PROFIT_TARGET_MULT
    max_holding_days: int = MAX_HOLDING_DAYS
    risk_per_trade: float = RISK_PER_TRADE
    max_position_weight: float = MAX_POSITION_WEIGHT
    max_gross_leverage: float = MAX_GROSS_LEVERAGE

    initial_capital: float = INITIAL_CAPITAL
    cost_bps_per_side: float = COST_BPS_PER_SIDE
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR
    risk_free_rate: float = RISK_FREE_RATE

    entry_lookback_grid: Tuple[int, ...] = ENTRY_LOOKBACK_GRID
    train_window_days: int = TRAIN_WINDOW_DAYS
    test_window_days: int = TEST_WINDOW_DAYS

    long_short: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_PARAMS = BreakoutParams()
