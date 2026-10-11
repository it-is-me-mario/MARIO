"""Catalogue every local OECD ICIO edition/year through the full MARIO parser.

Only top-level CSVs in the two explicitly supplied local directories are read.
No downloads, matrix inverses, or changes to source files are performed.
"""
from pathlib import Path
import argparse, copy, gc, gzip, hashlib, json, logging, sys, time
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'doc/scripts'), str(ROOT/'doc/source/_static/reproduce')]
import mario
from mario.parsers import oecd_icio
from database_catalogue import extract_profile
from economy_browser import aggregate

logging.getLogger('mario').setLevel(logging.ERROR)
ALIASES = {'CN1':'CHN', 'CN2':'CHN', 'MX1':'MEX', 'MX2':'MEX'}

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    if path.suffix == '.gz': raw = gzip.compress(raw)
    temp = path.with_suffix(path.suffix+'.tmp'); temp.write_bytes(raw); temp.replace(path)

def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4*1024**2), b''): h.update(chunk)
    return h.hexdigest()

def collect(path, edition, year, stage, seed, notebook):
    start = time.time()
    identifier = f'oecd-icio-{year}-{edition.lower()}'
    folder = stage/'readings'/identifier
    # The observer retains only the original factor rows. The full MARIO reader
    # and split-region normalisation still run unchanged, exactly once per CSV.
    original = oecd_icio._read_oecd_icio_frame
    observed = {}
    def read(*args, **kwargs):
        frame = original(*args, **kwargs)
        observed.update(factors=frame.loc[['VA','TLS']].copy(), shape=list(frame.shape))
        return frame
    with patch.object(oecd_icio, '_read_oecd_icio_frame', read):
        db = mario.parse_oecd(path=str(path), dataset='ICIO', year=year, calc_all=False)
    r = copy.deepcopy(seed)
    r.update(id=identifier, label=f'OECD ICIO · {edition}', release=edition, year=year,
             parser_options={'year':year, 'dataset':'ICIO'}, ghg_method='No emissions extension in this reading.')
    r.pop('sector_groups', None)
    parameters = {'path':str(path), **r['parser_options'], 'calc_all':False}
    job = {'id':identifier, 'label':f'OECD ICIO · {edition} · {year}', 'source':'OECD', 'release':edition, 'year':year}
    p = extract_profile(db, job=job, recipe=notebook, parameters=parameters)
    sets = p['sets']; r.update(sectors=sets['Sector'], regions=p['geography']['regions'], consumption_categories=sets['Consumption category'])
    factors = observed['factors']
    if not factors.columns.is_unique or not np.isfinite(factors.to_numpy()).all():
        raise ValueError('Original indicator rows contain duplicates or non-finite values')
    fd = {region:0.0 for region in sets['Region']}
    raw_va = {region:0.0 for region in sets['Region']}
    raw_taxes = {region:0.0 for region in sets['Region']}
    native_regions = set()
    for column in factors.columns:
        if '_' not in column: continue
        region, item = column.split('_',1)
        native_regions.add(region)
        parsed = ALIASES.get(region,region)
        if item in r['sectors']:
            raw_va[parsed] += float(factors.loc['VA',column])*r['currency_scale']
            raw_taxes[parsed] += float(factors.loc['TLS',column])*r['currency_scale']
        elif item in r['consumption_categories']:
            fd[parsed] += float(factors.loc['TLS',column])
            raw_taxes[parsed] += float(factors.loc['TLS',column])*r['currency_scale']
        else: raise ValueError('Unrecognised source column '+column)
    rows = aggregate(db,r,fd)
    max_error = 0.0
    for region in rows:
        code = region['code']; va = sum(region['value_added'])
        for actual, expected in [(va,raw_va[code]),(region['net_product_taxes'],raw_taxes[code]),(region['gdp'],raw_va[code]+raw_taxes[code])]:
            if not np.isclose(actual,expected,rtol=1e-12,atol=.05):
                raise ValueError(f'Raw/parsed indicator mismatch: {identifier} {code}: {actual} vs {expected}')
            max_error = max(max_error, abs(actual-expected))
        if 'ghg' in region: raise ValueError('ICIO must not acquire an emissions indicator')
    r['gdp_bridge_verified'] = True
    r['attribution'] = f'OECD ICIO, {edition}, {year}. Indicators calculated with MARIO; cite OECD.'
    prov = p['provenance']
    prov.update(mario_version=mario.__version__, source_url=r['source_url'], input_filename=path.name,
                input_sha256=digest_file(path), input_bytes=path.stat().st_size,
                reading_scope='Full local MARIO ICIO parse (Z, Y, V, E, EY), calc_all=False; raw VA/TLS totals independently reconciled by country.',
                raw_shape=observed['shape'], raw_region_count=len(native_regions),
                split_region_handling='CN1/CN2 are summed into CHN; MX1/MX2 into MEX. National placeholder columns do not add extra VA.' if edition=='Extended' else 'Original national regions retained.')
    snapshot = {'schema_version':1,'recipe':r,'regions':rows,'generated_at':p['parsed_at'],'provenance':prov}
    validation = {'id':identifier, 'counts':p['counts'], 'raw_region_count':len(native_regions),
                  'max_raw_parsed_error_usd':max_error, 'world_value_added_usd':sum(sum(row['value_added']) for row in rows),
                  'world_gdp_usd':sum(row['gdp'] for row in rows), 'seconds':round(time.time()-start,2)}
    write(folder/'profile.json.gz',p); write(folder/'snapshot.json',snapshot); write(folder/'validation.json',validation)
    del db, p, factors, rows; gc.collect()
    return validation

if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--extended',type=Path,required=True); cli.add_argument('--regular',type=Path,required=True)
    cli.add_argument('--stage',type=Path,required=True); cli.add_argument('--limit',type=int)
    args = cli.parse_args()
    seed = json.loads((ROOT/'doc/source/_static/data/economy/oecd-icio-2022-extended.json').read_text())['recipe']
    notebook = next(r for r in json.loads((ROOT/'doc/database_catalogue.recipes.json').read_text())['recipes'] if r['id']=='oecd--01')
    jobs = []
    for edition, directory, suffix in [('Extended',args.extended,''),('Regular',args.regular,'_SML')]:
        directory = directory.resolve()
        if directory.name != edition: raise ValueError('Supply the explicit '+edition+' directory')
        for path in sorted(directory.glob('*.csv')):
            stem = path.stem.removesuffix(suffix) if suffix else path.stem
            if not (len(stem)==4 and stem.isdecimal() and path.name==stem+suffix+'.csv'): continue
            if not path.is_file() or not path.stat().st_blocks: raise ValueError('CSV is not hydrated locally: '+str(path))
            jobs.append((path,edition,int(stem)))
    if args.limit: jobs=jobs[:args.limit]
    if not jobs: raise ValueError('No local ICIO CSVs found')
    write(args.stage/'inventory.json',[{'edition':e,'year':y,'filename':p.name,'bytes':p.stat().st_size} for p,e,y in jobs])
    results=[]
    for path, edition, year in jobs:
        result=collect(path,edition,year,args.stage,seed,notebook); results.append(result)
        write(args.stage/'run-report.json',results)
        print(f'{len(results)}/{len(jobs)} {edition} {year}: {result["counts"]} ({result["seconds"]}s)',flush=True)
    print('Completed',len(results),'full local ICIO parses.',flush=True)
