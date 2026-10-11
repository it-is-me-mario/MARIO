"""Stream GLORIA's signed product-tax bridge with MARIO's native SUT reader.
Only regional aggregates are retained. Matrix axes and signed subsidies are
checked; world GDP is validated against all five final-demand valuations.
"""
from pathlib import Path
import argparse,json,sys,zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))


def summarize(resource,nr,ns,nf):
    from mario.parsers.gloria import _iter_csv_batches
    width=nr*(2*ns if '_T-Results_' in resource.name else nf)
    totals=np.zeros((2,width));seen=0
    for rows,values in _iter_csv_batches(resource,columns=np.arange(width),dtype=np.dtype('float64'),batch_size=96):
        if not np.isfinite(values).all():raise ValueError('Non-finite GLORIA valuation')
        mask=rows%(ns*2)<ns
        totals[0]+=values[mask].sum(axis=0);totals[1]+=values[~mask].sum(axis=0);seen+=len(rows)
    if seen!=nr*ns*2:raise ValueError('GLORIA valuation axes changed')
    return dict(activity_row_column_totals=totals[0].tolist(),commodity_row_column_totals=totals[1].tolist())


def build(snapshot,summaries,source_audit=None):
    recipe=snapshot['recipe'];codes=[r['code'] for r in snapshot['regions']]
    nr,ns,nf=len(codes),len(recipe['sectors']),len(recipe['consumption_categories'])
    components={};sources=[]
    for markup,kind in [(4,'product_taxes'),(5,'product_subsidies')]:
        parts={}
        for block in ['T','Y']:
            d=summaries[f'{block}{markup}'];a=np.asarray(d['activity_row_column_totals']);c=np.asarray(d['commodity_row_column_totals'])
            if np.max(np.abs(a))>1e-6:raise ValueError('Unexpected activity-row product-tax valuations')
            if block=='T':
                c=c.reshape(nr,2*ns)
                if np.max(np.abs(c[:,ns:]))>1e-6:raise ValueError('Unexpected supply-side product-tax valuations')
                parts['intermediate']=c[:,:ns].sum(axis=1)
            else:parts['final']=c.reshape(nr,nf).sum(axis=1)
            sources.append(d['member'])
        components[kind]={k:v.tolist() for k,v in parts.items()}
    # Subsidies are source-signed negative values; never subtract them twice.
    if any(v>1e-6 for part in components['product_subsidies'].values() for v in part):raise ValueError('Review changed subsidy sign')
    net=sum(np.asarray(v) for item in components.values() for v in item.values())*recipe['currency_scale']
    va=np.array([sum(r['value_added']) for r in snapshot['regions']]);gdp=va+net
    expenditure=sum(sum(summaries[f'Y{i}']['commodity_row_column_totals']) for i in range(1,6))*recipe['currency_scale']
    residual=float(gdp.sum()-expenditure)
    identity_status='within_tolerance'
    if abs(residual)>max(1,abs(expenditure))*1e-5:
        # Do not silently widen the balance tolerance. A source residual can be
        # retained only after independent direct CSV sums reproduce Va and all
        # five final-use valuations, with matching source member CRCs.
        if source_audit is None:raise ValueError(f'World GDP income/expenditure identity failed: {residual}')
        v=source_audit['V1']
        if v['native_commodity']!=0 or not np.isclose(v['native_activity']*recipe['currency_scale'],va.sum(),rtol=1e-12):raise ValueError('Independent source Va audit mismatch')
        for i in range(1,6):
            cached=summaries[f'Y{i}'];audit=source_audit[f'Y{i}']
            if cached['member']['name']!=audit['member'] or cached['member']['crc32']!=audit['crc32']:raise ValueError('Independent source Y identity mismatch')
            for key,axis in [('native_activity','activity_row_column_totals'),('native_commodity','commodity_row_column_totals')]:
                if not np.isclose(audit[key],sum(cached[axis]),rtol=1e-12,atol=1e-5):raise ValueError('Independent source Y audit mismatch')
        inventory={i['name']:i for i in snapshot['provenance'].get('economic_members',[])}
        if inventory.get(v['member'],{}).get('crc32')!=v['crc32']:raise ValueError('Independent source V identity mismatch')
        identity_status='independently_reproduced_source_residual'
    return {'schema_version':1,'id':recipe['id'],'currency':recipe['currency'],'currency_scale':recipe['currency_scale'],
        'region_codes':codes,'components_native':components,'net_product_taxes':net.tolist(),'gdp':gdp.tolist(),'sources':sources,
        'validation':{'world_value_added':float(va.sum()),'world_net_product_taxes':float(net.sum()),'world_gdp_income':float(gdp.sum()),
            'world_gdp_expenditure':float(expenditure),'income_minus_expenditure':residual,'relative_residual':residual/expenditure,'tolerance':1e-5,'identity_status':identity_status},
        'source_accounting_audit':source_audit,
        'basis':'Basic-price gross value added plus signed product-tax and subsidy valuations on intermediate and final commodity uses, including imports. Source subsidies enter with their original negative sign. Trade and transport margins are excluded from the tax bridge. All five final-demand valuations provide an independent world expenditure-side check.',
        'source_url':'https://ielab.info/resources/gloria','documentation':'GLORIA_ReleaseNotes_060.pdf, part II, National Accounting Identity; GLORIA_ReadMe_060.xlsx, Valuations and MR-SUT structure.'}


def apply(snapshot,bridge):
    recipe=snapshot['recipe']
    if recipe['id']!=bridge['id'] or [r['code'] for r in snapshot['regions']]!=bridge['region_codes']:raise ValueError('GDP bridge reading/region mismatch')
    for row,tax,gdp in zip(snapshot['regions'],bridge['net_product_taxes'],bridge['gdp']):
        if not np.isclose(sum(row['value_added'])+tax,gdp,rtol=1e-12,atol=1e-4):raise ValueError('GDP/GVA bridge mismatch')
        row.update(net_product_taxes=tax,gdp=gdp)
    residual=abs(bridge['validation']['relative_residual'])*100
    checked=bridge['validation'].get('identity_status')=='independently_reproduced_source_residual'
    identity_note=f'The world income/expenditure check has a {residual:.3f}% source residual, reproduced by independent direct CSV sums; values are not balanced or adjusted.' if checked else 'The world income/expenditure check differs by less than 0.001%.'
    recipe.update(tax_bridge='gloria_valuations',gdp_bridge_verified=True,gdp_basis='GDP at market prices: basic-price value added plus net product taxes',
        gdp_identity_status=bridge['validation'].get('identity_status','within_tolerance'),
        gdp_note='GLORIA GDP adds original product taxes and signed subsidies on intermediate and final commodity uses to the six basic-price value-added rows. '+identity_note+' Source vintages may differ from World Bank national accounts.',
        scope_note=f"GLORIA {recipe['year']}: economic vintage {recipe.get('economic_vintage', '20260122')}; satellite vintage {recipe.get('satellite_vintage', '20240417')}. GDP includes the verified source product-tax valuation bridge.")
    snapshot['provenance']['gdp_bridge']={k:bridge[k] for k in ['sources','validation','basis','documentation']}
    if checked:recipe['gdp_quality_note']=f"GLORIA {recipe['year']}: the world income/expenditure check has a {residual:.3f}% source residual, independently reproduced from the original tables. The income-side GDP is retained without a balancing adjustment."
    else:recipe.pop('gdp_quality_note',None)
    if bridge.get('source_accounting_audit'):snapshot['provenance']['gdp_bridge']['source_accounting_audit']=bridge['source_accounting_audit']
    return snapshot


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ['snapshot','archive','output','cache']:cli.add_argument('--'+name,type=Path,required=True)
    cli.add_argument('--source-audit',type=Path,help='Independent direct CSV accounting sums for a reviewed source residual.')
    args=cli.parse_args();snapshot=json.loads(args.snapshot.read_text());r=snapshot['recipe'];args.cache.mkdir(parents=True,exist_ok=True)
    nr,ns,nf=len(snapshot['regions']),len(r['sectors']),len(r['consumption_categories']);summaries={}
    from mario.parsers.gloria import GloriaResource
    with zipfile.ZipFile(args.archive) as z:members=z.infolist()
    for block,markups in [('Y',range(1,6)),('T',[4,5])]:
        for markup in markups:
            info=next(i for i in members if f'_{block}-Results_{r["year"]}_{r["release"]}_Markup00{markup}' in i.filename)
            identity={'name':info.filename,'size':info.file_size,'compressed':info.compress_size,'crc32':f'{info.CRC:08x}'}
            cache=args.cache/f'gloria-{block}-markup{markup}-totals.json'
            if cache.exists():
                d=json.loads(cache.read_text())
                if d['member']!=identity:raise ValueError('Cached GLORIA member identity changed')
            else:
                print('Reading',info.filename,flush=True);d=summarize(GloriaResource(args.archive,info.filename),nr,ns,nf);d['member']=identity
                cache.write_text(json.dumps(d))
            summaries[f'{block}{markup}']=d
    bridge=build(snapshot,summaries,json.loads(args.source_audit.read_text()) if args.source_audit else None);args.output.write_text(json.dumps(bridge,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps(bridge['validation']))
