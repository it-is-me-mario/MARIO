"""Parse every supplied local EMERGING release/year with MARIO, one process per file."""
from pathlib import Path
import argparse,copy,gzip,hashlib,json,logging,subprocess,sys,time
import numpy as np
import h5py
from scipy.io import loadmat

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'doc/scripts'),str(ROOT/'doc/source/_static/reproduce')]
import mario
from mario.parsers import emerging
from database_catalogue import extract_profile
from economy_browser import aggregate
logging.getLogger('mario').setLevel(logging.ERROR)
RECORDS={'1.0':'10956623','2.0':'17557778','2.2':'19461860','E':'18303090'}
# EMERGING-E publishes no CO2 companion; the standard 2.2 companion for the same year is projected by the parser.
E_CO2_RELEASE='2.2'
E_PROJECTION_NOTE=' EMERGING-E has no published CO2 companion: the EMERGING 2.2 companion for the same year (133 sectors) is projected onto the 146 EMERGING-E sectors; aggregated electricity CO2 is assigned to the 14 electricity technologies by fuel.'

def configure_indicators(recipe, has_co2):
    """Reviewed presentation proxies; preserve the original native VA/CO2 data."""
    recipe.update(gdp_proxy='native_value_added', gdp_bridge_verified=False,
      gdp_basis='GDP proxy: value added (no product-tax detail in source)',
      gdp_note='EMERGING: GDP is approximated by value added. The source table does not break out product taxes, so no adjustment to market prices is applied.',
      value_added_note='Sum of the native value added row. The source table does not break out product taxes separately.',
      final_demand_emissions_loaded=False,
      ghg_factors={name:1e6 for name in emerging.EMERGING_CO2_LABELS} if has_co2 else {},
      ghg_proxy='fossil_co2_only' if has_co2 else None,
      ghg_basis='Fossil CO2 by fuel; incomplete GHG proxy' if has_co2 else 'Emissions unavailable',
      gwp_basis='CO2 only (GWP = 1 under AR5 and AR6)' if has_co2 else None,
      gwp_horizon=100 if has_co2 else None,
      ghg_method=('Fossil CO2 summed across seven native fuel accounts. Source Mt CO2eq converted to tonnes using 1e6. CO2 has GWP 1 under AR5 and AR6; no CH4, N2O or F-gases are included. No direct final-demand emissions are supplied.'+(E_PROJECTION_NOTE if recipe.get('release')=='E' else '')) if has_co2 else 'No matching local CO2 companion; emissions are unavailable.',
      ghg_note=('EMERGING: GHG is a fossil CO2-only proxy (seven fuel accounts). CH4, N2O, F-gases and direct final-demand emissions are not included.'+(E_PROJECTION_NOTE if recipe.get('release')=='E' else '')) if has_co2 else None)
    return recipe

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if path.suffix=='.gz':raw=gzip.compress(raw)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_bytes(raw);temp.replace(path)

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024**2),b''):h.update(chunk)
    return h.hexdigest()

def jobs_at(base):
    jobs=[]
    for release,folder,pattern in [('2.0','2.0','EMERGING_V2_*_m.mat'),('2.2','2.2','EMERGING_V2_*_m.mat'),('1.0','1.0','global_mrio_*.mat'),('E','EMERGING-E','EMERGING_E_*.mat')]:
        for path in sorted((base/folder).glob(pattern)):
            year=int(path.stem.split('_')[2] if release in {'2.0','2.2','E'} else path.stem.split('_')[-1])
            co2_release=E_CO2_RELEASE if release=='E' else release
            co2=base/co2_release/f'EMERGING_CO2_{year}.mat' if release=='E' else path.parent/f'EMERGING_CO2_{year}.mat'
            jobs.append({'id':f'emerging-{release.replace(".","").lower()}-{year}', 'release':release,'year':year,'path':str(path),'co2_path':str(co2) if co2.exists() else None,'co2_release':co2_release})
    if not jobs:raise ValueError('No economic EMERGING bundles in the supplied directories')
    return jobs

def native_co2(job,region_count,sector_count):
    """Companion CO2 in the reading's native region x sector rows, seven fuel columns."""
    raw=np.asarray(loadmat(job['co2_path'])['CO2'],dtype=float)
    if job['release']!='E':return raw
    projected=emerging._project_standard_emerging_power_co2_to_emerging_e(raw,region_positions=list(range(region_count)),sector_count=sector_count).T
    if not np.isclose(projected.sum(),raw.sum(),rtol=1e-12,atol=0):raise ValueError('EMERGING-E CO2 projection does not conserve the companion total')
    return projected

def flow_totals(frame):
    # Sum sparse columns without densifying or allocating a second full COO matrix.
    rows=np.zeros(frame.shape[0]);columns=np.zeros(frame.shape[1])
    for i in range(frame.shape[1]):
        array=frame.iloc[:,i].array
        if hasattr(array,"sp_values") and array.fill_value==0:
            values=array.sp_values;indices=array.sp_index.indices
            np.add.at(rows,indices,values);columns[i]=values.sum()
        else:
            values=np.asarray(array,dtype=float);rows+=values;columns[i]=values.sum()
    return rows,columns

def collect(job,stage):
    start=time.time();path=Path(job['path']);variant='E' if job['release']=='E' else 'standard'
    print('START',job['id'],path.name,'local' if path.stat().st_blocks else 'hydrating from OneDrive',flush=True)
    options={'table':'IOT','year':job['year'],'variant':variant,'calc_all':False}
    if job['co2_path']:options['co2_path']=job['co2_path']
    db=mario.parse_emerging(path=str(path),**options)
    if db.table_type!='IOT' or int(db.meta.year)!=job['year']:raise ValueError('Unexpected table or year')
    seed='emerging-e-2018-iot' if variant=='E' else 'emerging-22-2023-co2'
    recipe=copy.deepcopy(json.loads((ROOT/'doc/source/_static/data/economy'/f'{seed}.json').read_text())['recipe'])
    release=job['release'];recipe.update(id=job['id'],release=release,year=job['year'],label='EMERGING-E' if variant=='E' else f'EMERGING {release}',
      source_url=f'https://zenodo.org/records/{RECORDS[release]}',parser_options={k:v for k,v in options.items() if k not in {'calc_all','co2_path'}},
      attribution=f'EMERGING {release}, {job["year"]}, doi:10.5281/zenodo.{RECORDS[release]}. CC BY 4.0; indicators calculated with MARIO.')
    notebook=next(r for r in json.loads((ROOT/'doc/database_catalogue.recipes.json').read_text())['recipes'] if r['id']==('emerging--02' if variant=='E' else 'emerging--03'))
    profile=extract_profile(db,job={**job,'source':'EMERGING','label':recipe['label'],'guide':'emerging'},recipe=notebook,parameters={'path':str(path),**options})
    recipe.update(sectors=profile['sets']['Sector'],regions=profile['geography']['regions'],consumption_categories=profile['sets']['Consumption category'],
      expected_units={name:frame['unit'].astype(str).to_dict() for name,frame in db.units.items()},ghg_factors={},gdp_bridge_verified=False)
    recipe.pop('sector_groups',None)
    if profile['geography']['unresolved_count']:raise ValueError('Unresolved native region labels')
    configure_indicators(recipe, bool(job['co2_path']))
    rows=aggregate(db,recipe)
    with h5py.File(path,'r') as handle:
        group=emerging._resolve_emerging_e_container(handle) if variant=='E' else emerging._resolve_emerging_container(handle)
        raw_va=np.asarray(group['MRIO_VA_E' if variant=='E' else 'va'][()]).reshape(-1)
        raw_regions=db.get_index('Region');nsectors=len(recipe['sectors'])
        if raw_va.size!=len(raw_regions)*nsectors:raise ValueError('Source VA dimensions disagree with parsed sets')
        raw_va=raw_va.reshape(len(raw_regions),nsectors)*recipe['currency_scale']
        actual=np.asarray([r['value_added'] for r in rows]);raw_by_code=dict(zip(raw_regions,raw_va))
        expected=np.asarray([raw_by_code[r['code']] for r in rows])
        if not np.allclose(actual,expected,rtol=1e-12,atol=1e-3):raise ValueError('Raw and parsed VA disagree')
        source_keys=sorted(group.keys())
        source_x=np.asarray(group['MRIO_X_E' if variant=='E' else 'X'][()]).reshape(-1)
    z_rows,z_columns=flow_totals(db.get_block('Z'));y_rows,_=flow_totals(db.get_block('Y'))
    source_va=raw_va.reshape(-1)/recipe['currency_scale']
    denominator=np.abs(source_x).sum()
    flow_errors={"relative_output_balance_error":float(np.abs(z_rows+y_rows-source_x).sum()/denominator),
                 "relative_input_balance_error":float(np.abs(z_columns+source_va-source_x).sum()/denominator)}
    if max(flow_errors.values())>5e-6:raise ValueError('Parsed Z/Y/V do not reconcile to source X: '+str(flow_errors))
    co2_validation={}
    if job['co2_path']:
        co2=native_co2(job,len(raw_regions),nsectors)
        if co2.shape!=(len(raw_regions)*nsectors,7):raise ValueError('Companion CO2 dimensions do not match this release')
        actual_co2=db.get_block('E').to_numpy()
        if not np.array_equal(actual_co2,co2.T):raise ValueError('Raw and parsed CO2 disagree')
        co2_validation={'source_co2_shape':list(co2.shape),'co2_native_total':float(co2.sum()),'co2_sha256':sha(Path(job['co2_path'])),'co2_source_release':job['co2_release']}
    if any(r['gdp'] != sum(r['value_added']) for r in rows):raise ValueError('GDP proxy must equal native VA exactly')
    if bool(job['co2_path']) != all('ghg' in r for r in rows):raise ValueError('GHG proxy availability must match the native companion')
    provenance=profile['provenance'];provenance.update(mario_version=mario.__version__,source_url=recipe['source_url'],input_filename=path.name,input_sha256=sha(path),
      reading_scope='Full MARIO economic parse, calc_all=False. Every native VA/CO2 cell reconciled; parsed supplying-row Z, Y and V reconcile to source X.', flow_validation=flow_errors,source_keys=source_keys)
    if job['co2_path']:
        provenance['emissions']={'filename':Path(job['co2_path']).name,'release':job['co2_release'],'sha256':co2_validation['co2_sha256'],'year':job['year'],'boundary':'Fossil CO2 by fuel; not a complete GHG inventory.'}
        if release=='E':provenance['emissions']['projection']=E_PROJECTION_NOTE.strip()
    snapshot={'schema_version':1,'recipe':recipe,'regions':rows,'generated_at':profile['parsed_at'],'provenance':provenance}
    validation={'id':job['id'],'release':release,'year':job['year'],'counts':profile['counts'],'max_raw_parsed_va_error_usd':float(np.max(np.abs(actual-expected))),
      'world_value_added_usd':float(actual.sum()),'input_sha256':provenance['input_sha256'],'seconds':round(time.time()-start,2),'flow_verified':True,'indicator_proxies_verified':True,**flow_errors,**co2_validation}
    folder=stage/'readings'/job['id'];write(folder/'snapshot.json',snapshot);write(folder/'profile.json.gz',profile);write(folder/'validation.json',validation)
    print('DONE',job['id'],profile['counts'],validation['seconds'],'s',flush=True)

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--base',type=Path,required=True);cli.add_argument('--stage',type=Path,required=True);cli.add_argument('--id');cli.add_argument('--limit',type=int);cli.add_argument('--release',help='Collect and publish only this release, e.g. E')
    args=cli.parse_args();jobs=[j for j in jobs_at(args.base) if not args.release or j['release']==args.release]
    if args.id:collect(next(j for j in jobs if j['id']==args.id),args.stage)
    else:
        write(args.stage/'inventory.json',jobs)
        for job in jobs[:args.limit] if args.limit else jobs:
            validation=args.stage/'readings'/job['id']/'validation.json'
            if not validation.exists() or not all(json.loads(validation.read_text()).get(k) for k in ['flow_verified','indicator_proxies_verified']):
                subprocess.run([sys.executable,__file__,'--base',str(args.base),'--stage',str(args.stage),'--id',job['id']],check=True)
            reports=[json.loads(p.read_text()) for p in sorted((args.stage/'readings').glob('*/validation.json'))]
            write(args.stage/'run-report.json',reports)
        print('Completed',len(reports),'EMERGING readings.',flush=True)
