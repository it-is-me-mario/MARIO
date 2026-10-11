"""Read every official 3.8.2 SUT's native metadata and income components.

For emissions and the final-use tax bridge use only its exact, verified,
same-release/year IOT counterpart, as in MARIO's add_extensions option.
"""
from pathlib import Path
import argparse,copy,gzip,hashlib,io,json,sys,time,zipfile,datetime
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np
import pandas as pd
from collect import ROOT,STAGE,NOTEBOOK,enrich_profile,write,axis_records,scalar
from remote_zip import RemoteArchive,archive_url
from mario.parsers.exiobase_sut import _activity_axis,_commodity_axis,_final_demand_axis

def jobs():
 d=json.loads((STAGE/'zenodo-5589597.json').read_text())
 return [{**f,'id':f'exiobase-382-{f["key"][6:10]}-sut','year':int(f['key'][6:10]),'record':str(d['id'])} for f in d['files'] if f['key'].startswith('MRSUT_') and f['key'].endswith('.zip')]

def read(job):
 start=time.time();folder=STAGE/'readings'/job['id'];paired=STAGE/'readings'/f'exiobase-382-{job["year"]}-ixi'
 if (folder/'snapshot.json').exists():
  cached=json.loads((folder/'snapshot.json').read_text())
  if cached['provenance'].get('archive_checksum')==job['checksum']:return job['id'],'cached',0
 if not (paired/'snapshot.json').exists():return job['id'],'waiting for matching IOT',0
 iot=json.loads((paired/'snapshot.json').read_text());ip=json.loads(gzip.decompress((paired/'profile.json.gz').read_bytes()))
 remote=RemoteArchive(archive_url(job['record'],job['key']),job['size']);hashes={}
 with zipfile.ZipFile(remote) as archive:
  prefix=f'MRSUT_{job["year"]}/'
  def member(name):return archive.getinfo(prefix+name)
  info=member('meta.json');remote.prefetch(info);raw=archive.read(info);metadata=json.loads(raw)
  if metadata['year']!=job['year'] or metadata['currency']!='Euro':raise ValueError('Unexpected SUT year/currency')
  hashes['meta.json']=hashlib.sha256(raw).hexdigest()
  info=member('value_added.csv');remote.prefetch(info);raw=archive.read(info);hashes['value_added.csv']=hashlib.sha256(raw).hexdigest()
  va=pd.read_csv(io.BytesIO(raw),sep='\t',index_col=0,header=[0,1]);activity_axis=_activity_axis(va.columns);activity_axis.names=['Region','Level','Item']
  info=member('supply.csv');remote.prefetch(info)
  with archive.open(info) as stream:
   # Read original commodity coordinates while streaming over values; CRC is
   # checked after decompression reaches the end of this original member.
   labels=pd.read_csv(stream,sep='\t',usecols=[0,1],skiprows=2,header=0)
  native_commodities=pd.MultiIndex.from_frame(labels.iloc[:,:2]);commodity_axis=_commodity_axis(native_commodities);commodity_axis.names=activity_axis.names
  if not commodity_axis.is_unique:raise ValueError('Duplicated native commodity coordinates')
  info=member('final_demand.csv');remote.prefetch(info)
  with archive.open(info) as stream:
   header=pd.read_csv(stream,sep='\t',header=[0,1],index_col=[0,1],nrows=0)
  fd_axis=_final_demand_axis(header.columns);fd_axis.names=activity_axis.names
  hashes['supply.csv']={'crc32':f'{member("supply.csv").CRC:08x}','uncompressed_size':member('supply.csv').file_size,'scope':'Native coordinates streamed from original member; CRC verified.'}
  hashes['final_demand.csv']={'crc32':f'{info.CRC:08x}','scope':'Only original column headers read; full member CRC not independently checked.'}
  r=copy.deepcopy(iot['recipe']);sectors=list(dict.fromkeys(activity_axis.get_level_values('Item')))
  regions=sorted(set(activity_axis.get_level_values('Region')))
  if regions!=sorted(x['code'] for x in iot['regions']) or set(sectors)!=set(iot['recipe']['sectors']):raise ValueError('SUT/IOT region or activity mismatch')
  if set(fd_axis.get_level_values('Item'))!=set(iot['recipe']['consumption_categories']):raise ValueError('SUT/IOT final-demand categories mismatch')
  rows=[];taxrow=va.loc[r['product_tax_rows']].sum();income=va.loc[r['value_added_rows']].sum()
  for original in iot['regions']:
   region=original['code'];observed=income.xs(region);expected=dict(zip(iot['recipe']['sectors'],original['value_added']))
   # The monetary SUT reports EUR, while IOT source files report million EUR.
   if not np.allclose(observed.values,[expected[label] for label in observed.index],rtol=1e-9,atol=1):raise ValueError('SUT income differs from matching IOT')
   result=copy.deepcopy(original);result['value_added']=[float(observed[s]) for s in sectors]
   ghg=dict(zip(iot['recipe']['sectors'],original['ghg']));result['ghg']=[ghg[s] for s in sectors]
   result['gdp']=sum(result['value_added'])+result['net_product_taxes'];rows.append(result)
  now=datetime.datetime.now(datetime.timezone.utc).isoformat();source='https://zenodo.org/records/5589597'
  options={'table':'SUT','unit':'Monetary','add_extensions':'/path/to/corresponding-IOT'}
  r.update(id=job['id'],label='EXIOBASE 3.8.2 · monetary SUT',table='SUT',dimension='Activity',parser_options=options,currency_scale=1,value_added_block='Va',emissions_block='Ea',sectors=sectors,tax_bridge='exiobase_matching_iot',gdp_note='Source SUT value added, in EUR, matches the same-release/year IOT activity by activity. Its verified final-use product-tax bridge and satellite accounts are supplied by that exact matching IOT.',expected_units={'Factor of production':{label:'EUR' for label in va.index},'Satellite account':iot['recipe']['expected_units']['Satellite account']})
  provenance={**iot['provenance'],'source_url':source,'archive_url':remote.url,'archive_checksum':job['checksum'],'selected_members':hashes,'matched_iot':{'id':iot['recipe']['id'],'source_provenance':iot['provenance'],'validation':'Every region/activity income value and all native final-demand labels match.'},'options':options,'reading_scope':'Original SUT income components, activity/commodity/final-demand axes; matching IOT satellite accounts. Supply/use numeric transactions are not loaded.','source_metadata':metadata}
  sets={'Region':regions,'Activity':sectors,'Commodity':list(dict.fromkeys(commodity_axis.get_level_values('Item'))),'Consumption category':list(dict.fromkeys(fd_axis.get_level_values('Item'))),'Factor of production':list(va.index),'Satellite account':ip['sets']['Satellite account']}
  axes=[]
  for matrix,side,axis in [('Va','index',va.index),('Va','columns',activity_axis),('S','index',activity_axis),('S','columns',commodity_axis),('Yc','index',commodity_axis),('Yc','columns',fd_axis)]:
   names,coords=axis_records(axis);axes.append({'matrix':matrix,'side':side,'names':names,'records':[[scalar(v) for v in row] for row in coords]})
  memberships=[{'set':name,'region':coord[0],'label':coord[2]} for name,axis in [('Activity',activity_axis),('Commodity',commodity_axis),('Consumption category',fd_axis)] for coord in axis]
  units=[{'set':name,'index_names':[None],'index':[label],'values':{'unit':'EUR'}} for name in ['Activity','Commodity','Factor of production'] for label in sets[name]]+[u for u in ip['units'] if u['set']=='Satellite account']
  profile={'schema_version':1,'id':job['id'],'guide':'exiobase-monetary','label':f'EXIOBASE 3.8.2 · {job["year"]} · monetary SUT','source':'EXIOBASE','release':'3.8.2','year':job['year'],'table':'SUT','status':'parsed','scenario':'baseline','parsed_at':now,'provenance':provenance,'sets':sets,'counts':{k:len(v) for k,v in sets.items()},'axes':axes,'units':units,'region_items':memberships,'region_counts':[{'region':region,'set':name,'count':sum(x['region']==region and x['set']==name for x in memberships)} for region in regions for name in ['Activity','Commodity','Consumption category']],'classifications':{'status':'native_labels','mappings':[]}}
  enrich_profile(profile);r['regions']=profile['geography']['regions']
  write(folder/'profile.json.gz',profile);write(folder/'snapshot.json',{'schema_version':1,'recipe':r,'regions':rows,'generated_at':now,'provenance':provenance});write(folder/'validation.json',{'matching_income_cells':len(income),'native_currency_unit':'EUR','counts':profile['counts'],'seconds':time.time()-start})
 return job['id'],'ok',round(time.time()-start,1)

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--workers',type=int,default=1);cli.add_argument('--year',type=int);cli.add_argument('--watch',action='store_true');args=cli.parse_args();todo=jobs()
 if args.year:todo=[j for j in todo if j['year']==args.year]
 while True:
  waiting=[]
  for j in todo:
   snapshot=STAGE/'readings'/j['id']/'snapshot.json'
   if not snapshot.exists() or json.loads(snapshot.read_text())['provenance'].get('archive_checksum')!=j['checksum']:waiting.append(j)
  if not waiting:print('Completed all',len(todo),'official SUT readings.',flush=True);break
  ready=[j for j in waiting if (STAGE/'readings'/f'exiobase-382-{j["year"]}-ixi'/'snapshot.json').exists()]
  if ready:
   with ThreadPoolExecutor(max_workers=args.workers) as pool:
    for result in pool.map(read,ready):print(result,flush=True)
  if not args.watch:break
  if not ready:time.sleep(20)
