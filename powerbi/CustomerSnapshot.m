let
    Source = Csv.Document(File.Contents(DataFolder & "/customer_snapshot.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"customer_key", type text}, {"cohort_month", type text}, {"purchase_orders", Int64.Type}, {"gross_sales_gbp", type number}, {"credit_value_gbp", type number}, {"net_sales_gbp", type number}, {"first_purchase_date_key", Int64.Type}, {"last_purchase_date_key", Int64.Type}, {"buyer_group", type text}}, "en-US")
in
    Typed
