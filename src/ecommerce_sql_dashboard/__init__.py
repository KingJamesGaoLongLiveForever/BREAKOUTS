"""SQL-first e-commerce analytics portfolio project."""

from .data import DATASET_URLS, ensure_raw_data
from .pipeline import build_dashboard_artifacts

__all__ = ["DATASET_URLS", "ensure_raw_data", "build_dashboard_artifacts"]
