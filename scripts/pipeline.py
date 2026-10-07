"""Download UCI Online Retail, reconcile a merchandise ledger and export a BI model."""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = 'https://archive.ics.uci.edu/static/public/352/online+retail.zip'
SOURCE_PAGE = 'https://archive.ics.uci.edu/dataset/352/online+retail'
START = date(2010, 12, 1)
END_EXCLUSIVE = date(2011, 12, 1)
EXPECTED_HEADERS = ('InvoiceNo','StockCode','Description','Quantity','InvoiceDate','UnitPrice','CustomerID','Country')


def identifier(value) -> str:
    if isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))
    return str(value).strip() if value is not None else ''


def classify(invoice: str, sku: str, quantity: int, price: Decimal) -> str:
    if not re.fullmatch(r'\d{5}[A-Za-z]*', sku):
        return 'Non-merchandise'
    if price <= 0 or quantity == 0:
        return 'Invalid value'
    if invoice.upper().startswith('C') and quantity < 0:
        return 'Credit'
    if invoice.isdigit() and quantity > 0:
        return 'Sale'
    return 'Review adjustment'


def normalize(row: tuple, source_row: int) -> tuple:
    invoice, sku, description, quantity, timestamp, price, customer, country = row
    if not isinstance(timestamp, datetime):
        raise ValueError(f'Invalid invoice date at source row {source_row}')
    if isinstance(quantity, bool) or quantity is None or int(quantity) != quantity:
        raise ValueError(f'Invalid quantity at source row {source_row}')
    quantity = int(quantity)
    price = Decimal(str(price))
    if not price.is_finite():
        raise ValueError(f'Invalid price at source row {source_row}')
    invoice, sku = identifier(invoice), identifier(sku).upper()
    if not invoice or not sku or not country:
        raise ValueError(f'Missing transaction identifiers at source row {source_row}')
    pence = int((price * quantity * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return (source_row, invoice, sku, str(description).strip() if description is not None else None,
            quantity, timestamp.isoformat(timespec='seconds'), str(price),
            identifier(customer) or None, str(country).strip(), pence,
            classify(invoice, sku, quantity, price))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def load_source(path: Path, conn: sqlite3.Connection) -> int:
    import openpyxl
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = book.active.iter_rows(values_only=True)
        if tuple(next(rows)) != EXPECTED_HEADERS:
            raise ValueError('Source columns changed; review schema before ingestion')
        seen, batch, count = set(), [], 0
        for source_row, row in enumerate(rows, start=2):
            record = normalize(row, source_row)
            fingerprint = hashlib.sha256(json.dumps(row, ensure_ascii=False, default=str).encode()).digest()
            batch.append((*record, int(fingerprint in seen)))
            seen.add(fingerprint)
            count += 1
            if len(batch) >= 5000:
                conn.executemany('INSERT INTO raw_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', batch)
                batch.clear()
        conn.executemany('INSERT INTO raw_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', batch)
        return count
    finally:
        book.close()


def build_dimensions_and_fact(conn: sqlite3.Connection, start: date, end: date) -> None:
    conn.execute('CREATE TEMP VIEW eligible AS SELECT * FROM raw_lines '
                 "WHERE classification IN ('Sale','Credit') "
                 f"AND substr(invoice_datetime,1,10)>='{start.isoformat()}' "
                 f"AND substr(invoice_datetime,1,10)<'{end.isoformat()}'")
    calendar = []
    day = start
    while day < end:
        calendar.append((int(day.strftime('%Y%m%d')),day.isoformat(),day.year,day.month,day.strftime('%Y-%m')))
        day += timedelta(days=1)
    conn.executemany('INSERT INTO DimDate VALUES (?,?,?,?,?)', calendar)
    conn.execute('''INSERT INTO DimProduct
        WITH labels AS (
            SELECT stock_code,description,COUNT(*) AS n,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY COUNT(*) DESC,description) AS rn
            FROM eligible WHERE description IS NOT NULL GROUP BY stock_code,description
        )
        SELECT DISTINCT e.stock_code,COALESCE(l.description,e.stock_code)
        FROM eligible e LEFT JOIN labels l ON e.stock_code=l.stock_code AND l.rn=1''')
    conn.execute('INSERT INTO DimCountry SELECT DISTINCT country,country FROM eligible')
    conn.execute("INSERT INTO DimCustomer VALUES ('Unknown',NULL,NULL,0)")
    conn.execute('''INSERT INTO DimCustomer
        SELECT customer_id,
               MIN(CASE WHEN classification='Sale' THEN substr(invoice_datetime,1,10) END),
               MIN(CASE WHEN classification='Sale' THEN substr(invoice_datetime,1,7) END),1
        FROM eligible WHERE customer_id IS NOT NULL GROUP BY customer_id''')
    conn.execute('''INSERT INTO FactOrderLine
        SELECT source_row,invoice_no,CAST(replace(substr(invoice_datetime,1,10),'-','') AS INTEGER),
               stock_code,country,COALESCE(customer_id,'Unknown'),classification,quantity,line_pence,exact_duplicate
        FROM eligible''')
    conn.executescript((ROOT/'sql/analytics.sql').read_text(encoding='utf-8'))


def export_query(conn: sqlite3.Connection, query: str, path: Path) -> None:
    cursor = conn.execute(query)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow([column[0] for column in cursor.description])
        writer.writerows(cursor)


def reconcile(conn: sqlite3.Connection, start: date, end: date) -> dict:
    source = conn.execute('''SELECT COUNT(*),SUM(line_pence),
        SUM(CASE WHEN classification='Sale' THEN line_pence ELSE 0 END),
        SUM(CASE WHEN classification='Credit' THEN line_pence ELSE 0 END)
        FROM raw_lines WHERE classification IN ('Sale','Credit')
        AND substr(invoice_datetime,1,10)>=? AND substr(invoice_datetime,1,10)<?''',
        (start.isoformat(), end.isoformat())).fetchone()
    fact = conn.execute('''SELECT COUNT(*),SUM(line_pence),
        SUM(CASE WHEN transaction_type='Sale' THEN line_pence ELSE 0 END),
        SUM(CASE WHEN transaction_type='Credit' THEN line_pence ELSE 0 END)
        FROM FactOrderLine''').fetchone()
    if source != fact:
        raise ValueError(f'Source-to-fact reconciliation failed: {source} vs {fact}')
    foreign_keys = conn.execute('PRAGMA foreign_key_check').fetchall()
    if foreign_keys:
        raise ValueError('Broken dimension references')
    conflicting_invoices = conn.execute('''SELECT COUNT(*) FROM (
        SELECT invoice_no FROM FactOrderLine GROUP BY invoice_no
        HAVING COUNT(DISTINCT date_key)>1 OR COUNT(DISTINCT country_key)>1
            OR COUNT(DISTINCT customer_key)>1)''').fetchone()[0]
    if conflicting_invoices:
        raise ValueError('Invoice has conflicting dates, countries or customer IDs')
    cohorts = conn.execute('SELECT * FROM v_cohort_activity').fetchall()
    if any(row[4] > row[3] or (row[1] == 0 and row[4] != row[3]) for row in cohorts):
        raise ValueError('Cohort population reconciliation failed')
    observed_months = (end.year-start.year)*12+end.month-start.month
    if any(row[1] >= observed_months for row in cohorts):
        raise ValueError('Unobserved cohort age generated')
    return {'passed':True,'source_and_fact_rows':fact[0], 'net_sales_pence':fact[1],
            'gross_sales_pence':fact[2], 'credit_pence_signed':fact[3],
            'foreign_key_violations':0,'conflicting_invoices':0,'observed_cohort_cells':len(cohorts)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Deliberately download a new source snapshot')
    args = parser.parse_args()
    for folder in ('raw','processed','warehouse'):
        (ROOT/'data'/folder).mkdir(parents=True, exist_ok=True)
    archive = ROOT/'data/raw/online_retail.zip'
    if args.refresh or not archive.exists():
        temporary = archive.with_suffix('.zip.part')
        with urlopen(Request(SOURCE_URL, headers={'User-Agent':'Retail-analytics-portfolio'}), timeout=60) as r, temporary.open('wb') as f:
            shutil.copyfileobj(r, f)
        temporary.replace(archive)
    xlsx = ROOT/'data/raw/Online Retail.xlsx'
    if args.refresh or not xlsx.exists():
        with ZipFile(archive) as zipped:
            xlsx.write_bytes(zipped.read('Online Retail.xlsx'))
    database = ROOT/'data/warehouse/retail.sqlite'
    temporary_db = database.with_suffix('.sqlite.building')
    temporary_db.unlink(missing_ok=True)
    conn = sqlite3.connect(temporary_db)
    try:
        conn.executescript((ROOT/'sql/schema.sql').read_text(encoding='utf-8'))
        rows = load_source(xlsx, conn)
        build_dimensions_and_fact(conn, START, END_EXCLUSIVE)
        checks = reconcile(conn, START, END_EXCLUSIVE)
        conn.commit()
        tables = {'DimDate':'dim_date','DimProduct':'dim_product','DimCountry':'dim_country',
                  'DimCustomer':'dim_customer','FactOrderLine':'fact_order_line',
                  'v_customer_snapshot':'customer_snapshot','v_cohort_activity':'cohort_activity',
                  'v_monthly_sales':'monthly_sales','v_product_sales':'product_sales','v_country_sales':'country_sales'}
        for table, file in tables.items():
            export_query(conn, f'SELECT * FROM {table}', ROOT/'data/processed'/f'{file}.csv')
        classifications = dict(conn.execute('SELECT classification,COUNT(*) FROM raw_lines GROUP BY classification'))
        duplicates = conn.execute('SELECT SUM(exact_duplicate) FROM raw_lines').fetchone()[0]
        outside_window = conn.execute("SELECT COUNT(*) FROM raw_lines WHERE classification IN ('Sale','Credit') AND (substr(invoice_datetime,1,10)<? OR substr(invoice_datetime,1,10)>=?)",(START.isoformat(),END_EXCLUSIVE.isoformat())).fetchone()[0]
        summary = dict(zip(['orders','identified_buyers','unknown_customer_sale_rows'],conn.execute("SELECT COUNT(DISTINCT CASE WHEN transaction_type='Sale' THEN invoice_no END), COUNT(DISTINCT CASE WHEN transaction_type='Sale' AND customer_key<>'Unknown' THEN customer_key END), SUM(CASE WHEN transaction_type='Sale' AND customer_key='Unknown' THEN 1 ELSE 0 END) FROM FactOrderLine").fetchone()))
        summary.update({'repeat_buyers':conn.execute('SELECT COUNT(*) FROM v_customer_snapshot WHERE purchase_orders>=2').fetchone()[0],
                        'products':conn.execute('SELECT COUNT(*) FROM DimProduct').fetchone()[0],
                        'countries':conn.execute('SELECT COUNT(*) FROM DimCountry').fetchone()[0]})
        write_json(ROOT/'docs/quality_report.json', {'source_url':SOURCE_URL,'source_page':SOURCE_PAGE,
            'license':'CC BY 4.0','snapshot_sha256':hashlib.sha256(xlsx.read_bytes()).hexdigest(),
            'processed_at_utc':datetime.now(timezone.utc).isoformat(),'source_rows':rows,
            'analysis_start':START.isoformat(),'analysis_end_exclusive':END_EXCLUSIVE.isoformat(),
            'classification_counts':classifications,'outside_window_eligible_rows':outside_window,
            'exact_duplicate_rows_retained':duplicates,'duplicate_policy':'Keep and flag exact duplicate observations; source has no unique line identifier.',
            'checks':checks,'summary':summary})
    finally:
        conn.close()
    temporary_db.replace(database)
    print(json.dumps({'source_rows':rows,'checks':checks,'summary':summary},indent=2))


if __name__ == '__main__':
    main()

