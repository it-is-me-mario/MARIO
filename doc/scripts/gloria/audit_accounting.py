"""Independently sum original GLORIA Va and every Y valuation from raw CSV.

This deliberately bypasses MARIO's block readers to audit a source accounting
residual. Original numbers are preserved. No balance adjustment is made.
"""
from pathlib import Path
import argparse,json,time,zipfile
import numpy as np


def audit(archive,snapshot,profile,summaries):
    recipe=snapshot['recipe'];nr=len(snapshot['regions']);ns=len(recipe['sectors'])
    nf=len(recipe['consumption_categories']);nv=profile['counts']['Factor of production']
    checks={};start=time.time()
    with zipfile.ZipFile(archive) as z:
        members=z.namelist()
        for block,markup in [('V',1),*[('Y',i) for i in range(1,6)]]:
            member=next(n for n in members if f'_{block}-Results_{recipe["year"]}_{recipe["release"]}_Markup00{markup}' in n)
            total=0.;other=0.;rows=0
            with z.open(member) as f:
                for line in f:
                    row=np.fromstring(line.decode('ascii'),sep=',',dtype=np.float64)
                    expected=nr*(2*ns if block=='V' else nf)
                    if len(row)!=expected or not np.isfinite(row).all():raise ValueError('Unexpected direct CSV structure')
                    if block=='V':
                        a=row.reshape(nr,2*ns);total+=a[:,:ns].sum();other+=a[:,ns:].sum()
                    elif rows%(2*ns)<ns:other+=row.sum()
                    else:total+=row.sum()
                    rows+=1
            if rows!=(nr*nv if block=='V' else nr*ns*2):raise ValueError('Unexpected direct CSV row count')
            checks[f'{block}{markup}']={'member':member,'crc32':f'{z.getinfo(member).CRC:08x}','rows':rows,
                'native_activity':float(total if block=='V' else other),'native_commodity':float(other if block=='V' else total)}
            print('INDEPENDENT',block,markup,checks[f'{block}{markup}'],flush=True)
    va=sum(sum(r['value_added']) for r in snapshot['regions'])
    if not np.isclose(checks['V1']['native_activity']*recipe['currency_scale'],va,rtol=1e-12) or checks['V1']['native_commodity']!=0:
        raise ValueError('Independent source Va/Vc sums differ')
    for i in range(1,6):
        for key,source in [('native_activity','activity_row_column_totals'),('native_commodity','commodity_row_column_totals')]:
            if not np.isclose(checks[f'Y{i}'][key],sum(summaries[f'Y{i}'][source]),rtol=1e-12,atol=1e-5):raise ValueError('Independent source Y sums differ')
    checks.update(reading_scope='Independent direct CSV scalar sums (NumPy), without MARIO block readers; V and all five Y valuations. Source labels, shapes and CRCs checked.',seconds=time.time()-start)
    return checks


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--archive',type=Path,required=True);cli.add_argument('--stage',type=Path,required=True)
    args=cli.parse_args();p=args.stage
    snapshot=json.loads((p/'snapshot-base.json').read_text());profile=json.loads((p/'profile.json').read_text())
    sums={f'Y{i}':json.loads((p/f'Y{i}-summary.json').read_text()) for i in range(1,6)}
    result=audit(args.archive,snapshot,profile,sums)
    (p/'source-accounting-audit.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
