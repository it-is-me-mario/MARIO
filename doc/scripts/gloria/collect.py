"""Collect one GLORIA year at a time with MARIO's native block readers.

Only Va/Vc/Ea/Ec/EY and signed valuation totals are needed for this browser.
Full use/supply transactions and derived inverses are not materialized.
The source archives are returned to online-only after successful validation.
"""
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
from datetime import datetime,timezone
import argparse,copy,gc,hashlib,json,os,subprocess,sys,time,zipfile
import numpy as np
import pandas as pd
ROOT=Path(os.environ.get('MARIO_DOCS_ROOT',Path(__file__).resolve().parents[3]))
sys.path[:0]=[str(ROOT),str(ROOT/'doc/scripts'),str(ROOT/'doc/source/_static/reproduce')]
import mario
from mario.parsers import gloria as G
from mario.parsers.specs import GLORIA_MONETARY_UNIT
from database_catalogue import extract_profile
from economy_browser import aggregate
from product_taxes import build as build_bridge,apply as apply_bridge,summarize
from audit_accounting import audit as audit_accounting


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')


def source_members(path):
    with zipfile.ZipFile(path) as archive:
        return [dict(name=i.filename,size=i.file_size,compressed=i.compress_size,crc32=f'{i.CRC:08x}') for i in archive.infolist() if not i.is_dir()]


def collect(root,year,stage,evict_command=None):
    folder=stage/f'gloria-060-{year}-sut';folder.mkdir(parents=True,exist_ok=True);start=time.time()
    economic=root/f'GLORIA_MRIO_Loop060_part_I_MRIOdatabase/GLORIA_MRIOs_60_{year}.zip'
    satellite=root/f'GLORIA_MRIO_Loop060_part_III_satelliteaccounts/GLORIA_SatelliteAccounts_060_{year}.zip'
    print('YEAR',year,'hydrate economic and satellite archives',flush=True)
    items=source_members(economic);sat_items=source_members(satellite)
    write(folder/'inventory.json',{'economic':items,'satellite':sat_items})
    layout,metadata=G.detect_gloria_layout(economic,year=year)
    if layout.release!='060' or layout.year!=year:raise ValueError('Wrong GLORIA source year/release')
    tq=next(i for i in sat_items if '_TQ-Results_' in i['name']);yq=next(i for i in sat_items if '_YQ-Results_' in i['name'])
    if f'_{year}_060_' not in tq['name'] or f'_{year}_060_' not in yq['name']:raise ValueError('Satellite year/release mismatch')
    layout=replace(layout,TQ_path=G.GloriaResource(satellite,tq['name']),YQ_path=G.GloriaResource(satellite,yq['name']),satellite_root=satellite)
    codes=list(metadata.region_codes);nr,ns,nf=len(codes),len(metadata.sector_names),len(metadata.final_demand_names)
    positions=list(range(nr));ac=G._activity_positions(positions,ns);cc=G._commodity_positions(positions,ns);fd=G._final_demand_positions(positions,nf)
    satellites,sa,su=G._select_gloria_satellites(metadata,'Emissions')
    gas="Emissions (EDGAR) | 'GHG_total_EDGAR_consistent'"
    if su.loc[gas,'unit']!='kilotonnes CO2-equivalent':raise ValueError('Unexpected native GHG unit')
    aa,ca,fa,va_axis,sa=G._build_axes(codes,metadata.sector_names,metadata.factor_names,metadata.final_demand_names,tuple(sa))
    for axis in [aa,ca,fa]:axis.names=['Region','Level','Item']
    dtype=np.dtype('float64')
    print('YEAR',year,'read Va/Vc, float64',flush=True)
    vd,vc=G._read_value_added_blocks(layout.V_path,activity_columns=ac,commodity_columns=cc,factor_count=len(va_axis),selected_positions=positions,va_shape=(len(va_axis),len(aa)),vc_shape=(len(va_axis),len(ca)),dtype=dtype)
    print('YEAR',year,'read native Emissions Ea/Ec/EY',flush=True)
    ea,ec=G._read_satellite_transaction_blocks(layout.TQ_path,activity_columns=ac,commodity_columns=cc,row_map={raw:i for i,raw in enumerate(satellites)},dtype=dtype)
    ey=G._read_sparse_all_rows(layout.YQ_path,columns=fd,row_map={raw:i for i,raw in enumerate(satellites)},dtype=dtype)
    blocks={'Va':pd.DataFrame(vd,index=va_axis,columns=aa),'Vc':G._sparse_dataframe(vc,va_axis,ca),'Ea':G._sparse_dataframe(ea,sa,aa),'Ec':G._sparse_dataframe(ec,sa,ca),'EY':G._sparse_dataframe(ey,sa,fa)}
    sets={'Region':codes,'Activity':list(metadata.sector_names),'Commodity':list(metadata.sector_names),'Factor of production':list(metadata.factor_names),'Consumption category':list(metadata.final_demand_names),'Satellite account':list(sa)}
    units={name:pd.DataFrame({'unit':[GLORIA_MONETARY_UNIT]*len(sets[name])},index=sets[name]) for name in ['Activity','Commodity','Factor of production']};units['Satellite account']=su
    database=SimpleNamespace(table_type='SUT',units=units,get_index=lambda name:sets,list_matrices=lambda:list(blocks),get_block=blocks.__getitem__)
    notebook=next(r for r in json.loads((ROOT/'doc/database_catalogue.recipes.json').read_text())['recipes'] if r['id']=='gloria--02')
    params={'path':str(economic),'year':year,'satellites':'Emissions','dtype':'float64','calc_all':False}
    job={'id':folder.name,'label':f'GLORIA 060 · {year} · SUT','source':'GLORIA','release':'060','year':year}
    profile=extract_profile(database,job=job,recipe=notebook,parameters=params)
    # Source README names disambiguate aggregates and retained historical codes.
    geography={r['label']:r for r in profile['geography']['regions']}
    for code,name in zip(codes,metadata.region_names):
        if code.startswith('X'):geography[code].update(kind='aggregate',name=name,iso3=None)
        if code=='SDS':geography[code].update(kind='country',name=name,iso3='SSD')
        if code=='DYE':geography[code].update(kind='unresolved',name=name,iso3=None)
    recipe=copy.deepcopy(json.loads((ROOT/'doc/source/_static/data/economy/gloria-060-2024-sut.json').read_text())['recipe'])
    recipe.update(id=folder.name,year=year,parser_options={k:v for k,v in params.items() if k not in ['path','calc_all']},regions=list(geography.values()),sectors=list(metadata.sector_names),gdp_bridge_verified=False)
    recipe['expected_units']={'Factor of production':dict.fromkeys(metadata.factor_names,GLORIA_MONETARY_UNIT),'Satellite account':{gas:su.loc[gas,'unit']}}
    recipe['economic_vintage']=min(i['name'][:8] for i in items);recipe['satellite_vintage']=tq['name'][:8]
    rows=aggregate(database,recipe)
    provenance={**profile['provenance'],'mario_version':mario.__version__,'reading_scope':'MARIO native Va/Vc/Ea/Ec/EY readers and canonical axes, float64. Full transaction blocks and inverses are not loaded. Signed product-tax valuations are independently streamed for the GDP bridge.','economic_members':items,'satellite_members':sat_items,'readme_sha256':hashlib.sha256(layout.readme_path.read_bytes()).hexdigest()}
    snapshot={'schema_version':1,'recipe':recipe,'regions':rows,'provenance':provenance,'generated_at':datetime.now(timezone.utc).isoformat()}
    profile['provenance']=provenance
    write(folder/'profile.json',profile);write(folder/'snapshot-base.json',snapshot)
    del database,blocks,ea,ec,ey,vd,vc;gc.collect()
    summaries={}
    for block,markups in [('Y',range(1,6)),('T',[4,5])]:
        for markup in markups:
            item=next(i for i in items if f'_{block}-Results_{year}_060_Markup00{markup}' in i['name'])
            cache=folder/f'{block}{markup}-summary.json'
            if cache.exists():
                d=json.loads(cache.read_text())
                if d['member']!=item:raise ValueError('Cached valuation identity changed')
            else:
                print('YEAR',year,'stream',block,'valuation',markup,flush=True)
                d=summarize(G.GloriaResource(economic,item['name']),nr,ns,nf);d['member']=item;write(cache,d)
            summaries[f'{block}{markup}']=d
    audit=folder/'source-accounting-audit.json'
    try:
        bridge=build_bridge(snapshot,summaries,json.loads(audit.read_text()) if audit.is_file() else None)
    except ValueError as error:
        if 'World GDP income/expenditure identity failed' not in str(error):raise
        print('YEAR',year,'independently audit source accounting residual',flush=True)
        source_audit=audit_accounting(economic,snapshot,profile,summaries);write(audit,source_audit)
        bridge=build_bridge(snapshot,summaries,source_audit)
    apply_bridge(snapshot,bridge)
    assert all(len(r['value_added'])==ns and len(r['ghg'])==ns and r.get('household_ghg') is not None and r.get('gdp') is not None for r in rows)
    assert all(np.isfinite(v) for r in rows for key in ['value_added','ghg'] for v in r[key])
    write(folder/'gdp-bridge.json',bridge);write(folder/'snapshot.json',snapshot)
    write(folder/'validation.json',{'year':year,'counts':profile['counts'],'gdp':bridge['validation'],'world_ghg_tonnes':sum(sum(r['ghg'])+r['household_ghg'] for r in rows),'seconds':round(time.time()-start,1),'precision':'float64'})
    print('YEAR',year,'VALIDATED',json.dumps(json.loads((folder/'validation.json').read_text())),flush=True)
    if evict_command:
        for file in [economic,satellite]:
            subprocess.run([str(evict_command),str(file)],check=True)
            # macOS File Provider can retain small cache extents after eviction.
            # SF_DATALESS (sys/stat.h) is the placeholder flag; block count alone
            # incorrectly rejects a successful online-only transition.
            state=file.stat()
            if state.st_blocks and not (sys.platform=='darwin' and state.st_flags & 0x40000000):
                raise ValueError('Cloud file did not become online-only: '+file.name)
        print('YEAR',year,'ONLINE_ONLY',flush=True)
    return snapshot,profile


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--root',type=Path,required=True);cli.add_argument('--years',type=int,nargs='+',required=True);cli.add_argument('--stage',type=Path,required=True);cli.add_argument('--evict-command',type=Path)
    args=cli.parse_args()
    for year in args.years:collect(args.root,year,args.stage,args.evict_command)
