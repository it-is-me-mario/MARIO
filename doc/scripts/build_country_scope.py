"""Build country scope and reviewed classification lookups from parsed set metadata.

No economic matrices are read. Legacy correspondence is retained with its source
revision; only explicit EXIOBASE product-code bridges are used for current products.
Run: python build_country_scope.py --concordances /path/to/EXIOBASE/concordances
"""
from pathlib import Path
import argparse, hashlib, json, re
import openpyxl


def read_book(path, sheet=None):
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return list((book[sheet] if sheet else book.active).values)
    finally:
        book.close()


def build(data, concordances):
    catalogue = json.loads((data/'database_profiles.json').read_text())
    external_path=data/'external_profiles.json'
    if external_path.is_file():
        catalogue['profiles'].extend(json.loads(external_path.read_text())['profiles'])
    manifest = json.loads((data/'economy/manifest.json').read_text())
    readings = {d['id']: {**manifest['templates'][d['template']]['recipe'], **d} for d in manifest['datasets']}
    sections = json.loads((data/'economy/sector-sections.json').read_text())['mappings']
    rows, maps, classes = [], {}, {}
    aliases = {'Asian Development Bank': 'ADB'}
    normal = {'nace-1.1-adb':'nace-1.1', 'nace-2-wiod':'nace-2'}
    for p in catalogue['profiles']:
        if p['status'] not in ['parsed','source_verified']:
            continue
        detail = json.loads((data.parent.parent/p['detail']).read_text())
        ids = [r['id'] for r in detail.get('readings',[]) if r['id'] in readings]
        if not ids and p['id'] in readings:
            ids = [p['id']]
        family = aliases.get(p['source'],p['source'])
        if not ids:
            opts = p.get('provenance',{}).get('options',{})
            ids = [rid for rid,r in readings.items() if r['source']==family and str(r['release'])==str(p['release']) and
                   r.get('table','IOT')==p['table'] and r['year'] in p.get('years',[p['year']]) and
                   r.get('parser_options',{}).get('unit','Monetary')==opts.get('unit','Monetary') and
                   (not opts.get('system') or r.get('parser_options',{}).get('system')==opts['system'])]
        if p.get('numeric_publication') is False:ids=[]
        recipe = readings[ids[0]] if ids else None
        opts = recipe.get('parser_options',{}) if recipe else p.get('provenance',{}).get('options',{})
        units = opts.get('unit','Monetary')
        system = None if p['table']=='SUT' else opts.get('system') or ('pxp' if family=='EXIOBASE' and units=='Hybrid' else 'pxp' if opts.get('iot_mode')=='product' else 'ixi' if opts.get('iot_mode')=='industry' else (recipe or {}).get('dimension'))
        native_sets = {key: values for key,values in detail['sets'].items() if key!='Region'}
        memberships = {}
        for item in detail.get('region_items',[]):
            if item['set'] in ['Sector','Activity','Commodity']:
                memberships.setdefault(item['region'],{}).setdefault(item['set'],[]).append(item['label'])
        # Store overrides only when a country's set differs from the union.
        memberships = {region:{key: sorted(set(values)) for key,values in sets.items() if set(values)!=set(native_sets[key])}
                       for region,sets in memberships.items()}
        memberships = {key:value for key,value in memberships.items() if value}
        mapping = next((sections[rid] for rid in ids if rid in sections), None)
        mid = None; mids = []
        for native_mapping in ([mapping, *mapping.get('additional_mappings', [])] if mapping else []):
            cls = normal.get(native_mapping['classification_id'],native_mapping['classification_id'])
            classes.setdefault(cls, {'id':cls,'label':('NACE Rev. 2' if cls=='nace-2' else native_mapping['classification'].replace(' · WIOD','')),'nodes':{},'levels':[1], 'source_url':native_mapping['classification_url']})
            for code,name in native_mapping['sections'].items():
                for part in code.split('+'):
                    if len(part)==1:
                        classes[cls]['nodes'].setdefault(part,{'code':part,'name': name if '+' not in code else part,'level':1,'parent':None})
                        if '+' not in code and classes[cls]['nodes'][part]['name']==part:classes[cls]['nodes'][part]['name']=name
            entries = [{'native_code':e.get('native_code') or e['native_label'], 'native_label':e['native_label'], 'official_code':e['section'], 'relation':'section_assignment'} for e in native_mapping['entries']]
            key = json.dumps([cls,native_mapping.get('dimension'),entries],sort_keys=True)
            mapping_id = hashlib.sha256(key.encode()).hexdigest()[:16]; mids.append(mapping_id)
            if mid is None:mid = mapping_id
            maps.setdefault(mapping_id, {'classification':cls,'depth':1,'dimension':native_mapping.get('dimension'),'source_url':native_mapping['source_url'],'basis':native_mapping.get('basis','Verified native section assignment; no cross-revision allocation.'),'entries':entries, 'complete':True})
        rows.append({'id':p['id'],'family':family,'release':str(p['release']),'units':units,'format':p['table'],'system':system,'price_basis':p.get('price_basis',''),
                     'years':p.get('years',[p['year']]),'counts':p['counts'],'region_counts':p.get('region_counts',[]),
                     'regions':p['geography']['regions'],'memberships':memberships,'sets':native_sets,'set_flags':p.get('set_flags',{}),
                     'reading_ids':ids,'reading_years':{rid:readings[rid]['year'] for rid in ids},
                     'indicator_flags':{rid:{k:bool(readings[rid].get(k)) for k in ['gdp_proxy','ghg_proxy']} for rid in ids},
                     'availability':{rid: readings[rid]['availability'] for rid in ids},
                     'status':p['status'],'parser_supported':p.get('parser_supported',True),'native_codes':detail.get('native_codes',{}),
                     'source_url':p.get('source_url') or p.get('provenance',{}).get('source_url'),'scope_note':p.get('scope_note',''),
                     'license_url':p.get('license_url'),'attribution':p.get('attribution',''),
                     'workbook':p['workbook'],'guide':next((g['doc']+'.html' for g in catalogue['guides'] if g['id']==p['guide']),None),
                     'mapping':mid,'mapping_ids':mids,'signature':p.get('coverage_signatures',{})})
        for key in ['environmental','numeric_publication','version','variant']:
            if key in p:rows[-1][key]=p[key]
    # NACE Rev. 1.1 taxonomy: official codes/descriptions in the source, without
    # pretending its EXIOBASE 2 native industry edges describe all current sectors.
    nace_path = concordances/'Archive/International classifications/NACE1.1 - EXIOBASE2.0_FINAL.xlsx'
    nace_rows = read_book(nace_path)[1:]
    nodes, ancestors = {}, {}
    for r in nace_rows:
        level = int(r[0])
        if level==2: # old subsections are not a NACE numeric digit level
            continue
        level = 1 if level==1 else level-1
        if level==1:
            code = str(r[4]); parent=None
        else:
            code = f'{float(r[4]):02.0f}' if level==2 else f'{float(r[4]):04.1f}' if level==3 else f'{float(r[4]):05.2f}'
            parent = ancestors[level-1]
        ancestors[level] = code
        nodes[code] = {'code':code,'name':str(r[5]),'level':level,'parent':parent}
    classes['nace-1.1'].update(nodes=nodes,levels=[1,2,3,4])
    # CPA hierarchy within this one revision: numeric ancestors of the official
    # six-digit codes; do not fabricate intermediate descriptions.
    cpa_path = concordances/'Archive/International classifications/CPA2002_6digit_EXIOBASE_FINAL.xlsx'
    bridge_path = concordances/'EXIOBASE/EXIOBASE2 products comparison with EXIOBASE3 products.xlsx'
    bridge = {r[1]:{'code':r[3],'name':r[2]} for r in read_book(bridge_path)[1:]}
    cls = classes['cpa-2002']; cpa_nodes = dict(cls['nodes']); edges=[]
    division_sections={n['code']:n['parent'] for n in nodes.values() if n['level']==2}
    for r in read_book(cpa_path)[1:]:
        if not r[1]:
            continue
        code = str(r[1]).strip()
        if not re.fullmatch(r'\d{2}\.\d{2}\.\d{2}',code):
            raise ValueError(f'Unexpected CPA code: {code}')
        prefixes=[code[:2],code[:4],code[:5],code[:7],code]
        parent=division_sections[code[:2]]
        for level,prefix in enumerate(prefixes,2):
            cpa_nodes.setdefault(prefix,{'code':prefix,'name':str(r[0]) if level==6 else 'CPA '+prefix,'level':level,'parent':parent})
            parent=prefix
        for target in str(r[3] or '').split(';'):
            target=target.strip()
            if not target: continue
            linked=bridge[target]
            edges.append({'official_code':code,'native_code':linked['code'],'bridge_label':linked['name'],'relation':'source_correspondence'})
    cls.update(nodes=cpa_nodes,levels=[1,2,3,4,5,6])
    for mid,mapping in list(maps.items()):
        if mapping['classification']!='cpa-2002': continue
        native={e['native_code']:e for e in mapping['entries']}
        verified=[]
        for edge in edges:
            item=native.get(edge['native_code'])
            # The bridge must agree with the actual current category name as well
            # as its identifier. Hybrid variants with different native codes stay
            # at their verified section assignment.
            if item and item['native_label']==edge['bridge_label']:
                verified.append({**edge,'native_label':item['native_label']})
        if not verified: continue
        detailed_id=mid+'-cpa'
        maps[detailed_id]={**mapping,'depth':6,'complete':False,'entries':verified,'section_entries':mapping['entries'],
                          'basis':'CPA 2002 → EXIOBASE 2.0 → explicit EXIOBASE 3 product-code/name bridge. Source links do not assert exact equivalence or provide numerical allocation weights.',
                          'source_files':[cpa_path.name,bridge_path.name],
                          'source_sha256':[hashlib.sha256(p.read_bytes()).hexdigest() for p in [cpa_path,bridge_path]],
                          'mapped_native_count':len({e['native_code'] for e in verified}),'native_count':len(native)}
        for row in rows:
            if row['mapping']==mid:
                row['mapping']=detailed_id
                row['mapping_ids']=[detailed_id if key==mid else key for key in row.get('mapping_ids',[mid])]
    return {'schema_version':1,'profiles':rows,'classifications':{k:{**v,'nodes':list(v['nodes'].values())} for k,v in classes.items()},'mappings':maps,
            'sources':['https://zenodo.org/records/23039074','https://ec.europa.eu/eurostat/web/cpa/correspondence-tables'],
            'note':'Metadata only. Classification queries do not disaggregate economic or emission values.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concordances',type=Path,required=True)
    parser.add_argument('--data',type=Path,default=Path(__file__).resolve().parents[1]/'source/_static/data')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(); result=build(args.data,args.concordances)
    output=args.output or args.data/'economy/country-scope.json'
    output.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({'profiles':len(result['profiles']),'classifications':{k:len(c['nodes']) for k,c in result['classifications'].items()},'detailed_native_counts':[(m['mapped_native_count'],m['native_count']) for m in result['mappings'].values() if m['depth']>1]}))
