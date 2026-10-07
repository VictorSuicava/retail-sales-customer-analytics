let
    Source = Csv.Document(File.Contents(DataFolder & "/dim_country.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"country_key", type text}, {"country_name", type text}}, "en-US")
in
    Typed
