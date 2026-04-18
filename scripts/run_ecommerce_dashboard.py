from __future__ import annotations

import argparse

from ecommerce_sql_dashboard.pipeline import build_dashboard_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the e-commerce SQL dashboard portfolio project.")
    parser.add_argument("--project-dir", default="projects/ecommerce_sql_dashboard")
    parser.add_argument("--docs-dir", default="docs/ecommerce-dashboard")
    parser.add_argument("--raw-dir", default="data/raw/olist")
    parser.add_argument("--warehouse-path", default="data/warehouse/olist.duckdb")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_dashboard_artifacts(
        project_dir=args.project_dir,
        docs_dir=args.docs_dir,
        raw_dir=args.raw_dir,
        warehouse_path=args.warehouse_path,
    )
    print("E-commerce SQL dashboard built successfully.")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
