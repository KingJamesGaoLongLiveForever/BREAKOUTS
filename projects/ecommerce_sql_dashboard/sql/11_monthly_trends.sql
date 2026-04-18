SELECT
    order_month,
    COUNT(*) AS monthly_orders,
    COUNT(DISTINCT customer_unique_id) AS monthly_customers,
    SUM(order_value) AS monthly_revenue,
    AVG(order_value) AS monthly_aov
FROM ecommerce.fct_orders
WHERE order_status = 'delivered'
GROUP BY 1
ORDER BY 1;
