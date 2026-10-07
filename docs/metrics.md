# Metric definitions

All sales metrics use merchandise lines between 2010-12-01 inclusive and 2011-12-01 exclusive. Line values are quantity multiplied by source unit price, rounded to integer pence using half-up rounding. Financial reconciliation uses integer pence. No exchange-rate conversion is applied.

| Metric | Definition |
|---|---|
| Gross sales GBP | Sum of positive-price, positive-quantity normal invoice merchandise line values / 100. |
| Credit value GBP | Negative of the sum of negative-quantity cancellation invoice merchandise line values / 100. |
| Net sales GBP | Gross sales minus recorded credit value. This is a merchandise ledger measure, not audited accounting revenue. |
| Orders | Distinct sale invoice numbers. Credits are excluded. Orders are not additive across products. |
| Average order GBP | Gross sales divided by sale orders in the same filter context. |
| Credit-to-sales ratio | Recorded credit value divided by gross sales in the same period and context. Credits may refer to earlier sales. |
| Identified buyers | Distinct non-missing customer IDs with at least one sale order. |
| Customer ID sales coverage | Gross sales with a customer ID divided by all gross sales. |
| Repeat buyer | Identified buyer with at least two distinct sale invoice numbers in the fixed reporting window. |
| Repeat buyer share | Repeat buyers / all identified buyers in that window. Later cohorts have less time to repeat. |
| Cohort | Month of first observed sale purchase within the reporting window. |
| Cohort monthly repurchase | Buyers with at least one sale in an observed month / original cohort size. Month zero is 100%. |

Missing customer IDs map to an `Unknown` dimension member. This member is never counted as a buyer. Credit-only customers may appear in the dimension but do not enter the buyer snapshot or cohort population.

Product codes are normalized to uppercase before dimension construction. This merges case aliases into one Power BI-compatible key without dropping or merging invoice lines. Duplicate flags compare original source cell values before this normalization.

Cohort age is the calendar-month difference between activity month and first observed month. The measure does not require consecutive purchases. An observed month with no purchases has a zero; a future, unobserved month has no row. Power BI row totals return blank, including the latest cohort with only month zero. Column totals pool active buyers and original cohort sizes at that observed age. The eligible cohorts change across ages, so the bottom row is not a fixed-population retention curve.

`CustomerSnapshot` and `CohortActivity` contain fixed-window SQL aggregates. They are intentionally disconnected from country/date filters. Standard sales measures use the star schema and respond to country filters on the first two pages.

Exact duplicates are retained. Monetary values and rankings therefore describe the source observations under this explicit policy. A source row number identifies an observation, not a guaranteed unique business event.
