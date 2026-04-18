SELECT
    p.payment_type,
    COUNT(DISTINCT p.order_id) AS orders,
    SUM(p.payment_value) AS payment_value,
    COUNT(DISTINCT p.order_id) * 100.0 / SUM(COUNT(DISTINCT p.order_id)) OVER () AS payment_share_pct
FROM ecommerce.stg_payments AS p
INNER JOIN ecommerce.fct_orders AS o USING (order_id)
WHERE o.order_status = 'delivered'
GROUP BY 1
ORDER BY payment_value DESC;
