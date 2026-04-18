"""Historical price loading.

Wraps :mod:`yfinance` with a small on-disk cache so that repeated backtest
runs are fast and fully reproducible even on a flaky network.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List

import pandas as pd


LOGGER = logging.getLogger(__name__)

#: Columns we expect downstream.
_REQUIRED_COLS = ["open", "high", "low", "close", "volume"]


def _cache_path(cache_dir: Path, ticker: str, start: str, end: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{ticker.replace('/', '_')}_{start}_{end}.csv"
    return cache_dir / fname


def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case columns, collapse yfinance MultiIndex if present, drop NaNs."""

    if isinstance(df.columns, pd.MultiIndex):
        # yfinance returns a MultiIndex even for a single ticker when
        # `group_by='ticker'`; we take the inner level.
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    df = df.rename(columns=str.lower)
    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"price frame is missing required columns: {missing}")

    df = df[_REQUIRED_COLS].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    return df


def download_prices(
    ticker: str,
    start: str,
    end: str,
    cache_dir: Path | str = "data/cache",
) -> pd.DataFrame:
    """Download OHLCV for a single ticker with on-disk parquet caching.

    Returns a DataFrame indexed by ``date`` with columns
    ``[open, high, low, close, volume]``.
    """

    cache_dir = Path(cache_dir)
    path = _cache_path(cache_dir, ticker, start, end)
    if path.exists():
        LOGGER.debug("cache hit for %s", ticker)
        return pd.read_csv(path, index_col=0, parse_dates=True)

    import yfinance as yf  # imported lazily so tests don't need the network

    LOGGER.info("downloading %s from yfinance", ticker)
    raw = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        auto_adjust=True,  # split/div-adjusted OHLC — appropriate for research
        actions=False,
    )
    if raw is None or raw.empty:
        raise RuntimeError(f"no data returned for {ticker}")

    df = _standardize(raw)
    df.to_csv(path)
    return df


def download_universe(
    tickers: Iterable[str],
    start: str,
    end: str,
    cache_dir: Path | str = "data/cache",
) -> dict[str, pd.DataFrame]:
    """Download every ticker in the universe, skipping failures with a warning."""

    out: dict[str, pd.DataFrame] = {}
    failed: List[str] = []
    for t in tickers:
        try:
            out[t] = download_prices(t, start, end, cache_dir=cache_dir)
        except Exception as exc:  # pragma: no cover — network edge cases
            LOGGER.warning("skipping %s: %s", t, exc)
            failed.append(t)
    if failed:
        LOGGER.warning("failed tickers: %s", failed)
    return out
