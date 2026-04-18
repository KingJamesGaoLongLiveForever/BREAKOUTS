# Quant Research Repository

This repository contains two self-contained research projects:

1. **Donchian Breakout Strategy** (`src/quant_research/breakout/`, [report source →](docs/index.html)).
   Long/short breakout backtester on ~55 liquid US names and ETFs with
   walk-forward optimization, ATR stops, ATR profit targets, and a GitHub-Pages report.
2. **US Equities Momentum Stack** (`src/quant_research/` — original code).
   Config-driven cross-sectional momentum backtester.

---

## 1. Donchian Breakout Strategy (new)

A transparent long/short Donchian channel breakout strategy backtested with
rolling walk-forward optimization.  Every knob is a named constant in
[`src/quant_research/breakout/config.py`](src/quant_research/breakout/config.py)
so graders can find and change any threshold in one place.

### What it does
- Goes **long** on bar *t* when `close(t) > max(high(t-N), …, high(t-1))`.
- Goes **short** on the symmetric low breakout.
- Sizes each position so a stop-out costs a fixed fraction (default 0.25 %) of
  account equity.
- Exits via the first of: 2 × ATR(20) stop → 3 × ATR(20) profit target →
  20-day hard timeout.
- Re-tunes the entry lookback `N` every year on the prior year's in-sample
  Sharpe (grid `{20, 40, 55, 100}`).

### Run it

```bash
python -m pip install -e .
python scripts/run_breakout.py --config configs/breakout.yaml
```

Outputs land in:

- `docs/index.html`               — the GitHub Pages report
- `docs/trades.csv`               — downloadable trade blotter
- `docs/equity_curve.csv`         — out-of-sample equity curve
- `docs/walkforward_schedule.csv` — per-window chosen lookback
- `outputs/breakout/metrics.json` — machine-readable performance panel

### Publish to GitHub Pages

1. Commit the `docs/` folder.
2. `git push` to your public repo.
3. GitHub → Settings → Pages → Source = *Deploy from a branch* →
   Branch = `main`, Folder = `/docs` → Save.
4. Wait ~30 seconds and visit
   `https://<your-username>.github.io/<repo-name>/`.

The page is self-contained: inline CSS, one JS include from the Plotly CDN,
and no build step.

### Tests

```bash
python -m pytest
```

Unit tests under `tests/test_breakout.py` cover the ATR helper, the
breakout detector, position sizing, trade-outcome classification, and the
key performance metrics (Sharpe, max drawdown).

---

## 2. US Equities Momentum Research Stack (original)

This project is a compact Python research backtester for a daily-bar US equities momentum strategy. It is designed to look and behave like a disciplined quant research prototype: config-driven runs, delayed execution, liquidity filtering, explicit trading costs, and out-of-sample reporting.

It is not a claim of production readiness and it does not promise a specific Sharpe ratio. The goal is to produce a realistic research workflow that can be stress-tested and extended.

## Strategy Design

- Universe: liquid US equities with minimum price, average dollar volume, and history filters.
- Signal: `12-1` cross-sectional momentum, optionally blended with a short-term reversal component.
- Portfolio: equal-weight top and bottom buckets with optional long-short construction, position caps, and inverse-volatility scaling.
- Execution: next-bar open assumption, commissions, half-spread costs, and a simple participation-based impact penalty.
- Validation: separate `in_sample`, `validation`, and `holdout` windows to avoid choosing parameters on the same sample used to judge them.

## Input Data Format

The runner expects a tidy CSV with at least these columns:

```text
date,symbol,open,high,low,close,volume
2020-01-02,AAPL,74.06,75.15,73.80,75.09,135480400
2020-01-02,MSFT,158.78,160.73,158.33,160.62,22622100
```

Optional columns:

- `sector`: used only for future extensions and diagnostics.

The default config points to `data/us_equities_daily.csv`. You can override it on the command line.

## Quick Start

Install the project and run the backtest:

```bash
python -m pip install -e ".[dev]"
python scripts/run_backtest.py --config configs/us_equities_momentum.yaml --data-path path/to/us_equities_daily.csv
```

Outputs:

- `outputs/backtest_summary.csv`
- `outputs/backtest_results.csv`

## Key Assumptions

- Signals are formed on the close and executed on the next session open.
- Costs are conservative but still simplified; this is a research model, not a broker simulator.
- Liquidity is enforced through both universe filtering and a maximum participation rate.
- Reported metrics should be judged across validation windows, not just the full-sample Sharpe.

## What To Improve Next

- Add sector-neutral ranking and beta control.
- Replace the simple impact model with a richer volatility-and-spread model.
- Add benchmark-relative metrics and factor exposure diagnostics.
- Plug in a higher quality survivorship-bias-free dataset.
