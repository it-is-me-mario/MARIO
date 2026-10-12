from pathlib import Path
import copy,hashlib,json,openpyxl
import argparse
from collect import ROOT as root,STAGE as p
cli=argparse.ArgumentParser();cli.add_argument('--classification',required=True,type=Path);args=cli.parse_args()
native=json.loads((p/'readings/exiobase-hybrid-3318-2011-iot/snapshot.json').read_text())['recipe']['sectors']
base=json.loads((root/'doc/source/_static/data/economy/sector-sections.json').read_text())['mappings']['exiobase-3112-2024-pxp']
by_code={e['native_code']:e for e in base['entries']};book=openpyxl.load_workbook(args.classification,read_only=True,data_only=True)
rows=list(book['Correspondence_products'].iter_rows(values_only=True))[1:]
codes={};groups={}
for row in rows:
 hsut,hiot_code,hiot_name=row[1],row[5],row[4]
 if hiot_name not in native:continue
 if hsut not in by_code:raise ValueError('Unmapped original product code '+str(hsut))
 codes.setdefault(hiot_name,set()).add(hiot_code);groups.setdefault(hiot_name,set()).add(by_code[hsut]['section'])
entries=[];sections=copy.deepcopy(base['sections'])
for i,name in enumerate(native):
 if name not in groups or len(codes[name])!=1:raise ValueError('Missing or ambiguous HIOT product mapping '+name)
 parts=sorted(groups[name]);section='+'.join(parts)
 if len(parts)>1:sections[section]=' / '.join(base['sections'][part] for part in parts)
 entries.append({'index':i,'native_label':name,'native_code':next(iter(codes[name])),'section':section})
book.close();m={**base,'entries':entries,'sections':{s:sections[s] for s in sorted({e['section'] for e in entries})},'source_url':'https://zenodo.org/records/7244919','classification_url':'https://zenodo.org/records/7244919/files/Classifications_v_3_3_18.xlsx','hybrid_concordance':{'sheet':'Correspondence_products','source_sha256':hashlib.sha256((args.classification).read_bytes()).hexdigest(),'method':'Original HSUT product code -> HIOT product code and label. Every constituent CPA section checked; combined sections remain combined.'}}
(p/'hybrid-product-mapping.json').write_text(json.dumps(m,ensure_ascii=False,separators=(',',':')))
print('Verified official Hybrid HIOT correspondence:',len(entries),'native products',len(m['sections']),'CPA sections.')
