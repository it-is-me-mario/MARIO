"""Verify supplied local EMERGING bundles against release-specific published MD5 checksums."""
from pathlib import Path
import argparse,hashlib,json,sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))

def verify(stage):
    manifest=json.loads(Path(__file__).with_name('source-checksums.json').read_text())
    expected={(r['release'],r['filename']):r for r in manifest['files']}
    rows=[]
    for job in json.loads((stage/'inventory.json').read_text()):
        for key in ['path','co2_path']:
            if not job.get(key):continue
            p=Path(job[key]);reference=expected[(job.get('co2_release',job['release']) if key=='co2_path' else job['release'],p.name)];h=hashlib.md5()
            with p.open('rb') as stream:
                for block in iter(lambda:stream.read(4*1024**2),b''):h.update(block)
            if h.hexdigest()!=reference['md5']:raise ValueError(f'{job["id"]}: {p.name} differs from the published MD5')
            rows.append({'id':job['id'],**reference})
            print('Verified original',job['id'],p.name,flush=True)
    (stage/'source-md5-verification.json').write_text(json.dumps(rows,indent=2)+'\n')
    print('Verified',len(rows),'source files.')
    jobs=json.loads((stage/'inventory.json').read_text())
    if any(j['release']=='E' for j in jobs):verify_e_labels(stage,next(j for j in jobs if j['release']=='E'))


def verify_e_labels(stage,job):
    import gzip,pandas as pd,requests
    from mario.parsers import emerging
    folder=Path(job['path']).parent;local=folder/'Figure data.xlsx'
    published_md5='52b7768abcb1773ea9920cdde269a924'
    target=local if hashlib.md5(local.read_bytes()).hexdigest()==published_md5 else stage/'E-official-figure.xlsx'
    url='https://zenodo.org/records/18303090/files/Figure%20data.xlsx?download=1'
    if not target.exists():
        response=requests.get(url,timeout=25);response.raise_for_status();target.write_bytes(response.content)
    if hashlib.md5(target.read_bytes()).hexdigest()!=published_md5:raise ValueError('Published E figure workbook checksum differs')
    actual=pd.read_excel(local,sheet_name='Figure S4')['ISO3'].dropna().astype(str).tolist()
    expected=pd.read_excel(target,sheet_name='Figure S4')['ISO3'].dropna().astype(str).tolist()
    profile=json.loads(gzip.decompress((stage/'readings'/job['id']/'profile.json.gz').read_bytes()))
    if actual!=expected or profile['sets']['Region']!=expected:raise ValueError('EMERGING-E regional ordering differs from the published figure workbook')
    sectors=profile['sets']['Sector'];builtin=emerging._load_emerging_e_builtin_sectors()
    if [v.casefold() for v in sectors]!=[v.casefold() for v in builtin]:raise ValueError('EMERGING-E sector positions differ from the MARIO classification')
    candidates=[p for p in folder.glob('*.xlsx') if p.name!='Figure data.xlsx' and emerging._read_emerging_e_sector_labels_from_workbook(p,sector_count=len(sectors))==sectors]
    result={'regional_labels':{'filename':local.name,'local_sha256':hashlib.sha256(local.read_bytes()).hexdigest(),'published_md5':published_md5,'source_url':url,'region_count':len(expected),'ordering_verified':True},
        'sector_labels':{'sector_count':len(sectors),'builtin_casefold_order_verified':True,'workbooks':[{'filename':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in candidates]}}
    (stage/'e-label-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Verified EMERGING-E ordering:',len(expected),'regions and',len(sectors),'sectors.')

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--stage',type=Path,required=True)
    verify(cli.parse_args().stage)
