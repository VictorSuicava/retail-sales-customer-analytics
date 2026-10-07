-- The reporting window is set by the Python pipeline. All measures use the same fact scope.
CREATE VIEW v_monthly_sales AS
SELECT d.month_label,
       SUM(CASE WHEN f.transaction_type='Sale' THEN f.line_pence ELSE 0 END) / 100.0 AS gross_sales_gbp,
       -SUM(CASE WHEN f.transaction_type='Credit' THEN f.line_pence ELSE 0 END) / 100.0 AS credit_value_gbp,
       SUM(f.line_pence) / 100.0 AS net_sales_gbp,
       COUNT(DISTINCT CASE WHEN f.transaction_type='Sale' THEN f.invoice_no END) AS orders,
       COUNT(DISTINCT CASE WHEN f.transaction_type='Sale' AND f.customer_key<>'Unknown' THEN f.customer_key END) AS identified_buyers,
       SUM(CASE WHEN f.transaction_type='Sale' AND f.customer_key<>'Unknown' THEN f.line_pence ELSE 0 END) * 1.0 /
           NULLIF(SUM(CASE WHEN f.transaction_type='Sale' THEN f.line_pence ELSE 0 END),0) AS customer_id_sales_coverage
FROM FactOrderLine f JOIN DimDate d USING(date_key)
GROUP BY d.month_label;

CREATE VIEW v_product_sales AS
SELECT p.product_key,p.product_name,
       SUM(CASE WHEN f.transaction_type='Sale' THEN f.line_pence ELSE 0 END) / 100.0 AS gross_sales_gbp,
       -SUM(CASE WHEN f.transaction_type='Credit' THEN f.line_pence ELSE 0 END) / 100.0 AS credit_value_gbp,
       SUM(f.line_pence) / 100.0 AS net_sales_gbp,
       COUNT(DISTINCT CASE WHEN f.transaction_type='Sale' THEN f.invoice_no END) AS orders,
       SUM(CASE WHEN f.transaction_type='Sale' THEN f.quantity ELSE 0 END) AS sold_units
FROM FactOrderLine f JOIN DimProduct p USING(product_key)
GROUP BY p.product_key,p.product_name;

CREATE VIEW v_country_sales AS
SELECT c.country_name,
       SUM(CASE WHEN f.transaction_type='Sale' THEN f.line_pence ELSE 0 END) / 100.0 AS gross_sales_gbp,
       -SUM(CASE WHEN f.transaction_type='Credit' THEN f.line_pence ELSE 0 END) / 100.0 AS credit_value_gbp,
       SUM(f.line_pence) / 100.0 AS net_sales_gbp,
       COUNT(DISTINCT CASE WHEN f.transaction_type='Sale' THEN f.invoice_no END) AS orders
FROM FactOrderLine f JOIN DimCountry c USING(country_key)
GROUP BY c.country_name;

-- One row per identified buyer. The unknown bucket is not a customer.
CREATE VIEW v_customer_snapshot AS
WITH orders AS (
    SELECT customer_key,invoice_no,MIN(date_key) AS order_date,
           SUM(line_pence) AS order_pence
    FROM FactOrderLine
    WHERE transaction_type='Sale' AND customer_key<>'Unknown'
    GROUP BY customer_key,invoice_no
), credits AS (
    SELECT customer_key,-SUM(line_pence) AS credit_pence
    FROM FactOrderLine WHERE transaction_type='Credit' GROUP BY customer_key
)
SELECT o.customer_key,c.cohort_month,COUNT(*) AS purchase_orders,
       SUM(o.order_pence) / 100.0 AS gross_sales_gbp,
       COALESCE(MAX(cr.credit_pence),0) / 100.0 AS credit_value_gbp,
       (SUM(o.order_pence)-COALESCE(MAX(cr.credit_pence),0)) / 100.0 AS net_sales_gbp,
       MIN(o.order_date) AS first_purchase_date_key,MAX(o.order_date) AS last_purchase_date_key,
       CASE WHEN COUNT(*)>=2 THEN 'Repeat buyer' ELSE 'One order' END AS buyer_group
FROM orders o JOIN DimCustomer c USING(customer_key)
LEFT JOIN credits cr USING(customer_key)
GROUP BY o.customer_key,c.cohort_month;

CREATE VIEW v_cohort_activity AS
WITH activity AS (
    SELECT DISTINCT f.customer_key,c.cohort_month,d.month_label AS activity_month,
        (CAST(substr(d.month_label,1,4) AS INTEGER)-CAST(substr(c.cohort_month,1,4) AS INTEGER))*12
        +CAST(substr(d.month_label,6,2) AS INTEGER)-CAST(substr(c.cohort_month,6,2) AS INTEGER) AS month_age
    FROM FactOrderLine f JOIN DimCustomer c USING(customer_key) JOIN DimDate d USING(date_key)
    WHERE f.transaction_type='Sale' AND f.customer_key<>'Unknown'
), sizes AS (
    SELECT cohort_month,COUNT(*) AS cohort_size FROM DimCustomer
    WHERE cohort_month IS NOT NULL GROUP BY cohort_month
), observed_months AS (SELECT DISTINCT month_label FROM DimDate)
SELECT s.cohort_month,
       (CAST(substr(m.month_label,1,4) AS INTEGER)-CAST(substr(s.cohort_month,1,4) AS INTEGER))*12
       +CAST(substr(m.month_label,6,2) AS INTEGER)-CAST(substr(s.cohort_month,6,2) AS INTEGER) AS month_age,
       m.month_label AS activity_month,s.cohort_size,
       COUNT(a.customer_key) AS active_customers,
       COUNT(a.customer_key)*1.0/s.cohort_size AS repurchase_rate
FROM sizes s CROSS JOIN observed_months m
LEFT JOIN activity a ON a.cohort_month=s.cohort_month AND a.activity_month=m.month_label
WHERE m.month_label>=s.cohort_month
GROUP BY s.cohort_month,m.month_label,s.cohort_size;

