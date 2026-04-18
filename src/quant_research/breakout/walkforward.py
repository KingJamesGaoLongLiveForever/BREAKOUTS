"""Rolling walk-forward optimization of the Donchian entry lookback.

For each non-overlapping block of ``test_window_days`` (default: 252
trading days ≈ 1 year) we:

1. Look at the ``train_window_days`` prior to that block.
2. For each candidate lookback in ``entry_lookback_grid``, run a short
   in-sample backtest restricted to the training window.
3. Pick the lookback with the best *in-sample Sharpe* (ties broken by
   total return).  If the training window produces no trades for any
   grid point, fall back to the static default.
4. Apply that lookback to the next out-of-sample block.

The chosen lookback per block is returned along with a full out-of-sample
backtest that stitches the individual block choices together.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .backtest import run_backtest
from .config import BreakoutParams
from .metrics import sharpe_ratio


def _block_sharpe(
    universe: Dict[str, pd.DataFrame],
    params: BreakoutParams,
    entry_lookback: int,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[float, float]:
    """Backtest a single (lookback, window) combo and report (sharpe, total_ret)."""

    # The trailing-exit channel must be strictly shorter than the entry
    # channel; otherwise detect_breakouts refuses to run.  Shrink it if a
    # small grid point would violate the invariant.
    exit_lb = min(params.exit_lookback_days, max(5, entry_lookback - 1))
    sub_params = BreakoutParams(**{
        **params.to_dict(),
        "entry_lookback_days": entry_lookback,
        "exit_lookback_days": exit_lb,
    })
    result = run_backtest(
        universe=universe,
        params=sub_params,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
    )
    eq = result["equity_curve"]["equity"]
    ret = result["equity_curve"]["returns"]
    if len(eq) < 10 or len(result["trades"]) == 0:
        return float("-inf"), 0.0
    sr = sharpe_ratio(ret, sub_params)
    if not np.isfinite(sr):
        sr = float("-inf")
    total_ret = float(eq.iloc[-1] / eq.iloc[0] - 1)
    return sr, total_ret


def walk_forward(
    universe: Dict[str, pd.DataFrame],
    params: BreakoutParams,
    start: str,
    end: str,
) -> dict:
    """Run a rolling walk-forward backtest.

    Returns a dict with:

    * ``schedule``    — DataFrame of (train_start, train_end, test_start,
      test_end, chosen_lookback, train_sharpe)
    * ``oos_backtest``— full backtest result using the chosen lookbacks
    * ``lookback_overrides`` — dict of ``{test_start -> lookback}``
    """

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)

    # Build a master calendar from the universe to step through.
    idx = pd.DatetimeIndex([])
    for df in universe.values():
        idx = idx.union(df.index)
    idx = idx[(idx >= start_ts) & (idx <= end_ts)].sort_values()
    if len(idx) < params.train_window_days + params.test_window_days:
        raise ValueError(
            f"not enough history ({len(idx)} bars) for "
            f"train={params.train_window_days} + test={params.test_window_days}"
        )

    schedule_rows: List[dict] = []
    overrides: Dict[pd.Timestamp, int] = {}

    cursor = params.train_window_days
    while cursor + params.test_window_days <= len(idx):
        train_start = idx[cursor - params.train_window_days]
        train_end = idx[cursor - 1]
        test_start = idx[cursor]
        test_end = idx[min(cursor + params.test_window_days - 1, len(idx) - 1)]

        best_lb, best_sr, best_ret = None, float("-inf"), float("-inf")
        for lb in params.entry_lookback_grid:
            sr, tr = _block_sharpe(universe, params, lb, train_start, train_end)
            if (sr > best_sr) or (sr == best_sr and tr > best_ret):
                best_lb, best_sr, best_ret = lb, sr, tr

        if best_lb is None or not np.isfinite(best_sr):
            best_lb = params.entry_lookback_days

        overrides[test_start] = best_lb
        schedule_rows.append({
            "train_start": train_start.date().isoformat(),
            "train_end": train_end.date().isoformat(),
            "test_start": test_start.date().isoformat(),
            "test_end": test_end.date().isoformat(),
            "chosen_lookback": best_lb,
            "train_sharpe": best_sr if np.isfinite(best_sr) else None,
        })

        cursor += params.test_window_days

    schedule = pd.DataFrame(schedule_rows)

    # Stitch the OOS backtest using the chosen per-block lookbacks.
    first_test_start = pd.Timestamp(schedule.iloc[0]["test_start"])
    last_test_end = pd.Timestamp(schedule.iloc[-1]["test_end"])
    oos = run_backtest(
        universe=universe,
        params=params,
        start=first_test_start.strftime("%Y-%m-%d"),
        end=last_test_end.strftime("%Y-%m-%d"),
        lookback_overrides=overrides,
    )

    return {
        "schedule": schedule,
        "oos_backtest": oos,
        "lookback_overrides": {k.strftime("%Y-%m-%d"): v for k, v in overrides.items()},
    }
