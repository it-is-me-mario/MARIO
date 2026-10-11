"""Download, parse and validate all current Eurostat FIGARO IOT/SUT years."""
from pathlib import Path
import argparse,concurrent.futures,copy,gc,importlib.util,json,os,shutil,sys,time
from unittest.mock import patch
import numpy as np
import pandas as pd
import requests

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'doc/scripts'),str(ROOT/'doc/source/_static/reproduce')]
import mario
from mario.parsers import figaro
from database_catalogue import extract_profile
from economy_browser import aggregate
spec=importlib.util.spec_from_file_location('figaro_local_collect',ROOT/'doc/scripts/figaro/collect.py')
local=importlib.util.module_from_spec(spec);spec.loader.exec_module(local)
write,checksum=local.write,local.checksum

def request(dataflow,params):
    for attempt in range(6):
        try:
            response=requests.get(figaro.FIGARO_API_BASE_URL.rstrip('/')+'/'+dataflow,params=params,timeout=(30,240))
            response.raise_for_status();payload=response.json()
            if 'error' in payload or 'dimension' not in payload:raise ValueError('Unexpected API payload: '+str(payload)[:200])
            return payload
        except (requests.RequestException,ValueError):
            if attempt==5:raise
            time.sleep(min(45,2**attempt))

def download(dataflow,year,cache,stage,*,row_dim,col_dim,include_dom=False,factor_codes=None):
    opts=dict(dataflow=dataflow,year=year,unit='MIO_EUR',row_dim=row_dim,col_dim=col_dim,countries=None,include_dom=include_dom,factor_codes=factor_codes)
    target=figaro._figaro_cache_file(cache,**opts)
    if target.exists():return target
    dimensions=request(dataflow,{'time':'9999','unit':'MIO_EUR'})
    cats={dim:figaro._jsonstat_category_codes(dimensions,dim) for dim in dimensions['id']}
    updated=dimensions.get('updated')
    pieces=stage/'chunks'/f'{dataflow}-{year}';pieces.mkdir(parents=True,exist_ok=True)
    def fetch(origin):
        chunk=pieces/(origin+'.csv')
        if chunk.exists():return chunk
        params={'time':year,'unit':'MIO_EUR'}
        if origin!='all':params['c_orig']=origin
        payload=request(dataflow,params)
        if payload.get('updated')!=updated:raise ValueError('API changed during download')
        frame=figaro._jsonstat_to_frame(payload)
        if frame.empty:raise ValueError(f'Empty requested FIGARO dataflow {dataflow} {year} {origin}')
        if 'geo' in frame:
            frame['c_orig']=frame.geo;frame['c_dest']=frame.geo
        ref=frame.c_orig.astype(str).map(figaro._from_api_region_code)
        if factor_codes:
            mask=frame[row_dim].astype(str).map(figaro._normalize_figaro_code).isin(factor_codes)
            ref=ref.mask(mask&frame.c_orig.eq('DOM'),'W2')
        values=pd.to_numeric(frame.obsValue,errors='raise')
        if not np.isfinite(values).all():raise ValueError('Nonfinite API observation')
        normalized=pd.DataFrame({'refArea':ref,'rowCode':frame[row_dim].astype(str).map(figaro._normalize_figaro_code),
            'counterpartArea':frame.c_dest.astype(str).map(figaro._from_api_region_code),'colCode':frame[col_dim].astype(str).map(figaro._normalize_figaro_code),'obsValue':values})
        if normalized.duplicated(['refArea','rowCode','counterpartArea','colCode']).any():raise ValueError('Duplicate API observation')
        temporary=chunk.with_suffix('.tmp');normalized.to_csv(temporary,index=False);temporary.replace(chunk)
        return chunk
    origins=['all'] if 'geo' in cats else [c for c in cats['c_orig'] if c!='DOM' or include_dom]
    if 'geo' not in cats and len(cats['c_dest'])!=50:raise ValueError('Unexpected destination geography')
    started=time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(fetch,origin):origin for origin in origins}
        for index,future in enumerate(concurrent.futures.as_completed(futures),1):
            future.result()
            if index%10==0 or index==len(origins):print('DOWNLOAD',dataflow,year,f'{index}/{len(origins)}',round(time.time()-started,1),flush=True)
    target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_suffix('.tmp')
    with temporary.open('wb') as output:
        for index,origin in enumerate(origins):
            with (pieces/(origin+'.csv')).open('rb') as stream:
                if index:stream.readline()
                shutil.copyfileobj(stream,output)
    temporary.replace(target)
    figaro._write_figaro_cache_metadata(target,**{k:v for k,v in opts.items() if k not in ['dataflow','factor_codes']},dataflow=dataflow,api_updated=updated,retrieved_at='2026-10-10',api_layout='domestic geo' if 'geo' in cats else 'origin/destination')
    shutil.rmtree(pieces)
    return target

def collect_sut(job,stage,seed,notebook):
    start=time.time();cache=Path(job['cache']);folder=stage/'readings'/job['id'];observed={};original=figaro._download_figaro_api_frame
    meta=figaro.load_figaro_metadata();factor_codes,factor_labels=figaro._label_map(meta,level='f');fd_codes,fd_labels=figaro._label_map(meta,level='n')
    _,activities=figaro._label_map(meta,level='a');_,commodities=figaro._label_map(meta,level='c')
    def observe(dataflow,**kw):
        frame=original(dataflow,**kw)
        if frame.duplicated(['refArea','rowCode','counterpartArea','colCode']).any() or not np.isfinite(frame.obsValue).all():raise ValueError('Duplicate or nonfinite SUT source observations')
        observed[dataflow]={'rows':len(frame),'row_codes':set(frame.loc[~frame.refArea.eq('W2')].rowCode),'col_codes':set(frame.loc[~frame.colCode.isin(fd_codes)].colCode)}
        if '_u' in dataflow:observed['factors']=frame.loc[frame.refArea.eq('W2')].copy()
        return frame
    def no_network(*a,**kw):raise RuntimeError('MARIO parses the fully downloaded caches without further requests')
    opts={'table':'SUT','year':job['year']}
    with patch.object(figaro,'_download_figaro_api_frame',observe),patch.object(figaro,'_request_figaro_json',no_network):
        db=mario.parse_figaro(path=str(cache),calc_all=False,**opts)
    p=extract_profile(db,job={'id':job['id'],'source':'FIGARO','release':'','year':job['year'],'label':'FIGARO · SUT'},recipe=notebook,parameters={'path':str(cache),'calc_all':False,**opts})
    if any(p['counts'].get(name)!=n for name,n in [('Region',50),('Activity',64),('Commodity',64),('Factor of production',6),('Consumption category',5)]):raise ValueError('Unexpected native SUT coverage')
    use=figaro.detect_figaro_sut_layout(job['year']).use_dataflow
    native={activities[c]:c for c in observed[use]['col_codes']}
    supply=figaro.detect_figaro_sut_layout(job['year']).supply_dataflow
    products={commodities[c]:c for c in observed[supply]['row_codes']}
    if set(native)!=set(p['sets']['Activity']) or set(products)!=set(p['sets']['Commodity']):raise ValueError('Unmatched native SUT codes')
    p['native_codes']={'Activity':native,'Commodity':products,'Factor of production':{label:code for code,label in factor_labels.items()},'Consumption category':{label:code for code,label in fd_labels.items()}};p['environmental']=False
    p['classifications']={'Activity':'NACE Rev.2 · A*64','Commodity':'CPA 2.1 · A*64'}
    part=observed['factors'];region_by_code={code:figaro._resolve_figaro_region_label(code,{}) for code in part.counterpartArea.unique()}
    if set(region_by_code.values())!=set(p['sets']['Region']):raise ValueError('Raw and parsed regions differ')
    for country in region_by_code:
        for factor in ['D1','D29X39','B2A3G','D21X31']:
            cells=part.loc[part.counterpartArea.eq(country)&part.rowCode.eq(factor)]
            if set(cells.colCode)!=set(native.values())|set(fd_codes):raise ValueError('Incomplete SUT factor grid')
    raw_va=part.loc[part.rowCode.isin(['D1','D29X39','B2A3G'])&~part.colCode.isin(fd_codes)].groupby('counterpartArea').obsValue.sum()
    tax=part.loc[part.rowCode.eq('D21X31')];raw_tax=tax.groupby('counterpartArea').obsValue.sum()
    final=tax.loc[tax.colCode.isin(fd_codes)].groupby('counterpartArea').obsValue.sum()
    r=copy.deepcopy(seed);r.update(id=job['id'],label='FIGARO · supply-use',release='',year=job['year'],parser_options=opts,sectors=p['sets']['Activity'],regions=p['geography']['regions'],dimension='Activity',table='SUT',value_added_block='Va',tax_bridge='figaro_csv',gdp_bridge_verified=True,
        value_added_rows=['Compensation of employees','Other net taxes on production','Gross operating surplus'],product_tax_rows=['Taxes less subsidies on products'],ghg_factors={},currency='EUR',currency_scale=1e6,price_basis='Current prices',world_total_available=True,
        ghg_method='No environmental accounts are supplied with this FIGARO SUT reading.',gdp_basis='Value added at basic prices plus net product taxes on intermediate and final uses',gdp_note='SUT: D1 + D29X39 + B2A3G in Va plus D21X31 on intermediate and final uses. Independently reconciled to source country totals. FIGARO compilation uses national accounts and World Bank world GDP; this is not an independent accuracy test.',attribution=f'Source: Eurostat FIGARO, {job["year"]}. Calculations by MARIO; Eurostat is not responsible for derived results.')
    r['expected_units']={name:{str(label):str(unit) for label,unit in frame['unit'].items()} for name,frame in db.units.items() if name in ['Activity','Commodity','Factor of production']}
    regions=aggregate(db,r,{region_by_code[c]:float(v) for c,v in final.items()});max_error=0
    for region in regions:
        code=next(c for c,label in region_by_code.items() if label==region['code'])
        for actual,want in zip([sum(region['value_added']),region['net_product_taxes'],region['gdp']],[float(raw_va[code])*1e6,float(raw_tax[code])*1e6,float(raw_va[code]+raw_tax[code])*1e6]):
            if not np.isclose(actual,want,rtol=1e-12,atol=.1):raise ValueError('Raw/parsed SUT GDP differs: '+code)
            max_error=max(max_error,abs(actual-want))
    sources=[{'filename':Path(file).name,'sha256':checksum(Path(file)),'bytes':Path(file).stat().st_size,'dataflow':json.loads(Path(file).with_suffix('.json').read_text())['dataflow'],'api_updated':json.loads(Path(file).with_suffix('.json').read_text())['api_updated']} for file in job['files']]
    prov=p['provenance'];prov.update(input_filename=' + '.join(x['filename'] for x in sources),input_sha256=' + '.join(x['sha256'] for x in sources),input_bytes=sum(x['bytes'] for x in sources),source_files=sources,source_url=r['source_url'],mario_version=mario.__version__,dataflow=' + '.join(x['dataflow'] for x in sources),reading_scope='Full MARIO SUT parse, calc_all=False; original factor/use grids independently reconcile country VA, taxes and GDP.',eurostat_unit='MIO_EUR',classification_url='https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_fcp_esms.htm',api_rows=sum(v['rows'] for k,v in observed.items() if k!='factors'))
    validation={'id':job['id'],'counts':p['counts'],'max_raw_parsed_error_eur':max_error,'seconds':round(time.time()-start,2),'world_gdp_eur':sum(x['gdp'] for x in regions)}
    write(folder/'profile.json.gz',p);write(folder/'snapshot.json',{'schema_version':1,'recipe':r,'regions':regions,'generated_at':p['parsed_at'],'provenance':prov});write(folder/'validation.json',validation)
    del db,regions,part,observed;gc.collect();return validation

def run(stage,source):
    inventory=json.loads((stage/'api-inventory.json').read_text())
    availability={p['dataflow']:set(map(int,p['years'])) for p in inventory}
    expected=[]
    for year in range(2024,2009,-1):
        for kind in ['pxp','ixi','sut']:
            flows=([figaro.detect_figaro_sut_layout(year).supply_dataflow,figaro.detect_figaro_sut_layout(year).use_dataflow] if kind=='sut' else [figaro.detect_figaro_iot_layout(year,mode='product' if kind=='pxp' else 'industry').dataflow])
            if not all(year in availability.get(f,set()) for f in flows):raise ValueError('Missing official year/table selection')
            expected.append({'id':f'figaro-{year}-{kind}','year':year,'kind':kind,'dataflows':flows,'cache':str(source/str(year))})
    write(stage/'inventory.json',expected)
    seed=next(r for r in json.loads((ROOT/'doc/economy_browser.recipes.json').read_text())['recipes'] if r['source']=='FIGARO' and r.get('table')=='IOT')
    notebooks=json.loads((ROOT/'doc/database_catalogue.recipes.json').read_text())['recipes']
    factors,_=figaro._label_map(figaro.load_figaro_metadata(),level='f')
    for job in expected:
        folder=stage/'readings'/job['id']
        if (folder/'validation.json').exists():print('RESUME',job['id'],flush=True);continue
        try:
            print('START',job['id'],flush=True);cache=Path(job['cache']);files=[]
            if job['kind']=='sut':
                files.append(download(job['dataflows'][0],job['year'],cache,stage,row_dim='cpa2_1',col_dim='nace_r2'))
                files.append(download(job['dataflows'][1],job['year'],cache,stage,row_dim='prd_ava',col_dim='ind_use',include_dom=True,factor_codes=factors))
                job['files']=list(map(str,files));notebook=next(r for r in notebooks if r['id']=='figaro--01')
                result=collect_sut(job,stage,seed,notebook)
            else:
                mode='product' if job['kind']=='pxp' else 'industry'
                file=download(job['dataflows'][0],job['year'],cache,stage,row_dim='prd_ava' if mode=='product' else 'ind_ava',col_dim='prd_use' if mode=='product' else 'ind_use',include_dom=True,factor_codes=factors)
                job.update(path=str(file),filename=file.name,mode=mode,dataflow=job['dataflows'][0]);notebook=next(r for r in notebooks if r['id']=='figaro--02')
                result=local.collect(job,stage,seed,notebook)
                s=json.loads((folder/'snapshot.json').read_text());s['provenance'].update(api_updated=json.loads(file.with_suffix('.json').read_text())['api_updated'],retrieved_at='2026-10-10');write(folder/'snapshot.json',s)
            print('VERIFIED',json.dumps(result),flush=True)
            if job['kind']=='sut':
                write(stage/'online-only-pending'/f'{job["year"]}.json',{'year':job['year'],'folder':str(cache)})
                print('YEAR_COMPLETE',job['year'],str(cache),flush=True)
        except Exception as error:
            write(stage/'errors'/f'{job["id"]}.json',{'error':str(error),'type':type(error).__name__});raise
    write(stage/'complete.json',{'readings':len(expected),'years':list(range(2010,2025)),'kinds':['pxp','ixi','SUT']})
    print('COMPLETE',len(expected),flush=True)

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--stage',type=Path,required=True);cli.add_argument('--source',type=Path,required=True);args=cli.parse_args();run(args.stage,args.source)
