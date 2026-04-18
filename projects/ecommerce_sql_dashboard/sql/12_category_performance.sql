SELECT
    category_name,
    COUNT(DISTINCT order_id) AS orders,
    SUM(gross_item_value) AS revenue,
    AVG(gross_item_value) AS avg_order_value,
    SUM(gross_item_value) / SUM(SUM(gross_item_value)) OVER () * 100.0 AS revenue_share_pct
FROM ecommerce.fct_order_items
WHERE order_status = 'delivered'
GROUP BY 1
HAVING COUNT(DISTINCT order_id) >= 100
ORDER BY revenue DESC;
