"""Render SQL-derived analytical previews; these are not Power BI screenshots."""
from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    conn = sqlite3.connect(ROOT/'data/warehouse/retail.sqlite')
    conn.row_factory = sqlite3.Row
    months = conn.execute('SELECT * FROM v_monthly_sales ORDER BY month_label').fetchall()
    countries = conn.execute('SELECT * FROM v_country_sales ORDER BY net_sales_gbp DESC LIMIT 5').fetchall()
    gross = sum(r['gross_sales_gbp'] for r in months)
    credit = sum(r['credit_value_gbp'] for r in months)
    orders = sum(r['orders'] for r in months)
    buyers, repeats, known_sales, repeat_sales = conn.execute("SELECT COUNT(*),SUM(CASE WHEN purchase_orders>=2 THEN 1 ELSE 0 END),SUM(gross_sales_gbp),SUM(CASE WHEN purchase_orders>=2 THEN gross_sales_gbp ELSE 0 END) FROM v_customer_snapshot").fetchone()
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
                         'axes.spines.right':False,'axes.edgecolor':'#CDD6DF','axes.labelcolor':'#334155',
                         'xtick.color':'#475569','ytick.color':'#475569','figure.facecolor':'#F7F9FC'})
    fig = plt.figure(figsize=(16,9),dpi=110)
    fig.text(.055,.935,'Retail sales and customer analytics',fontsize=24,weight='bold',color='#182230')
    fig.text(.055,.89,'SQL analytical preview. Twelve complete months: December 2010 to November 2011.',color='#475569')
    metrics = [('Gross sales',f'£{gross/1e6:.2f}m'),('Recorded credits',f'£{credit/1e3:.1f}k'),
               ('Net sales',f'£{(gross-credit)/1e6:.2f}m'),('Purchase orders',f'{orders:,}')]
    for i,(label,value) in enumerate(metrics):
        x = .055+i*.238
        fig.text(x,.81,label,fontsize=12,color='#475569')
        fig.text(x,.752,value,fontsize=27,weight='bold',color='#136F63')
    ax = fig.add_axes((.07,.36,.55,.31))
    positions = range(len(months))
    ax.plot(positions,[r['gross_sales_gbp'] for r in months],color='#4C78A8',marker='o',label='Gross sales')
    ax.plot(positions,[r['net_sales_gbp'] for r in months],color='#136F63',marker='o',label='Net sales')
    ax.set_xticks(list(positions),[r['month_label'] for r in months],rotation=45,ha='right',fontsize=9)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'£{x/1e6:.1f}m'))
    ax.set_title('Monthly merchandise sales',loc='left',weight='bold',pad=15)
    ax.grid(axis='y',alpha=.16)
    ax.legend(frameon=False,loc='upper left',fontsize=10)
    ax2 = fig.add_axes((.73,.36,.24,.31))
    labels = [r['country_name'].replace('United Kingdom','UK') for r in countries][::-1]
    ax2.barh(labels,[r['net_sales_gbp'] for r in countries][::-1],color='#136F63')
    ax2.xaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'£{x/1e6:.0f}m'))
    ax2.set_title('Top five countries by net sales',loc='left',weight='bold',pad=15)
    fig.text(.055,.21,f'{repeats/buyers:.1%} of identified buyers placed at least two orders.',fontsize=17,weight='bold',color='#182230')
    fig.text(.055,.16,f'They generated {repeat_sales/known_sales:.1%} of identified gross sales. Customer IDs cover {known_sales/gross:.1%} of all gross sales.',fontsize=12,color='#475569')
    fig.text(.055,.105,'Credits are recorded separately from their original sales. Unknown customer IDs remain in sales totals.',fontsize=11,color='#475569')
    fig.text(.055,.05,'Source: UCI Online Retail (CC BY 4.0). Merchandise only. Duplicate observations retained and flagged.',fontsize=10,color='#64748B')
    output = ROOT/'docs/images'
    output.mkdir(parents=True,exist_ok=True)
    fig.savefig(output/'sales-preview.png',facecolor=fig.get_facecolor())
    plt.close(fig)

    data = conn.execute('SELECT * FROM v_cohort_activity ORDER BY cohort_month,month_age').fetchall()
    labels = sorted({r['cohort_month'] for r in data})
    values = np.full((len(labels),12),np.nan)
    sizes = {}
    for r in data:
        values[labels.index(r['cohort_month']),r['month_age']] = r['repurchase_rate']
        sizes[r['cohort_month']] = r['cohort_size']
    fig,ax = plt.subplots(figsize=(16,9),dpi=110)
    fig.subplots_adjust(left=.16,right=.95,top=.77,bottom=.17)
    fig.text(.055,.935,'Monthly repurchase cohorts',fontsize=24,weight='bold',color='#182230')
    fig.text(.055,.88,'Share of identified buyers purchasing in each month after their first observed purchase.',color='#475569',fontsize=13)
    fig.text(.055,.835,'Grey cells are outside the observation window. Repurchase is monthly activity, not continuous retention.',color='#475569',fontsize=11)
    cmap = plt.get_cmap('YlGnBu').copy()
    cmap.set_bad('#E7EDF3')
    ax.imshow(np.ma.masked_invalid(values),cmap=cmap,vmin=0,vmax=1,aspect='auto')
    ax.set_xticks(range(12),range(12))
    ax.set_xlabel('Months since first observed purchase',labelpad=10)
    ax.set_yticks(range(len(labels)),[f'{label}  (n={sizes[label]:,})' for label in labels])
    for y in range(len(labels)):
        for x in range(12):
            if not np.isnan(values[y,x]):
                ax.text(x,y,f'{values[y,x]:.0%}',ha='center',va='center',fontsize=10,
                        color='white' if values[y,x]>.55 else '#182230')
    ax.set_xticks(np.arange(-.5,12,1),minor=True)
    ax.set_yticks(np.arange(-.5,len(labels),1),minor=True)
    ax.grid(which='minor',color='white',linewidth=1.5)
    ax.tick_params(which='minor',bottom=False,left=False)
    fig.text(.055,.065,'SQL preview. Source: UCI Online Retail. Window: 01 Dec 2010 to 30 Nov 2011. First observed purchase is not necessarily acquisition.',color='#64748B',fontsize=10)
    fig.savefig(output/'cohort-preview.png',facecolor=fig.get_facecolor())
    plt.close(fig)
    conn.close()
    print('Rendered two SQL analytical previews.')


if __name__=='__main__':
    main()
