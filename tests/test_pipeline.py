"""Regression tests for commercially consequential data definitions."""
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sqlite3
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from pipeline import classify, normalize, build_dimensions_and_fact, reconcile


def row(invoice='100001', sku='12345A', quantity=2, price=3.5, customer=12345, timestamp=datetime(2011,1,5)):
    return (invoice,sku,'TEST PRODUCT',quantity,timestamp,price,customer,'United Kingdom')


class RetailTests(unittest.TestCase):
    def test_credit_is_not_an_order(self):
        self.assertEqual(classify('C100001','12345A',-2,Decimal('3.50')),'Credit')
        self.assertEqual(classify('C100001','12345A',2,Decimal('3.50')),'Review adjustment')

    def test_non_product_fees_are_separate(self):
        self.assertEqual(classify('100001','POST',1,Decimal('10')),'Non-merchandise')

    def test_unknown_customer_remains_missing(self):
        self.assertIsNone(normalize(row(customer=None),2)[7])

    def test_line_money_is_rounded_after_multiplication(self):
        self.assertEqual(normalize(row(quantity=3,price=0.335),2)[9],101)

    def test_zero_and_negative_prices_are_excluded(self):
        for price in ('0','-1'):
            self.assertEqual(classify('100001','12345A',1,Decimal(price)),'Invalid value')

    def test_fractional_quantity_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Invalid quantity'):
            normalize(row(quantity=1.5),2)

    def test_invoice_grain_credits_unknowns_and_cohort_censoring(self):
        c = sqlite3.connect(':memory:')
        self.addCleanup(c.close)
        c.executescript((ROOT/'sql/schema.sql').read_text())
        raw = [row(),row(sku='54321',price=2),
               row(invoice='100002',timestamp=datetime(2011,2,4)),
               row(invoice='C100001',quantity=-1),
               row(invoice='100003',customer=None),
               row(invoice='100004',customer=22222,timestamp=datetime(2011,2,7)),
               row(invoice='100005',timestamp=datetime(2011,3,1))]
        c.executemany('INSERT INTO raw_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                      [(*normalize(r,i+2),0) for i,r in enumerate(raw)])
        build_dimensions_and_fact(c,date(2011,1,1),date(2011,3,1))
        result = reconcile(c,date(2011,1,1),date(2011,3,1))
        self.assertEqual(result['source_and_fact_rows'],6)
        self.assertEqual(c.execute("SELECT SUM(orders) FROM v_monthly_sales").fetchone()[0],4)
        self.assertEqual(c.execute("SELECT purchase_orders FROM v_customer_snapshot WHERE customer_key='12345'").fetchone()[0],2)
        self.assertEqual(c.execute("SELECT repurchase_rate FROM v_cohort_activity WHERE cohort_month='2011-01' AND month_age=1").fetchone()[0],1)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM v_cohort_activity WHERE cohort_month='2011-02' AND month_age=1").fetchone()[0],0)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM DimCustomer WHERE customer_key='Unknown'").fetchone()[0],1)

    def test_observed_inactive_cohort_cell_is_zero(self):
        c = sqlite3.connect(':memory:')
        self.addCleanup(c.close)
        c.executescript((ROOT/'sql/schema.sql').read_text())
        c.execute('INSERT INTO raw_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(*normalize(row(),2),0))
        build_dimensions_and_fact(c,date(2011,1,1),date(2011,3,1))
        self.assertEqual(c.execute("SELECT repurchase_rate FROM v_cohort_activity WHERE month_age=1").fetchone()[0],0)

    def test_conflicting_invoice_customer_is_rejected(self):
        c = sqlite3.connect(':memory:')
        self.addCleanup(c.close)
        c.executescript((ROOT/'sql/schema.sql').read_text())
        c.executemany('INSERT INTO raw_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                      [(*normalize(row(customer=customer),i+2),0) for i,customer in enumerate((12345,22222))])
        build_dimensions_and_fact(c,date(2011,1,1),date(2011,3,1))
        with self.assertRaisesRegex(ValueError,'conflicting dates'):
            reconcile(c,date(2011,1,1),date(2011,3,1))

    def test_sku_case_aliases_share_one_product_without_losing_sales(self):
        c = sqlite3.connect(':memory:')
        self.addCleanup(c.close)
        c.executescript((ROOT/'sql/schema.sql').read_text())
        records = [row(invoice='100001',sku='15056BL'),row(invoice='100002',sku='15056bl')]
        c.executemany('INSERT INTO raw_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                      [(*normalize(r,i+2),0) for i,r in enumerate(records)])
        build_dimensions_and_fact(c,date(2011,1,1),date(2011,3,1))
        self.assertEqual(c.execute('SELECT COUNT(*) FROM DimProduct').fetchone()[0],1)
        self.assertEqual(c.execute('SELECT SUM(line_pence),COUNT(*) FROM FactOrderLine').fetchone(),(1400,2))


if __name__ == '__main__':
    unittest.main()
