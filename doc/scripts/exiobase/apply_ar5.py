"""Apply validated EXIOBASE AR5 patches to staged and published aggregates."""
from __future__ import annotations
import datetime, hashlib, json, os, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
STAGE=pathlib.Path(os.environ.get('MARIO_EXIOBASE_STAGE',ROOT/'Output/exiobase-browser')).resolve()
PATCHES=pathlib.Path(os.environ.get('MARIO_EXIOBASE_AR5_PATCHES',STAGE/'ar5-patches')).resolve()
PUBLIC=ROOT/'doc/source/_static/data/economy'
sys.path.insert(0,str(ROOT/'doc/source/_static/reproduce'))
from economy_browser import annotate_ghg_method


def read(path):return json.loads(path.read_text())
def write(path,value):
    raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n'
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(raw);temp.replace(path)

def new_method(recipe):
    factors=recipe['ghg_factors']
    if recipe['parser_options'].get('unit') == 'Hybrid':
        recipe['ghg_method'] = ('GWP100: EDGAR-compatible IPCC AR5 for native CO₂ (1), CH₄ (28) and N₂O (265). '
            'Three-gas subtotal only; F-gases absent. Production and direct final-demand accounts are added once; '
            'the separate unregistered-waste extension is retained as published, with overlap unverified.')
        annotate_ghg_method(recipe)
        return
    g='GWP100: EDGAR-compatible IPCC AR5 for mass-reported CO₂ (1), CH₄ (28), N₂O (265), SF₆ (23,500)'
    if 'NF3 - air' in factors:g+=' and NF₃ (16,100)'
    g+='; HFC/PFC retain source CO₂-equivalents with unverified GWP basis. Biogenic CO₂ excluded. Production accounts; direct final-demand emissions calculated separately and included once in Whole economy.'
    if 'CH4_bio - combustion - air' not in factors:g+=' This release does not separately report biogenic combustion CH₄; its native combustion CH₄ row uses 28.'
    recipe['ghg_method']=g
    if 'ghg_coverage' in recipe:recipe['ghg_coverage']['gwp']='EDGAR-compatible IPCC AR5 GWP100 for native mass rows plus source-characterised HFC/PFC'
    annotate_ghg_method(recipe)

def apply_snapshot(snapshot,patch):
    recipe=snapshot['recipe']
    if recipe['parser_options'].get('unit') not in ('Monetary','Hybrid'):raise ValueError('Unexpected unit')
    recipe['ghg_factors']=patch['factors']
    new_method(recipe)
    target={r['code']:r for r in patch['regions']}
    if set(target)!={r['code'] for r in snapshot['regions']}:raise ValueError('Changed regions')
    for region in snapshot['regions']:
        p=target[region['code']]
        if len(p['ghg'])!=len(region['ghg']):raise ValueError('Changed sectors')
        region['ghg']=p['ghg'];region['household_ghg']=p['household_ghg']
    snapshot['provenance']['ghg_recharacterisation']={
        'method':'EDGAR-compatible IPCC AR5 GWP100 on native mass rows; source-characterised HFC/PFC retained',
        'factor_source':'https://ghgprotocol.org/sites/default/files/2024-08/Global-Warming-Potential-Values%20%28August%202024%29.pdf',
        'edgar_source':'https://edgar.jrc.ec.europa.eu/dataset_ghg2026',
        'paired_iot':patch['id'],
        'source_members':patch['validation']['source_members'],
        'old_ar6_reproduction_error':patch['validation']['old_max_relative_error']}
    snapshot['generated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    return snapshot

def main():
    jobs=read(STAGE/'inventory.json');ids={j['id'] for j in jobs}
    missing=ids-{p.stem for p in PATCHES.glob('*.json')}
    if missing:raise ValueError(f'Missing {len(missing)} patches: {sorted(missing)[:5]}')
    print('Validated',len(ids),'IOT patches.',flush=True)
    # Validate all inputs before any public mutation.
    plans=[]
    for ident in sorted(ids):
        patch=read(PATCHES/(ident+'.json'))
        if patch['id']!=ident or patch['validation']['old_max_relative_error']>1e-8:raise ValueError('Patch validation failed '+ident)
        for root in (STAGE/'readings'/ident, PUBLIC):
            path=root/(ident+'.json' if root==PUBLIC else 'snapshot.json')
            snapshot=read(path)
            if snapshot['recipe']['id']!=ident:raise ValueError('Snapshot identity mismatch')
            plans.append((path,apply_snapshot(snapshot,patch)))
    sut_ids=[]
    for folder in (STAGE/'readings').glob('exiobase-382-*-sut'):
        path=folder/'snapshot.json'
        if not path.exists():continue
        snapshot=read(path);ident=snapshot['recipe']['id'];year=snapshot['recipe']['year']
        patch=read(PATCHES/f'exiobase-382-{year}-ixi.json')
        iot_sectors=read(STAGE/'readings'/patch['id']/'snapshot.json')['recipe']['sectors']
        for root in (folder,PUBLIC):
            target=root/(ident+'.json' if root==PUBLIC else 'snapshot.json')
            content=read(target);sut_sectors=content['recipe']['sectors']
            if set(sut_sectors)!=set(iot_sectors) or len(sut_sectors)!=len(iot_sectors):
                raise ValueError('SUT/IOT sector mismatch '+ident)
            positions={name:i for i,name in enumerate(iot_sectors)}
            mapped_patch={**patch,'regions':[{**row,'ghg':[row['ghg'][positions[name]] for name in sut_sectors]} for row in patch['regions']]}
            plans.append((target,apply_snapshot(content,mapped_patch)))
        sut_ids.append(ident)
    hybrid_ids={'exiobase-hybrid-3318-2011-iot','exiobase-hybrid-3318-2011-sut'}
    for ident in sorted(hybrid_ids):
        patch=read(PATCHES/(ident+'.json'))
        if patch['id']!=ident or patch['validation']['old_max_relative_error']>1e-8:
            raise ValueError('Hybrid patch validation failed '+ident)
        path=PUBLIC/(ident+'.json')
        plans.append((path,apply_snapshot(read(path),patch)))
    updated=ids|set(sut_ids)|hybrid_ids
    for path,snapshot in plans:write(path,snapshot)
    # The staged HIOT predates the later GDP/GHG publication. Keep its snapshot
    # in sync so a future catalogue regeneration cannot replace the richer one.
    write(STAGE/'readings/exiobase-hybrid-3318-2011-iot/snapshot.json',
          read(PUBLIC/'exiobase-hybrid-3318-2011-iot.json'))
    # Refresh validation totals for staged IOT readings. SUT total comes from its paired IOT.
    for ident in ids:
        path=STAGE/'readings'/ident/'validation.json'
        if path.exists():
            val=read(path);patch=read(PATCHES/(ident+'.json'))
            val['world_ghg_tonnes']=patch['validation']['new_world_tonnes']
            val['ghg_characterisation']='EDGAR-compatible AR5 for native mass rows; source HFC/PFC retained'
            write(path,val)
    manifest_path=PUBLIC/'manifest.json';manifest=read(manifest_path)
    templates=manifest['templates'];old_templates=set(templates)
    keys=('source','release','dimension','parser_options','sectors','ghg_method','ghg_basis','gdp_basis','value_added_basis','source_url','license_url','parser_guide','ghg_factors','attribution','value_added_note','gdp_note','gdp_identity_status','gdp_quality_note','table','gdp_proxy','ghg_proxy','ghg_note','gwp_basis','gwp_horizon','final_demand_emissions_loaded','ghg_sectors','ghg_usable','ghg_unavailable_reason','ghg_quality_status','ghg_quality_sources','world_total_available','scope_note')
    for dataset in manifest['datasets']:
        ident=dataset['id']
        if ident not in updated:continue
        snapshot=read(PUBLIC/(ident+'.json'));recipe=snapshot['recipe']
        data={'recipe':{k:recipe[k] for k in keys if k in recipe},
              'regions':[{k:r[k] for k in ('code','name','iso3','kind')} for r in snapshot['regions']]}
        key=hashlib.sha256(json.dumps([data['recipe'],data['regions']],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
        templates[key]=data;dataset['template']=key
    live={d['template'] for d in manifest['datasets']}
    manifest['templates']={k:v for k,v in templates.items() if k in live}
    write(manifest_path,manifest)
    recipes_path=ROOT/'doc/economy_browser.recipes.json';recipes=read(recipes_path)
    changed=0
    for i,recipe in enumerate(recipes['recipes']):
        if recipe['id'] in updated:
            recipes['recipes'][i]=read(PUBLIC/(recipe['id']+'.json'))['recipe'];changed+=1
    if changed!=len(updated):raise ValueError(f'Updated only {changed}/{len(updated)} reproduction recipes')
    write(recipes_path,recipes)
    print(f'Updated {len(ids)} monetary IOT + {len(sut_ids)} monetary SUT + {len(hybrid_ids)} Hybrid readings, {changed} recipes, manifest templates {len(old_templates)} → {len(manifest["templates"])}.',flush=True)

if __name__=='__main__':main()
