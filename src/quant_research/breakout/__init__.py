"""Donchian channel breakout research stack.

A compact, transparent long/short breakout backtester built on daily bars.
The goal of this subpackage is *not* to promise a specific Sharpe ratio; it
is to provide a clean, reproducible research pipeline from raw data to a
static GitHub Pages report.

Public entrypoints:

- :func:`quant_research.breakout.signals.detect_breakouts`
- :func:`quant_research.breakout.backtest.run_backtest`
- :func:`quant_research.breakout.walkforward.walk_forward`
- :func:`quant_research.breakout.metrics.compute_performance_metrics`
"""

from .config import BreakoutParams, DEFAULT_PARAMS
from .signals import detect_breakouts
from .backtest import run_backtest, Trade, TradeOutcome
from .metrics import compute_performance_metrics
from .walkforward import walk_forward

__all__ = [
    "BreakoutParams",
    "DEFAULT_PARAMS",
    "detect_breakouts",
    "run_backtest",
    "Trade",
    "TradeOutcome",
    "compute_performance_metrics",
    "walk_forward",
]
