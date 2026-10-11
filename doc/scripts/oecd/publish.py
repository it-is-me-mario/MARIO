"""Prepare and publish verified local OECD ICIO browser assets."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "source/_static/reproduce"))
from economy_browser import annotate_ghg_method
import argparse, copy, gzip, hashlib, json, shutil

def read(path): return json.loads(path.read_text())
def digest(value): return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')

def prepare(root,stage):
    out=root/'doc/source/_static/data/economy'
    readings=[]; groups={}
    for folder in sorted((stage/'readings').iterdir()):
        s=read(folder/'snapshot.json'); p=json.loads(gzip.decompress((folder/'profile.json.gz').read_bytes()))
        if s['recipe']['id']!=p['id']: raise ValueError('Snapshot/profile ID mismatch')
        readings.append(s)
        k=digest({'release':p['release'],'sets':p['sets'],'units':p['units'],'region_items':p['region_items']})
        groups.setdefault(k,[]).append((s,p))
    inventory=read(stage/'inventory.json')
    expected={f'oecd-icio-{j["year"]}-{j["edition"].lower()}' for j in inventory}
    if {s['recipe']['id'] for s in readings}!=expected: raise ValueError('Incomplete or stale staged inventory')
    # Quantify the effect of Extended's split-region normalisation. Editions
    # remain independently selectable even when national totals agree.
    pairs={}; checks=[]
    for s in readings: pairs.setdefault(s['recipe']['year'],{})[s['recipe']['release']]=s
    for year,pair in sorted(pairs.items()):
        if set(pair)!={'Extended','Regular'}: raise ValueError('Missing matching edition/year')
        a={r['code']:r for r in pair['Extended']['regions']}; b={r['code']:r for r in pair['Regular']['regions']}
        if a.keys()!=b.keys(): raise ValueError('Parsed regional coverage differs between editions')
        differences=[abs(a[c]['gdp']-b[c]['gdp']) for c in a]
        checks.append({'year':year,'max_country_gdp_difference_usd':max(differences),
                       'world_gdp_difference_usd':sum(r['gdp'] for r in a.values())-sum(r['gdp'] for r in b.values())})
    write(stage/'edition-comparison.json',checks)
    catalogue=read(root/'doc/source/_static/data/database_profiles.json')
    catalogue['profiles']=[p for p in catalogue['profiles'] if not(p['source']=='OECD' and p['guide']=='oecd')]
    built=[]
    for k,group in groups.items():
        group.sort(key=lambda item:item[1]['year'],reverse=True)
        s,p=copy.deepcopy(group[0]); years=sorted({p['year'] for _,p in group})
        identifier=f'oecd-icio-{p["release"].lower()}-sets-{k[:8]}'
        p.update(id=identifier,years=years,label=f'OECD ICIO · {p["release"]} · {years[0]}–{years[-1]}')
        p['readings']=[{'id':r['recipe']['id'],'year':q['year'],'filename':q['provenance']['input_filename'],
                        'sha256':q['provenance']['input_sha256'],'counts':q['counts'],
                        'raw_region_count':q['provenance']['raw_region_count']} for r,q in group]
        folder=stage/'catalogue'/identifier; write(folder/'profile.json',p)
        built.append({'id':identifier,'profile':str(folder/'profile.json'),'workbook':str(folder/'sets.xlsx'),'source_url':s['recipe']['source_url']})
        fields=('id','guide','label','source','release','year','years','table','status','parsed_at','counts','region_counts','geography','classifications','coverage_signatures','set_flags')
        summary={name:p[name] for name in fields if name in p}
        summary['provenance']={name:p['provenance'][name] for name in ['parser','options','reading_scope','mario_version','source_url','split_region_handling']}
        summary['workbook']=f'_static/data/database_profiles/{identifier}.xlsx'; summary['detail']=f'_static/data/database_profiles/{identifier}.json'
        catalogue['profiles'].append(summary)
    old=read(out/'manifest.json')
    snapshots=[read(out/(d['id']+'.json')) for d in old['datasets'] if d['source']!='OECD']+readings
    snapshots.sort(key=lambda s:(-s['recipe']['year'],s['recipe']['label']))
    maps=read(out/'sector-sections.json')
    base=maps['mappings']['oecd-icio-2022-extended']
    maps['mappings']={k:m for k,m in maps['mappings'].items() if m['family']!='OECD'}
    for s in readings:
        r=annotate_ghg_method(s['recipe']); m=copy.deepcopy(base); entries={e['native_label']:e for e in m['entries']}
        if set(entries)!=set(r['sectors']): raise ValueError('OECD native sector correspondence changed')
        m['entries']=[{**entries[label],'index':i} for i,label in enumerate(r['sectors'])]
        m['version']=r['release']; maps['mappings'][r['id']]=m
    templates={}; datasets=[]
    for s in snapshots:
        r=annotate_ghg_method(s['recipe']); regions=[{k:region[k] for k in ['code','name','iso3','kind']} for region in s['regions']]
        fields=['source','release','dimension','parser_options','sectors','ghg_method','ghg_basis','gdp_basis','value_added_basis','source_url','license_url','parser_guide','ghg_factors','attribution','value_added_note','gdp_note', 'table', 'gdp_proxy', 'ghg_proxy', 'ghg_note', 'gwp_basis', 'gwp_horizon', 'final_demand_emissions_loaded', 'ghg_sectors']
        recipe={k:r[k] for k in fields if k in r}
        # Year is reading-specific: templates hold common ICIO options only.
        if r['source']=='OECD':
            recipe['parser_options']={k:v for k,v in recipe.get('parser_options',{}).items() if k!='year'}
            recipe['attribution']=f'OECD ICIO, {r["release"]}. Indicators calculated with MARIO; cite OECD.'
        template_key=digest([recipe,regions])[:16]
        templates.setdefault(template_key,{'recipe':recipe,'regions':regions})
        d={k:r[k] for k in ['id','label','source','year','dimension','currency','gdp_bridge_verified'] if k in r}
        d.update(template=template_key,availability={metric:all(region.get(metric) is not None for region in s['regions']) for metric in ['gdp','value_added','ghg']})
        datasets.append(d)
    manifest={'schema_version':2,'datasets':datasets,'templates':templates,'world_bank_sha256':old['world_bank_sha256']}
    write(stage/'manifest-ready.json',manifest); write(stage/'sections-ready.json',maps)
    write(stage/'catalogue-ready.json',catalogue); write(stage/'catalogue-build.json',built)
    write(stage/'recipes-ready.json',{'schema_version':1,'recipes':[s['recipe'] for s in snapshots]})
    print(f'Prepared {len(readings)} OECD readings; {len(groups)} native-set inventories; {len(datasets)} public readings.')
    return readings,built

def publish(root,stage,readings,built):
    if any(not Path(item['workbook']).is_file() for item in built): raise ValueError('Build and review the set workbooks before publishing')
    out=root/'doc/source/_static/data/economy'; target=root/'doc/source/_static/data/database_profiles'
    for s in readings: write(out/(s['recipe']['id']+'.json'),s)
    for name,filename in [('manifest','manifest.json'),('sections','sector-sections.json')]: shutil.copyfile(stage/(name+'-ready.json'),out/filename)
    shutil.copyfile(stage/'catalogue-ready.json',target.parent/'database_profiles.json')
    (root/'doc/economy_browser.recipes.json').write_text(json.dumps(read(stage/'recipes-ready.json'),ensure_ascii=False,indent=2)+'\n')
    for item in built:
        shutil.copyfile(item['profile'],target/(item['id']+'.json')); shutil.copyfile(item['workbook'],target/(item['id']+'.xlsx'))
    print('Published OECD aggregates, grouped set inventories, geography and native sector mappings.')

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__); cli.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[3]); cli.add_argument('--stage',type=Path,required=True); cli.add_argument('--publish',action='store_true')
    args=cli.parse_args(); readings,built=prepare(args.root,args.stage)
    if args.publish: publish(args.root,args.stage,readings,built)
