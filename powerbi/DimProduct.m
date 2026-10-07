let
    Source = Csv.Document(File.Contents(DataFolder & "/dim_product.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"product_key", type text}, {"product_name", type text}}, "en-US")
in
    Typed
