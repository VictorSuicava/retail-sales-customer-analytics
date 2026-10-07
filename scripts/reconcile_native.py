"""Compare captured native DAX results with independently computed SQL aggregates."""
import argparse
import json
import math
from pathlib import Path
import sqlite3

from pipeline import ROOT, write_json
from validation_evidence import analysis_fingerprint, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results',type=Path,help='JSON from the six queries in powerbi/validation_queries.dax')
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding='utf-8-sig'))
    data = {name:[{k.split('[',1)[-1].rstrip(']'):v for k,v in row.items()} for row in rows] for name,rows in data.items()}
    conn = sqlite3.connect(ROOT/'data/warehouse/retail.sqlite')
    conn.row_factory = sqlite3.Row
    checks = 0
    def same(actual,expected,label,empty_is_zero=False):
        nonlocal checks
        if actual is None and expected==0 and empty_is_zero:
            actual=0
        if expected is None:
            ok = actual is None
        elif isinstance(expected,(int,float)):
            tolerance = 1e-8 if abs(expected)<=1 else 0.005
            ok = isinstance(actual,(int,float)) and math.isclose(actual,expected,rel_tol=1e-10,abs_tol=tolerance)
        else:
            ok = actual==expected
        if not ok:
            raise ValueError(f'{label}: native={actual}, SQL={expected}')
        checks += 1
    quality = json.loads((ROOT/'docs/quality_report.json').read_text())
    expected = quality['checks']
    overall = data['overall'][0]
    for name,value in [('Gross',expected['gross_sales_pence']/100),('Credits',-expected['credit_pence_signed']/100),
                       ('Net',expected['net_sales_pence']/100),('Lines',expected['source_and_fact_rows']),
                       ('Orders',quality['summary']['orders']),('Buyers',quality['summary']['identified_buyers']),
                       ('RepeatBuyers',quality['summary']['repeat_buyers'])]:
        same(overall[name],value,'overall '+name)
    same(overall['AverageOrder'],overall['Gross']/overall['Orders'],'average order')
    same(overall['CreditRatio'],overall['Credits']/overall['Gross'],'credit ratio')
    same(overall['RepeatRate'],overall['RepeatBuyers']/overall['Buyers'],'repeat share')
    known_pence = conn.execute("SELECT SUM(line_pence) FROM FactOrderLine WHERE transaction_type='Sale' AND customer_key<>'Unknown'").fetchone()[0]
    same(overall['Coverage'],known_pence/expected['gross_sales_pence'],'customer ID coverage')
    summary = {}
    mappings = {'Gross':'gross_sales_gbp','Credits':'credit_value_gbp','Net':'net_sales_gbp','Orders':'orders',
                'Units':'sold_units','Coverage':'customer_id_sales_coverage'}
    for name,view,key in [('monthly','v_monthly_sales','month_label'),('countries','v_country_sales','country_name'),
                           ('products','v_product_sales','product_key')]:
        rows = {r[key]:dict(r) for r in conn.execute('SELECT * FROM '+view)}
        native = {r[key]:r for r in data[name]}
        if rows.keys()!=native.keys():
            raise ValueError(f'{name} population differs')
        for entity,row in native.items():
            for metric,column in mappings.items():
                if metric in row:
                    same(row[metric],rows[entity][column],f'{name} {entity} {metric}',empty_is_zero=metric in {'Gross','Credits','Net','Orders','Units'})
        summary[name]=len(rows)
    cohort_sql = {(r['cohort_month'],r['month_age']):r['repurchase_rate'] for r in conn.execute('SELECT * FROM v_cohort_activity')}
    cohort_native = {(r['cohort_month'],r['month_age']):r['Repurchase'] for r in data['cohorts']}
    if cohort_sql.keys()!=cohort_native.keys():
        raise ValueError('Observed cohort cells differ')
    for key,value in cohort_sql.items():
        same(cohort_native[key],value,f'cohort {key}')
    same(data['cohort_totals'][0]['UnfilteredRate'],None,'multi-age cohort total')
    same(data['cohort_totals'][0]['NovemberAgeOne'],None,'unobserved future cohort age')
    conn.close()
    result={'passed':True,'comparisons':checks,'monthly_groups':summary['monthly'],'country_groups':summary['countries'],
            'product_groups':summary['products'],'observed_cohort_cells':len(cohort_sql),
            'unobserved_ages_and_multi_age_totals':'blank','scope':'Native Power BI DAX engine compared with SQLite; visual layout is verified separately.',
            'analysis_fingerprint':analysis_fingerprint(), 'captured_results_sha256':digest(args.results)}
    write_json(ROOT/'docs/native_validation.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
