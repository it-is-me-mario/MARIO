"""Parse and independently validate the locally supplied FIGARO IOT series."""
from pathlib import Path
import argparse,copy,gc,gzip,hashlib,json,logging,re,sys,time
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'doc/scripts'),str(ROOT/'doc/source/_static/reproduce')]
import mario
from mario.parsers import figaro
from database_catalogue import extract_profile
from economy_browser import aggregate
logging.getLogger('mario').setLevel(logging.ERROR)
def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);raw=json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
 if path.suffix=='.gz':raw=gzip.compress(raw)
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_bytes(raw);temp.replace(path)
def checksum(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for chunk in iter(lambda:stream.read(4*1024**2),b''):h.update(chunk)
 return h.hexdigest()
def inventory(source):
 jobs=[]
 for f in sorted((source/'IOT').glob('*/*.csv')):
  m=re.fullmatch(r'(naio_10_fcp_(ip|ii)[1-4])_(\d{4})_MIO_EUR_[a-f0-9]{12}\.csv',f.name)
  if not m:raise ValueError('Unreviewed input filename: '+f.name)
  year=int(m[3]);sidecar=json.loads(f.with_suffix('.json').read_text())
  if sidecar['year']!=year or sidecar['dataflow']!=m[1] or sidecar['unit']!='MIO_EUR' or sidecar['countries'] is not None or not sidecar['include_dom']:raise ValueError('Unexpected cache selection')
  mode='product' if m[2]=='ip' else 'industry';layout=figaro.detect_figaro_iot_layout(year,mode=mode)
  factors=figaro._label_map(figaro.load_figaro_metadata(),level='f')[0]
  cache=figaro._figaro_cache_file(f.parent,dataflow=layout.dataflow,year=year,unit='MIO_EUR',row_dim='prd_ava' if mode=='product' else 'ind_ava',col_dim='prd_use' if mode=='product' else 'ind_use',countries=None,include_dom=True,factor_codes=factors)
  if cache!=f:raise ValueError('Local file does not match public parser cache key')
  jobs.append({'id':f'figaro-{year}-'+('pxp' if mode=='product' else 'ixi'),'year':year,'mode':mode,'path':str(f),'filename':f.name,'dataflow':m[1]})
 if sorted(j['year'] for j in jobs if j['mode']=='product')!=list(range(2010,2024)):raise ValueError('Expected local 2010–2023 product series')
 return jobs
def collect(job,stage,seed,notebook):
 start=time.time();file=Path(job['path']);folder=stage/'readings'/job['id'];observed={};original=figaro._download_figaro_api_frame
 meta=figaro.load_figaro_metadata();factor_codes,factor_labels=figaro._label_map(meta,level='f');fd_codes,fd_labels=figaro._label_map(meta,level='n')
 _,labels=figaro._label_map(meta,level='c' if job['mode']=='product' else 'a')
 def observe(*a,**kw):
  frame=original(*a,**kw);part=frame.loc[frame.refArea.eq('W2')].copy()
  if part.duplicated(['rowCode','counterpartArea','colCode']).any() or not np.isfinite(part.obsValue).all():raise ValueError('Duplicate or missing factor observations')
  observed.update(factors=part,rows=len(frame),sector_codes=set(frame.loc[~frame.refArea.eq('W2')].rowCode))
  return frame
 def no_network(*a,**kw):raise RuntimeError('This inventory uses only supplied local API caches')
 opts={'table':'IOT','year':job['year'],'iot_mode':job['mode']}
 with patch.object(figaro,'_download_figaro_api_frame',observe),patch.object(figaro,'_request_figaro_json',no_network):
  db=mario.parse_figaro(path=str(file.parent),calc_all=False,**opts)
 p=extract_profile(db,job={'id':job['id'],'source':'FIGARO','release':'','year':job['year'],'label':f'FIGARO · '+('pxp' if job['mode']=='product' else 'ixi')},recipe=notebook,parameters={'path':str(file.parent),'calc_all':False,**opts})
 if p['counts']['Region']!=50 or p['counts']['Sector']!=64 or p['counts']['Factor of production']!=6 or p['counts']['Consumption category']!=5:raise ValueError('Unexpected native coverage')
 part=observed['factors'];region_by_code={code:figaro._resolve_figaro_region_label(code,{}) for code in part.counterpartArea.unique()}
 if set(region_by_code.values())!=set(p['sets']['Region']):raise ValueError('Raw and parsed country axes differ')
 sectors=p['sets']['Sector'];code_by_label={labels[c]:c for c in observed['sector_codes']}
 if set(code_by_label)!=set(sectors):raise ValueError('Unmatched native classification')
 p['native_codes']={'Sector':code_by_label,'Factor of production':{label:code for code,label in factor_labels.items()},'Consumption category':{label:code for code,label in fd_labels.items()}};p['environmental']=False
 p['classifications']={'Sector':'CPA 2.1 · A*64' if job['mode']=='product' else 'NACE Rev.2 · A*64'}
 raw_va=part.loc[part.rowCode.isin(['D1','D29X39','B2A3G'])&~part.colCode.isin(fd_codes)].groupby('counterpartArea').obsValue.sum()
 tax=part.loc[part.rowCode.eq('D21X31')];raw_tax=tax.groupby('counterpartArea').obsValue.sum()
 final=tax.loc[tax.colCode.isin(fd_codes)].groupby('counterpartArea').obsValue.sum()
 # Completeness is checked per country, factor and use, including explicit zeros.
 native_codes=set(observed['sector_codes'])
 for code in region_by_code:
  for factor in ['D1','D29X39','B2A3G','D21X31']:
   cells=part.loc[part.counterpartArea.eq(code)&part.rowCode.eq(factor)]
   if set(cells.colCode)!=native_codes|set(fd_codes):raise ValueError('Incomplete raw factor/use grid')
 tax_fd={region_by_code[c]:float(v) for c,v in final.items()}
 r=copy.deepcopy(seed)
 r.update(id=job['id'],label=f'FIGARO · '+('product × product' if job['mode']=='product' else 'industry × industry'),release='',year=job['year'],parser_options=opts,sectors=sectors,regions=p['geography']['regions'],value_added_rows=['Compensation of employees','Other net taxes on production','Gross operating surplus'],product_tax_rows=['Taxes less subsidies on products'],tax_bridge='figaro_csv',gdp_bridge_verified=True,gdp_basis='Value added at basic prices plus net product taxes on intermediate and final uses',gdp_note='D1 + D29X39 + B2A3G plus D21X31 on intermediate and final uses. Country totals independently reconciled to source rows; residence-purchase adjustments are excluded from the income calculation.',currency='EUR',currency_scale=1e6,dimension='Product' if job['mode']=='product' else 'Industry',table='IOT',ghg_factors={},ghg_method='No environmental accounts are supplied with this local FIGARO IOT reading.',world_total_available=True,price_basis='Current prices',attribution=f'Source: Eurostat, FIGARO, {job["dataflow"]}, {job["year"]}. Calculations by MARIO; Eurostat is not responsible for the derived results.')
 r['expected_units']={name:{str(label):str(unit) for label,unit in frame['unit'].items()} for name,frame in db.units.items() if name in ['Sector','Factor of production']}
 regions=aggregate(db,r,tax_fd);max_error=0
 for region in regions:
  code=next(code for code,label in region_by_code.items() if label==region['code'])
  expected=[float(raw_va[code])*1e6,float(raw_tax[code])*1e6,float(raw_va[code]+raw_tax[code])*1e6]
  for actual,want in zip([sum(region['value_added']),region['net_product_taxes'],region['gdp']],expected):
   if not np.isclose(actual,want,rtol=1e-12,atol=.1):raise ValueError('Raw/parsed GDP differs: '+code)
   max_error=max(max_error,abs(actual-want))
 prov=p['provenance'];prov.update(input_filename=file.name,input_sha256=checksum(file),input_bytes=file.stat().st_size,source_url=r['source_url'],mario_version=mario.__version__,dataflow=job['dataflow'],cache_metadata_sha256=checksum(file.with_suffix('.json')),reading_scope='Full MARIO IOT parse using the supplied cache only; independently reconciled VA and D21X31 by country, calc_all=False.',classification_url='https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_fcp_esms.htm',api_rows=observed['rows'])
 result={'schema_version':1,'recipe':r,'regions':regions,'generated_at':p['parsed_at'],'provenance':prov}
 validation={'id':job['id'],'counts':p['counts'],'max_raw_parsed_error_eur':max_error,'source_rows':observed['rows'],'seconds':round(time.time()-start,2),'world_gdp_eur':sum(x['gdp'] for x in regions)}
 write(folder/'profile.json.gz',p);write(folder/'snapshot.json',result);write(folder/'validation.json',validation)
 del db,regions,part,observed;gc.collect();return validation
if __name__=='__main__':
 cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--source',type=Path,required=True);cli.add_argument('--stage',type=Path,required=True);cli.add_argument('--limit',type=int);args=cli.parse_args()
 jobs=inventory(args.source);write(args.stage/'inventory.json',jobs)
 seed=next(r for r in json.loads((ROOT/'doc/economy_browser.recipes.json').read_text())['recipes'] if r['source']=='FIGARO' and r.get('table')=='IOT')
 notebook=next(r for r in json.loads((ROOT/'doc/database_catalogue.recipes.json').read_text())['recipes'] if r['id']=='figaro--02')
 for job in jobs[:args.limit]:
  folder=args.stage/'readings'/job['id']
  if (folder/'validation.json').exists():print('RESUME',job['id'],flush=True);continue
  print('START',job['id'],flush=True)
  try:print(json.dumps(collect(job,args.stage,seed,notebook)),flush=True)
  except Exception as error:write(args.stage/'errors'/f"{job['id']}.json",{'error':str(error),'type':type(error).__name__});raise
