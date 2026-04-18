WITH customer_rollup AS (
    SELECT
        customer_unique_id,
        COUNT(*) AS orders,
        SUM(order_value) AS lifetime_value
    FROM ecommerce.fct_orders
    WHERE order_status = 'delivered'
    GROUP BY 1
)
SELECT
    CASE
        WHEN orders = 1 THEN 'One-time'
        WHEN orders = 2 THEN 'Repeat'
        ELSE 'Loyal'
    END AS segment,
    COUNT(*) AS customers,
    AVG(lifetime_value) AS avg_lifetime_value
FROM customer_rollup
GROUP BY 1
ORDER BY customers DESC;
