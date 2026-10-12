"""Parse local ADB MRIOTs, reconcile indicators and catalogue every native set."""
from pathlib import Path
import argparse,copy,gc,gzip,hashlib,json,logging,os,posixpath,re,sys,time,zipfile
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from unittest.mock import patch
import numpy as np
import pandas as pd

ROOT=Path(os.environ.get('MARIO_DOCS_ROOT',Path(__file__).resolve().parents[3]))
sys.path[:0]=[str(ROOT),str(ROOT/'doc/scripts'),str(ROOT/'doc/source/_static/reproduce')]
import mario
from mario.parsers import adb
from database_catalogue import extract_profile
from economy_browser import aggregate
logging.getLogger('mario').setLevel(logging.ERROR)
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if path.suffix=='.gz':raw=gzip.compress(raw)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(raw);tmp.replace(path)

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024**2),b''):h.update(chunk)
    return h.hexdigest()

def sheets(archive):
    rel={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
    result={}
    for sheet in ET.fromstring(archive.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS):
        target=rel[sheet.attrib[RID]]
        result[sheet.attrib['name']]=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl',target))
    return result

def preview(path,*,sheet_name):
    # Header-only ZIP streaming avoids materialising a multi-million-cell sheet
    # just to detect its original MARIO layout. Cached XLSX values are preserved.
    with zipfile.ZipFile(path) as archive:
        names=sheets(archive); strings=[]
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings=[''.join(t.text or '' for t in si.iterfind('.//s:t',NS)) for si in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        records=[];width=0
        with archive.open(names[sheet_name]) as stream:
            for _,element in ET.iterparse(stream,events=('end',)):
                if element.tag!=f'{{{NS["s"]}}}row':continue
                number=int(element.attrib['r'])
                if number>12:break
                record={}
                for cell in element.findall('s:c',NS):
                    address=cell.attrib['r'];letters=re.match('[A-Z]+',address)[0];column=0
                    for c in letters:column=column*26+ord(c)-64
                    column-=1;width=max(width,column+1)
                    value=cell.findtext('s:v',default='',namespaces=NS)
                    if cell.attrib.get('t')=='s':value=strings[int(value)] if value else None
                    elif cell.attrib.get('t')=='inlineStr':value=''.join(t.text or '' for t in cell.iterfind('.//s:t',NS))
                    elif value:
                        try:value=float(value)
                        except ValueError:pass
                    else:value=None
                    record[column]=value
                while len(records)<number-1:records.append({})
                records.append(record);element.clear()
        return pd.DataFrame([[row.get(i) for i in range(width)] for row in records])

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--path',type=Path,required=True);cli.add_argument('--inventory',type=Path,required=True);cli.add_argument('--stage',type=Path,required=True)
    cli.add_argument('--excel-engine',choices=['openpyxl','calamine'],default='openpyxl');cli.add_argument('--limit',type=int)
    args=cli.parse_args();base=args.path.resolve();inventory=json.loads(args.inventory.read_text());jobs=sorted(inventory['jobs'],key=lambda j:(-j['economies'],-j['year']))
    if args.limit:jobs=jobs[:args.limit]
    seed=json.loads((ROOT/'doc/source/_static/data/economy/adb-2024-74-economies.json').read_text())['recipe']
    notebook=next(r for r in json.loads((ROOT/'doc/database_catalogue.recipes.json').read_text())['recipes'] if r['id']=='adb--01')
    original_read=pd.read_excel;original_workbook=adb._read_adb_workbook
    extension_cache={};metadata_cache={};observed={}
    def sheet_name(path):
        with zipfile.ZipFile(path) as z:return next(name for name in sheets(z) if name.casefold()!='legend')
    def emission_sheet(path):
        with zipfile.ZipFile(path) as z:return next(name for name in sheets(z) if re.fullmatch(r'20\d{2}',name))
    def read(*a,**kw):
        path=Path(a[0]);kw['engine']=args.excel_engine
        if path.parent.name=='Air emissions' and kw.get('header') is None and not kw.get('nrows'):
            key=(str(path),kw.get('sheet_name'))
            if key not in extension_cache:extension_cache[key]=original_read(*a,**kw)
            return extension_cache[key].copy(deep=False)
        return original_read(*a,**kw)
    def read_workbook(*a,**kw):
        frame=original_workbook(*a,**kw)
        label_row,region_row,code_row,start,end,fd_start,fd_end=adb._find_header_rows(frame.iloc[:12])
        codes=frame.iloc[:,start-1].astype(str)
        factors=frame.loc[codes.isin(['r64','r99']),start:fd_end-1].copy()
        factors.index=codes[codes.isin(['r64','r99'])].tolist()
        observed.update(factors=factors,regions=frame.iloc[region_row,start:fd_end].astype(str).tolist(),sector_width=end-start,
                        sector_codes=dict(zip(frame.iloc[code_row,start:end].astype(str),frame.iloc[label_row,start:end].astype(str).str.strip())),shape=list(frame.shape))
        return frame
    results=[]
    with ExitStack() as stack:
        stack.enter_context(patch.object(pd,'read_excel',read));stack.enter_context(patch.object(adb,'_read_adb_preview',preview))
        stack.enter_context(patch.object(adb,'_find_adb_sheet',sheet_name));stack.enter_context(patch.object(adb,'_find_emissions_sheet',emission_sheet))
        stack.enter_context(patch.object(adb,'_read_adb_workbook',read_workbook))
        for job in jobs:
            start=time.time();path=base/job['file'];identifier=f'adb-{job["year"]}-{job["economies"]}-economies';folder=args.stage/'readings'/identifier
            if not path.stat().st_blocks:raise ValueError('Source workbook must already be local: '+path.name)
            params={'year':job['year'],'economies':job['economies']}
            ext=base/job['extensions'] if job['extensions'] else None
            if ext:params['add_extensions']=str(ext)
            db=mario.parse_adb(path=str(path),calc_all=False,**params)
            r=copy.deepcopy(seed);r.update(id=identifier,label=f'ADB · {job["economies"]} economies',release=f'{job["economies"]} economies',year=job['year'],parser_options=params)
            p=extract_profile(db,job={'id':identifier,'label':f'ADB {job["year"]} · {job["economies"]} economies','source':'Asian Development Bank','release':r['release'],'year':job['year']},recipe=notebook,parameters={'path':str(path),**params,'calc_all':False})
            r.update(sectors=p['sets']['Sector'],regions=p['geography']['regions'],consumption_categories=p['sets']['Consumption category'])
            if p['geography']['unresolved_count']:raise ValueError('Unresolved ADB native region labels: '+str([x['label'] for x in r['regions'] if x['kind']=='unresolved']))
            r['expected_units']={name:frame['unit'].astype(str).to_dict() for name,frame in db.units.items()}
            r['ghg_factors']={'GHG | Total by substance':1000.0} if ext else {}
            r['ghg_method']='Published GHG total in Gg CO₂eq, using source AR5 GWP100; converted to tonnes without applying GWP twice. CO₂, CH₄, N₂O and F-gases. Residence-based SEEA accounts; LULUCF excluded. Direct final-demand emissions kept separately.' if ext else ('The same-year emissions workbook does not cover every native region in this version.' if job['emissions_missing_regions'] else 'No matching same-year emissions extension available locally.')
            if ext:r['ghg_basis']='ADB SEEA industry accounts; source AR5 GWP100; excludes LULUCF'
            factors=observed['factors'].apply(pd.to_numeric,errors='raise').fillna(0)
            if set(factors.index)!= {'r64','r99'}:raise ValueError('Expected one original VA and tax row')
            va=factors.loc['r64'].iloc[:observed['sector_width']].groupby(observed['regions'][:observed['sector_width']]).sum()*1e6
            tax=factors.loc['r99'].groupby(observed['regions']).sum()*1e6
            fd=factors.loc['r99'].iloc[observed['sector_width']:].groupby(observed['regions'][observed['sector_width']:]).sum().to_dict()
            rows=aggregate(db,r,fd);errors=[]
            for region in rows:
                code=region['code']
                for actual,expected in [(sum(region['value_added']),va[code]),(region['net_product_taxes'],tax[code]),(region['gdp'],va[code]+tax[code])]:
                    if not np.isclose(actual,expected,rtol=1e-12,atol=.1):raise ValueError(f'Indicator reconciliation failed: {identifier} {code}')
                    errors.append(abs(actual-expected))
            gas_check={}
            if ext:
                layout=adb.detect_adb_emissions_layout(ext);native=extension_cache[(str(ext),layout.sheet_name)]
                totals=native.loc[native.iloc[:,0].eq('Total by substance'),layout.sector_start:layout.final_demand_end-1].copy()
                totals.index=native.loc[native.iloc[:,0].eq('Total by substance')].iloc[:,1].tolist()
                totals=totals.apply(pd.to_numeric,errors='raise').fillna(0)
                components=totals.loc[['CO2','CH4','N2O','GWP_100_AR5_F-gases']].sum()
                if not np.allclose(components,totals.loc['GHG'],rtol=1e-9,atol=1e-5):raise ValueError('Published GHG/component totals disagree')
                e_total=float(totals.loc['GHG'].iloc[:layout.sector_end-layout.sector_start].sum())*1000
                ey_total=float(totals.loc['GHG'].iloc[layout.sector_end-layout.sector_start:].sum())*1000
                parsed_e=sum(sum(row['ghg']) for row in rows);parsed_ey=sum(row['household_ghg'] for row in rows)
                if not np.isclose(parsed_e,e_total,rtol=1e-12,atol=.1) or not np.isclose(parsed_ey,ey_total,rtol=1e-12,atol=.1):raise ValueError('World GHG was lost during regional alignment')
                gas_check={'world_ghg_tonnes':parsed_e,'world_final_demand_ghg_tonnes':parsed_ey,'source_world_ghg_tonnes':e_total,'source_world_final_demand_ghg_tonnes':ey_total}
                r['parser_options']['add_extensions']='/path/to/same-year-Air-Emissions.xlsx'
            r['gdp_bridge_verified']=True;r.pop('sector_groups',None)
            p['provenance'].update(mario_version=mario.__version__,source_url=r['source_url'],input_filename=path.name,input_sha256=sha256(path),reading_scope='Full local MARIO MRIOT parse with calc_all=False. Original VA and tax rows reconciled by country; matching extensions reconciled to source world totals.',economies=job['economies'],region_note='The version counts individual economies; MARIO region counts also include aggregate regions.',source_sector_codes=observed['sector_codes'])
            if ext:p['provenance']['emissions']={'filename':ext.name,'sha256':sha256(ext),'year':job['year'],'regional_remap_to_RoW':job['emissions_remap_to_row'],'method':'Published GHG | Total by substance, Gg CO2eq, source AR5. No recharacterisation.','source_notes':next(e['notes'] for e in inventory['extensions'] if e['year']==job['year'])}
            if job['emissions_missing_regions']:p['provenance']['emissions_unavailable']={'missing_regions':job['emissions_missing_regions'],'reason':'The original 72-economy extension cannot disaggregate the larger economic coverage.'}
            snapshot={'schema_version':1,'recipe':r,'regions':rows,'generated_at':p['parsed_at'],'provenance':p['provenance']}
            validation={'id':identifier,'year':job['year'],'economies':job['economies'],'counts':p['counts'],'max_raw_parsed_error_usd':max(errors),'world_value_added_usd':sum(sum(row['value_added']) for row in rows),'world_gdp_usd':sum(row['gdp'] for row in rows),'seconds':round(time.time()-start,2),**gas_check}
            write(folder/'snapshot.json',snapshot);write(folder/'profile.json.gz',p);write(folder/'validation.json',validation)
            results.append(validation);write(args.stage/'run-report.json',results)
            print(f'{len(results)}/{len(jobs)} {job["economies"]} economies {job["year"]}: {p["counts"]}; GHG {bool(ext)}; {validation["seconds"]}s',flush=True)
            del db,p,rows,factors;observed.clear();gc.collect()
    write(args.stage/'inventory.json',inventory)
    print('Completed',len(results),'full local ADB MRIOT readings.',flush=True)

if __name__=='__main__':main()
