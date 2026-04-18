"""Plotly figures used by the GitHub Pages report.

Each function returns a ``plotly.graph_objects.Figure`` so the caller can
decide whether to render to HTML, PNG, or JSON.  The page embeds them as
HTML fragments (``plotly.offline.plot(fig, include_plotlyjs='cdn', ...)``).
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


_BRAND_COLORS = {
    "long": "#1f77b4",
    "short": "#d62728",
    "equity": "#111827",
    "dd": "#ef4444",
    "bg": "#f9fafb",
    "grid": "#e5e7eb",
}


def _style(fig: go.Figure, title: str, height: int = 420) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0.01, xanchor="left", font=dict(size=16)),
        template="plotly_white",
        margin=dict(l=40, r=20, t=50, b=40),
        height=height,
        hovermode="x unified",
        plot_bgcolor=_BRAND_COLORS["bg"],
    )
    fig.update_xaxes(showgrid=True, gridcolor=_BRAND_COLORS["grid"])
    fig.update_yaxes(showgrid=True, gridcolor=_BRAND_COLORS["grid"])
    return fig


def equity_and_drawdown(equity_curve: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        subplot_titles=("Equity curve (USD)", "Drawdown"),
    )

    fig.add_trace(
        go.Scatter(
            x=equity_curve.index, y=equity_curve["equity"],
            name="Equity", line=dict(color=_BRAND_COLORS["equity"], width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>Equity: $%{y:,.0f}<extra></extra>",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=equity_curve.index, y=equity_curve["drawdown"] * 100,
            name="Drawdown", fill="tozeroy",
            line=dict(color=_BRAND_COLORS["dd"], width=1),
            hovertemplate="%{x|%Y-%m-%d}<br>DD: %{y:.2f}%<extra></extra>",
        ),
        row=2, col=1,
    )
    fig.update_yaxes(title_text="USD", row=1, col=1, tickformat="~s")
    fig.update_yaxes(title_text="%", row=2, col=1, tickformat=".1f")
    return _style(fig, "Walk-forward equity & drawdown", height=520)


def trade_outcome_histogram(trades_frame: pd.DataFrame) -> go.Figure:
    if trades_frame.empty:
        return _style(go.Figure(), "Trade outcomes (no trades)", height=320)

    counts = (
        trades_frame.groupby("outcome")
        .agg(count=("net_pnl", "size"), mean_ret=("return_pct", "mean"))
        .reset_index()
    )
    pretty = {
        "successful": "Successful (profit target)",
        "timeout": "Timed out",
        "stop_loss": "Stop-loss triggered",
    }
    counts["label"] = counts["outcome"].map(pretty).fillna(counts["outcome"])
    colors = {
        "successful": "#10b981",
        "timeout": "#f59e0b",
        "stop_loss": "#ef4444",
    }
    counts["color"] = counts["outcome"].map(colors).fillna("#6b7280")

    fig = go.Figure(
        go.Bar(
            x=counts["label"], y=counts["count"],
            marker_color=counts["color"],
            text=[f"n={c}<br>avg ret {r*100:.2f}%" for c, r in zip(counts["count"], counts["mean_ret"])],
            textposition="outside",
            hovertemplate="%{x}<br>count: %{y}<extra></extra>",
        )
    )
    fig.update_yaxes(title_text="trades")
    return _style(fig, "Trade outcome histogram", height=360)


def return_distribution(trades_frame: pd.DataFrame) -> go.Figure:
    if trades_frame.empty:
        return _style(go.Figure(), "Per-trade return distribution (no trades)", height=320)
    fig = go.Figure(
        go.Histogram(
            x=trades_frame["return_pct"] * 100,
            nbinsx=30,
            marker_color="#4f46e5",
            hovertemplate="%{x:.2f}% return<br>count: %{y}<extra></extra>",
        )
    )
    fig.add_vline(
        x=float(trades_frame["return_pct"].mean() * 100),
        line=dict(color="#111827", dash="dash"),
        annotation_text="mean", annotation_position="top right",
    )
    fig.update_xaxes(title_text="Return per trade (%)")
    fig.update_yaxes(title_text="trades")
    return _style(fig, "Per-trade return distribution", height=360)


def price_with_trades(
    prices: pd.DataFrame,
    ticker: str,
    trades_frame: pd.DataFrame,
    entry_lookback: int,
    exit_lookback: int,
) -> go.Figure:
    sub = trades_frame[trades_frame["ticker"] == ticker]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=prices.index, y=prices["close"],
            name="Close", line=dict(color="#111827", width=1.2),
        )
    )
    upper = prices["high"].rolling(entry_lookback).max().shift(1)
    lower = prices["low"].rolling(entry_lookback).min().shift(1)
    fig.add_trace(go.Scatter(x=prices.index, y=upper, name=f"{entry_lookback}d high",
                             line=dict(color="#1f77b4", width=1, dash="dot")))
    fig.add_trace(go.Scatter(x=prices.index, y=lower, name=f"{entry_lookback}d low",
                             line=dict(color="#d62728", width=1, dash="dot")))

    longs = sub[sub["direction"] == "long"]
    shorts = sub[sub["direction"] == "short"]

    if not longs.empty:
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(longs["entry_date"]),
            y=longs["entry_price"],
            mode="markers",
            marker=dict(symbol="triangle-up", size=11, color=_BRAND_COLORS["long"],
                        line=dict(color="white", width=1)),
            name="Long entry",
            hovertemplate="%{x|%Y-%m-%d}<br>Long @ $%{y:.2f}<extra></extra>",
        ))
    if not shorts.empty:
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(shorts["entry_date"]),
            y=shorts["entry_price"],
            mode="markers",
            marker=dict(symbol="triangle-down", size=11, color=_BRAND_COLORS["short"],
                        line=dict(color="white", width=1)),
            name="Short entry",
            hovertemplate="%{x|%Y-%m-%d}<br>Short @ $%{y:.2f}<extra></extra>",
        ))

    if not sub.empty:
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(sub["exit_date"]),
            y=sub["exit_price"],
            mode="markers",
            marker=dict(symbol="x", size=9, color="#6b7280"),
            name="Exit",
            hovertemplate="%{x|%Y-%m-%d}<br>Exit @ $%{y:.2f}<extra></extra>",
        ))

    return _style(fig, f"{ticker}: price, Donchian channel & trades", height=480)
