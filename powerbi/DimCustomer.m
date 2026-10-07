let
    Source = Csv.Document(File.Contents(DataFolder & "/dim_customer.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"customer_key", type text}, {"first_observed_purchase", type date}, {"cohort_month", type text}, {"is_identified", Int64.Type}}, "en-US")
in
    Typed
