CREATE SCHEMA IF NOT EXISTS ecommerce;

CREATE OR REPLACE VIEW ecommerce.stg_orders AS
SELECT
    order_id,
    customer_id,
    order_status,
    CAST(order_purchase_timestamp AS TIMESTAMP) AS order_purchase_ts,
    CAST(order_approved_at AS TIMESTAMP) AS order_approved_ts,
    CAST(order_delivered_carrier_date AS TIMESTAMP) AS order_delivered_carrier_ts,
    CAST(order_delivered_customer_date AS TIMESTAMP) AS order_delivered_customer_ts,
    CAST(order_estimated_delivery_date AS TIMESTAMP) AS order_estimated_delivery_ts
FROM read_csv_auto('data/raw/olist/orders.csv', header=true);

CREATE OR REPLACE VIEW ecommerce.stg_customers AS
SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
FROM read_csv_auto('data/raw/olist/customers.csv', header=true);

CREATE OR REPLACE VIEW ecommerce.stg_order_items AS
SELECT
    order_id,
    order_item_id,
    product_id,
    seller_id,
    CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_ts,
    CAST(price AS DOUBLE) AS price,
    CAST(freight_value AS DOUBLE) AS freight_value
FROM read_csv_auto('data/raw/olist/order_items.csv', header=true);

CREATE OR REPLACE VIEW ecommerce.stg_payments AS
SELECT
    order_id,
    payment_sequential,
    payment_type,
    payment_installments,
    CAST(payment_value AS DOUBLE) AS payment_value
FROM read_csv_auto('data/raw/olist/payments.csv', header=true);

CREATE OR REPLACE VIEW ecommerce.stg_products AS
SELECT
    product_id,
    product_category_name,
    product_name_lenght,
    product_description_lenght,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm
FROM read_csv_auto('data/raw/olist/products.csv', header=true);

CREATE OR REPLACE VIEW ecommerce.stg_category_translation AS
SELECT
    product_category_name,
    trim(product_category_name_english) AS product_category_name_english
FROM read_csv_auto('data/raw/olist/translations.csv', header=true);
