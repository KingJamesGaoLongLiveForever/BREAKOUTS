SELECT
    s.seller_state,
    COUNT(DISTINCT fi.order_id) AS orders,
    COUNT(DISTINCT fi.seller_id) AS sellers,
    SUM(fi.gross_item_value) AS revenue,
    AVG(fi.gross_item_value) AS avg_item_value
FROM ecommerce.fct_order_items AS fi
INNER JOIN read_csv_auto('data/raw/olist/sellers.csv', header=true) AS s USING (seller_id)
WHERE fi.order_status = 'delivered'
GROUP BY 1
ORDER BY revenue DESC;
