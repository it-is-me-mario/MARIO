"""Prepare public assets from successful readings; share identical native sets."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "source/_static/reproduce"))
from economy_browser import annotate_ghg_method
import argparse,copy,gzip,hashlib,json,shutil,sys
from collect import ROOT,STAGE
OUT=ROOT/'doc/source/_static/data/economy';PROFILES=ROOT/'doc/source/_static/data/database_profiles'

def jsonread(path):return json.loads(path.read_text())
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')

def prepare():
 readings=[];profiles=[];groups={}
 for folder in sorted((STAGE/'readings').iterdir()):
  if not (folder/'snapshot.json').exists():continue
  snapshot=jsonread(folder/'snapshot.json');snapshot['recipe'].pop('sector_groups',None);profile=json.loads(gzip.decompress((folder/'profile.json.gz').read_bytes()))
  if snapshot['recipe']['parser_options']['unit']=='Monetary' and 'CH4_bio - combustion - air' not in snapshot['recipe']['ghg_factors'] and 'does not separately report biogenic combustion' not in snapshot['recipe']['ghg_method']:
   snapshot['recipe']['ghg_method']+=' This release does not separately report biogenic combustion CH₄; its native combustion CH₄ row uses 28.'
  if snapshot['recipe']['id']!=profile['id']:raise ValueError('Snapshot/profile ID mismatch')
  readings.append(snapshot);profiles.append(profile)
  # Equal counts are insufficient. Require the same native labels, units and
  # regional economic associations in the same source/release/table/system.
  key=digest({'release':profile['release'],'table':profile['table'],'system':snapshot['recipe']['parser_options'].get('system'),'sets':profile['sets'],'units':profile['units'],'region_items':profile['region_items']})
  groups.setdefault(key,[]).append((snapshot,profile))
 replacement_ids={f'exiobase-{group[0][0]["recipe"]["release"].replace(".","")}-{group[0][0]["recipe"]["parser_options"].get("system") or group[0][0]["recipe"]["table"].lower()}-sets-'+key[:8] for key,group in groups.items()}
 catalogue=jsonread(ROOT/'doc/source/_static/data/database_profiles.json')
 catalogue['profiles']=[p for p in catalogue['profiles'] if not(p['source']=='EXIOBASE' and p['guide']=='exiobase-monetary') and p['id'] not in replacement_ids|{p['id'] for p in profiles}]
 built=[]
 for key,group in groups.items():
  group.sort(key=lambda x:x[1]['year'],reverse=True);snapshot,profile=copy.deepcopy(group[0])
  years=sorted({p['year'] for _,p in group});profile['years']=years
  r=annotate_ghg_method(snapshot['recipe']);system=r['parser_options'].get('system') or r['table'].lower()
  identifier=f'exiobase-{r["release"].replace(".","")}-{system}-sets-'+key[:8]
  profile['id']=identifier;profile['label']=f'EXIOBASE {r["release"]} · {system} · {years[0]}–{years[-1]}'
  profile['readings']=[{'id':s['recipe']['id'],'year':p['year'],'source_url':s['recipe']['source_url'],'archive_url':p['provenance'].get('archive_url'),'archive_checksum':p['provenance'].get('archive_checksum'),'selected_members':p['provenance'].get('selected_members'),'counts':p['counts']} for s,p in group]
  folder=STAGE/'catalogue'/identifier;write(folder/'profile.json',profile)
  built.append({'id':identifier,'profile':str(folder/'profile.json'),'workbook':str(folder/'sets.xlsx'),'source_url':r['source_url'],'recipe':r['id']})
  fields=('id','guide','label','source','release','year','years','table','status','parsed_at','counts','provenance','region_counts','geography','classifications','coverage_signatures','set_flags')
  summary={k:profile[k] for k in fields if k in profile}
  # Reading-specific hashes live in the detailed profile, keeping catalogue
  # metadata small enough to embed in the geographical explorer.
  summary['provenance']={k:v for k,v in profile['provenance'].items() if k in ['parser','options','reading_scope','mario_version','source_url']}
  summary['workbook']=f'_static/data/database_profiles/{identifier}.xlsx';summary['detail']=f'_static/data/database_profiles/{identifier}.json';catalogue['profiles'].append(summary)
 write(STAGE/'catalogue-build.json',built);write(STAGE/'catalogue-ready.json',catalogue)
 existing=jsonread(OUT/'manifest.json');by_id={d['id']:jsonread(OUT/(d['id']+'.json')) for d in existing['datasets'] if d['source']!='EXIOBASE' or d['id'].startswith('exiobase-hybrid')}
 by_id.update({s['recipe']['id']:s for s in readings})
 snapshots=sorted(by_id.values(),key=lambda s:(-s['recipe']['year'],s['recipe']['label']))
 maps=jsonread(OUT/'sector-sections.json');old_mappings=list(maps['mappings'].values())
 if (STAGE/'hybrid-product-mapping.json').exists():maps['mappings']['exiobase-hybrid-3318-2011-iot']=jsonread(STAGE/'hybrid-product-mapping.json')
 for s in readings:
  r=annotate_ghg_method(s['recipe']);match=next((m for m in old_mappings if m['family']=='EXIOBASE' and set(e['native_label'] for e in m['entries'])==set(r['sectors'])),None)
  if match:
   m=copy.deepcopy(match);entries={e['native_label']:e for e in m['entries']};m['entries']=[{**entries[label],'index':i} for i,label in enumerate(r['sectors'])];m['source_url']=r['source_url'];maps['mappings'][r['id']]=m
 templates={};datasets=[]
 for s in snapshots:
  r=annotate_ghg_method(s['recipe']);regions=[{k:region[k] for k in ['code','name','iso3','kind']} for region in s['regions']]
  keys=['source', 'release', 'dimension', 'parser_options', 'sectors', 'ghg_method', 'ghg_basis', 'gdp_basis', 'value_added_basis', 'source_url', 'license_url', 'parser_guide', 'ghg_factors', 'attribution', 'value_added_note', 'gdp_note', 'table', 'gdp_proxy', 'ghg_proxy', 'ghg_note', 'gwp_basis', 'gwp_horizon', 'final_demand_emissions_loaded', 'ghg_sectors', 'ghg_usable', 'ghg_unavailable_reason', 'ghg_quality_status', 'ghg_quality_sources', 'world_total_available', 'scope_note']
  recipe={k:r[k] for k in keys if k in r};template_key=digest([recipe,regions])[:16]
  templates.setdefault(template_key,{'recipe':recipe,'regions':regions})
  d={k:r[k] for k in ['id','label','source','year','dimension','currency','gdp_bridge_verified'] if k in r}
  d.update(template=template_key,availability={metric:(metric!='ghg' or r.get('ghg_usable') is not False) and all(region.get(metric) is not None for region in s['regions']) for metric in ['gdp','value_added','ghg']});datasets.append(d)
 manifest={'schema_version':2,'datasets':datasets,'templates':templates,'world_bank_sha256':hashlib.sha256((STAGE/'world-bank-ready.json').read_bytes()).hexdigest()}
 write(STAGE/'manifest-ready.json',manifest);write(STAGE/'sections-ready.json',maps);write(STAGE/'recipes-ready.json',{'schema_version':1,'recipes':[s['recipe'] for s in snapshots]})
 print(f'Prepared {len(readings)} EXIOBASE readings, {len(groups)} exact native set groups, {len(templates)} lightweight browser templates.')
 return snapshots,built

def publish(snapshots,built):
 for item in built:
  workbook=Path(item['workbook'])
  if not workbook.exists():raise ValueError('Workbook not built: '+item['id'])
 for s in snapshots:write(OUT/(s['recipe']['id']+'.json'),s)
 shutil.copyfile(STAGE/'world-bank-ready.json',OUT/'world-bank.json')
 shutil.copyfile(STAGE/'manifest-ready.json',OUT/'manifest.json');shutil.copyfile(STAGE/'sections-ready.json',OUT/'sector-sections.json')
 # Recipes remain an independently usable input to the local full-parser runner.
 (ROOT/'doc/economy_browser.recipes.json').write_text(json.dumps(jsonread(STAGE/'recipes-ready.json'),ensure_ascii=False,indent=2)+'\n')
 shutil.copyfile(STAGE/'catalogue-ready.json',ROOT/'doc/source/_static/data/database_profiles.json')
 for item in built:
  shutil.copyfile(item['profile'],PROFILES/(item['id']+'.json'));shutil.copyfile(item['workbook'],PROFILES/(item['id']+'.xlsx'))
 print('Updated public aggregates, pinned references, native set downloads and catalogue.')

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--publish',action='store_true');args=cli.parse_args();snapshots,built=prepare()
 if args.publish:publish(snapshots,built)
