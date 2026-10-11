from pathlib import Path
import argparse, json, os, sys
import pandas as pd
ROOT=Path(os.environ.get('MARIO_DOCS_ROOT',Path(__file__).resolve().parents[3]))
sys.path[:0]=[str(ROOT),str(ROOT/'doc/scripts')]
from mario.parsers import adb
cli=argparse.ArgumentParser(description="Inventory local ADB MRIOT workbooks and compatible same-year emissions extensions.")
cli.add_argument('--path',type=Path,required=True)
cli.add_argument('--output',type=Path,required=True)
cli.add_argument('--excel-engine',choices=['openpyxl','calamine'],default='openpyxl')
args=cli.parse_args();base=args.path

raw_read=pd.read_excel
def fast_read(*args,**kwargs):return raw_read(*args,**{**kwargs,'engine':args.excel_engine})
pd.read_excel=fast_read
jobs=[]
for folder in ['62 economies','71 economies','72 economies','74 economies']:
    for file in sorted((base/folder).glob('*.xlsx')):
        layout=adb.detect_adb_layout(file)
        preview=adb._read_adb_preview(file,sheet_name=layout.sheet_name)
        regions=list(dict.fromkeys(preview.iloc[layout.region_row,layout.sector_start:layout.sector_end].astype(str)))
        jobs.append({'file':str(file.relative_to(base)),'year':layout.year,'economies':int(folder.split()[0]),'regions':regions,'sheet':layout.sheet_name})
extensions=[]
for file in sorted((base/'Air emissions').glob('*.xlsx')):
    layout=adb.detect_adb_emissions_layout(file)
    frame=pd.read_excel(file,sheet_name=layout.sheet_name,header=None)
    regions=list(dict.fromkeys(frame.iloc[layout.region_row,layout.sector_start:layout.sector_end].astype(str)))
    labels=[adb._build_satellite_label(frame.iat[i,0],frame.iat[i,1]) for i in range(layout.code_row+1,len(frame))]
    labels=[x for x in labels if x]
    gases=[x for x in labels if x.endswith('| Total by substance')]
    notes=pd.read_excel(file,sheet_name='Notes',header=None) if 'Notes' in pd.ExcelFile(file).sheet_names else pd.DataFrame()
    texts=[str(x) for x in notes.to_numpy().ravel() if pd.notna(x)]
    extensions.append({'file':str(file.relative_to(base)),'year':layout.year,'regions':regions,'unit':layout.unit,'total_rows':gases,'notes':[x for x in texts if any(k in x for k in ['GWP','global warming','AR5','LULUCF','residence','carbon dioxide equivalent'])]})
    print('Emissions',layout.year,'regions',len(regions),'unit',layout.unit,'totals',gases,flush=True)
for job in jobs:
    ext=next((x for x in extensions if x['year']==job['year']),None)
    missing=[] if not ext else sorted(set(job['regions'])-set(ext['regions']))
    job['extensions']=ext['file'] if ext and not missing else None
    job['emissions_missing_regions']=missing
    job['emissions_remap_to_row']=[] if not ext or missing else sorted(set(ext['regions'])-set(job['regions']))
    print(job['economies'],job['year'],'parsed regions',len(job['regions']),'GHG',bool(job['extensions']),'missing',missing,'RoW absorbs',job['emissions_remap_to_row'],flush=True)
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps({'jobs':jobs,'extensions':extensions},indent=2))
