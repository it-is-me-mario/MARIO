"""Collect all supported official EXIOBASE indicator blocks and native set lists.

Reads original ZIP members through HTTP ranges. Transactions and inverse
matrices are not needed for V/E/EY indicators. Uses MARIO's numeric reader and
canonical axes; the profile explicitly records this narrower reading scope.
"""
from pathlib import Path
import argparse,copy,gzip,hashlib,io,json,logging,os,re,sys,tempfile,time,traceback,zipfile,zlib,uuid
from concurrent.futures import ThreadPoolExecutor,as_completed
from types import SimpleNamespace
import numpy as np
import pandas as pd
import requests
from remote_zip import RemoteArchive,archive_url

ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(os.environ.get('MARIO_EXIOBASE_STAGE', ROOT/'Output/exiobase-browser')).resolve()
sys.path[:0]=[str(ROOT),str(ROOT/'doc/scripts'),str(ROOT/'doc/source/_static/reproduce')]
import mario
from mario.parsers.exiobase_iot import _read_numeric_matrix,_build_sector_axis,_build_final_demand_axis,_normalize_version,_EXTENSION_DIRECTORY_ORDER
from mario.parsers.specs import EXIO_FACTOR_ROWS,EXIOBASE_MONETARY_ZENODO_RECORDS
from database_catalogue import enrich_profile,axis_records,scalar
from economy_browser import aggregate

BASE=json.loads((ROOT/'doc/source/_static/data/economy/exiobase-3112-2024-ixi.json').read_text())['recipe']
NOTEBOOK=next(r for r in json.loads((ROOT/'doc/database_catalogue.recipes.json').read_text())['recipes'] if r['id']=='exiobase-monetary--01')
RELEASES=set(EXIOBASE_MONETARY_ZENODO_RECORDS)
logging.getLogger('mario').setLevel(logging.ERROR)

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if path.suffix=='.gz':raw=gzip.compress(raw)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_bytes(raw);temp.replace(path)

def fetch_inventory():
    STAGE.mkdir(parents=True,exist_ok=True)
    for release,spec in EXIOBASE_MONETARY_ZENODO_RECORDS.items():
        response=requests.get(f"https://zenodo.org/api/records/{spec['record_id']}",timeout=90)
        response.raise_for_status();record=response.json()
        if record['metadata']['version']!=release:raise ValueError('Record release mismatch')
        write(STAGE/f"zenodo-{spec['record_id']}.json",record)

def inventory():
    jobs=[]
    for path in STAGE.glob('zenodo-*.json'):
        d=json.loads(path.read_text());release=d['metadata']['version']
        if release not in RELEASES:continue
        for f in d['files']:
            m=re.fullmatch(r'IOT_(\d{4})_(ixi|pxp)\.zip',f['key'])
            if not m:continue
            year=int(m[1]);system=m[2]
            jobs.append({**f,'id':f'exiobase-{release.replace(".","")}-{year}-{system}','release':release,'year':year,'system':system,'record':str(d['id'])})
    return sorted(jobs,key=lambda j:(tuple(-int(x) for x in j['release'].split('.')),-j['year'],j['system']))

def canonical(frame,fd=False):
    frame.columns=(_build_final_demand_axis if fd else _build_sector_axis)(frame.columns)
    frame.columns.names=['Region','Level','Item'];frame.index.name=None
    return frame.sort_index(axis=0).sort_index(axis=1)

def read_job(job):
    started=time.time();folder=STAGE/'readings'/job['id']
    if (folder/'snapshot.json').exists() and (folder/'profile.json.gz').exists():
        cached=json.loads((folder/'snapshot.json').read_text())
        if cached['provenance'].get('archive_checksum')==job['checksum']:return job['id'],'cached',0
    remote=RemoteArchive(archive_url(job['record'],job['key']),job['size'])
    provenance={};metadata={}
    with zipfile.ZipFile(remote) as archive,tempfile.TemporaryDirectory(prefix='exio-indicators-') as directory:
        temp=Path(directory);infos=[i for i in archive.infolist() if not i.is_dir()]
        top=next(i for i in infos if i.filename.endswith('unit.txt') and '/'.join(i.filename.split('/')[:-1]) in ('',job['key'][:-4]))
        prefix=top.filename[:-len('unit.txt')]
        files={i.filename[len(prefix):]:i for i in infos if i.filename.startswith(prefix)}
        split='factor_inputs/F.txt' in files
        selected=[n for n in files if n in ('unit.txt','metadata.json','file_parameters.json') or n.endswith('/unit.txt') and not n.startswith('impacts/')]
        selected += [f'{directory}/{file}' for directory in (('factor_inputs','air_emissions') if split else ('satellite',)) for file in ('F.txt','F_Y.txt')]
        for name in dict.fromkeys(selected):
            if name not in files:raise ValueError('Missing source member '+name)
            info=files[name]
            cache_key=hashlib.sha256(f"{name}|{info.CRC}|{info.file_size}".encode()).hexdigest()
            large=info.file_size>=2*1024**2
            cache=STAGE/'member-cache'/(cache_key+('.gz' if large else '.bin'))
            reused=cache.exists()
            if reused:
                raw=gzip.decompress(cache.read_bytes()) if large else cache.read_bytes()
                if len(raw)!=info.file_size or zlib.crc32(raw)!=info.CRC:raise ValueError('Invalid cached ZIP member')
            else:
                remote.prefetch(info)
                raw=archive.read(info) # ZipFile verifies the original member CRC.
                if info.file_size<250*1024**2:
                    cache.parent.mkdir(parents=True,exist_ok=True)
                    pending=cache.with_suffix('.'+uuid.uuid4().hex+'.tmp');pending.write_bytes(gzip.compress(raw,compresslevel=1) if large else raw);pending.replace(cache)
            target=temp/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            provenance[name]={'sha256':hashlib.sha256(raw).hexdigest(),'crc32':f'{files[name].CRC:08x}','size':len(raw),'verification':'cached member matches archive CRC32 and uncompressed size' if reused else 'original ZIP member decompressed and CRC32 verified'}
        if (temp/'metadata.json').exists():metadata=json.loads((temp/'metadata.json').read_text())
        detected=_normalize_version(metadata.get('version'))
        # Official v3.8.2 archives retain a v3.81 field but explicitly name exio382.
        stale382=job['release']=='3.8.2' and detected=='3.8.1' and metadata.get('name')=='exio382_ntnu'
        if detected and detected!=job['release'] and not stale382:raise ValueError(f'Source release mismatch: {detected}')
        if metadata.get('system')!=job['system']:raise ValueError('Source system mismatch')
        match=re.search(r'(19|20)\d{2}',str(metadata.get('description','')))
        if not match or int(match[0])!=job['year']:raise ValueError('Source year mismatch')
        factor='factor_inputs' if split else 'satellite'
        rawF=_read_numeric_matrix(temp/factor/'F.txt',index_col=[0],header=[0,1])
        rawFY=_read_numeric_matrix(temp/factor/'F_Y.txt',index_col=[0],header=[0,1])
        factor_units=pd.read_csv(temp/factor/'unit.txt',sep='\t',index_col=0)
        if split:
            V=rawF;VY=rawFY;fu=factor_units
            E=_read_numeric_matrix(temp/'air_emissions/F.txt',index_col=[0],header=[0,1])
            EY=_read_numeric_matrix(temp/'air_emissions/F_Y.txt',index_col=[0],header=[0,1])
            directories=[n[:-len('/unit.txt')] for n in selected if n.endswith('/unit.txt') and not n.startswith('factor_inputs/')]
            directories=sorted(set(directories),key=lambda n:(_EXTENSION_DIRECTORY_ORDER.index(n) if n in _EXTENSION_DIRECTORY_ORDER else 100,n))
            eu=pd.concat([pd.read_csv(temp/n/'unit.txt',sep='\t',index_col=0) for n in directories])
        else:
            V=rawF.loc[EXIO_FACTOR_ROWS];VY=rawFY.loc[EXIO_FACTOR_ROWS];fu=factor_units.loc[EXIO_FACTOR_ROWS]
            E=rawF.drop(EXIO_FACTOR_ROWS);EY=rawFY.drop(EXIO_FACTOR_ROWS);eu=factor_units.drop(EXIO_FACTOR_ROWS)
        native_units=pd.read_csv(temp/'unit.txt',sep='\t')
        native_axis=pd.MultiIndex.from_frame(native_units[['region','sector']])
        if not V.columns.is_unique or set(V.columns)!=set(native_axis):raise ValueError('Value-added and native-unit axes differ')
        if set(E.columns)!=set(V.columns) or set(EY.columns)!=set(VY.columns):raise ValueError('Extension axes differ')
        if set(E.index)!=set(EY.index) or not eu.index.is_unique:raise ValueError('Invalid extension row identity')
        if not set(E.index)<=set(eu.index):raise ValueError('Missing satellite units')
        for frame in [V,VY,E,EY]:
            if not np.isfinite(frame.to_numpy(dtype=float)).all():raise ValueError('Non-finite original indicator block')
        blocks={k:canonical(v,k in ['EY','VY']) for k,v in {'V':V,'VY':VY,'E':E,'EY':EY}.items()}
        V=blocks['V'];E=blocks['E'];EY=blocks['EY'];VY=blocks['VY']
        sets={'Region':list(dict.fromkeys(V.columns.get_level_values('Region'))),'Sector':list(dict.fromkeys(V.columns.get_level_values('Item'))),'Consumption category':list(dict.fromkeys(EY.columns.get_level_values('Item'))),'Factor of production':list(V.index),'Satellite account':sorted(eu.index)}
        su=native_units[['sector','unit']].drop_duplicates().set_index('sector');su.index.name=None
        if not su.index.is_unique:raise ValueError('Inconsistent economic units')
        units={'Sector':su,'Factor of production':fu,'Satellite account':eu}
        unit_records=[]
        for name,frame in units.items():
            for label,value in frame['unit'].items():unit_records.append({'set':name,'index_names':[None],'index':[label],'values':{'unit':value}})
        axes=[];members=[]
        for name,frame in blocks.items():
            for side in ['index','columns']:
                axis=getattr(frame,side);names,records=axis_records(axis)
                axes.append({'matrix':name,'side':side,'names':names,'records':[[scalar(v) for v in row] for row in records]})
        for row in V.columns:members.append({'set':'Sector','region':row[0],'label':row[2]})
        for row in EY.columns:members.append({'set':'Consumption category','region':row[0],'label':row[2]})
        import datetime
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        source=f"https://zenodo.org/records/{job['record']}"
        params={'table':'IOT','system':job['system'],'version':job['release'],'unit':'Monetary'}
        prov={'notebook':NOTEBOOK['notebook'],'cell':NOTEBOOK['cell'],'recipe':NOTEBOOK['id'],'fingerprint':NOTEBOOK['fingerprint'],'parser':'parse_exiobase','options':params,'mario_version':mario.__version__,'reading_scope':'MARIO numeric readers and canonical axes for V, VY, E and EY; all native set labels/units inventoried. Transaction matrices and derived inverses are not loaded.','source_url':source,'archive_url':remote.url,'archive_checksum':job['checksum'],'archive_checksum_scope':'Published checksum identifies the archive; selected members are individually CRC-verified and SHA-256 hashed. Full archive checksum not independently recalculated.','selected_members':provenance,'source_metadata':metadata,'downloaded_bytes':remote.downloaded}
        if stale382:prov['source_metadata_note']='Official 3.8.2 archive names exio382_ntnu but retains a stale v3.81 version field.'
        profile={'schema_version':1,'id':job['id'],'guide':'exiobase-monetary','label':f"EXIOBASE {job['release']} · {job['year']} · monetary {job['system']}",'source':'EXIOBASE','release':job['release'],'year':job['year'],'table':'IOT','status':'parsed','scenario':'baseline','parsed_at':now,'provenance':prov,'sets':sets,'counts':{k:len(v) for k,v in sets.items()},'axes':axes,'units':unit_records,'region_items':members,'region_counts':[{'region':region,'set':name,'count':sum(x['region']==region and x['set']==name for x in members)} for region in sets['Region'] for name in ['Sector','Consumption category']],'classifications':{'status':'native_labels','mappings':[]}}
        enrich_profile(profile)
        r=copy.deepcopy(BASE);r.update(id=job['id'],label=f"EXIOBASE {job['release']} · {'industry × industry' if job['system']=='ixi' else 'product × product'}",release=job['release'],year=job['year'],dimension='Industry' if job['system']=='ixi' else 'Product',parser_options=params,source_url=source,license_url=(source+'/files/LICENSE.txt?download=1') if job['release']!='3.8.2' else 'https://creativecommons.org/licenses/by/4.0/',sectors=sets['Sector'],regions=profile['geography']['regions'],consumption_categories=sets['Consumption category'])
        if job['release']=='3.9.4':r['license_url']=source+'/files/License.txt?download=1'
        gases={label:weight for label,weight in BASE['ghg_factors'].items() if label in E.index}
        if 'NF3 - air' in E.index:gases['NF3 - air']=16.1
        # EDGAR publishes GWP100_AR5_GHG with CH4=28. Recharacterise native
        # mass rows on this basis; already-characterised HFC/PFC stay native.
        gases={label:(0.028 if label.startswith('CH4') else 0.265 if label.startswith('N2O') else 23.5 if label=='SF6 - air' else 16.1 if label=='NF3 - air' else weight) for label,weight in gases.items()}
        required=set(BASE['ghg_factors'])-{'CH4_bio - combustion - air','N2O_bio - combustion - air','NF3 - air'}
        if job['release']=='3.11.2':required.add('NF3 - air')
        if required-set(gases):raise ValueError('Required GHG rows missing: '+str(required-set(gases)))
        expected={label:('kg CO2-eq' if label in ['HFC - air','PFC - air'] else 'kg') for label in gases}
        if any(eu.loc[k,'unit']!=u for k,u in expected.items()):raise ValueError('Unexpected GHG source units')
        if any(fu.loc[k,'unit']!='M.EUR' for k in r['value_added_rows']+r['product_tax_rows']):raise ValueError('Unexpected monetary units')
        r['ghg_factors']=gases;r['ghg_method']='GWP100: EDGAR-compatible IPCC AR5 for mass-reported CO₂ (1), CH₄ (28), N₂O (265), SF₆ (23,500)'+(' and NF₃ (16,100)' if 'NF3 - air' in gases else '')+'; HFC/PFC retain source CO₂-equivalents with unverified GWP basis. Biogenic CO₂ excluded. Production accounts; direct household emissions reported separately.'
        r['ghg_coverage']={'included_native_rows':list(gases),'nf3':'included' if 'NF3 - air' in gases else 'not separately reported by source','gwp':'EDGAR-compatible IPCC AR5 GWP100 for native mass rows plus source-characterised HFC/PFC'}
        r['expected_units']={'Factor of production':fu['unit'].to_dict(),'Satellite account':expected}
        r['tax_bridge']='exiobase_factor_inputs' if split else 'exiobase_satellite'
        taxes=VY.loc[r['product_tax_rows']].sum().groupby(level='Region').sum().to_dict()
        rows=aggregate(SimpleNamespace(get_block=blocks.__getitem__),r,taxes)
        va=sum(abs(v) for row in rows for v in row['value_added']);tax=sum(abs(row['net_product_taxes']) for row in rows)
        r['gdp_bridge_verified']=tax>va*1e-6
        r['gdp_basis']='GDP reconstructed with the source product-tax bridge' if r['gdp_bridge_verified'] else 'GDP estimate; unverified market-price bridge'
        r['gdp_note']='Value added plus original net product taxes on intermediate and final uses.' if r['gdp_bridge_verified'] else 'The source has negligible product-tax entries; the income aggregate is labelled a GDP estimate.'
        r['attribution']=f"EXIOBASE {job['release']}, {source}. Indicator aggregates calculated with MARIO; source licence applies."
        snapshot={'schema_version':1,'recipe':r,'regions':rows,'generated_at':now,'provenance':prov}
        # Save only aggregate numeric results, set metadata and hashes, never raw blocks.
        write(folder/'profile.json.gz',profile);write(folder/'snapshot.json',snapshot)
        write(folder/'validation.json',{'year':job['year'],'release':job['release'],'system':job['system'],'counts':profile['counts'],'world_value_added_eur':sum(sum(x['value_added']) for x in rows),'world_ghg_tonnes':sum(sum(x['ghg']) for x in rows),'tax_bridge_absolute_eur':tax,'downloaded_bytes':remote.downloaded,'seconds':round(time.time()-started,2),'source_metadata_note':prov.get('source_metadata_note')})
    return job['id'],'ok',round(time.time()-started,1)

if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('--workers',type=int,default=3);cli.add_argument('--ids',nargs='*');cli.add_argument('--release');cli.add_argument('--exclude-release');cli.add_argument('--limit',type=int);cli.add_argument('--refresh-inventory',action='store_true');args=cli.parse_args()
    if args.refresh_inventory or not all((STAGE/f"zenodo-{spec['record_id']}.json").exists() for spec in EXIOBASE_MONETARY_ZENODO_RECORDS.values()):fetch_inventory()
    jobs=inventory();write(STAGE/'inventory.json',jobs)
    if args.ids:jobs=[j for j in jobs if j['id'] in args.ids]
    if args.release:jobs=[j for j in jobs if j['release']==args.release]
    if args.exclude_release:jobs=[j for j in jobs if j['release']!=args.exclude_release]
    if args.limit:jobs=jobs[:args.limit]
    print('Scheduled',len(jobs),'official IOT readings',flush=True)
    results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(read_job,j):j for j in jobs}
        for future in as_completed(futures):
            job=futures[future]
            try:
                id,status,seconds=future.result();result={'id':id,'status':status,'seconds':seconds};print(len(results)+1,'/',len(jobs),result,flush=True)
            except Exception as e:
                result={'id':job['id'],'status':'failed','error':str(e),'traceback':traceback.format_exc()};write(STAGE/'errors'/(job['id']+'.json'),result);print('FAILED',job['id'],str(e),flush=True)
            results.append(result);write(STAGE/'run-report.json',results)
    print('Finished',sum(r['status']!='failed' for r in results),'/',len(results),flush=True)
    if any(r['status']=='failed' for r in results):sys.exit(1)
