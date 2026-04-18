"""Performance metrics for the breakout backtest.

All metrics operate on two inputs:

* a trade blotter (``DataFrame`` or list of :class:`Trade`) — for
  per-trade statistics like win rate, profit factor, expectancy.
* a daily-returns series — for time-series statistics like Sharpe,
  Sortino, and max drawdown.

Sharpe uses an explicitly stated annual risk-free rate (default 4 %,
converted to a daily rate) so the number is reproducible.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from .config import BreakoutParams, DEFAULT_PARAMS


def _daily_rf(params: BreakoutParams) -> float:
    return (1 + params.risk_free_rate) ** (1 / params.trading_days_per_year) - 1


_NUM_EPS = 1e-12


def sharpe_ratio(daily_returns: pd.Series, params: BreakoutParams = DEFAULT_PARAMS) -> float:
    if daily_returns is None or len(daily_returns) < 2:
        return float("nan")
    excess = daily_returns - _daily_rf(params)
    std = float(excess.std(ddof=1))
    if not np.isfinite(std) or std < _NUM_EPS:
        return float("nan")
    return float(excess.mean() / std * np.sqrt(params.trading_days_per_year))


def sortino_ratio(daily_returns: pd.Series, params: BreakoutParams = DEFAULT_PARAMS) -> float:
    if daily_returns is None or len(daily_returns) < 2:
        return float("nan")
    excess = daily_returns - _daily_rf(params)
    downside = excess[excess < 0]
    if downside.empty:
        return float("nan")
    dd = float(np.sqrt((downside ** 2).mean()))
    if not np.isfinite(dd) or dd < _NUM_EPS:
        return float("nan")
    return float(excess.mean() / dd * np.sqrt(params.trading_days_per_year))


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    return float(dd.min())


def cagr(equity: pd.Series, params: BreakoutParams = DEFAULT_PARAMS) -> float:
    if equity.empty:
        return 0.0
    total_return = equity.iloc[-1] / equity.iloc[0]
    years = len(equity) / params.trading_days_per_year
    if years <= 0 or total_return <= 0:
        return 0.0
    return float(total_return ** (1 / years) - 1)


def compute_performance_metrics(
    trades_frame: pd.DataFrame,
    equity_curve: pd.DataFrame,
    params: BreakoutParams = DEFAULT_PARAMS,
) -> Dict[str, float | int | str]:
    """Compute the full metric panel used by the report."""

    metrics: Dict[str, float | int | str] = {
        "num_trades": int(len(trades_frame)),
        "risk_free_rate": params.risk_free_rate,
    }

    if len(trades_frame) == 0:
        metrics.update({
            "avg_return_per_trade_pct": 0.0,
            "median_return_per_trade_pct": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": float("nan"),
            "expectancy_pct": 0.0,
            "avg_holding_days": 0.0,
            "sharpe_ratio": float("nan"),
            "sortino_ratio": float("nan"),
            "max_drawdown_pct": 0.0,
            "cagr_pct": 0.0,
            "total_return_pct": 0.0,
        })
        return metrics

    ret = trades_frame["return_pct"]
    wins = trades_frame[trades_frame["net_pnl"] > 0]
    losses = trades_frame[trades_frame["net_pnl"] < 0]

    gross_win = wins["net_pnl"].sum()
    gross_loss = -losses["net_pnl"].sum()
    profit_factor = float(gross_win / gross_loss) if gross_loss > 0 else float("inf")

    win_rate = float(len(wins) / len(trades_frame))
    avg_win = float(wins["return_pct"].mean()) if not wins.empty else 0.0
    avg_loss = float(losses["return_pct"].mean()) if not losses.empty else 0.0
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

    outcomes = trades_frame["outcome"].value_counts().to_dict()

    daily_returns = equity_curve["returns"] if "returns" in equity_curve else pd.Series(dtype=float)
    equity = equity_curve["equity"] if "equity" in equity_curve else pd.Series(dtype=float)

    metrics.update({
        "avg_return_per_trade_pct": float(ret.mean() * 100),
        "median_return_per_trade_pct": float(ret.median() * 100),
        "win_rate_pct": win_rate * 100,
        "profit_factor": profit_factor,
        "expectancy_pct": expectancy * 100,
        "avg_holding_days": float(trades_frame["holding_days"].mean()),
        "sharpe_ratio": sharpe_ratio(daily_returns, params),
        "sortino_ratio": sortino_ratio(daily_returns, params),
        "max_drawdown_pct": max_drawdown(equity) * 100,
        "cagr_pct": cagr(equity, params) * 100,
        "total_return_pct": float((equity.iloc[-1] / equity.iloc[0] - 1) * 100) if not equity.empty else 0.0,
        "outcomes_stop_loss": int(outcomes.get("stop_loss", 0)),
        "outcomes_successful": int(outcomes.get("successful", 0)),
        "outcomes_timeout": int(outcomes.get("timeout", 0)),
    })
    return metrics
