WITH delivered AS (
    SELECT *
    FROM ecommerce.fct_orders
    WHERE order_status = 'delivered'
),
repeat_base AS (
    SELECT customer_unique_id
    FROM delivered
    GROUP BY 1
)
SELECT
    COUNT(*) AS total_orders,
    COUNT(DISTINCT customer_unique_id) AS active_customers,
    SUM(order_value) AS total_revenue,
    AVG(order_value) AS avg_order_value,
    100.0 * AVG(CASE WHEN lifetime_orders > 1 THEN 1.0 ELSE 0.0 END) AS repeat_customer_rate_pct,
    (
        SELECT AVG(orv.review_score)
        FROM read_csv_auto('data/raw/olist/reviews.csv', header=true) AS orv
        INNER JOIN delivered AS d USING (order_id)
    ) AS avg_review_score
FROM delivered
INNER JOIN (
    SELECT customer_unique_id, COUNT(*) AS lifetime_orders
    FROM delivered
    GROUP BY 1
) AS history USING (customer_unique_id);
