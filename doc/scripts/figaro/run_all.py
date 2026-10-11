"""Two bounded FIGARO workers with validated resume checkpoints."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import copy,json,sys,time,os,signal
import argparse
ROOT=Path(__file__).resolve().parents[3]
STAGE=None;SOURCE=None

def collect_job(job,stage):
    global STAGE
    STAGE=stage
    sys.path.insert(0,str(ROOT/'doc/scripts/figaro'))
    import collect_all as c
    folder=STAGE/'readings'/job['id']
    if (folder/'validation.json').exists():return json.loads((folder/'validation.json').read_text())
    print('START',job['id'],flush=True)
    cache=Path(job['cache']);files=[];factors,_=c.figaro._label_map(c.figaro.load_figaro_metadata(),level='f')
    seed=next(r for r in json.loads((ROOT/'doc/economy_browser.recipes.json').read_text())['recipes'] if r['source']=='FIGARO' and r.get('table')=='IOT')
    notebooks=json.loads((ROOT/'doc/database_catalogue.recipes.json').read_text())['recipes']
    try:
        if job['kind']=='sut':
            files.append(c.download(job['dataflows'][0],job['year'],cache,STAGE,row_dim='cpa2_1',col_dim='nace_r2'))
            files.append(c.download(job['dataflows'][1],job['year'],cache,STAGE,row_dim='prd_ava',col_dim='ind_use',include_dom=True,factor_codes=factors))
            job['files']=list(map(str,files));notebook=next(r for r in notebooks if r['id']=='figaro--01')
            result=c.collect_sut(job,STAGE,seed,notebook)
        else:
            mode='product' if job['kind']=='pxp' else 'industry'
            file=c.download(job['dataflows'][0],job['year'],cache,STAGE,row_dim='prd_ava' if mode=='product' else 'ind_ava',col_dim='prd_use' if mode=='product' else 'ind_use',include_dom=True,factor_codes=factors)
            job.update(path=str(file),filename=file.name,mode=mode,dataflow=job['dataflows'][0]);notebook=next(r for r in notebooks if r['id']=='figaro--02')
            result=c.local.collect(job,STAGE,seed,notebook)
            snapshot=json.loads((folder/'snapshot.json').read_text());snapshot['provenance'].update(api_updated=json.loads(file.with_suffix('.json').read_text())['api_updated'],retrieved_at='2026-10-10');c.write(folder/'snapshot.json',snapshot)
        print('VERIFIED',json.dumps(result),flush=True);return result
    except Exception as error:
        c.write(STAGE/'errors'/f'{job["id"]}.json',{'error':str(error),'type':type(error).__name__});raise

def run():
    jobs=json.loads((STAGE/'inventory.json').read_text())
    pending=[j for j in jobs if not(STAGE/'readings'/j['id']/'validation.json').exists()]
    print('RESUME',len(jobs)-len(pending),'verified; two workers;',len(pending),'remaining',flush=True)
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(collect_job,j,STAGE):j for j in pending}
        for future in as_completed(futures):
            job=futures[future];future.result()
            if all((STAGE/'readings'/f'figaro-{job["year"]}-{kind}'/'validation.json').exists() for kind in ['pxp','ixi','sut']):
                folder=STAGE/'online-only-pending';folder.mkdir(parents=True,exist_ok=True)
                (folder/f'{job["year"]}.json').write_text(json.dumps({'year':job['year'],'folder':job['cache']}))
                print('YEAR_COMPLETE',job['year'],job['cache'],flush=True)
    assert all((STAGE/'readings'/j['id']/'validation.json').exists() for j in jobs)
    (STAGE/'complete.json').write_text(json.dumps({'readings':len(jobs),'years':sorted({j['year'] for j in jobs}),'kinds':['pxp','ixi','SUT']}))
    print('COMPLETE',len(jobs),flush=True)

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--stage',type=Path,required=True)
    args=cli.parse_args();STAGE=args.stage
    # Inventory contains the explicit cache folder per reading; collect_all.py
    # creates it after probing the available official years.
    run()
