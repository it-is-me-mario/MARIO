"""Parse only local WIOD 2016 multiregional inputs through MARIO.

Observe original VA/TXSP rows during the same full parse and independently
reconcile country GDP. Source matrices are never exported or inverted.
"""
from pathlib import Path
import argparse,copy,functools,gc,gzip,hashlib,json,logging,re,sys,time
from unittest.mock import patch
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'doc/scripts'),str(ROOT/'doc/source/_static/reproduce')]
import mario
from mario.parsers import wiod
from mario.parsers.specs import WIOD_FACTOR_ROWS,WIOD_FINAL_DEMAND_CODES,WIOD_SUT_FINAL_DEMAND_CODES
from database_catalogue import extract_profile
from economy_browser import aggregate
logging.getLogger('mario').setLevel(logging.ERROR)

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if path.suffix=='.gz':raw=gzip.compress(raw)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_bytes(raw);temp.replace(path)

def checksum(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024**2),b''):h.update(chunk)
    return h.hexdigest()

def inventory(source):
    jobs=[]
    for kind,folder,pattern in [('iot-current','WIOTS_in_EXCEL',r'WIOT(\d{4})_Nov16_ROW.xlsb'),('iot-pyp','WIOTS_PYP_in_EXCEL',r'WIOT(\d{4})_PYP_Nov16_ROW.xlsb'),('sut','SUT_international',r'intsut(\d{2})_nov16.xlsb')]:
        for path in sorted((source/folder).glob('*.xlsb')):
            m=re.fullmatch(pattern,path.name,re.I)
            if not m:raise ValueError('Unreviewed filename: '+path.name)
            year=int(m[1])+(2000 if len(m[1])==2 else 0)
            if not path.stat().st_blocks:raise ValueError('Expected a hydrated local input: '+str(path))
            jobs.append({'id':f'wiod-2016-{year}-{kind}','kind':kind,'year':year,'path':str(path),'filename':path.name})
    expected={'iot-current':list(range(2000,2015)),'iot-pyp':list(range(2001,2015)),'sut':list(range(2000,2015))}
    for kind,years in expected.items():
        if sorted(j['year'] for j in jobs if j['kind']==kind)!=years:raise ValueError('Incomplete local '+kind+' inventory')
    return jobs

def collect(job,stage,sea,seed,notebooks):
    start=time.time();folder=stage/'readings'/job['id'];source=Path(job['path']);is_sut=job['kind']=='sut';pyp=job['kind']=='iot-pyp'
    observed={};original_iot=wiod._read_wiod_workbook;original_sut=wiod._read_wiod_table_sheet
    def read_iot(*a,**kw):
        f=original_iot(*a,**kw)
        observed.update(headers=f.iloc[2:5,4:].copy(),factors=f.loc[f.iloc[:,0].isin(['VA','TXSP'])].copy(),shape=list(f.shape),price_label=str(f.iloc[1,0]))
        return f
    def read_sut(*a,**kw):
        f=original_sut(*a,**kw)
        if kw['sheet_name']=='USE':
            observed.update(factors=f.loc[f['PAR'].eq('ZZZ')&f['CPA'].isin(['VA','TXSP'])].copy(),shape=list(f.shape),columns=list(f.columns))
        return f
    opts={'table':'SUT' if is_sut else 'IOT'}
    if is_sut:opts['row_mode']='external_account'
    if not pyp:opts['add_extensions']=str(sea)
    with patch.object(wiod,'_read_wiod_workbook',read_iot),patch.object(wiod,'_read_wiod_table_sheet',read_sut):
        db=mario.parse_wiod(path=str(source),calc_all=False,**opts)
    if int(db.meta.year)!=job['year']:raise ValueError('Parsed year differs from source year')
    notebook=notebooks['wiod--03' if is_sut else 'wiod--02' if pyp else 'wiod--07']
    p=extract_profile(db,job={'id':job['id'],'source':'WIOD','release':'2016','year':job['year'],'label':'WIOD 2016 · '+job['kind']},recipe=notebook,parameters={'path':str(source),'calc_all':False,**opts})
    native=p['sets'];sectors=native['Activity' if is_sut else 'Sector'];regions=native['Region']
    if len(regions)!=(43 if is_sut else 44) or len(sectors)!=56:raise ValueError('Unexpected WIOD coverage')
    r=copy.deepcopy(seed)
    for key in ['units','expected_units','sectors','regions','sector_groups']:r.pop(key,None)
    r.update(id=job['id'],label=f'WIOD 2016 · {"SUT" if is_sut else "IOT"} · {"previous-year prices" if pyp else "current prices"}',
      release='2016',year=job['year'],table='SUT' if is_sut else 'IOT',parser_options={**opts},
      sectors=sectors,regions=p['geography']['regions'],value_added_block='Va' if is_sut else 'V',
      price_basis='Previous year prices' if pyp else 'Current prices',currency='USD',currency_scale=1e6,
      dimension='Activity' if is_sut else 'Industry',value_added_rows=['Value added at basic prices'],
      product_tax_rows=['taxes less subsidies on products'],tax_bridge='wiod_sut_vy' if is_sut else 'wiod_iot',
      gdp_bridge_verified=True,gdp_basis='Value added at basic prices plus net product taxes on intermediate and final uses',
      gdp_note='Source VA plus TXSP on intermediate and final uses, independently reconciled by country. Balancing and transport-margin rows are excluded.',
      ghg_factors={},ghg_method='No local WIOD environmental accounts. Socio-economic accounts are not GHG emissions.',
      world_total_available=not is_sut,consumption_categories=native['Consumption category'],
      price_note='Previous-year prices and previous-year US dollars; not comparable with current-price World Bank GDP.' if pyp else '',
      scope_note='International SUT has 43 endogenous countries. ROW imports are external factor accounts; no complete ROW economy or World total is available.' if is_sut else '',
      attribution='WIOD 2016 release, Timmer et al. (2015). CC BY 4.0; indicators calculated by MARIO.')
    r['parser_options'].pop('add_extensions',None)
    if not pyp:r['parser_options']['add_extensions']='/path/to/Socio_Economic_Accounts.xlsx'
    p['environmental']=False
    p['price_basis']=r['price_basis'];p['world_total_available']=r['world_total_available']
    p['scope_note']=r['scope_note']
    tax_fd={code:0.0 for code in regions};raw_va={code:0.0 for code in regions};raw_tax={code:0.0 for code in regions}
    blank_cells=0
    if not is_sut:
        h=observed['headers'];f=observed['factors'];codes=h.iloc[0].tolist();reg=h.iloc[2].tolist()
        code_map=dict(zip(h.iloc[0,:56],h.iloc[1,:56]))
        if len(code_map)!=56:raise ValueError('Unexpected native industry codes')
        code_map={label:code for code,label in code_map.items()}
        if (stage/'native-industry-codes.json').exists() and json.loads((stage/'native-industry-codes.json').read_text())!=code_map:raise ValueError('Native code/label correspondence changed')
        write(stage/'native-industry-codes.json',code_map)
        source_rows={str(row.iloc[0]):pd.to_numeric(row.iloc[4:],errors='raise') for _,row in f.iterrows()}
        if set(source_rows)!= {'VA','TXSP'}:raise ValueError('Cannot identify unique source VA and TXSP rows')
        for i,(code,region) in enumerate(zip(codes,reg)):
            if region not in raw_va:continue
            va=source_rows['VA'].iloc[i];tax=source_rows['TXSP'].iloc[i]
            blank_cells+=int(pd.isna(va))+int(pd.isna(tax));va=0.0 if pd.isna(va) else float(va);tax=0.0 if pd.isna(tax) else float(tax)
            if code in WIOD_FINAL_DEMAND_CODES:tax_fd[region]+=tax
            elif code!='GO':raw_va[region]+=va
            else:continue
            raw_tax[region]+=tax
        if ('previous' in observed['price_label'].lower())!=pyp:raise ValueError('PYP filename/header mismatch')
    else:
        f=observed['factors'];VY=db.get_block('VY')
        parsed_fd=VY.loc[r['product_tax_rows']].sum(axis=0).groupby(level='Region').sum()
        for code in regions:
            rows=f.loc[f['REP'].eq(code)]
            if sorted(rows['CPA'])!=['TXSP','VA']:raise ValueError('Missing or duplicate source SUT factor row')
            va=pd.to_numeric(rows.loc[rows['CPA'].eq('VA'),sectors].iloc[0],errors='raise')
            tx=pd.to_numeric(rows.loc[rows['CPA'].eq('TXSP'),sectors+list(WIOD_SUT_FINAL_DEMAND_CODES)].iloc[0],errors='raise')
            blank_cells+=int(va.isna().sum()+tx.isna().sum())
            raw_va[code]=float(va.fillna(0).sum());raw_tax[code]=float(tx.fillna(0).sum())
            tax_fd[code]=float(tx.loc[list(WIOD_SUT_FINAL_DEMAND_CODES)].fillna(0).sum())
            if not np.isclose(tax_fd[code],parsed_fd[code],rtol=1e-12,atol=.0001):raise ValueError('Source/SUT VY tax mismatch')
        p['geography']['external_accounts']=[{'label':'ROW','name':'Rest of World','kind':'aggregate','members':[],'membership_status':'not_mapped','representation':'external_account'}]
        p['geography']['scope']='global'
    result=aggregate(db,r,tax_fd);max_error=0.0
    for row in result:
        code=row['code'];expected=[raw_va[code]*1e6,raw_tax[code]*1e6,(raw_va[code]+raw_tax[code])*1e6]
        for actual,want in zip([sum(row['value_added']),row['net_product_taxes'],row['gdp']],expected):
            if not np.isfinite(actual) or not np.isclose(actual,want,rtol=1e-12,atol=.1):raise ValueError('Raw/parsed GDP mismatch '+code)
            max_error=max(max_error,abs(actual-want))
        if 'ghg' in row:raise ValueError('No WIOD GHG indicator is authorized by these source files')
    prov=p['provenance'];prov.update(input_filename=source.name,input_sha256=checksum(source),input_bytes=source.stat().st_size,
      source_url=r['source_url'],mario_version=mario.__version__,price_basis=r['price_basis'],world_total_available=r['world_total_available'],
      reading_scope='Full local MARIO WIOD parse, calc_all=False; raw VA/TXSP country totals independently reconciled.',raw_shape=observed['shape'],
      extensions_filename=sea.name if not pyp else None,extensions_sha256=SEA_HASH if not pyp else None)
    if is_sut:prov['external_accounts']='ROW imports retained in Va/VY factor accounts; 43 endogenous countries.'
    r['expected_units']={group:{str(label):str(unit) for label,unit in frame['unit'].items()} for group,frame in db.units.items() if group in ['Sector','Activity','Factor of production']}
    snapshot={'schema_version':1,'recipe':r,'regions':result,'generated_at':p['parsed_at'],'provenance':prov}
    validation={'id':job['id'],'year':job['year'],'kind':job['kind'],'counts':p['counts'],'price_basis':r['price_basis'],'max_raw_parsed_error_usd':max_error,
      'source_blank_factor_cells':blank_cells,'world_total_available':not is_sut,'sum_endogenous_gdp_usd':sum(row['gdp'] for row in result),'seconds':round(time.time()-start,2)}
    (stage/'errors'/f"{job['id']}.json").unlink(missing_ok=True)
    write(folder/'profile.json.gz',p);write(folder/'snapshot.json',snapshot);write(folder/'validation.json',validation)
    del db,p,result;gc.collect();return validation

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--source',type=Path,required=True);cli.add_argument('--stage',type=Path,required=True);cli.add_argument('--kind',choices=['iot-current','iot-pyp','sut']);cli.add_argument('--inventory-only',action='store_true');cli.add_argument('--limit',type=int)
    args=cli.parse_args();jobs=inventory(args.source)
    if args.inventory_only:write(args.stage/'inventory.json',jobs);print('WIOD inventory:',len(jobs),'multiregional inputs');sys.exit(0)
    seed=next(r for r in json.loads((ROOT/'doc/economy_browser.recipes.json').read_text())['recipes'] if r['source']=='WIOD')
    notebooks={r['id']:r for r in json.loads((ROOT/'doc/database_catalogue.recipes.json').read_text())['recipes'] if r['guide']=='wiod'}
    sea=args.source/'Socio_Economic_Accounts.xlsx';SEA_HASH=checksum(sea)
    original_sea=wiod._load_wiod_socioeconomic_accounts
    cached_sea=functools.lru_cache(maxsize=1)(original_sea)
    def load_sea(*a,**kw):
        data,meta=cached_sea(*a,**kw);return data.copy(deep=False),copy.deepcopy(meta)
    selected=[j for j in jobs if args.kind is None or j['kind']==args.kind]
    if args.limit:selected=selected[:args.limit]
    with patch.object(wiod,'_load_wiod_socioeconomic_accounts',load_sea):
        for job in selected:
            if (args.stage/'readings'/job['id']/'validation.json').is_file():print('RESUME',job['id'],flush=True);continue
            print('START',job['id'],flush=True)
            try:print(json.dumps(collect(job,args.stage,sea,seed,notebooks)),flush=True)
            except Exception as exc:write(args.stage/'errors'/f"{job['id']}.json",{'id':job['id'],'type':type(exc).__name__,'error':str(exc)});raise
