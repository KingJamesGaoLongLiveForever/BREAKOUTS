"""Download helpers for the public Olist e-commerce dataset."""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve


DATASET_URLS: dict[str, str] = {
    "customers": "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_customers_dataset.csv",
    "orders": "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_orders_dataset.csv",
    "order_items": "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_order_items_dataset.csv",
    "payments": "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_order_payments_dataset.csv",
    "reviews": "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_order_reviews_dataset.csv",
    "products": "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_products_dataset.csv",
    "sellers": "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_sellers_dataset.csv",
    "translations": "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/product_category_name_translation.csv",
}


def ensure_raw_data(raw_dir: str | Path = "data/raw/olist") -> dict[str, Path]:
    """Download the CSVs used by the portfolio project if absent."""

    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for name, url in DATASET_URLS.items():
        target = raw_path / f"{name}.csv"
        if not target.exists():
            urlretrieve(url, target)
        out[name] = target
    return out
