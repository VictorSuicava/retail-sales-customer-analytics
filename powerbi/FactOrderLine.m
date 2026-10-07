let
    Source = Csv.Document(File.Contents(DataFolder & "/fact_order_line.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"line_key", Int64.Type}, {"invoice_no", type text}, {"date_key", Int64.Type}, {"product_key", type text}, {"country_key", type text}, {"customer_key", type text}, {"transaction_type", type text}, {"quantity", Int64.Type}, {"line_pence", Int64.Type}, {"exact_duplicate", Int64.Type}}, "en-US")
in
    Typed
