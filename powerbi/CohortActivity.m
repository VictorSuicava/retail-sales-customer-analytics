let
    Source = Csv.Document(File.Contents(DataFolder & "/cohort_activity.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"cohort_month", type text}, {"month_age", Int64.Type}, {"activity_month", type text}, {"cohort_size", Int64.Type}, {"active_customers", Int64.Type}, {"repurchase_rate", type number}}, "en-US")
in
    Typed
