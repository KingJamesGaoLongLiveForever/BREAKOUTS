CREATE OR REPLACE VIEW ecommerce.fct_order_items AS
WITH item_base AS (
    SELECT
        oi.order_id,
        oi.order_item_id,
        oi.product_id,
        oi.seller_id,
        oi.price,
        oi.freight_value,
        o.customer_id,
        c.customer_unique_id,
        c.customer_state,
        o.order_status,
        o.order_purchase_ts,
        o.order_delivered_customer_ts,
        p.product_category_name,
        COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category_name
    FROM ecommerce.stg_order_items AS oi
    INNER JOIN ecommerce.stg_orders AS o USING (order_id)
    INNER JOIN ecommerce.stg_customers AS c USING (customer_id)
    LEFT JOIN ecommerce.stg_products AS p USING (product_id)
    LEFT JOIN ecommerce.stg_category_translation AS t USING (product_category_name)
)
SELECT
    *,
    price + freight_value AS gross_item_value,
    DATE_TRUNC('month', order_purchase_ts) AS order_month
FROM item_base;

CREATE OR REPLACE VIEW ecommerce.fct_orders AS
WITH order_rollup AS (
    SELECT
        fi.order_id,
        fi.customer_id,
        fi.customer_unique_id,
        fi.customer_state,
        MIN(fi.order_purchase_ts) AS order_purchase_ts,
        MIN(fi.order_month) AS order_month,
        MAX(fi.order_status) AS order_status,
        SUM(fi.price) AS item_revenue,
        SUM(fi.freight_value) AS freight_revenue,
        SUM(fi.gross_item_value) AS order_value,
        COUNT(*) AS items_per_order,
        COUNT(DISTINCT fi.seller_id) AS sellers_per_order,
        COUNT(DISTINCT fi.category_name) AS categories_per_order
    FROM ecommerce.fct_order_items AS fi
    GROUP BY 1, 2, 3, 4
),
payment_rollup AS (
    SELECT
        order_id,
        SUM(payment_value) AS payment_value,
        COUNT(*) AS payment_events,
        MODE(payment_type) AS payment_type
    FROM ecommerce.stg_payments
    GROUP BY 1
)
SELECT
    o.*,
    p.payment_value,
    p.payment_events,
    p.payment_type
FROM order_rollup AS o
LEFT JOIN payment_rollup AS p USING (order_id);

CREATE OR REPLACE VIEW ecommerce.dim_customer_order_history AS
WITH ranked AS (
    SELECT
        customer_unique_id,
        order_id,
        order_month,
        order_purchase_ts,
        order_value,
        ROW_NUMBER() OVER (PARTITION BY customer_unique_id ORDER BY order_purchase_ts) AS order_number,
        COUNT(*) OVER (PARTITION BY customer_unique_id) AS lifetime_orders,
        SUM(order_value) OVER (PARTITION BY customer_unique_id) AS lifetime_value,
        MIN(order_month) OVER (PARTITION BY customer_unique_id) AS first_order_month
    FROM ecommerce.fct_orders
    WHERE order_status = 'delivered'
)
SELECT * FROM ranked;
