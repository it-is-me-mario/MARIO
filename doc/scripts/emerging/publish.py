"""Prepare and publish verified EMERGING local readings and grouped native-set downloads."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "source/_static/reproduce"))
from economy_browser import annotate_ghg_method
import argparse,copy,gzip,hashlib,json,shutil

def read(p):return json.loads(p.read_text())
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def write(p,value):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')

AUTHORS={"1.0":"Huo, J.; Chen, P.; Hubacek, K.; Zheng, H.; Meng, J.; Guan, D.",
         "2.0":"Huo, J.; Wang, W.; Guan, D.", "2.2":"Huo, J.; Wang, W.; Guan, D.", "E":"Huo, J."}
RECORDS={"1.0":"10956623", "2.0":"17557778", "2.2":"19461860", "E":"18303090"}
def attribution(release,year=None):
    title="EMERGING-E" if release=="E" else "EMERGING "+release
    return f'{AUTHORS[release]} {title}{", "+str(year) if year else ""}. doi:10.5281/zenodo.{RECORDS[release]}. CC BY 4.0; indicators calculated with MARIO.'

def prepare(root,stage):
    out=root/'doc/source/_static/data/economy';readings=[];groups={}
    source_checks={(v['release'],v['filename']):v for v in read(stage/'source-md5-verification.json')}
    for folder in sorted((stage/'readings').iterdir()):
        s=read(folder/'snapshot.json');p=json.loads(gzip.decompress((folder/'profile.json.gz').read_bytes()))
        if s['recipe']['id']!=p['id']:raise ValueError('Reading/profile mismatch')
        s['recipe']['attribution']=attribution(s['recipe']['release'],s['recipe']['year'])
        check=source_checks[(p['release'],p['provenance']['input_filename'])]
        p['provenance']['published_md5']=check['md5']
        if p['release']=='E':
            labels=read(stage/'e-label-verification.json')
            if not labels['regional_labels']['ordering_verified'] or not labels['sector_labels']['builtin_casefold_order_verified']:raise ValueError('Verify EMERGING-E regional and sector ordering')
            p['provenance']['label_verification']=labels
        if p['provenance'].get('emissions'):
            emissions=p['provenance']['emissions']
            emissions['published_md5']=source_checks[(emissions.get('release',p['release']),emissions['filename'])]['md5']
        s['provenance']=copy.deepcopy(p['provenance'])
        readings.append(s)
        key=digest({'release':p['release'],'sets':p['sets'],'units':p['units'],'region_items':p['region_items']})
        groups.setdefault(key,[]).append((s,p))
    if any(not all(read(folder/'validation.json').get(k) for k in ['flow_verified','indicator_proxies_verified']) for folder in (stage/'readings').iterdir()):raise ValueError('Verify the corrected MATLAB flow orientation in every reading before publication')
    expected={j['id'] for j in read(stage/'inventory.json')}
    if {s['recipe']['id'] for s in readings}!=expected:raise ValueError('Incomplete local EMERGING inventory')
    # A stage may hold only some releases (collect.py --release); published readings of the other releases are kept.
    staged={s['recipe']['release'] for s in readings}
    catalogue=read(root/'doc/source/_static/data/database_profiles.json');catalogue['profiles']=[p for p in catalogue['profiles'] if p['guide']!='emerging' or p['release'] not in staged]
    built=[]
    for key,group in groups.items():
        group.sort(key=lambda pair:-pair[1]['year']);s,p=copy.deepcopy(group[0]);years=sorted({p['year'] for _,p in group})
        identifier=f'emerging-{p["release"].replace(".","").lower()}-sets-{key[:8]}'
        p.update(id=identifier,years=years,label='EMERGING-E' if p['release']=='E' else 'EMERGING '+p['release'])
        p['readings']=[{'id':s['recipe']['id'],'year':q['year'],'filename':q['provenance']['input_filename'],'sha256':q['provenance']['input_sha256'],'counts':q['counts'],'emissions':q['provenance'].get('emissions')} for s,q in group]
        folder=stage/'catalogue'/identifier;write(folder/'profile.json',p)
        built.append({'id':identifier,'profile':str(folder/'profile.json'),'workbook':str(folder/'sets.xlsx'),'source_url':s['recipe']['source_url']})
        fields=('id','guide','label','source','release','year','years','table','status','parsed_at','counts','region_counts','geography','classifications','coverage_signatures','set_flags')
        summary={k:p[k] for k in fields};summary['provenance']={k:p['provenance'][k] for k in ['parser','options','mario_version','reading_scope','source_url']}
        summary['workbook']=f'_static/data/database_profiles/{identifier}.xlsx';summary['detail']=f'_static/data/database_profiles/{identifier}.json';catalogue['profiles'].append(summary)
    old=read(out/'manifest.json');all_snapshots=[s for s in (read(out/(d['id']+'.json')) for d in old['datasets']) if s['recipe']['source']!='EMERGING' or s['recipe']['release'] not in staged]+readings
    all_snapshots.sort(key=lambda s:(-s['recipe']['year'],s['recipe']['label']))
    sections=read(out/'sector-sections.json')
    if any(m['family']=='EMERGING' for m in sections['mappings'].values()):raise ValueError('Review existing EMERGING mappings before replacing the inventory')
    templates={};datasets=[]
    fields=['source','release','dimension','parser_options','sectors','ghg_method','ghg_basis','gdp_basis','value_added_basis','source_url','license_url','parser_guide','ghg_factors','attribution','value_added_note','gdp_note', 'table', 'gdp_proxy', 'ghg_proxy', 'ghg_note', 'gwp_basis', 'gwp_horizon', 'final_demand_emissions_loaded', 'ghg_sectors']
    for s in all_snapshots:
        r=annotate_ghg_method(s['recipe']);recipe={k:r[k] for k in fields if k in r}
        if r['source'] in ['ADB','OECD','EMERGING']:
            recipe['parser_options']={k:v for k,v in recipe['parser_options'].items() if k!='year'}
            if r['source']=='OECD':recipe['attribution']=f'OECD ICIO, {r["release"]}. Indicators calculated with MARIO; cite OECD.'
            if r['source']=='EMERGING':recipe['attribution']=attribution(r['release'])
        regions=[{k:row[k] for k in ['code','name','iso3','kind'] if k in row} for row in s['regions']]
        key=digest([recipe,regions])[:16];templates.setdefault(key,{'recipe':recipe,'regions':regions})
        d={k:r[k] for k in ['id','label','source','year','dimension','currency','gdp_bridge_verified'] if k in r}
        d.update(template=key,availability={metric:all(row.get(metric) is not None for row in s['regions']) for metric in ['gdp','value_added','ghg']});datasets.append(d)
    write(stage/'manifest-ready.json',{'schema_version':2,'datasets':datasets,'templates':templates,'world_bank_sha256':old['world_bank_sha256']})
    write(stage/'catalogue-ready.json',catalogue);write(stage/'catalogue-build.json',built);write(stage/'sections-ready.json',sections)
    write(stage/'recipes-ready.json',{'schema_version':1,'recipes':[s['recipe'] for s in all_snapshots]})
    print(f'Prepared {len(readings)} EMERGING readings, {len(groups)} set inventories; {len(datasets)} public readings.')
    return readings,built

def publish(root,stage,readings,built):
    if any(not Path(j['workbook']).is_file() for j in built):raise ValueError('Build and review native-set workbooks first')
    out=root/'doc/source/_static/data/economy';target=root/'doc/source/_static/data/database_profiles'
    for s in readings:write(out/(s['recipe']['id']+'.json'),s)
    shutil.copyfile(stage/'manifest-ready.json',out/'manifest.json');shutil.copyfile(stage/'catalogue-ready.json',target.parent/'database_profiles.json')
    (root/'doc/economy_browser.recipes.json').write_text(json.dumps(read(stage/'recipes-ready.json'),ensure_ascii=False,indent=2)+'\n')
    for j in built:shutil.copyfile(j['profile'],target/(j['id']+'.json'));shutil.copyfile(j['workbook'],target/(j['id']+'.xlsx'))
    current={j['id'] for j in built}
    for release in {s['recipe']['release'] for s in readings}:
        for stale in target.glob(f'emerging-{release.replace(".","").lower()}-sets-*'):
            if stale.stem not in current:stale.unlink()
    print('Published EMERGING indicators, scope and native-set downloads.')

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[3]);cli.add_argument('--stage',type=Path,required=True);cli.add_argument('--publish',action='store_true')
    args=cli.parse_args();readings,built=prepare(args.root,args.stage)
    if args.publish:publish(args.root,args.stage,readings,built)
