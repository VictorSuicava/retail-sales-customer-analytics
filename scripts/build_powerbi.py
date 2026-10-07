"""Create a portable four-page PBIP report and its local import semantic model."""
import argparse
import csv
import json
from pathlib import Path
import re

from pbi_layout import Page, REPORT, ROOT, SCHEMA, column, measure, literal, identifier, write_json

POWERBI = ROOT/'powerbi'
MODEL = POWERBI/'Retail.SemanticModel'
TABLES = {'DimDate':'dim_date','DimProduct':'dim_product','DimCountry':'dim_country',
          'DimCustomer':'dim_customer','FactOrderLine':'fact_order_line',
          'CustomerSnapshot':'customer_snapshot','CohortActivity':'cohort_activity'}
INTEGER_FIELDS = {'date_key','year','month','is_identified','line_key','quantity','line_pence',
                  'exact_duplicate','purchase_orders','first_purchase_date_key','last_purchase_date_key',
                  'month_age','cohort_size','active_customers'}
DECIMAL_FIELDS = {'gross_sales_gbp','credit_value_gbp','net_sales_gbp','repurchase_rate'}


def model(data: Path) -> None:
    tables = []
    for table, filename in TABLES.items():
        with (data/f'{filename}.csv').open(encoding='utf-8',newline='') as f:
            fields = next(csv.reader(f))
        types, columns = [], []
        for field in fields:
            if field in INTEGER_FIELDS:
                mtype, datatype = 'Int64.Type','int64'
            elif field in DECIMAL_FIELDS:
                mtype, datatype = 'type number','double'
            elif field in {'date_iso','first_observed_purchase'}:
                mtype, datatype = 'type date','dateTime'
            else:
                mtype, datatype = 'type text','string'
            types.append('{"'+field+'", '+mtype+'}')
            c = {'name':field,'dataType':datatype,'sourceColumn':field,'summarizeBy':'none',
                 'lineageTag':identifier(table+':'+field)}
            if field.endswith('_key') or field=='line_pence' or field=='exact_duplicate':
                c['isHidden'] = True
            if field=='date_iso':
                c.update({'isKey':True,'formatString':'dd MMM yyyy'})
            if field in DECIMAL_FIELDS:
                c['formatString'] = '0.0%' if field=='repurchase_rate' else '£#,0.00'
            columns.append(c)
        query = 'let\n    Source = Csv.Document(File.Contents(DataFolder & "/'+filename+'.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n    Typed = Table.TransformColumnTypes(Headers, {'+', '.join(types)+'}, "en-US")\nin\n    Typed'
        (POWERBI/f'{table}.m').write_text(query+'\n',encoding='utf-8')
        item = {'name':table,'lineageTag':identifier(table),'columns':columns,
                'partitions':[{'name':table,'mode':'import','source':{'type':'m','expression':query}}]}
        if table=='DimDate':
            item['dataCategory']='Time'
        tables.append(item)
    definitions = re.sub(r'(?m)^//.*$','',(POWERBI/'measures.dax').read_text(encoding='utf-8'))
    measures = []
    for text in re.split(r'\n\s*\n',definitions.strip()):
        name, expression = text.split('=',1)
        name = name.strip()
        fmt = '£#,0.00' if name.endswith('GBP') else '0.0%' if any(x in name for x in ('Rate','Ratio','Coverage')) else '#,0'
        measures.append({'name':name,'expression':expression.strip(),'formatString':fmt,
                         'displayFolder':'Retail','lineageTag':identifier(name)})
    tables.append({'name':'Metrics','columns':[{'name':'_placeholder','dataType':'int64','sourceColumn':'_placeholder','isHidden':True}],
                   'partitions':[{'name':'Metrics','mode':'import','source':{'type':'m','expression':'#table(type table [_placeholder = Int64.Type], {{0}})'}}],
                   'measures':measures})
    relationships = [{'name':identifier(table+':'+key),'fromTable':'FactOrderLine','fromColumn':key,
                      'toTable':table,'toColumn':key,'crossFilteringBehavior':'oneDirection'}
                     for table,key in [('DimDate','date_key'),('DimProduct','product_key'),('DimCountry','country_key'),('DimCustomer','customer_key')]]
    body = {'name':'RetailAnalytics','compatibilityLevel':1600,'model':{'culture':'en-US',
            'defaultPowerBIDataSourceVersion':'powerBI_V3','sourceQueryCulture':'en-US','tables':tables,
            'relationships':relationships,'expressions':[{'name':'DataFolder','kind':'m','expression':'"'+data.as_posix().replace('"','""')+'" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'}],
            'annotations':[{'name':'__PBI_TimeIntelligenceEnabled','value':'0'}]}}
    write_json(MODEL/'model.bim',body)
    write_json(MODEL/'definition.pbism',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json','version':'4.0','settings':{'qnaEnabled':False}})


def header(page: Page, title: str, subtitle: str, slicer: bool = True) -> None:
    page.text(title,(24,14,950,50),24,True)
    page.text(subtitle,(24,66,1232,42),11)
    if slicer:
        page.slicer('DimCountry','country_name','Country',(992,14,264,90))
    page.text('Source: UCI Online Retail. Merchandise only. 01 Dec 2010 to 30 Nov 2011. Currency: GBP.',(24,680,1232,28),9)


def descending(name):
    return {'field':measure(name)['field'],'direction':'Descending'}


def report() -> None:
    overview = Page('retail-overview','01 | Sales overview')
    header(overview,'Retail sales overview','Gross sales, recorded credits and net merchandise sales across twelve complete months.')
    for i,m in enumerate(('Gross Sales GBP','Credit Value GBP','Net Sales GBP','Orders')):
        overview.card(m,(24+i*312,124,296,104))
    overview.visual('lineChart','Monthly gross and net sales',(24,248,760,300),{
        'Category':[column('DimDate','month_label','Month')],'Y':[measure('Gross Sales GBP'),measure('Net Sales GBP')]},
        sort={'field':column('DimDate','month_label')['field'],'direction':'Ascending'})
    overview.visual('barChart','Net sales by country',(804,248,452,300),{
        'Category':[column('DimCountry','country_name','Country')],'Y':[measure('Net Sales GBP')]},sort=descending('Net Sales GBP'))
    for i,m in enumerate(('Average Order GBP','Credit to Sales Ratio','Customer ID Sales Coverage')):
        overview.card(m,(24+i*416,568,400,92))

    products = Page('retail-products','02 | Products and credits')
    header(products,'Products and credits','Compare recorded credit value with sales. Credits are not linked to their original orders.')
    products.visual('tableEx','Products | sorted by net sales',(24,124,1232,330),{'Values':[
        column('DimProduct','product_key','SKU'),column('DimProduct','product_name','Product'),
        *[measure(m) for m in ('Gross Sales GBP','Credit Value GBP','Net Sales GBP','Sold Units')]]},sort=descending('Net Sales GBP'))
    products.visual('clusteredColumnChart','Monthly recorded credits',(24,474,760,186),{
        'Category':[column('DimDate','month_label','Month')],'Y':[measure('Credit Value GBP')]},
        sort={'field':column('DimDate','month_label')['field'],'direction':'Ascending'})
    products.card('Credit to Sales Ratio',(804,474,452,186))

    customers = Page('retail-customers','03 | Customer repeat purchasing')
    header(customers,'Customer repeat purchasing','Identified buyers only. Fixed full-window snapshot. One observed order does not imply churn.',False)
    for i,(m,label) in enumerate((('Snapshot Buyers','Identified buyers'),('Snapshot Repeat Buyers','Repeat buyers'),('Snapshot Repeat Rate','Repeat buyer share'))):
        customers.card(m,(24+i*416,124,400,104),label)
    customers.visual('barChart','Gross sales by observed buyer group',(24,248,452,412),{
        'Category':[column('CustomerSnapshot','buyer_group','Buyer group')],'Y':[measure('Snapshot Gross Sales GBP','Gross sales GBP')]},
        objects={'categoryAxis':[{'properties':{'maxSize':literal(50),'fontSize':literal(10)}}]})
    customers.visual('tableEx','Customer value | sorted by gross sales',(496,248,760,412),{'Values':[
        column('CustomerSnapshot','customer_key','Customer ID'),column('CustomerSnapshot','cohort_month','First observed month'),
        column('CustomerSnapshot','purchase_orders','Orders'),column('CustomerSnapshot','gross_sales_gbp','Gross sales GBP'),
        column('CustomerSnapshot','credit_value_gbp','Credits GBP')]},
        sort={'field':column('CustomerSnapshot','gross_sales_gbp')['field'],'direction':'Descending'})

    cohort = Page('retail-cohorts','04 | Monthly repurchase cohorts')
    header(cohort,'Monthly repurchase cohorts','First observed purchase defines each cohort. Cells show purchasing in that month, not cumulative survival.',False)
    cohort.visual('pivotTable','Share of cohort buying again by months since first observed purchase',(24,124,1232,350),{
        'Rows':[column('CohortActivity','cohort_month','First observed month')],
        'Columns':[column('CohortActivity','month_age','Months since first purchase')],
        'Values':[measure('Cohort Repurchase Rate')]},objects={
            'values':[{'properties':{'fontSize':literal(11)}}],
            'rowHeaders':[{'properties':{'fontSize':literal(11)}}],
            'columnHeaders':[{'properties':{'fontSize':literal(11)}}]})
    cohort.visual('tableEx','Cohort population and observed activity',(24,494,1232,166),{'Values':[
        column('CohortActivity','cohort_month','Cohort'),column('CohortActivity','month_age','Month age'),
        column('CohortActivity','cohort_size','Cohort size'),column('CohortActivity','active_customers','Active buyers'),
        measure('Cohort Repurchase Rate')]})
    pages = [p.name for p in (overview,products,customers,cohort)]
    write_json(REPORT/'definition/pages/pages.json',{'$schema':SCHEMA+'definition/pagesMetadata/1.0.0/schema.json','pageOrder':pages,'activePageName':pages[0]})
    write_json(REPORT/'definition/version.json',{'$schema':SCHEMA+'definition/versionMetadata/1.0.0/schema.json','version':'2.0.0'})
    version = {'visual':'2.7.0','page':'2.1.0','report':'3.2.0'}
    theme = 'RetailTheme'
    write_json(REPORT/'StaticResources/RegisteredResources'/theme,json.loads((POWERBI/'theme.json').read_text()))
    write_json(REPORT/'definition/report.json',{'$schema':SCHEMA+'definition/report/3.2.0/schema.json',
        'themeCollection':{'baseTheme':{'name':'CY24SU06','reportVersionAtImport':version,'type':'SharedResources'},
                           'customTheme':{'name':theme,'reportVersionAtImport':version,'type':'RegisteredResources'}},
        'resourcePackages':[{'name':'RegisteredResources','type':'RegisteredResources','items':[{'name':theme,'path':theme,'type':'CustomTheme'}]}]})
    write_json(REPORT/'definition.pbir',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json',
                                      'version':'4.0','datasetReference':{'byPath':{'path':'../Retail.SemanticModel'}}})
    write_json(POWERBI/'Retail.pbip',{'version':'1.0','artifacts':[{'report':{'path':'Retail.Report'}}],'settings':{'enableAutoRecovery':True}})


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--overwrite',action='store_true',help='Deliberately replace local model and report edits')
    args = parser.parse_args()
    if (MODEL/'definition').exists():
        parser.error('A Desktop-authored TMDL model exists. Use a separate project folder.')
    if (MODEL/'model.bim').exists() and not args.overwrite:
        parser.error('Local model exists. Open Retail.pbip or explicitly use --overwrite.')
    model((ROOT/'data/processed').resolve())
    if not REPORT.exists() or args.overwrite:
        report()
    print('Power BI source ready:',POWERBI/'Retail.pbip')
    print('Open in Desktop and refresh. Native rendering and DAX execution need Desktop validation.')
