"""Prepare and publish verified local FIGARO IOT browser assets."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "source/_static/reproduce"))
from economy_browser import annotate_ghg_method
import argparse, copy, csv, gzip, hashlib, json, shutil

def read(path): return json.loads(path.read_text())
def digest(value): return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')

def set_signature(profile):
    return digest({key:profile[key] for key in ['table','sets','units','native_codes','region_items']})

def prepare(root,stage):
    out=root/'doc/source/_static/data/economy'
    readings=[]; groups={}
    existing={}
    for summary in read(root/'doc/source/_static/data/database_profiles.json')['profiles']:
        if summary['source']=='FIGARO':
            profile=read(root/'doc/source'/summary['detail'])
            existing[set_signature(profile)]=summary['id']
    for folder in sorted((stage/'readings').iterdir()):
        s=read(folder/'snapshot.json'); p=json.loads(gzip.decompress((folder/'profile.json.gz').read_bytes()))
        if s['recipe']['id']!=p['id']: raise ValueError('Snapshot/profile ID mismatch')
        s['recipe']['release']=p['release']=''
        readings.append(s)
        s['recipe']['parser_options'].pop('unit',None)
        p['provenance']['options'].pop('unit',None)
        p['provenance']['eurostat_unit']='MIO_EUR'
        reviewed=next(recipe for recipe in read(root/'doc/database_catalogue.recipes.json')['recipes'] if recipe['id']==('figaro--01' if p['table']=='SUT' else 'figaro--02'))
        p['provenance'].update(notebook=reviewed['notebook'],cell=reviewed['cell'],recipe=reviewed['id'],fingerprint=reviewed['fingerprint'])
        if 'independent accuracy test' not in s['recipe']['gdp_note']:
            s['recipe']['gdp_note']+=' FIGARO compilation uses national-accounts aggregates and World Bank world GDP; this comparison is not an independent accuracy test.'
        s['provenance'].update(p['provenance'])
        metadata=list(csv.DictReader((root/'mario/parsers/figaro_metadata.csv').open(encoding='utf-8-sig')))
        for name,level in [('Factor of production','f'),('Consumption category','n')]:
            lookup={row['Name']:row['Code'] for row in metadata if row['Level']==level}
            p['native_codes'][name]={label:lookup[label] for label in p['sets'][name]}
        p['environmental']=False
        k=set_signature(p)
        groups.setdefault(k,[]).append((s,p))
    inventory=read(stage/'inventory.json')
    expected={j['id'] for j in inventory}
    if {s['recipe']['id'] for s in readings}!=expected: raise ValueError('Incomplete or stale staged FIGARO inventory')
    if len(readings)!=len(inventory): raise ValueError('Incomplete staged FIGARO readings')
    catalogue=read(root/'doc/source/_static/data/database_profiles.json')
    catalogue['profiles']=[p for p in catalogue['profiles'] if p['source']!='FIGARO']
    built=[]
    for k,group in groups.items():
        group.sort(key=lambda item:item[1]['year'],reverse=True)
        s,p=copy.deepcopy(group[0]); years=sorted({p['year'] for _,p in group})
        kind='sut' if p['table']=='SUT' else 'pxp' if s['recipe']['parser_options']['iot_mode']=='product' else 'ixi'
        identifier=existing.get(k) or f'figaro-{kind}-sets-{k[:8]}'
        p.update(id=identifier,years=years,label=f'FIGARO · {p["table"]}'+(f' · {kind}' if kind!='sut' else '')+f' · {years[0]}–{years[-1]}')
        p['readings']=[{'id':r['recipe']['id'],'year':q['year'],'filename':q['provenance']['input_filename'],
                        'sha256':q['provenance']['input_sha256'],'counts':q['counts'],
                        'raw_region_count':q['counts']['Region'],'dataflow':q['provenance']['dataflow'],
                        'source_files':q['provenance'].get('source_files',[])} for r,q in group]
        folder=stage/'catalogue'/identifier; write(folder/'profile.json',p)
        built.append({'id':identifier,'profile':str(folder/'profile.json'),'workbook':str(folder/'sets.xlsx'),'source_url':s['recipe']['source_url']})
        fields=('id','guide','label','source','release','year','years','table','status','parsed_at','counts','region_counts','geography','classifications','coverage_signatures','set_flags','price_basis','world_total_available','scope_note','environmental')
        summary={name:p[name] for name in fields if name in p}
        summary['provenance']={name:p['provenance'][name] for name in ['parser','options','reading_scope','mario_version','source_url','eurostat_unit','classification_url']}
        summary['workbook']=f'_static/data/database_profiles/{identifier}.xlsx'; summary['detail']=f'_static/data/database_profiles/{identifier}.json'
        catalogue['profiles'].append(summary)
    old=read(out/'manifest.json')
    snapshots=[read(out/(d['id']+'.json')) for d in old['datasets'] if d['source']!='FIGARO']+readings
    snapshots.sort(key=lambda s:(-s['recipe']['year'],s['recipe']['label']))
    maps=read(out/'sector-sections.json')
    product_base=copy.deepcopy(next(m for m in maps['mappings'].values() if m['family']=='FIGARO'))
    activity_base=copy.deepcopy(next(m for m in maps['mappings'].values() if m['family']=='WIOD' and m['classification_id']=='nace-2-wiod'))
    maps['mappings']={key:m for key,m in maps['mappings'].items() if m['family']!='FIGARO'}
    product_base.update(classification='CPA 2.1',classification_id='cpa-2.1',classification_url='https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_fcp_esms.htm')
    activity_base["sections"].pop("R+S",None)
    activity_base["sections"].update(R="Arts, entertainment and recreation",S="Other service activities")
    activity_base.update(family='FIGARO',classification='NACE Rev.2',classification_id='nace-2',source_url=product_base['source_url'],classification_url='https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_fcp_esms.htm')
    def native_mapping(base,profile,dimension):
        mapping=copy.deepcopy(base);code_by_label=profile['native_codes'][dimension]
        labels=profile['sets'][dimension]
        mapping['entries']=[{'index':i,'native_label':label,'native_code':code_by_label[label],'section':code_by_label[label].removeprefix('CPA_')[0]} for i,label in enumerate(labels)]
        if any(e['section'] not in mapping['sections'] for e in mapping['entries']):raise ValueError('Unknown FIGARO section')
        mapping['dimension']=dimension;mapping.pop('additional_mappings',None);return mapping
    for snapshot,profile in [pair for group in groups.values() for pair in group]:
        recipe=annotate_ghg_method(snapshot['recipe'])
        activity=recipe['table']=='SUT' or recipe['parser_options'].get('iot_mode')=='industry'
        dimension='Activity' if recipe['table']=='SUT' else 'Sector'
        mapping=native_mapping(activity_base if activity else product_base,profile,dimension)
        if recipe['table']=='SUT':mapping['additional_mappings']=[native_mapping(product_base,profile,'Commodity')]
        maps['mappings'][recipe['id']]=mapping
    templates={}; datasets=[]
    for s in snapshots:
        r=annotate_ghg_method(s['recipe']); regions=[{k:region[k] for k in ['code','name','iso3','kind']} for region in s['regions']]
        fields=['source','release','dimension','parser_options','sectors','ghg_method','ghg_basis','gdp_basis','value_added_basis','source_url','license_url','parser_guide','ghg_factors','attribution','value_added_note','gdp_note', 'table', 'gdp_proxy', 'ghg_proxy', 'ghg_note', 'gwp_basis', 'gwp_horizon', 'final_demand_emissions_loaded', 'ghg_sectors','price_basis','price_note','scope_note','world_total_available']
        recipe={k:r[k] for k in fields if k in r}
        template_key=digest([recipe,regions])[:16]
        templates.setdefault(template_key,{'recipe':recipe,'regions':regions})
        d={k:r[k] for k in ['id','label','source','year','dimension','currency','gdp_bridge_verified'] if k in r}
        d.update(template=template_key,availability={metric:all(region.get(metric) is not None for region in s['regions']) for metric in ['gdp','value_added','ghg']})
        datasets.append(d)
    manifest={'schema_version':2,'datasets':datasets,'templates':templates,'world_bank_sha256':old['world_bank_sha256']}
    write(stage/'manifest-ready.json',manifest); write(stage/'sections-ready.json',maps)
    write(stage/'catalogue-ready.json',catalogue); write(stage/'catalogue-build.json',built)
    write(stage/'recipes-ready.json',{'schema_version':1,'recipes':[s['recipe'] for s in snapshots]})
    print(f'Prepared {len(readings)} FIGARO readings; {len(groups)} native-set inventories; {len(datasets)} public readings.')
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
    print('Published FIGARO aggregates, grouped set inventories, geography and native sector mappings.')

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__); cli.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[3]); cli.add_argument('--stage',type=Path,required=True); cli.add_argument('--publish',action='store_true')
    args=cli.parse_args(); readings,built=prepare(args.root,args.stage)
    if args.publish: publish(args.root,args.stage,readings,built)
