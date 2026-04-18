# E-commerce SQL Dashboard

This project is a recruiter-friendly `Data Analyst / Business Analyst` portfolio case built on the public Olist Brazilian e-commerce dataset. It is intentionally SQL-first: the core deliverable is a DuckDB warehouse, a set of readable analysis queries, a metric dictionary, and a static dashboard that communicates business decisions quickly.

## Business questions
- How did delivered-order revenue and order volume trend over time?
- Which product categories drive the most revenue, and which ones carry stronger average order value?
- How concentrated is seller performance across regions?
- What share of customers become repeat buyers, and how quickly do cohorts decay?
- Which payment types dominate the marketplace mix?

## Stack
- `DuckDB` for local analytics and SQL execution
- `SQL` for staging, curated views, KPIs, retention, and segmentation
- `Python` for orchestration and static report generation
- `Plotly` for GitHub-friendly HTML charts

## Project structure
- `sql/01_stage_tables.sql`: raw CSV staging views
- `sql/02_curated_views.sql`: analyst-friendly fact and dimension views
- `sql/10_*.sql` to `sql/16_*.sql`: business KPI and insight queries
- `data/metric_dictionary.csv`: business metric definitions
- `docs/ecommerce-dashboard/`: generated dashboard and downloadable CSV outputs

## How to run
```bash
python -m pip install -e .
python scripts/run_ecommerce_dashboard.py
```

The build downloads the public Olist CSV files into `data/raw/olist/`, creates a local DuckDB warehouse in `data/warehouse/olist.duckdb`, writes query outputs to `projects/ecommerce_sql_dashboard/data/`, and publishes a static dashboard to `docs/ecommerce-dashboard/index.html`.

## Key deliverables
- SQL that demonstrates joins, CTEs, cohort logic, and business KPI calculation
- A static dashboard for recruiters and hiring managers
- A metric dictionary for clear stakeholder communication
- Downloadable CSV outputs that reconcile with the dashboard

## Notes
- The dataset is a public anonymized sample published by Olist and commonly mirrored on GitHub/Kaggle.
- This project is framed like an analyst take-home: business context first, implementation second.
