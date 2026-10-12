"""Refresh reviewed presentation proxies from verified VA snapshots and CO2 files.

The full economic bundle was already parsed and reconciled by collect.py.
This refresh only reads the small matching CO2 companion, verifies its SHA-256,
and reuses the native MARIO axes and characterisation routine. It neither
downloads nor reads the large economic matrices again.
"""
from pathlib import Path
import argparse, gzip, hashlib, json, sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'doc/scripts/emerging'),str(ROOT/'doc/source/_static/reproduce')]
from collect import configure_indicators, native_co2, write
from economy_browser import characterise

def refresh(stage):
    reports=[]
    for job in json.loads((stage/'inventory.json').read_text()):
        folder=stage/'readings'/job['id']
        snapshot=json.loads((folder/'snapshot.json').read_text())
        profile=json.loads(gzip.decompress((folder/'profile.json.gz').read_bytes()))
        validation=json.loads((folder/'validation.json').read_text())
        if not validation.get('flow_verified') or validation['max_raw_parsed_va_error_usd']>1e-3:
            raise ValueError('First run the full MARIO parse and source flow checks')
        recipe=configure_indicators(snapshot['recipe'],bool(job['co2_path']))
        native_regions=profile['sets']['Region'];sectors=profile['sets']['Sector']
        if recipe['sectors']!=sectors:raise ValueError('Native sector ordering changed')
        emissions={}
        if job['co2_path']:
            path=Path(job['co2_path'])
            raw=path.read_bytes();checksum=hashlib.sha256(raw).hexdigest()
            if checksum!=validation['co2_sha256']:raise ValueError('CO2 source changed')
            units={u['index'][0]:u['values']['unit'] for u in profile['units'] if u['set']=='Satellite account'}
            if any(units.get(name)!='Mt CO2eq' for name in recipe['ghg_factors']):
                raise ValueError('Unexpected source CO2 unit: '+str(units))
            co2=native_co2(job,len(native_regions),len(sectors))
            if co2.shape!=(len(native_regions)*len(sectors),7) or not np.isfinite(co2).all():
                raise ValueError('Unexpected native CO2 shape/values')
            columns=pd.MultiIndex.from_product([native_regions,['Sector'],sectors],names=['Region','Level','Item'])
            frame=pd.DataFrame(co2.T,index=list(recipe['ghg_factors']),columns=columns)
            weighted=characterise(frame,recipe['ghg_factors'])
            emissions={code:weighted.xs(code,level='Region').to_list() for code in native_regions}
            expected=co2.reshape(len(native_regions),len(sectors),7).sum(axis=2)*1e6
            actual=np.asarray([emissions[code] for code in native_regions])
            if not np.allclose(actual,expected,rtol=1e-14,atol=1e-6):raise ValueError('CO2 proxy differs from fuel sum')
            validation['co2_proxy_max_abs_error_tonnes']=float(np.abs(actual-expected).max())
        for region in snapshot['regions']:
            region['gdp']=sum(region['value_added'])
            region.pop('household_ghg',None)
            if emissions:region['ghg']=emissions[region['code']]
            else:region.pop('ghg',None)
        validation.update(indicator_proxies_verified=True,
                          world_gdp_proxy_usd=sum(r['gdp'] for r in snapshot['regions']))
        if emissions:validation['world_co2_proxy_tonnes']=sum(sum(r['ghg']) for r in snapshot['regions'])
        write(folder/'snapshot.json',snapshot);write(folder/'validation.json',validation)
        reports.append(validation)
        print(job['id'],'GDP proxy',round(validation['world_gdp_proxy_usd']/1e12,3),'trillion USD',
              'CO2 '+str(round(validation.get('world_co2_proxy_tonnes',0)/1e9,3))+' Gt' if emissions else 'CO2 unavailable',flush=True)
    write(stage/'proxy-validation.json',reports)

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--stage',type=Path,required=True)
    refresh(cli.parse_args().stage)
