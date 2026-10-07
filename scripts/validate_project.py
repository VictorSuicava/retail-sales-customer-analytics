"""Validate CSV exports, model references and optional official PBIR JSON schemas.

This does not execute DAX or establish native Power BI rendering correctness.
"""
import argparse
import csv
import hashlib
import json
import re
import sqlite3
from urllib.request import Request, urlopen

from build_powerbi import MODEL, REPORT, TABLES, POWERBI, ROOT
from pipeline import reconcile, START, END_EXCLUSIVE, write_json
from validation_evidence import analysis_fingerprint, report_fingerprint, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schemas',action='store_true',help='Requires requirements-validation.txt and network on the first run')
    args = parser.parse_args()
    with sqlite3.connect(ROOT/'data/warehouse/retail.sqlite') as conn:
        checks = reconcile(conn,START,END_EXCLUSIVE)
        exported = {}
        for table,filename in TABLES.items():
            actual_table = {'CustomerSnapshot':'v_customer_snapshot','CohortActivity':'v_cohort_activity'}.get(table,table)
            expected = conn.execute(f'SELECT COUNT(*) FROM {actual_table}').fetchone()[0]
            with (ROOT/'data/processed'/f'{filename}.csv').open(encoding='utf-8',newline='') as handle:
                reader = csv.reader(handle)
                next(reader)
                count = sum(1 for _ in reader)
            if count != expected:
                raise ValueError(f'CSV row count differs for {table}: {count} vs {expected}')
            exported[table] = count
    model = json.loads((MODEL/'model.bim').read_text(encoding='utf-8'))['model']
    fields = {t['name']:{c['name'] for c in t['columns']} for t in model['tables']}
    measures = {m['name']:m['expression'] for t in model['tables'] for m in t.get('measures',[])}
    for name,expression in measures.items():
        for table,field in re.findall(r'(\w+)\[([^\]]+)\]',expression):
            if table not in fields or field not in fields[table]:
                raise ValueError(f'Unknown DAX column in {name}: {table}[{field}]')
        for ref in re.findall(r'(?<!\w)\[([^\]]+)\]',expression):
            if ref not in measures:
                raise ValueError(f'Unknown measure in {name}: [{ref}]')
    def validate_fields(value):
        if isinstance(value,dict):
            for kind in ('Column','Measure'):
                if kind in value and 'Property' in value[kind]:
                    field = value[kind]
                    table = field['Expression']['SourceRef']['Entity']
                    allowed = measures if kind=='Measure' else fields.get(table,set())
                    if field['Property'] not in allowed:
                        raise ValueError(f'Unknown visual {kind}: {table}.{field["Property"]}')
            for item in value.values():
                validate_fields(item)
        elif isinstance(value,list):
            for item in value:
                validate_fields(item)
    schema_files = 0
    if args.schemas:
        from jsonschema.validators import validator_for
        from referencing import Registry, Resource
        cache = ROOT/'.cache/schemas'
        cache.mkdir(parents=True,exist_ok=True)
        def retrieve(uri):
            path = cache/(hashlib.sha256(uri.encode()).hexdigest()+'.json')
            if not path.exists():
                if not uri.startswith(('https://developer.microsoft.com/json-schemas/','https://json-schema.org/')):
                    raise ValueError(f'Unexpected schema host: {uri}')
                with urlopen(Request(uri,headers={'User-Agent':'Retail-PBIR-validator'}),timeout=30) as response:
                    path.write_bytes(response.read())
            return Resource.from_contents(json.loads(path.read_text(encoding='utf-8')))
        registry = Registry(retrieve=retrieve)
    json_files = list(REPORT.rglob('*.json'))+[REPORT/'definition.pbir',MODEL/'definition.pbism']
    visuals = 0
    for path in json_files:
        data = json.loads(path.read_text(encoding='utf-8'))
        validate_fields(data)
        if path.name=='visual.json':
            visuals += 1
            p = data['position']
            if p['x']<0 or p['y']<0 or p['x']+p['width']>1280 or p['y']+p['height']>720:
                raise ValueError(f'Visual exceeds page bounds: {path.name}')
        if args.schemas and '$schema' in data:
            resource = retrieve(data['$schema'])
            schema = resource.contents
            validator_for(schema)(schema,registry=registry).validate(data)
            schema_files += 1
    page_order = json.loads((REPORT/'definition/pages/pages.json').read_text())['pageOrder']
    if len(page_order)!=4 or len(set(page_order))!=4:
        raise ValueError('Expected four distinct report pages')
    native_path = ROOT/'docs/native_validation.json'
    native = json.loads(native_path.read_text()) if native_path.exists() else {}
    current_native = native.get('passed') is True and native.get('analysis_fingerprint') == analysis_fingerprint()
    delivery_path = ROOT/'docs/delivery_validation.json'
    delivery = json.loads(delivery_path.read_text()) if delivery_path.exists() else {}
    pbix = ROOT/'powerbi/RetailPortfolio.pbix'
    current_delivery = (delivery.get('visual_review') == 'passed'
                        and delivery.get('report_fingerprint') == report_fingerprint()
                        and delivery.get('analysis_fingerprint') == analysis_fingerprint()
                        and pbix.exists() and delivery.get('pbix_sha256') == digest(pbix))
    result = {'sql_reconciliation':checks,'csv_row_counts':exported,'pages':len(page_order),
              'visuals':visuals,'measure_count':len(measures),'model_and_visual_references':'passed',
              'official_schema_files_validated':schema_files,
              'native_desktop_refresh':'passed' if current_native else 'pending',
              'native_dax_execution':'passed' if current_native else 'pending',
              'native_visual_validation':'passed' if current_delivery else 'pending'}
    write_json(ROOT/'docs/project_validation.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
