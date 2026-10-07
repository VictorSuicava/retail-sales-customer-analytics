# Findings and decisions to investigate

These descriptive findings use the twelve complete months ending 30 November 2011. Reproduce them using the SQLite views in `sql/analytics.sql`.

## Repeat buyers account for most identified sales

2,742 of 4,293 identified buyers placed at least two sale orders: **63.9%**. They account for **92.2% of gross sales among identified buyers**. Customer IDs cover 85.4% of all gross sales, so this share must not be applied to unidentified sales.

Commercial implication: inspect the concentration of sales among frequent buyers and distinguish wholesale purchasing from consumer behaviour before proposing a loyalty programme. The dataset contains many wholesalers and gives no margin or campaign-cost evidence.

```sql
SELECT buyer_group, COUNT(*) AS buyers, SUM(gross_sales_gbp) AS gross_sales_gbp
FROM v_customer_snapshot
GROUP BY buyer_group;
```

## January credit value is dominated by one very large record

January 2011 has **£91,526.30** of recorded merchandise credits. Credit invoice `C541433` contains **£77,183.60** for stock code `23166`, quantity -74,215 at £1.04. This single record represents 84.3% of January credit value.

Commercial implication: check the original invoice and ledger context before interpreting January as a broad deterioration in customer satisfaction. The record is retained rather than removed as an outlier. There is no causal or original-order linkage claim.

```sql
SELECT invoice_no, stock_code, quantity, unit_price_gbp, line_pence / 100.0 AS credit_gbp
FROM raw_lines
WHERE classification='Credit' AND substr(invoice_datetime,1,7)='2011-01'
ORDER BY line_pence LIMIT 5;
```

## The UK dominates sales, while country order profiles differ

UK net merchandise sales are **£7,902,009.63**, approximately **84.5%** of the total. The Netherlands records £271,751.52 from 90 sale orders, while Germany records £193,963.70 from 426. Country totals alone do not describe typical customer size or profitability.

Commercial implication: compare order value and buyer concentration before drawing conclusions about market expansion. There are no shipping costs, acquisition costs or margins in the source.

```sql
SELECT * FROM v_country_sales ORDER BY net_sales_gbp DESC;
```

## Cohorts expose unequal observation time

The December 2010 cohort has 884 identified buyers, of whom 323 buy in January: **36.5%** monthly repurchase at age one. The October 2011 cohort has 357 buyers, with 84 buying in November: **23.5%** at age one. November has no observable age-one cell in the reporting window.

These differences do not establish a change in acquisition quality. The first cohort can contain customers who were already active before source coverage, and month-specific buying patterns can differ. Compare equal observed ages and investigate customer mix before making a retention recommendation.

```sql
SELECT * FROM v_cohort_activity WHERE month_age=1 ORDER BY cohort_month;
```
