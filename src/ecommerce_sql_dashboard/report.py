"""Static HTML dashboard for the e-commerce SQL portfolio project."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio


def _fig_div(fig, div_id: str) -> str:
    return pio.to_html(
        fig,
        include_plotlyjs=False,
        full_html=False,
        div_id=div_id,
        config={"displaylogo": False, "responsive": True},
    )


def _metric_card(label: str, value: str, blurb: str) -> str:
    return (
        "<div class='metric-card'>"
        f"<div class='metric-label'>{html.escape(label)}</div>"
        f"<div class='metric-value'>{html.escape(value)}</div>"
        f"<div class='metric-blurb'>{html.escape(blurb)}</div>"
        "</div>"
    )


def _pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%"


def _usd(value: float) -> str:
    return f"${value:,.0f}"


def _metric_dictionary_table(metric_defs: pd.DataFrame) -> str:
    rows = []
    for _, row in metric_defs.iterrows():
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(row['metric']))}</td>"
            f"<td>{html.escape(str(row['definition']))}</td>"
            f"<td>{html.escape(str(row['grain']))}</td>"
            "</tr>"
        )
    return (
        "<table class='summary-table'>"
        "<thead><tr><th>Metric</th><th>Definition</th><th>Grain</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def build_site(
    docs_dir: Path,
    metric_defs: pd.DataFrame,
    executive_kpis: pd.DataFrame,
    monthly_trends: pd.DataFrame,
    category_performance: pd.DataFrame,
    payment_mix: pd.DataFrame,
    seller_performance: pd.DataFrame,
    retention: pd.DataFrame,
    customer_segments: pd.DataFrame,
) -> Path:
    """Write a single-page recruiter-friendly dashboard."""

    docs_dir.mkdir(parents=True, exist_ok=True)
    kpi = executive_kpis.iloc[0]

    trend_fig = px.line(
        monthly_trends,
        x="order_month",
        y=["monthly_revenue", "monthly_orders"],
        markers=True,
        title="Monthly revenue and order volume",
    )
    trend_fig.update_layout(template="plotly_white", legend_title_text="")

    category_fig = px.bar(
        category_performance.head(10),
        x="category_name",
        y="revenue",
        color="avg_order_value",
        title="Top 10 categories by revenue",
        labels={"category_name": "Category", "revenue": "Revenue", "avg_order_value": "AOV"},
    )
    category_fig.update_layout(template="plotly_white", xaxis_tickangle=-30)

    retention_fig = px.line(
        retention,
        x="cohort_index",
        y="retention_pct",
        color="cohort_month",
        title="Monthly repeat-purchase retention by cohort",
        labels={"cohort_index": "Months since first purchase", "retention_pct": "Retention %"},
    )
    retention_fig.update_layout(template="plotly_white", legend_title_text="Cohort")

    payment_fig = px.pie(
        payment_mix,
        values="payment_share_pct",
        names="payment_type",
        title="Payment mix",
    )
    payment_fig.update_layout(template="plotly_white")

    seller_fig = px.bar(
        seller_performance.head(10),
        x="seller_state",
        y="revenue",
        title="Top seller states by revenue",
        labels={"seller_state": "Seller state", "revenue": "Revenue"},
    )
    seller_fig.update_layout(template="plotly_white")

    segment_fig = px.bar(
        customer_segments,
        x="segment",
        y="customers",
        color="avg_lifetime_value",
        title="Customer segments by order frequency",
        labels={"customers": "Customers", "avg_lifetime_value": "Avg LTV"},
    )
    segment_fig.update_layout(template="plotly_white")

    cards = "".join(
        [
            _metric_card("Total revenue", _usd(float(kpi["total_revenue"])), "Delivered order item revenue plus freight."),
            _metric_card("Orders", f"{int(kpi['total_orders']):,}", "Delivered orders in the public Olist sample."),
            _metric_card("Active customers", f"{int(kpi['active_customers']):,}", "Distinct unique customers who placed delivered orders."),
            _metric_card("AOV", _usd(float(kpi["avg_order_value"])), "Average delivered order value including freight."),
            _metric_card("Repeat customer rate", _pct(float(kpi["repeat_customer_rate_pct"])), "Share of customers with more than one delivered order."),
            _metric_card("Avg review score", f"{float(kpi['avg_review_score']):.2f}", "Average review score for delivered orders with ratings."),
        ]
    )

    insights = f"""
    <ul>
      <li><strong>Repeat purchase is the clearest growth lever.</strong> The delivered-order repeat rate is <strong>{_pct(float(kpi['repeat_customer_rate_pct']))}</strong>, which means most growth still depends on first-time acquisition rather than compounding customer value.</li>
      <li><strong>Category mix is uneven.</strong> The top categories generate a disproportionate share of revenue, so merchandising and inventory decisions should focus on both top-line contribution and AOV quality.</li>
      <li><strong>Seller concentration matters operationally.</strong> Revenue is not evenly distributed across seller states, which suggests fulfillment support and freight policy should be localized rather than fully standardized.</li>
    </ul>
    """

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>E-commerce SQL Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
  <style>
    :root {{
      --fg:#111827; --muted:#6b7280; --bg:#ffffff; --panel:#f9fafb; --border:#e5e7eb;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; background:var(--bg); color:var(--fg);
      font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height:1.55;
    }}
    .container {{ max-width:1100px; margin:0 auto; padding:0 20px; }}
    .hero {{ background:linear-gradient(135deg, #0f172a, #1d4ed8); color:#f8fafc; padding:56px 0 36px; }}
    .hero p {{ max-width:820px; color:#cbd5e1; }}
    h2 {{ margin-top:36px; border-bottom:1px solid var(--border); padding-bottom:6px; }}
    .metrics-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:14px; }}
    .metric-card {{ background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:14px 16px; }}
    .metric-label {{ font-size:0.82rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.04em; }}
    .metric-value {{ font-size:1.45rem; font-weight:600; margin-top:4px; }}
    .metric-blurb {{ color:var(--muted); font-size:0.85rem; margin-top:6px; }}
    .summary-table {{ border-collapse:collapse; width:100%; font-size:0.92rem; }}
    .summary-table th, .summary-table td {{ border-bottom:1px solid var(--border); padding:8px 10px; text-align:left; vertical-align:top; }}
    .summary-table th {{ background:var(--panel); }}
    .muted {{ color:var(--muted); }}
    footer {{ margin:40px auto 60px; color:var(--muted); font-size:0.92rem; }}
  </style>
</head>
<body>
  <header class="hero">
    <div class="container">
      <h1>E-commerce SQL Dashboard</h1>
      <p>
        A Data Analyst / Business Analyst portfolio project built on the public Olist marketplace dataset.
        The deliverable is intentionally SQL-first: a DuckDB warehouse, business-facing KPI definitions,
        and a static dashboard that highlights growth, retention, category mix, and seller performance.
      </p>
    </div>
  </header>
  <main class="container">
    <section>
      <h2>1. Executive KPI panel</h2>
      <div class="metrics-grid">{cards}</div>
    </section>
    <section>
      <h2>2. Business questions answered</h2>
      <ul>
        <li>How did delivered-order revenue and order volume trend over time?</li>
        <li>Which product categories drive the most revenue, and which ones carry stronger AOV?</li>
        <li>How concentrated is seller performance across regions?</li>
        <li>What share of customers become repeat buyers, and how fast do cohorts decay?</li>
        <li>Which payment types dominate the marketplace mix?</li>
      </ul>
    </section>
    <section>
      <h2>3. Monthly performance</h2>
      {_fig_div(trend_fig, "fig-trends")}
    </section>
    <section>
      <h2>4. Category and seller mix</h2>
      {_fig_div(category_fig, "fig-category")}
      {_fig_div(seller_fig, "fig-seller")}
    </section>
    <section>
      <h2>5. Retention and customer segmentation</h2>
      {_fig_div(retention_fig, "fig-retention")}
      {_fig_div(segment_fig, "fig-segments")}
    </section>
    <section>
      <h2>6. Payment mix</h2>
      {_fig_div(payment_fig, "fig-payment")}
    </section>
    <section>
      <h2>7. Recommendations</h2>
      {insights}
    </section>
    <section>
      <h2>8. Metric dictionary</h2>
      {_metric_dictionary_table(metric_defs)}
    </section>
  </main>
  <footer class="container">
    <p>
      Dataset: public Olist Brazilian e-commerce sample. Artifacts: downloadable CSVs in this folder.
      Reproduce locally with <code>python scripts/run_ecommerce_dashboard.py</code>.
    </p>
  </footer>
</body>
</html>
"""

    out = docs_dir / "index.html"
    out.write_text(html_doc, encoding="utf-8")
    return out
