from pathlib import Path
import argparse,copy,hashlib,json,sys,numpy as np,pandas as pd
import requests
from collect import ROOT,STAGE,write
import mario
from database_catalogue import extract_profile
from economy_browser import aggregate,final_demand_taxes
cli=argparse.ArgumentParser(description='Verify official Hybrid HIOT with the full MARIO parser.')
cli.add_argument('--path',required=True,type=Path);args=cli.parse_args();source=args.path
response=requests.get('https://zenodo.org/api/records/7244919',timeout=90)
response.raise_for_status();record=response.json();verified={}
for item in record['files']:
 file=source/item['key']
 if not file.is_file():raise ValueError('Missing official Hybrid file: '+item['key'])
 raw=file.read_bytes()
 if 'md5:'+hashlib.md5(raw).hexdigest()!=item['checksum']:raise ValueError('Hybrid source checksum mismatch')
 verified[item['key']]={'published_checksum':item['checksum'],'sha256':hashlib.sha256(raw).hexdigest()}
write(STAGE/'hybrid-record.json',record)
db=mario.parse_exiobase(table='IOT',unit='Hybrid',path=str(source),extensions='all',calc_all=False)
metadata=pd.read_excel(source/'Classifications_v_3_3_18.xlsx',sheet_name='Value_added')
native=pd.read_excel(source/'MR_HIOT_2011_v3_3_18_extensions.xlsx',sheet_name='VA_act',index_col=0,header=[0,1,2,3]).fillna(0)
from mario.parsers.exiobase_hybrid import _drop_unnamed_columns
native=_drop_unnamed_columns(native)
codes=list(metadata.loc[metadata['Unit'].str.lower()=='meuro','Code 1'])
native_total=native.loc[codes].sum().sum();parsed_total=db.get_block('V').sum().sum()
if not np.isclose(native_total,parsed_total,rtol=1e-9):raise ValueError(f'Hybrid income not conserved: {native_total} vs {parsed_total}')
notebook=next(r for r in json.loads((ROOT/'doc/database_catalogue.recipes.json').read_text())['recipes'] if r['guide']=='exiobase-hybrid')
job={'id':'exiobase-hybrid-3318-2011-iot','label':'EXIOBASE Hybrid 3.3.18 · 2011 · IOT','source':'EXIOBASE','release':'3.3.18','year':2011}
profile=extract_profile(db,job=job,recipe=notebook,parameters={'table':'IOT','unit':'Hybrid','extensions':'all','calc_all':False})
base=json.loads((ROOT/'doc/source/_static/data/economy/exiobase-hybrid-3318-2011-sut.json').read_text())['recipe']
r=copy.deepcopy(base);r.update(id=job['id'],label='EXIOBASE 3.3.18 · hybrid IOT',table='IOT',dimension='Product / activity',value_added_block='V',parser_options={'table':'IOT','unit':'Hybrid','extensions':'all'},sectors=profile['sets']['Sector'],regions=profile['geography']['regions'],consumption_categories=profile['sets']['Consumption category'])
r.pop('emissions_block',None)  # HIOT emissions are in E; the HSUT recipe uses Ea
r['expected_units']={}
for u in profile['units']:r['expected_units'].setdefault(u['set'],{})[u['index'][0]]=u['values']['unit']
rows=aggregate(db,r,final_demand_taxes(source,r))
profile['provenance'].update(mario_version=mario.__version__,source_url=r['source_url'],reading_scope='Full MARIO HIOT parsing, all supported extensions; original monetary VA total checked for conservation.',source_files=verified)
folder=STAGE/'readings'/job['id'];write(folder/'profile.json.gz',profile);write(folder/'snapshot.json',{'schema_version':1,'recipe':r,'regions':rows,'generated_at':profile['parsed_at'],'provenance':profile['provenance']});write(folder/'validation.json',{'counts':profile['counts'],'native_va_million_eur':float(native_total),'parsed_va_million_eur':float(parsed_total)})
print('PASS full official Hybrid HIOT:',profile['counts'],'income conserved.',flush=True)
