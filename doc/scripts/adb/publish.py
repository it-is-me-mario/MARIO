"""Prepare and publish local ADB MRIOT indicators and grouped set inventories."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "source/_static/reproduce"))
from economy_browser import annotate_ghg_method
import argparse,copy,gzip,hashlib,json,shutil
def read(p):return json.loads(p.read_text())
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')

def prepare(root,stage):
    out=root/'doc/source/_static/data/economy';snapshots=[];groups={}
    for folder in sorted((stage/'readings').iterdir()):
        s=read(folder/'snapshot.json');p=json.loads(gzip.decompress((folder/'profile.json.gz').read_bytes()))
        if s['recipe']['id']!=p['id']:raise ValueError('Reading/profile mismatch')
        snapshots.append(s)
        k=digest({'release':p['release'],'sets':p['sets'],'units':p['units'],'region_items':p['region_items']})
        groups.setdefault(k,[]).append((s,p))
    inventory=read(stage/'inventory.json');expected={f'adb-{j["year"]}-{j["economies"]}-economies' for j in inventory['jobs']}
    if {s['recipe']['id'] for s in snapshots}!=expected:raise ValueError('Incomplete ADB local collection')
    catalogue=read(root/'doc/source/_static/data/database_profiles.json');catalogue['profiles']=[p for p in catalogue['profiles'] if p['guide']!='adb']
    built=[]
    for key,group in groups.items():
        group.sort(key=lambda pair:-pair[1]['year']);s,p=copy.deepcopy(group[0]);years=sorted({p['year'] for _,p in group})
        economies=p['provenance']['economies'];identifier=f'adb-{economies}-economies-sets-{key[:8]}'
        p.update(id=identifier,years=years,label=f'ADB · {economies} economies · '+('with air-emissions accounts' if p['counts']['Satellite account'] else 'economic accounts'))
        p['readings']=[{'id':s['recipe']['id'],'year':q['year'],'filename':q['provenance']['input_filename'],'sha256':q['provenance']['input_sha256'],'counts':q['counts'],'emissions':q['provenance'].get('emissions')} for s,q in group]
        folder=stage/'catalogue'/identifier;write(folder/'profile.json',p)
        built.append({'id':identifier,'profile':str(folder/'profile.json'),'workbook':str(folder/'sets.xlsx'),'source_url':s['recipe']['source_url']})
        fields=('id','guide','label','source','release','year','years','table','status','parsed_at','counts','region_counts','geography','classifications','coverage_signatures','set_flags')
        summary={k:p[k] for k in fields};summary['provenance']={k:p['provenance'][k] for k in ['parser','options','mario_version','reading_scope','source_url','economies','region_note']}
        summary['workbook']=f'_static/data/database_profiles/{identifier}.xlsx';summary['detail']=f'_static/data/database_profiles/{identifier}.json';catalogue['profiles'].append(summary)
    old=read(out/'manifest.json');all_snapshots=[read(out/(d['id']+'.json')) for d in old['datasets'] if d['source']!='ADB']+snapshots
    all_snapshots.sort(key=lambda s:(-s['recipe']['year'],s['recipe']['label']))
    mappings=read(out/'sector-sections.json');base=mappings['mappings']['adb-2024-74-economies'];entries={e['native_label']:e for e in base['entries']}
    mappings['mappings']={k:v for k,v in mappings['mappings'].items() if v['family']!='ADB'}
    for s in snapshots:
        r=annotate_ghg_method(s['recipe']);source_codes={label:code for code,label in s['provenance']['source_sector_codes'].items()}
        if set(source_codes)!=set(r['sectors']) or set(source_codes)!=set(entries) or set(source_codes.values())!={f'c{i}' for i in range(1,36)}:raise ValueError('ADB native code/label classification changed')
        m=copy.deepcopy(base);m['version']=r['release'];m['entries']=[{**entries[label],'native_code':source_codes[label],'index':i} for i,label in enumerate(r['sectors'])]
        mappings['mappings'][r['id']]=m
    templates={};datasets=[]
    fields=['source','release','dimension','parser_options','sectors','ghg_method','ghg_basis','gdp_basis','value_added_basis','source_url','license_url','parser_guide','ghg_factors','attribution','value_added_note','gdp_note', 'table', 'gdp_proxy', 'ghg_proxy', 'ghg_note', 'gwp_basis', 'gwp_horizon', 'final_demand_emissions_loaded', 'ghg_sectors']
    for s in all_snapshots:
        r=annotate_ghg_method(s['recipe']);recipe={k:r[k] for k in fields if k in r}
        if r['source'] in ['ADB','OECD']:
            recipe['parser_options']={k:v for k,v in recipe['parser_options'].items() if k!='year'}
            if r['source']=='OECD':recipe['attribution']=f'OECD ICIO, {r["release"]}. Indicators calculated with MARIO; cite OECD.'
        regions=[{k:row[k] for k in ['code','name','iso3','kind'] if k in row} for row in s['regions']]
        key=digest([recipe,regions])[:16];templates.setdefault(key,{'recipe':recipe,'regions':regions})
        d={k:r[k] for k in ['id','label','source','year','dimension','currency','gdp_bridge_verified'] if k in r}
        d.update(template=key,availability={metric:all(row.get(metric) is not None for row in s['regions']) for metric in ['gdp','value_added','ghg']});datasets.append(d)
    write(stage/'manifest-ready.json',{'schema_version':2,'datasets':datasets,'templates':templates,'world_bank_sha256':old['world_bank_sha256']})
    write(stage/'catalogue-ready.json',catalogue);write(stage/'catalogue-build.json',built);write(stage/'sections-ready.json',mappings)
    write(stage/'recipes-ready.json',{'schema_version':1,'recipes':[s['recipe'] for s in all_snapshots]})
    print(f'Prepared {len(snapshots)} ADB readings, {len(groups)} native-set inventories; {len(datasets)} public readings.')
    return snapshots,built

def publish(root,stage,snapshots,built):
    if any(not Path(j['workbook']).is_file() for j in built):raise ValueError('Build/review the native set workbooks first')
    out=root/'doc/source/_static/data/economy';target=root/'doc/source/_static/data/database_profiles'
    for s in snapshots:write(out/(s['recipe']['id']+'.json'),s)
    shutil.copyfile(stage/'manifest-ready.json',out/'manifest.json');shutil.copyfile(stage/'sections-ready.json',out/'sector-sections.json')
    shutil.copyfile(stage/'catalogue-ready.json',target.parent/'database_profiles.json')
    (root/'doc/economy_browser.recipes.json').write_text(json.dumps(read(stage/'recipes-ready.json'),ensure_ascii=False,indent=2)+'\n')
    for j in built:shutil.copyfile(j['profile'],target/(j['id']+'.json'));shutil.copyfile(j['workbook'],target/(j['id']+'.xlsx'))
    print('Published ADB indicators, native set downloads, scope and verified sector sections.')

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[3]);cli.add_argument('--stage',type=Path,required=True);cli.add_argument('--publish',action='store_true')
    args=cli.parse_args();snapshots,built=prepare(args.root,args.stage)
    if args.publish:publish(args.root,args.stage,snapshots,built)
