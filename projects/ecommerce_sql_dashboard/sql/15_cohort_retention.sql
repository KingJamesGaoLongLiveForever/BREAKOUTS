WITH base AS (
    SELECT
        customer_unique_id,
        first_order_month AS cohort_month,
        order_month,
        DATE_DIFF('month', first_order_month, order_month) AS cohort_index
    FROM ecommerce.dim_customer_order_history
),
cohort_size AS (
    SELECT
        cohort_month,
        COUNT(DISTINCT customer_unique_id) AS cohort_customers
    FROM base
    WHERE cohort_index = 0
    GROUP BY 1
),
retained AS (
    SELECT
        cohort_month,
        cohort_index,
        COUNT(DISTINCT customer_unique_id) AS retained_customers
    FROM base
    GROUP BY 1, 2
)
SELECT
    r.cohort_month,
    r.cohort_index,
    r.retained_customers,
    c.cohort_customers,
    100.0 * r.retained_customers / c.cohort_customers AS retention_pct
FROM retained AS r
INNER JOIN cohort_size AS c USING (cohort_month)
WHERE r.cohort_index BETWEEN 0 AND 6
ORDER BY 1, 2;
