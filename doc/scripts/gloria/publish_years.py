"""Prepare validated GLORIA years with one shared native-set profile.

Run prepare, update the shared workbook with build_sets.mjs, then --publish.
The 2024 profile/download identifier remains stable for existing links.
"""
from pathlib import Path
import argparse,copy,hashlib,json,shutil,sys
HERE=Path(__file__).resolve().parent
DOC=HERE.parents[1]
sys.path[:0]=[str(DOC/'scripts'),str(HERE)]
from build_economy_browser import publish as publish_indicators
from build_extension_scope import period

SOURCE_COVERAGE = {
    'first_year': 1990, 'last_year': 2029, 'forecast_from': 2024,
    'source_document': 'GLORIA_ReleaseNotes_060.pdf',
    'source_url': 'https://ielab.info/resources/gloria/supportingdocs',
}
SOURCE_COVERAGE_NOTE = 'Publisher series: 1990–2029; 2024–2029 are forecasts in the v060 release notes. Only the listed local years are verified in this explorer.'


def read(path):return json.loads(path.read_text())


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')


def signature(profile):
    fields={'sets':profile['sets'],
        'units':sorted(profile['units'],key=lambda u:(u['set'],str(u['index']))),
        'region_items':sorted(profile['region_items'],key=lambda r:(r['region'],r['set'],r['label']))}
    return hashlib.sha256(json.dumps(fields,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def prepare(stage,doc):
    stage,doc=Path(stage),Path(doc);data=doc/'source/_static/data';out=stage/'public';economy=out/'economy'
    snapshots=[];profiles=[]
    for folder in sorted(stage.glob('gloria-060-*-sut')):
        if not (folder/'validation.json').is_file():continue
        s,p=read(folder/'snapshot.json'),read(folder/'profile.json')
        if not s['recipe'].get('gdp_bridge_verified'):raise ValueError('Unverified GDP bridge')
        snapshots.append(s);profiles.append(p)
    if not snapshots:raise ValueError('No validated new GLORIA years')
    original=read(data/'database_profiles/gloria-060-2024-sut.json')
    if any(signature(p)!=signature(original) for p in profiles):raise ValueError('GLORIA native sets changed: create a separate scope profile')
    existing=read(data/'economy/manifest.json')
    combined={d['id']:read(data/'economy'/f"{d['id']}.json") for d in existing['datasets'] if d['source']=='GLORIA'}
    combined.update({s['recipe']['id']:s for s in snapshots})
    ordered=sorted(combined.values(),key=lambda s:s['recipe']['year'])
    # Stage only modified public assets. Source matrices stay outside publication.
    economy.mkdir(parents=True,exist_ok=True)
    for name in ['manifest.json','world-bank.json']:
        shutil.copyfile(data/'economy'/name,economy/name)
    for snapshot in snapshots:
        r=snapshot['recipe'];publish_indicators(r,snapshot['regions'],snapshot['provenance'],economy)
    group=copy.deepcopy(original);group.update(label='GLORIA 060 · SUT',years=[s['recipe']['year'] for s in ordered])
    group['readings']=[{'id':s['recipe']['id'],'year':s['recipe']['year'],'source_url':s['recipe']['source_url'],
        'counts':original['counts'],'precision':s['recipe'].get('parser_options',{}).get('dtype','float32'),
        'source_members':{k:s['provenance'].get(k) for k in ['economic_members','satellite_members'] if s['provenance'].get(k)}} for s in ordered]
    group['source_coverage'] = SOURCE_COVERAGE
    group['scope_note']='GLORIA 060 / '+', '.join(map(str,group['years']))+': identical native sets verified across readings. GDP includes signed product-tax valuations; native GHG characterisation is retained. '+SOURCE_COVERAGE_NOTE
    write(out/'database_profiles'/f"{group['id']}.json",group)
    workbook=stage/'workbook'/group['id'];write(workbook/'profile.json',group)
    catalogue=read(data/'database_profiles.json');summary=next(p for p in catalogue['profiles'] if p['id']==group['id'])
    for key in ['label','years','scope_note','source_coverage']:summary[key]=group[key]
    write(out/'database_profiles.json',catalogue)
    mappings=read(data/'economy/sector-sections.json');base=mappings['mappings'][group['id']]
    for snapshot in snapshots:
        if [e['native_label'] for e in base['entries']]!=snapshot['recipe']['sectors']:raise ValueError('Changed GLORIA classification labels')
        mappings['mappings'][snapshot['recipe']['id']]=copy.deepcopy(base)
    write(economy/'sector-sections.json',mappings)
    recipes=read(doc/'economy_browser.recipes.json');new={s['recipe']['id']:s['recipe'] for s in snapshots}
    recipes['recipes']=[r for r in recipes['recipes'] if r['id'] not in new]+list(new.values());write(out/'economy_browser.recipes.json',recipes)
    scope=read(data/'economy/country-scope.json');target=next(p for p in scope['profiles'] if p['id']==group['id'])
    manifest=read(economy/'manifest.json');by_id={d['id']:d for d in manifest['datasets']}
    ids=[s['recipe']['id'] for s in ordered]
    target.update(years=group['years'],reading_ids=ids,reading_years={s['recipe']['id']:s['recipe']['year'] for s in ordered},
        availability={id:by_id[id]['availability'] for id in ids},
        indicator_flags={s['recipe']['id']:{k:bool(s['recipe'].get(k)) for k in ['gdp_proxy','ghg_proxy']} for s in ordered},scope_note=group['scope_note'],source_coverage=group['source_coverage'])
    write(economy/'country-scope.json',scope)
    # An annual refresh changes availability, not reviewed concordances or
    # display policies. Rebuilding the graph here would overwrite later
    # editorial review (e.g. GTAP Power placement and Hybrid defaults).
    sectoral=read(data/'economy/sectoral-scope.json')
    for columns in sectoral['columns'].values():
        for column in columns:
            if column['family']=='GLORIA':
                column['years']=group['years']
    write(economy/'sectoral-scope.json',sectoral)
    extensions=read(data/'economy/extension-scope.json')
    readings=[r for f in extensions['families'] if f['family']=='GLORIA'
        for v in f['variants'] for r in v['readings'] if r['id']==group['id']]
    if len(readings)!=1:raise ValueError('Expected one shared GLORIA extension profile')
    readings[0]['years']=period(group['years'])
    write(economy/'extension-scope.json',extensions)
    write(stage/'publication.json',{'new_ids':list(new),'shared_profile':group['id'],'years':group['years'],'native_signature':signature(group)})
    print('Prepared GLORIA',group['years'],'with one native-set profile')


def publish(stage,doc):
    stage,doc=Path(stage),Path(doc);report=read(stage/'publication.json');out=stage/'public';target=doc/'source/_static/data'
    workbook=stage/'workbook'/report['shared_profile']/'sets.xlsx'
    if not workbook.is_file():raise ValueError('Build the reviewed shared native-set workbook before publication')
    for source in out.rglob('*.json'):
        relative=source.relative_to(out)
        dest=doc/'economy_browser.recipes.json' if relative.name=='economy_browser.recipes.json' else target/relative
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    shutil.copyfile(workbook,target/'database_profiles'/f"{report['shared_profile']}.xlsx")
    for id in report['new_ids']:
        year=read(stage/id/'snapshot.json')['recipe']['year']
        shutil.copyfile(stage/id/'gdp-bridge.json',doc/'scripts/gloria'/f'gdp-bridge-{year}.json')
    print('Published GLORIA',report['years'],'without duplicated native sets')


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--stage',type=Path,required=True);cli.add_argument('--doc',type=Path,default=DOC);cli.add_argument('--publish',action='store_true');args=cli.parse_args()
    (publish if args.publish else prepare)(args.stage,args.doc)
