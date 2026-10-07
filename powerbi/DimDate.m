let
    Source = Csv.Document(File.Contents(DataFolder & "/dim_date.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"date_key", Int64.Type}, {"date_iso", type date}, {"year", Int64.Type}, {"month", Int64.Type}, {"month_label", type text}}, "en-US")
in
    Typed
