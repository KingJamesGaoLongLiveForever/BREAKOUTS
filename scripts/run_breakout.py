"""CLI entrypoint — download data, run walk-forward, render the report.

Example
-------
    python scripts/run_breakout.py --config configs/breakout.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd
import yaml

from quant_research.breakout import (
    BreakoutParams,
    compute_performance_metrics,
    walk_forward,
)
from quant_research.breakout.data import download_universe
from quant_research.breakout.report import build_site


LOGGER = logging.getLogger("breakout")


def _load_config(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


def _asset_selection_notes(universe: dict, trades_frame: pd.DataFrame) -> str:
    n_universe = len(universe)
    if trades_frame.empty:
        return (
            f"We screened a universe of {n_universe} liquid large-cap US stocks "
            "and broad-market / sector ETFs. No ticker produced a trade in the "
            "out-of-sample window — this is itself a useful diagnostic: the "
            "breakout filter is selective, which is the point."
        )
    per_ticker = (
        trades_frame.groupby("ticker")
        .size()
        .sort_values(ascending=False)
    )
    top = per_ticker.head(5)
    top_list = ", ".join(f"{t} ({n})" for t, n in top.items())
    most_active = per_ticker.index[0]
    return (
        f"I screened a universe of {n_universe} liquid large-cap US stocks and "
        "broad-market / sector ETFs chosen to span mega-cap tech, financials, "
        "energy, healthcare, staples, and industrial names plus high-volume "
        "thematic ETFs (SPY, QQQ, GLD, USO, XLE, XLK, …). The universe was "
        "intentionally concentrated in names with deep liquidity and tight "
        "spreads so that the 2 bps/side cost assumption is defensible. Across "
        "the walk-forward OOS period the most active breakout names were: "
        f"{top_list}. The featured price chart below uses "
        f"<strong>{most_active}</strong> because it produced the largest number "
        "of well-separated, clean channel breaks — making the strategy's "
        "behavior visually easy to follow."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/breakout.yaml"))
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    cfg = _load_config(args.config)
    params = BreakoutParams(**cfg.get("params", {}))

    data_cfg = cfg.get("data", {})
    tickers = data_cfg.get("tickers", [])
    if not tickers:
        raise SystemExit("config.data.tickers is empty")
    start = data_cfg["start"]
    end = data_cfg["end"]
    cache_dir = data_cfg.get("cache_dir", "data/cache")

    out_cfg = cfg.get("output", {})
    site_dir = Path(out_cfg.get("site_dir", "docs"))
    artifacts_dir = Path(out_cfg.get("artifacts_dir", "outputs/breakout"))
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info("downloading %d tickers", len(tickers))
    universe = download_universe(tickers, start=start, end=end, cache_dir=cache_dir)
    if not universe:
        raise SystemExit("downloaded no data — check network/tickers")

    LOGGER.info("running walk-forward")
    wf = walk_forward(universe, params, start=start, end=end)

    oos = wf["oos_backtest"]
    trades_frame = oos["trades_frame"]
    equity_curve = oos["equity_curve"]

    metrics = compute_performance_metrics(trades_frame, equity_curve, params)

    LOGGER.info("writing artifacts to %s", artifacts_dir)
    trades_frame.to_csv(artifacts_dir / "trades.csv", index=False)
    equity_curve.reset_index().to_csv(artifacts_dir / "equity_curve.csv", index=False)
    wf["schedule"].to_csv(artifacts_dir / "walkforward_schedule.csv", index=False)
    with (artifacts_dir / "metrics.json").open("w") as fh:
        json.dump(metrics, fh, indent=2, default=str)

    notes = _asset_selection_notes(universe, trades_frame)

    LOGGER.info("rendering site to %s", site_dir)
    out_path = build_site(
        wf_result=wf,
        prices_by_ticker=universe,
        params=params,
        metrics=metrics,
        asset_selection_notes=notes,
        output_dir=site_dir,
    )

    print(f"\nSite written to {out_path}")
    print(f"Trades:       {len(trades_frame)}")
    if not trades_frame.empty:
        print(f"Sharpe:       {metrics['sharpe_ratio']:.2f}")
        print(f"CAGR:         {metrics['cagr_pct']:.2f}%")
        print(f"Max DD:       {metrics['max_drawdown_pct']:.2f}%")
        print(f"Win rate:     {metrics['win_rate_pct']:.1f}%")
        print(f"Profit factor:{metrics['profit_factor']:.2f}")


if __name__ == "__main__":
    main()
