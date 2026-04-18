from __future__ import annotations

from pathlib import Path

from ecommerce_sql_dashboard.data import DATASET_URLS


def test_dataset_urls_cover_required_sources():
    required = {
        "customers",
        "orders",
        "order_items",
        "payments",
        "reviews",
        "products",
        "sellers",
        "translations",
    }
    assert required.issubset(DATASET_URLS)


def test_project_sql_files_exist():
    base = Path("projects/ecommerce_sql_dashboard/sql")
    expected = [
        "01_stage_tables.sql",
        "02_curated_views.sql",
        "10_executive_kpis.sql",
        "11_monthly_trends.sql",
        "12_category_performance.sql",
        "13_payment_mix.sql",
        "14_seller_performance.sql",
        "15_cohort_retention.sql",
        "16_customer_segments.sql",
    ]
    for name in expected:
        assert (base / name).exists(), f"missing SQL file: {name}"
