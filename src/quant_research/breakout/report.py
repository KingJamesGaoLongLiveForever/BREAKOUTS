"""Render the GitHub Pages site for the breakout strategy.

Produces a single self-contained ``docs/index.html`` (plus a few static
asset files) that answers every required section of the assignment:

1. Breakout detection function — plain-English description + parameter
   snapshot.
2. Trade ledger — a readable HTML table + downloadable ``trades.csv`` and
   ``trades.parquet``.
3. Trade outcome histogram + return distribution.
4. Performance metrics panel with risk-free rate shown.
5. Strategy logic paragraph, asset selection, breakout definition.

The page uses only inline CSS and the Plotly JS CDN — no build step,
no framework — which is ideal for GitHub Pages hosting.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from .config import BreakoutParams
from .plots import (
    equity_and_drawdown,
    price_with_trades,
    return_distribution,
    trade_outcome_histogram,
)


def _fig_to_div(fig: go.Figure, div_id: str) -> str:
    return pio.to_html(
        fig,
        include_plotlyjs=False,
        full_html=False,
        div_id=div_id,
        config={"displaylogo": False, "responsive": True},
    )


def _metric_card(label: str, value: str, blurb: str) -> str:
    return f"""
    <div class="metric-card">
      <div class="metric-label">{html.escape(label)}</div>
      <div class="metric-value">{html.escape(value)}</div>
      <div class="metric-blurb">{html.escape(blurb)}</div>
    </div>
    """


def _format_metrics_panel(metrics: Dict, params: BreakoutParams) -> str:
    def fmt(x, pct=False, dec=2):
        if x is None:
            return "n/a"
        try:
            if pd.isna(x):
                return "n/a"
        except Exception:
            pass
        if pct:
            return f"{x:.{dec}f}%"
        return f"{x:.{dec}f}"

    rf_pct = f"{params.risk_free_rate * 100:.2f}%"

    cards = [
        _metric_card(
            "Average return / trade",
            fmt(metrics["avg_return_per_trade_pct"], pct=True),
            "Mean of per-trade % P&L. A positive value means the typical trade is a winner.",
        ),
        _metric_card(
            "Sharpe ratio (ann.)",
            fmt(metrics["sharpe_ratio"]),
            f"Daily excess returns over rf={rf_pct}, annualized by sqrt(252). Higher is better.",
        ),
        _metric_card(
            "Sortino ratio (ann.)",
            fmt(metrics["sortino_ratio"]),
            "Like Sharpe but penalizes only downside vol. Helpful for asymmetric breakout P&Ls.",
        ),
        _metric_card(
            "Win rate",
            fmt(metrics["win_rate_pct"], pct=True, dec=1),
            "Fraction of trades with positive net P&L.",
        ),
        _metric_card(
            "Profit factor",
            fmt(metrics["profit_factor"]),
            "Gross winning P&L / gross losing P&L. >1 means winners dominate losers.",
        ),
        _metric_card(
            "Expectancy / trade",
            fmt(metrics["expectancy_pct"], pct=True, dec=3),
            "win_rate · avg_win + (1-win_rate) · avg_loss. Statistical edge per trade.",
        ),
        _metric_card(
            "Max drawdown",
            fmt(metrics["max_drawdown_pct"], pct=True),
            "Worst peak-to-trough equity decline. Risk budget reality-check.",
        ),
        _metric_card(
            "CAGR",
            fmt(metrics["cagr_pct"], pct=True),
            "Compounded annual growth rate of the equity curve over the OOS period.",
        ),
        _metric_card(
            "Total return (OOS)",
            fmt(metrics["total_return_pct"], pct=True),
            "Total equity change over the walk-forward out-of-sample window.",
        ),
        _metric_card(
            "# trades",
            f"{int(metrics['num_trades'])}",
            "Sample size the other stats are computed on.",
        ),
        _metric_card(
            "Avg holding days",
            fmt(metrics["avg_holding_days"], dec=1),
            f"Mean bars per trade. Timeout cap is {params.max_holding_days} days.",
        ),
    ]
    return "<div class='metrics-grid'>" + "\n".join(cards) + "</div>"


def _trade_outcome_summary(metrics: Dict) -> str:
    total = (metrics.get("outcomes_stop_loss", 0)
             + metrics.get("outcomes_successful", 0)
             + metrics.get("outcomes_timeout", 0))
    if total == 0:
        return "<p><em>No trades were generated.</em></p>"
    rows = [
        ("Successful (profit target)", metrics.get("outcomes_successful", 0)),
        ("Timed out", metrics.get("outcomes_timeout", 0)),
        ("Stop-loss triggered", metrics.get("outcomes_stop_loss", 0)),
    ]
    body = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{v}</td><td>{v/total*100:.1f}%</td></tr>"
        for k, v in rows
    )
    return f"""
    <table class='summary-table'>
      <thead><tr><th>Outcome</th><th>Trades</th><th>Share</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
    """


def _walkforward_schedule(schedule: pd.DataFrame) -> str:
    if schedule.empty:
        return "<p><em>No walk-forward schedule.</em></p>"
    rows = "".join(
        f"<tr><td>{r['train_start']}</td><td>{r['train_end']}</td>"
        f"<td>{r['test_start']}</td><td>{r['test_end']}</td>"
        f"<td>{r['chosen_lookback']}</td>"
        f"<td>{('%.2f' % r['train_sharpe']) if pd.notna(r['train_sharpe']) else 'n/a'}</td></tr>"
        for _, r in schedule.iterrows()
    )
    return f"""
    <table class='summary-table'>
      <thead><tr>
        <th>Train start</th><th>Train end</th>
        <th>Test start</th><th>Test end</th>
        <th>Chosen lookback (days)</th><th>In-sample Sharpe</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _trade_blotter_table(trades_frame: pd.DataFrame, max_rows: int = 400) -> str:
    if trades_frame.empty:
        return "<p><em>No trades were generated.</em></p>"

    shown = trades_frame.tail(max_rows)
    header = "".join(f"<th>{html.escape(c)}</th>" for c in shown.columns)
    body = []
    for _, row in shown.iterrows():
        cells = []
        for c in shown.columns:
            v = row[c]
            if isinstance(v, float):
                if c in ("return_pct",):
                    cells.append(f"<td>{v*100:.2f}%</td>")
                elif c in ("net_pnl", "gross_pnl", "cost"):
                    cls = "pos" if v > 0 else ("neg" if v < 0 else "")
                    cells.append(f"<td class='{cls}'>{v:,.2f}</td>")
                else:
                    cells.append(f"<td>{v:,.4f}</td>")
            else:
                cells.append(f"<td>{html.escape(str(v))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    body_html = "\n".join(body)
    note = ""
    if len(trades_frame) > max_rows:
        note = (
            f"<p class='muted'>Showing the last {max_rows} of {len(trades_frame)} "
            f"trades. Download the full ledger below.</p>"
        )
    return f"""
    {note}
    <div class='table-wrap'>
      <table class='trade-table'>
        <thead><tr>{header}</tr></thead>
        <tbody>{body_html}</tbody>
      </table>
    </div>
    """


def build_site(
    wf_result: dict,
    prices_by_ticker: Dict[str, pd.DataFrame],
    params: BreakoutParams,
    metrics: Dict,
    asset_selection_notes: str,
    output_dir: Path | str = "docs",
    featured_ticker: str | None = None,
) -> Path:
    """Write the full GitHub Pages site to ``output_dir``."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    oos = wf_result["oos_backtest"]
    trades_frame: pd.DataFrame = oos["trades_frame"]
    equity_curve: pd.DataFrame = oos["equity_curve"]
    schedule: pd.DataFrame = wf_result["schedule"]

    # -- write downloadable ledgers ------------------------------------
    trades_frame.to_csv(output_dir / "trades.csv", index=False)
    try:
        trades_frame.to_parquet(output_dir / "trades.parquet", index=False)
    except Exception:
        # parquet is optional; fall back silently if the engine is missing
        pass
    equity_curve.reset_index().to_csv(output_dir / "equity_curve.csv", index=False)
    schedule.to_csv(output_dir / "walkforward_schedule.csv", index=False)

    # -- charts --------------------------------------------------------
    eq_fig = equity_and_drawdown(equity_curve)
    outcome_fig = trade_outcome_histogram(trades_frame)
    return_fig = return_distribution(trades_frame)

    # Pick a "featured" ticker for the price chart (the one with the most
    # trades in the OOS window).  This makes the page instantly readable.
    if featured_ticker is None and not trades_frame.empty:
        featured_ticker = trades_frame["ticker"].value_counts().idxmax()

    if featured_ticker and featured_ticker in prices_by_ticker:
        price_fig = price_with_trades(
            prices=prices_by_ticker[featured_ticker].loc[
                pd.Timestamp(schedule.iloc[0]["test_start"]):
                pd.Timestamp(schedule.iloc[-1]["test_end"])
            ],
            ticker=featured_ticker,
            trades_frame=trades_frame,
            entry_lookback=params.entry_lookback_days,
            exit_lookback=params.exit_lookback_days,
        )
        price_div = _fig_to_div(price_fig, "fig-price")
    else:
        price_div = "<p class='muted'>No trades to plot on a price chart.</p>"

    eq_div = _fig_to_div(eq_fig, "fig-equity")
    outcome_div = _fig_to_div(outcome_fig, "fig-outcomes")
    return_div = _fig_to_div(return_fig, "fig-returns")

    metrics_panel = _format_metrics_panel(metrics, params)
    outcome_table = _trade_outcome_summary(metrics)
    wf_table = _walkforward_schedule(schedule)
    blotter_table = _trade_blotter_table(trades_frame)

    # -- HTML ----------------------------------------------------------
    css = _inline_css()
    params_json = html.escape(json.dumps(params.to_dict(), indent=2, default=str))
    asset_notes_html = html.escape(asset_selection_notes).replace("\n", "<br>")

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Donchian Breakout — Backtest Report</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
  <style>{css}</style>
</head>
<body>
  <header class="hero">
    <div class="container">
      <h1>Donchian Channel Breakout</h1>
      <p class="tagline">
        A transparent long/short breakout strategy on liquid US equities &amp;
        ETFs, validated with rolling walk-forward optimization.
      </p>
      <p class="meta">
        Parameters searched in-sample (1y train) → applied out-of-sample (1y test).
        Risk-free rate: <strong>{params.risk_free_rate*100:.2f}%</strong>
        · Timeout: <strong>{params.max_holding_days} trading days</strong>
        · Stop: <strong>{params.atr_stop_mult}× ATR({params.atr_lookback_days})</strong>
        · Profit target: <strong>{params.profit_target_mult}× ATR({params.atr_lookback_days})</strong>
        · Cost: <strong>{params.cost_bps_per_side} bps / side</strong>
      </p>
    </div>
  </header>

  <main class="container">

    <section>
      <h2>1. Strategy in one paragraph</h2>
      <p>
        This strategy takes long positions when price breaks out <em>above</em> its
        prior N-day high and short positions when it breaks <em>below</em> its
        prior N-day low &mdash; the classic <em>Donchian channel</em> rule used by
        the 1980s Turtle Traders. A breakout is read as statistical evidence that a
        trend has begun. Every trade is protected by a volatility-scaled stop at
        entry <code>± {params.atr_stop_mult} × ATR({params.atr_lookback_days})</code>,
        aims for a symmetric volatility-scaled target at
        <code>± {params.profit_target_mult} × ATR({params.atr_lookback_days})</code>,
        and is closed at the market after a <strong>{params.max_holding_days}-day</strong>
        hard timeout if neither boundary is reached. Position size is set so that a stop-out costs roughly
        <strong>{params.risk_per_trade*100:.1f}%</strong> of current equity, capped at
        <strong>{params.max_position_weight*100:.0f}%</strong> of equity per name. The
        N we use for the entry channel is not fixed &mdash; it is re-chosen each
        year by an in-sample Sharpe search, then frozen for the next year of live
        trading.  Everything in this page is derived from the out-of-sample window
        only.
      </p>
    </section>

    <section>
      <h2>2. Asset selection</h2>
      <p>{asset_notes_html}</p>
    </section>

    <section>
      <h2>3. Breakout definition &amp; parameters</h2>
      <p>
        A <strong>long breakout</strong> fires on bar <em>t</em> when
        <code>close(t) &gt; max(high(t-N), …, high(t-1))</code>.
        A <strong>short breakout</strong> is the symmetric case on the low.
        Here N (the entry channel length) is the single parameter that walk-forward
        optimization tunes; we search the grid
        <code>{list(params.entry_lookback_grid)}</code>. Signals formed on the
        close execute at the <em>next bar's open</em>, never the same close, so
        there is no look-ahead. A position is only opened if ATR(20) is at least
        <code>{params.min_atr_pct*100:.2f}%</code> of price &mdash; filtering out
        dead markets where a "break" is really noise. A trade then exits via the
        first of:
      </p>
      <ol>
        <li><strong>Stop-loss:</strong> intrabar low (for longs) or high (for shorts)
            pierces <code>entry ∓ {params.atr_stop_mult} × ATR({params.atr_lookback_days})</code>
            &rarr; filled at the stop level.</li>
        <li><strong>Successful trade:</strong> intrabar high (for longs) or low (for shorts)
            reaches <code>entry ± {params.profit_target_mult} × ATR({params.atr_lookback_days})</code>
            &rarr; filled at the target level.</li>
        <li><strong>Timeout:</strong> the position has been held for
            <code>{params.max_holding_days}</code> bars and neither of the above has
            fired &rarr; closed at that bar's close (market-on-close).</li>
      </ol>
      <p class="muted">
        A one-paragraph plain-English version of the detector function lives in
        the docstring of <code>src/quant_research/breakout/signals.py</code>
        (<code>detect_breakouts</code>); every threshold above is a named
        constant in <code>src/quant_research/breakout/config.py</code>.
      </p>
    </section>

    <section>
      <h2>4. Performance metrics (out-of-sample)</h2>
      {metrics_panel}
    </section>

    <section>
      <h2>5. Equity curve &amp; drawdown</h2>
      {eq_div}
    </section>

    <section>
      <h2>6. Trade outcomes</h2>
      {outcome_table}
      {outcome_div}
      {return_div}
    </section>

    <section>
      <h2>7. Featured asset: trades on a price chart</h2>
      {price_div}
    </section>

    <section>
      <h2>8. Trade ledger / blotter</h2>
      <p>
        Every trade in the walk-forward out-of-sample window. Download the full
        ledger as <a href="trades.csv" download>CSV</a>
        (or <a href="trades.parquet" download>Parquet</a>).  Additional artifacts:
        <a href="equity_curve.csv" download>equity_curve.csv</a>,
        <a href="walkforward_schedule.csv" download>walkforward_schedule.csv</a>.
      </p>
      {blotter_table}
    </section>

    <section>
      <h2>9. Walk-forward schedule</h2>
      <p>
        For each test year, the lookback N that maximized in-sample Sharpe on the
        prior year is selected and then frozen for the out-of-sample window.
      </p>
      {wf_table}
    </section>

    <section>
      <h2>10. Assumptions</h2>
      <ul>
        <li>Daily bars, split- and dividend-adjusted (<code>yfinance</code>, <code>auto_adjust=True</code>).</li>
        <li>Signals formed on the close; execution on the <em>next bar's open</em>.</li>
        <li>Round-trip cost: <strong>{params.cost_bps_per_side*2:.1f} bps</strong> of notional
            (commission + spread + slippage), applied on both entry and exit.</li>
        <li><strong>Single shared capital pool</strong> of
            <strong>${params.initial_capital:,.0f}</strong>. Every trade, on every ticker,
            is sized off the <em>same</em> running equity.  Exits are processed before new
            entries on each bar, so capital released by a closing trade can be reused that
            same day.  A hard <strong>{params.max_gross_leverage:.1f}×</strong> gross
            leverage cap (|long|+|short| &divide; equity) prevents concurrent entries from
            implicitly over-committing the book.</li>
        <li><strong>Risk-free rate</strong>: <strong>{params.risk_free_rate*100:.2f}%</strong>
            per annum, converted to a daily rate for Sharpe / Sortino.  The reported
            equity curve is <em>pure strategy</em> — idle cash is <em>not</em> accreted at
            rf, so Sharpe can subtract rf explicitly without any double-counting.</li>
        <li>Walk-forward signals are computed on the <em>full</em> price history and then
            sliced to each test window, so rolling-window lookbacks warm up before the
            window starts (no NaN signals at block boundaries).</li>
        <li>Only one open position per ticker at a time; no pyramiding.</li>
        <li>Stop-loss and profit-target priority: if both conditions fire on the same bar,
            the stop-loss is assumed to hit first (conservative fill).</li>
      </ul>
    </section>

    <section>
      <h2>11. Parameter snapshot</h2>
      <pre><code>{params_json}</code></pre>
    </section>

  </main>

  <footer class="container">
    <p class="muted">
      Source: <code>src/quant_research/breakout/</code> ·
      Reproduce: <code>python scripts/run_breakout.py --config configs/breakout.yaml</code> ·
      Data: yfinance.
    </p>
  </footer>
</body>
</html>
"""

    out = output_dir / "index.html"
    out.write_text(html_doc, encoding="utf-8")
    return out


def _inline_css() -> str:
    return """
    :root {
      --fg:#111827; --muted:#6b7280; --bg:#ffffff; --panel:#f9fafb;
      --border:#e5e7eb; --accent:#2563eb; --pos:#10b981; --neg:#ef4444;
    }
    * { box-sizing:border-box; }
    html,body { margin:0; padding:0; background:var(--bg); color:var(--fg);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height:1.55; }
    .container { max-width: 1100px; margin: 0 auto; padding: 0 20px; }
    header.hero { background: linear-gradient(135deg, #0f172a, #1e3a8a);
      color:#f9fafb; padding: 56px 0 40px; margin-bottom: 32px; }
    header.hero h1 { margin:0 0 12px; font-size: 2.1rem; letter-spacing:-0.01em; }
    header.hero .tagline { font-size: 1.05rem; color: #cbd5e1; max-width: 780px; }
    header.hero .meta { font-size: 0.92rem; color:#cbd5e1; margin-top: 18px; }
    h2 { margin-top: 40px; font-size: 1.3rem; border-bottom:1px solid var(--border); padding-bottom:6px; }
    section { margin-bottom: 40px; }
    p { max-width: 820px; }
    code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    pre { background: var(--panel); border:1px solid var(--border); padding: 12px; overflow-x:auto; border-radius:6px; font-size:0.85rem; }
    code { background:#eef2ff; padding: 1px 5px; border-radius:4px; font-size:0.92em; }
    .metrics-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:14px; }
    .metric-card { background: var(--panel); border:1px solid var(--border); padding:14px 16px; border-radius:10px; }
    .metric-label { font-size:0.82rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.04em; }
    .metric-value { font-size:1.5rem; font-weight:600; margin-top:4px; color:var(--fg); }
    .metric-blurb { font-size:0.82rem; color:var(--muted); margin-top:6px; }
    .summary-table, .trade-table { border-collapse:collapse; width:100%; font-size:0.9rem; }
    .summary-table th, .summary-table td, .trade-table th, .trade-table td {
      border-bottom:1px solid var(--border); padding:8px 10px; text-align:left;
    }
    .summary-table th, .trade-table th { background: var(--panel); position: sticky; top:0; }
    .trade-table td.pos { color: var(--pos); font-weight:600; }
    .trade-table td.neg { color: var(--neg); font-weight:600; }
    .table-wrap { max-height: 540px; overflow:auto; border:1px solid var(--border); border-radius:6px; }
    .muted { color: var(--muted); font-size:0.9rem; }
    footer { margin: 40px auto 60px; color:var(--muted); font-size:0.9rem; }
    ol li { margin-bottom: 6px; }
    @media (max-width: 640px) {
      header.hero h1 { font-size: 1.6rem; }
      .metric-value { font-size: 1.25rem; }
    }
    """
