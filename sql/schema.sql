PRAGMA foreign_keys = ON;

CREATE TABLE raw_lines (
    source_row INTEGER PRIMARY KEY,
    invoice_no TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    description TEXT,
    quantity INTEGER NOT NULL,
    invoice_datetime TEXT NOT NULL,
    unit_price_gbp TEXT NOT NULL,
    customer_id TEXT,
    country TEXT NOT NULL,
    line_pence INTEGER NOT NULL,
    classification TEXT NOT NULL,
    exact_duplicate INTEGER NOT NULL CHECK (exact_duplicate IN (0,1))
);

CREATE TABLE DimDate (
    date_key INTEGER PRIMARY KEY,
    date_iso TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_label TEXT NOT NULL
);
CREATE TABLE DimProduct (
    product_key TEXT PRIMARY KEY,
    product_name TEXT NOT NULL
);
CREATE TABLE DimCountry (
    country_key TEXT PRIMARY KEY,
    country_name TEXT NOT NULL
);
CREATE TABLE DimCustomer (
    customer_key TEXT PRIMARY KEY,
    first_observed_purchase TEXT,
    cohort_month TEXT,
    is_identified INTEGER NOT NULL
);
CREATE TABLE FactOrderLine (
    line_key INTEGER PRIMARY KEY,
    invoice_no TEXT NOT NULL,
    date_key INTEGER NOT NULL REFERENCES DimDate,
    product_key TEXT NOT NULL REFERENCES DimProduct,
    country_key TEXT NOT NULL REFERENCES DimCountry,
    customer_key TEXT NOT NULL REFERENCES DimCustomer,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('Sale','Credit')),
    quantity INTEGER NOT NULL,
    line_pence INTEGER NOT NULL,
    exact_duplicate INTEGER NOT NULL
);
CREATE INDEX ix_line_date ON FactOrderLine(date_key);
CREATE INDEX ix_line_customer ON FactOrderLine(customer_key,invoice_no);
CREATE INDEX ix_line_product ON FactOrderLine(product_key);

