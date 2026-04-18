"""Pipeline orchestration for the e-commerce SQL dashboard project."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from .data import ensure_raw_data
from .report import build_site


def _read_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_query_file(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    sql = _read_sql(path)
    con.execute(sql)


def _table(con: duckdb.DuckDBPyConnection, query_path: Path) -> pd.DataFrame:
    return con.execute(_read_sql(query_path)).df()


def build_dashboard_artifacts(
    project_dir: str | Path = "projects/ecommerce_sql_dashboard",
    docs_dir: str | Path = "docs/ecommerce-dashboard",
    raw_dir: str | Path = "data/raw/olist",
    warehouse_path: str | Path = "data/warehouse/olist.duckdb",
) -> dict[str, object]:
    """Build the SQL warehouse, exports, and static dashboard."""

    project_dir = Path(project_dir)
    docs_dir = Path(docs_dir)
    warehouse_path = Path(warehouse_path)
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "data").mkdir(parents=True, exist_ok=True)

    ensure_raw_data(raw_dir)
    con = duckdb.connect(str(warehouse_path))

    for sql_file in [
        project_dir / "sql" / "01_stage_tables.sql",
        project_dir / "sql" / "02_curated_views.sql",
    ]:
        _run_query_file(con, sql_file)

    metric_defs = pd.read_csv(project_dir / "data" / "metric_dictionary.csv")
    executive_kpis = _table(con, project_dir / "sql" / "10_executive_kpis.sql")
    monthly_trends = _table(con, project_dir / "sql" / "11_monthly_trends.sql")
    category_performance = _table(con, project_dir / "sql" / "12_category_performance.sql")
    payment_mix = _table(con, project_dir / "sql" / "13_payment_mix.sql")
    seller_performance = _table(con, project_dir / "sql" / "14_seller_performance.sql")
    retention = _table(con, project_dir / "sql" / "15_cohort_retention.sql")
    customer_segments = _table(con, project_dir / "sql" / "16_customer_segments.sql")

    for name, df in {
        "executive_kpis": executive_kpis,
        "monthly_trends": monthly_trends,
        "category_performance": category_performance,
        "payment_mix": payment_mix,
        "seller_performance": seller_performance,
        "cohort_retention": retention,
        "customer_segments": customer_segments,
    }.items():
        df.to_csv(project_dir / "data" / f"{name}.csv", index=False)
        df.to_csv(docs_dir / f"{name}.csv", index=False)

    site_path = build_site(
        docs_dir=docs_dir,
        metric_defs=metric_defs,
        executive_kpis=executive_kpis,
        monthly_trends=monthly_trends,
        category_performance=category_performance,
        payment_mix=payment_mix,
        seller_performance=seller_performance,
        retention=retention,
        customer_segments=customer_segments,
    )

    summary = {
        "warehouse_path": str(warehouse_path),
        "site_path": str(site_path),
        "num_orders": int(executive_kpis.loc[0, "total_orders"]),
        "num_customers": int(executive_kpis.loc[0, "active_customers"]),
        "total_revenue": float(executive_kpis.loc[0, "total_revenue"]),
    }
    with (project_dir / "data" / "build_summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    with (docs_dir / "build_summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return summary
