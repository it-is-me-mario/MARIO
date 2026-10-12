"""Recharacterise official EXIOBASE Hybrid three-gas subtotal from extension sheets."""
import argparse, hashlib, json, os, pathlib
import numpy as np
import pandas as pd

ROOT=pathlib.Path(__file__).resolve().parents[3]
STAGE=pathlib.Path(os.environ.get('MARIO_EXIOBASE_STAGE',ROOT/'Output/exiobase-browser')).resolve()
PUBLIC=ROOT/'doc/source/_static/data/economy'
OUT=pathlib.Path(os.environ.get('MARIO_EXIOBASE_AR5_PATCHES',STAGE/'ar5-patches')).resolve()
record=json.loads((STAGE/'hybrid-record.json').read_text())
source={f['key']:f for f in record['files']}


def read_sheet(path,name):
    frame=pd.read_excel(path,sheet_name=name,index_col=[0,1,2],header=[0,1,2,3]).fillna(0)
    keep=~frame.columns.get_level_values(0).astype(str).str.startswith('Unnamed:')
    return frame.loc[:,keep]


def gas_values(frame,ch4,n2o):
    result=None
    for gas,factor in [('Carbon dioxide, fossil',1),('CH4',ch4),('N2O',n2o)]:
        s=frame.loc[(gas,'tonnes','air')].astype(float)
        if not np.isfinite(s).all():raise ValueError('Non-finite original Hybrid gas')
        result=s*factor if result is None else result+s*factor
    return result


def map_values(series,snapshot,fd,sector_labels=None):
    if fd:return series.groupby(level=0).sum().to_dict()
    if sector_labels is None:sector_labels=list(series.index.get_level_values(1))
    values=pd.Series(series.to_numpy(),index=pd.MultiIndex.from_arrays([series.index.get_level_values(0),sector_labels])).groupby(level=[0,1]).sum()
    expected={(r['code'],sector) for r in snapshot['regions'] for sector in snapshot['recipe']['sectors']}
    if set(values.index.to_list())!=expected or len(values)!=len(expected):
        raise ValueError('Hybrid satellite sector axes changed')
    return values.to_dict()


def run(kind,table,source_dir):
    filename=f'MR_{kind}_2011_v3_3_18_extensions.xlsx';path=source_dir/filename
    info=source[filename];raw=path.read_bytes()
    if 'md5:'+hashlib.md5(raw).hexdigest()!=info['checksum']:raise ValueError('Official Hybrid MD5 mismatch')
    ident=f'exiobase-hybrid-3318-2011-{table}'
    snapshot=json.loads((PUBLIC/(ident+'.json')).read_text())
    frames={key:read_sheet(path,key) for key in ['Emiss_act','Emiss_FD','Emis_unreg_w_act','Emis_unreg_w_FD']}
    if table=='iot':
        principal_path=source_dir/'MR_HIOT_2011_v3_3_18_principal_production.csv'
        principal_info=source[principal_path.name]
        principal_raw=principal_path.read_bytes()
        if 'md5:'+hashlib.md5(principal_raw).hexdigest()!=principal_info['checksum'] or len(principal_raw)!=principal_info['size']:
            raise ValueError('Official Hybrid principal mapping checksum mismatch')
        principal=pd.read_csv(principal_path,header=[0,1,2,3])
        sector_labels=principal.iloc[0].tolist()
        if len(sector_labels)!=frames['Emiss_act'].shape[1]:raise ValueError('Hybrid principal axis length changed')
    else:sector_labels=list(frames['Emiss_act'].columns.get_level_values(1))
    old={};new={}
    for basis,ch4,n2o in [('old',29.8,273),('new',28,265)]:
        activity=gas_values(frames['Emiss_act'],ch4,n2o)+gas_values(frames['Emis_unreg_w_act'],ch4,n2o)
        final=gas_values(frames['Emiss_FD'],ch4,n2o)+gas_values(frames['Emis_unreg_w_FD'],ch4,n2o)
        (old if basis=='old' else new).update(sectors=map_values(activity,snapshot,False,sector_labels),household=map_values(final,snapshot,True))
    worst=0
    for region in snapshot['regions']:
        code=region['code']
        for sector,stored in zip(snapshot['recipe']['sectors'],region['ghg']):
            observed=old['sectors'][(code,sector)];worst=max(worst,abs(observed-stored)/max(1,abs(stored)))
        stored=region['household_ghg'];worst=max(worst,abs(old['household'][code]-stored)/max(1,abs(stored)))
    if worst>1e-8:raise ValueError('Old Hybrid GHG mismatch '+str(worst))
    old_factors=snapshot['recipe']['ghg_factors'];factors={label:(28 if label.startswith('CH4') else 265 if label.startswith('N2O') else weight) for label,weight in old_factors.items()}
    data={'id':ident,'factors':factors,'regions':[{'code':r['code'],'ghg':[float(new['sectors'][(r['code'],sector)]) for sector in snapshot['recipe']['sectors']],'household_ghg':float(new['household'][r['code']])} for r in snapshot['regions']], 'validation':{'old_max_relative_error':worst,'old_world_tonnes':sum(old['sectors'].values())+sum(old['household'].values()),'new_world_tonnes':sum(new['sectors'].values())+sum(new['household'].values()),'source_members':[{'name':filename,'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw),'published_md5':info['checksum']}]+([{'name':principal_path.name,'sha256':hashlib.sha256(principal_raw).hexdigest(),'size':len(principal_raw),'published_md5':principal_info['checksum']}] if table=='iot' else []),'archive_checksum':info['checksum']}}
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/(ident+'.json');temp=target.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False));temp.replace(target)
    print(ident,'verified',worst,'old/new Gt',round(data['validation']['old_world_tonnes']/1e9,3),round(data['validation']['new_world_tonnes']/1e9,3),flush=True)

if __name__=='__main__':
    cli=argparse.ArgumentParser()
    cli.add_argument('--source',type=pathlib.Path,required=True,help='Directory containing the two verified Hybrid extension workbooks and principal-production CSV')
    args=cli.parse_args()
    run('HIOT','iot',args.source);run('HSUTs','sut',args.source)
