"""Build reference-leaf heatmaps from typed, source-referenced correspondence routes.

No economic matrices, numerical allocation or fuzzy label matching. Normalized
source inputs live in doc/classifications/sectoral; source URLs and original
checksums are retained. Run this script after updating country-scope.json.
"""
import argparse
import copy
from collections import defaultdict
import hashlib
import json
from pathlib import Path


def reviewed_pilot_routes(pilot, bridges):
    """Recompose every typed prefix against complete official terminal tables."""
    graph=defaultdict(list)
    allowed={'S04','S05','S08','S09','S10','S15'}
    for edge in pilot['edges']:
        if edge['source'] in allowed:graph[tuple(edge['left'])].append(edge)
    official=defaultdict(list);revisions=defaultdict(list)
    for edge in bridges['edges']:
        (official if edge['source']=='S06' else revisions)[edge['right'][1] if edge['source']=='S06' else edge['left'][1]].append(edge)
    inverse={'Left within right':'Left contains right','Left contains right':'Left within right'}
    def source_step(edge,reverse=False):
        s={k:edge.get(k,'') for k in ['source','location','note','left_part','right_part','raw_type','part_flags_origin']}
        return {**s,'source_left':edge['left'],'source_right':edge['right'],'source_relation':edge['relation'],
                'relation':inverse.get(edge['relation'],edge['relation']) if reverse else edge['relation']}
    result={}
    def prefixes(node,nodes,steps):
        if node[0]=='ISIC4':
            yield nodes,steps;return
        if len(nodes)>8:raise ValueError('Unexpected classification prefix depth')
        for edge in graph[tuple(node)]:
            if edge['right'] in nodes:raise ValueError('Cyclic classification correspondence')
            s=source_step(edge)
            if edge['source']=='S09':
                s.update(relation='Commodity / industry descriptor to producing NAICS activity',
                         note=(s['note']+' BEA industry/commodity descriptor; this producer bridge does not establish product/activity identity.').strip())
            yield from prefixes(edge['right'],nodes+[edge['right']],steps+[s])
    for native in pilot['native']:
        ns,code=native['node']
        if ns not in ['ADB35','CEDA2024']:continue
        links={}
        for nodes,steps in prefixes(native['node'],[native['node']],[]):
            for edge in official[nodes[-1][1]]:
                for revision in revisions[edge['left'][1]]:
                    ref=revision['right'][1]
                    route={'nodes':nodes+[edge['left'],revision['right']],
                           'steps':steps+[source_step(edge,True),source_step(revision)]}
                    partial=ns=='CEDA2024' or any(s['source_relation']=='Partial overlap' for s in route['steps'])
                    if ref not in links:
                        links[ref]={**route,'alternatives':[],'status':'partial' if partial else 'documented',
                            'exclusive_reference':False if ns=='CEDA2024' else None,
                            'mapping_origin':'published_producing_activity' if ns=='CEDA2024' else 'published',
                            'relation':'Qualified commodity-descriptor / producing-activity footprint' if ns=='CEDA2024' else 'Published activity classification footprint',
                            'review_note':'Native CEDA descriptors are commodity-owned in nxbase. The NACE view explicitly follows their producer classification; it is not an activity/product equivalence.' if ns=='CEDA2024' else ''}
                    else:
                        links[ref]['alternatives'].append(route)
                        if partial:links[ref]['status']='partial'
        result[ns,code]=links
    return result


def reuse_shared_exiobase_activities(hybrid, monetary, monetary_identities, hybrid_identities):
    """Reuse published activity footprints only after verifying both native identities.

    The existing Hybrid parent snapshot remains evidence. It is not expanded
    into descendants, and neither gas subdivisions nor the lead-label variant
    inherit the monetary aggregate. Reviewed electricity paths stay independent.
    """
    normalize=lambda name:' '.join(name.split())
    official={a['code']:a for a in monetary_identities['activities']}
    natives={n['code']:n for n in monetary}
    if set(natives)!=set(official) or any(normalize(n['name'])!=normalize(official[c]['name']) for c,n in natives.items()):
        raise ValueError('Monetary parsed/publisher activity identity mismatch')
    hofficial={a['code']:a for a in hybrid_identities['activities']}
    result=copy.deepcopy(hybrid);shared=0;reused=0
    for item in result['items']:
        activity=hofficial[item['code']];other=official.get(item['code'])
        if not other or normalize(activity['name'])!=normalize(other['name']):continue
        if activity['alias']!=other['alias']:
            raise ValueError('Shared EXIOBASE activity alias changed: '+item['code'])
        shared+=1
        if item['code'].startswith('i40.11.'):continue # Preserve reviewed technology containment and pending cases.
        original=natives[item['code']]
        if not original['links']:raise ValueError('Shared monetary footprint unavailable: '+item['code'])
        identity_step={'source':'S25','location':other['location'],'relation':'Native activity identity',
            'source_relation':'Native activity identity','source_left':['EX3h',item['nxbase_short']],
            'source_right':['EXIO3I',item['code']],
            'note':f"Matching activity code, label and alias {other['alias']} in both publisher classifications; Hybrid {activity['location']}. This is a classification bridge, not an nxbase parent."}
        native_step={'source':'S23','location':activity['location'],'relation':'Native identity',
            'source_relation':'Native identity','source_left':['EXIO3H',item['code']],
            'source_right':['EX3h',item['nxbase_short']],'note':'Published Hybrid activity code and exact nxbase EX3h identity.'}
        note='Shared activity identity verified in the Hybrid and monetary publisher classifications. The existing monetary correspondence footprint and all overlap flags are retained; no economic allocation is inferred.'
        item['links']=copy.deepcopy(original['links'])
        for link in item['links'].values():
            for route in [link,*link.get('alternatives',[])]:
                if route['nodes'][0]!=['EXIO3I',item['code']]:raise ValueError('Unexpected monetary activity route origin')
                route['nodes']=[['EXIO3H',item['code']],['EX3h',item['nxbase_short']],*route['nodes']]
                route['steps']=[copy.deepcopy(native_step),copy.deepcopy(identity_step),*route['steps']]
            link['mapping_origin']='shared_exiobase_activity'
            link['review_note']=note+((' '+link['review_note']) if link.get('review_note') else '')
        item['shared_activity']={'monetary_code':other['code'],'name':other['name'],'alias':other['alias'],
            'hybrid_location':activity['location'],'monetary_location':other['location']}
        item.pop('coarse',None);item.pop('unresolved',None)
        reused+=1
    if shared!=161 or reused!=149:raise ValueError('EXIOBASE activity vocabularies changed; review the shared bridge')
    result['sources'].append(monetary_identities['source'])
    return result


def build(inputs, scope):
    pilot = json.loads((inputs/'activity-pilot.json').read_text())
    official = json.loads((inputs/'nace21-structure.json').read_text())
    sources = {s['id']:s for s in pilot['sources']}
    native = defaultdict(list)
    for n in pilot['native']:
        native[n['node'][0]].append({'code':n['code'],'name':n['label'],'links':{}})
    by_native = {ns:{n['code']:n for n in nsitems} for ns,nsitems in native.items()}
    paths={p['id']:p for p in pilot['paths']}
    edges={e['id']:e for e in pilot['edges']}
    # Published activity correspondences only. Proposals and broad nxbase parent
    # expansions are not used to assign membership at the reference leaf level.
    for a in pilot['associations']:
        ns,code=a['native'];p=paths[a['path']]
        by_native[ns][code]['links'][a['reference']]={
            'relation':a['relation'], 'nodes':p['nodes'],
            'steps':[{**{k:edges[e].get(k,'') for k in ['source','location','note','left_part','right_part','raw_type']},'relation':p['relations'][i],'source_left':edges[e]['left'],'source_right':edges[e]['right'],'source_relation':edges[e]['relation']} for i,e in enumerate(p['edges'])],
            'status':'partial' if any(edges[e]['relation']=='Partial overlap' for e in p['edges']) else 'documented'}
    bridges=json.loads((inputs/'official-activity-bridges.json').read_text())
    sources.update({s['id']:s for s in bridges['sources']})
    for (ns,code),links in reviewed_pilot_routes(pilot,bridges).items():by_native[ns][code]['links']=links
    reviewed=json.loads((inputs/'nxbase-reviewed-activities.json').read_text())
    sources.update({s['id']:s for s in reviewed['sources']})
    for item in reviewed['items']:
        n=by_native[item['namespace']][item['code']]
        if n['name']!=item['name']:raise ValueError('Reviewed native name mismatch')
        if item['links']:
            n.update({k:item[k] for k in ['links','mapping_origin','review_note','reviewed_parent']})
        else:
            # The direct legacy industry table does not define this native
            # item. Retain the separate published producer footprint, with
            # explicit qualification, rather than promote it to containment.
            for link in n['links'].values():
                link.update(status='partial',exclusive_reference=False,mapping_origin='published_producing_activity',
                    review_note='Direct native-industry membership is unverified. This is only the published product / producing-activity footprint; it cannot establish exact NACE containment.')
    # A reviewed native activity containment route is more precise than a
    # product/producer path followed by a many-to-many revision correspondence.
    # Replace the complete old footprint for that native item, not just the
    # selected leaf. Pending anchors never contribute to a numeric colour.
    refinements=json.loads((inputs/'nxbase-activity-refinements.json').read_text())
    for source in [refinements['source'],refinements['evidence']]:
        sources[source['id']]=source
    node_names=dict(pilot['node_names'])
    node_names.update(bridges['node_names']);node_names.update(reviewed['node_names'])
    for item in refinements['items']:
        ns,code=item['native'];n=by_native[ns][code]
        if n['name']!=item['name']:
            raise ValueError('Refinement native label mismatch: '+code)
        for node,name in zip(item['nodes'],item['names']):
            node_names[':'.join(node)]=name
        n['links']={}
        route={'relation':'Native activity contained in NACE class via nxbase',
               'nodes':item['nodes'],'steps':item['steps'],'status':'reviewed',
               'review_note':item['review_note']}
        if item['status']=='reviewed':
            n['links'][item['reference']]=route
        else:
            n['pending']={**route,'status':'pending',
                          'references':item['candidate_references']}
    # Governed native parents plus explicit extensions, snapshotted from nxbase.
    # This supersedes section-only GLORIA context, never the original labels.
    governed=json.loads((inputs/'nxbase-gloria-icio.json').read_text())
    for source in governed['sources']:sources[source['id']]=source
    node_names.update(governed['node_names'])
    for item in governed['items']:
        native[item['namespace']].append({k:item[k] for k in ['code','name','links','mapping_origin','relation','review_note','lineage']})
    nace_based=json.loads((inputs/'nxbase-figaro-wiod.json').read_text())
    if nace_based['workbook_sha256']!=refinements['source']['sha256']:
        raise ValueError('Refresh all nxbase activity snapshots after a workbook update')
    for source in nace_based['sources']:sources[source['id']]=source
    for code,name in nace_based['node_names'].items():node_names.setdefault(code,name)
    for item in nace_based['items']:
        native[item['namespace']].append({k:item[k] for k in ['code','name','links','mapping_origin','relation','review_note','native_description','lineage']})
    gtap=json.loads((inputs/'nxbase-gtap.json').read_text())
    if gtap['workbook_sha256']!=refinements['source']['sha256']:
        raise ValueError('Refresh GTAP nxbase paths after a workbook update')
    for source in gtap['sources']:sources[source['id']]=source
    for code,name in gtap['node_names'].items():node_names.setdefault(code,name)
    for item in gtap['items']:
        native[item['namespace']].append({k:item[k] for k in ['code','name','links','mapping_origin','relation','review_note']})
    products=json.loads((inputs/'nxbase-products.json').read_text())
    if products['workbook_sha256']!=refinements['source']['sha256']:
        raise ValueError('Refresh all commodity snapshots after nxbase updates')
    for source in products['sources']:sources[source['id']]=source
    node_names.update(products['node_names'])
    for item in products['items']:
        if item.get('production_review'):
            activity_ns={'CEDA2024P':'CEDA2024','GLORIA060P':'GLORIA060'}[item['namespace']]
            activity=next(n for n in native[activity_ns] if n['code']==item['code'])
            if sorted(activity['links'])!=sorted(item['production_review']['producer_scope'][1]):
                raise ValueError('Refresh qualified product producer review: '+item['name'])
        for link in item['links'].values():
            steps=[products['route_steps'][s] for s in link['steps']]
            link['nodes']=[steps[0]['source_left'],*[s['source_right'] for s in steps]]
            if any(a['source_right']!=b['source_left'] for a,b in zip(steps,steps[1:])):
                raise ValueError('Disconnected compressed product route')
        native[item['namespace']].append(item)
    hybrid=json.loads((inputs/'nxbase-exiobase-hybrid.json').read_text())
    hybrid=reuse_shared_exiobase_activities(hybrid,native['EXIO3I'],
        json.loads((inputs/'exiobase-monetary-activities.json').read_text()),
        json.loads((inputs/'exiobase-hybrid-activities.json').read_text()))
    if hybrid['classification']!='EX3h' or len(hybrid['items'])!=164:
        raise ValueError('Unexpected Hybrid activity snapshot')
    for source in hybrid['sources']:
        if source['id']=='S24' and source['sha256']!=refinements['source']['sha256']:
            raise ValueError('Refresh all nxbase snapshots after a workbook update')
        sources[source['id']]=source
    for code,name in hybrid['node_names'].items():node_names.setdefault(code,name)
    native[hybrid['namespace']]=hybrid['items']
    # Official hierarchy; NACE headings are in parent-before-child order.
    nodes=[];ancestors={}
    for r in official['nodes']:
        code=r['code'];level=1 if code.isalpha() else 2 if len(code)==2 else 3 if len(code)==4 else 4
        parent=None if level==1 else ancestors[level-1]
        nodes.append({**r,'level':level,'parent':parent});ancestors[level]=code
    refs={'activity':{'label':'NACE Rev. 2.1','short_label':'NACE','leaf_name':'class','namespace':'NACE2.1','nodes':nodes,'leaf_level':4,'source':'S14'},
          'commodity':{'label':'CPA 2.2','short_label':'CPA','leaf_name':'subcategory','namespace':'CPA2.2','nodes':products['reference_nodes'],'leaf_level':6,'source':'P01'}}
    for ref in refs.values():
        indexed={n['code']:n for n in ref['nodes']}
        for node in ref['nodes']:
            current=node
            while current['parent']:current=indexed[current['parent']]
            node['section']=current['code']
        # Corrected CPA rows can be appended in source files. Display the
        # hierarchy in canonical order rather than treating file order as a parent.
        children=defaultdict(list)
        for n in ref['nodes']:children[n['parent']].append(n)
        ordered=[]
        def visit(parent):
            for n in sorted(children[parent],key=lambda n:n['code']):ordered.append(n);visit(n['code'])
        visit(None);ref['nodes']=ordered
        ref['leaves']=[n['code'] for n in ref['nodes'] if n['level']==ref['leaf_level']]
        ref['section_counts']={n['code']:sum(indexed[c]['section']==n['code'] for c in ref['leaves']) for n in ref['nodes'] if n['level']==1}
    # A published section anchor is useful search context, but expanding it to
    # every descendant class would invent native membership and a numeric score.
    gloria=json.loads((inputs/'gloria-060-sections.json').read_text())
    sources.update({s['id']:s for s in gloria['sources']})
    isic={n['code']:n for n in gloria['isic_nodes']}
    nace21={n['code']:n for n in refs['activity']['nodes']}
    revisions=defaultdict(list)
    for e in pilot['edges']:
        if e['source']=='S07':revisions[e['left'][1]].append(e)
    section_context=defaultdict(dict)
    for e in pilot['edges']:
        if e['source']!='S06':continue
        section=isic[e['right'][1]]['section']
        for revision in revisions[e['left'][1]]:
            leaf=nace21.get(revision['right'][1])
            if not leaf or leaf['level']!=4:continue
            section_context[section].setdefault(leaf['section'],{
                'isic_class':e['right'][1],'nace2_class':e['left'][1],
                'nace21_class':leaf['code'],'sources':['S06','S07'],
                'locations':[e['location'],revision['location']]})
    for item in gloria['native'] if not native['GLORIA060'] else []:
        anchors=[]
        for a in item['anchors']:
            node=['ISIC4',a['code']];node_names[':'.join(node)]=a['name']
            anchors.append({**a,'nodes':[['GLORIA060',item['code']],node],
                'steps':[{'source':'S18','location':a['location'],
                    'relation':'Published section correspondence',
                    'source_relation':'Published section correspondence',
                    'source_left':['GLORIA060',item['code']],'source_right':node,
                    'note':'The source gives a section, not an enumeration of descendant classes.'}],
                'reference_context':section_context[a['code']]})
        native['GLORIA060'].append({'code':item['code'],'name':item['name'],'links':{},
            'coarse':{'classification':'ISIC Rev. 4','anchors':anchors,
                'reference_sections':sorted({s for a in anchors for s in a['reference_context']}),
                'note':'Published section anchor only. Candidate NACE sections follow ISIC Rev. 4 → NACE Rev. 2 → NACE Rev. 2.1; this does not establish membership of the selected class.'}})
    # Catalogued but unmapped classifications remain selectable, explicitly gray.
    columns={'activity':[],'commodity':[]};groups={}
    # The published header code/label bridge, not row order, joins WIOD IOT/SUT.
    wiod_names={n['code']:n['name'] for n in native['WIOD2016']}
    for p in scope['profiles']:
        if len({r.get('iso3') or r['label'] for r in p['regions'] if r['kind']=='country'})<2:continue # National models are not compared.
        for dimension, labels in p['sets'].items():
            if dimension not in ['Sector','Activity','Commodity']:continue
            if dimension=='Activity':kind='activity'
            elif dimension=='Commodity':kind='commodity'
            elif p['family']=='CEDA':kind='activity' # Publisher's industry descriptors; qualified producer route.
            elif p['system'] in ['ixi','Industry']:kind='activity'
            elif p['system'] in ['pxp','Product / service']:kind='commodity'
            else:continue # Mixed/unspecified Sector is not silently assigned to either set.
            if kind!='activity':continue
            if p['family']=='WIOD' and dimension=='Activity':
                if set(labels)!=set(wiod_names):raise ValueError('WIOD activity code vocabulary changed')
                labels=[wiod_names[code] for code in labels]
            signature=hashlib.sha256(json.dumps(sorted(labels),ensure_ascii=False).encode()).hexdigest()[:12]
            key=(p['family'],p['units'],kind,signature)
            if key not in groups:
                known_ns='EXIO3I' if p['family']=='EXIOBASE' and p['units']=='Monetary' and kind=='activity' else 'EXIO3H' if p['family']=='EXIOBASE' and p['units']=='Hybrid' else 'ADB35' if p['family']=='ADB' else 'CEDA2024' if p['family']=='CEDA' else 'GLORIA060' if p['family']=='GLORIA' and p['release']=='060' else 'ICIO2025' if p['family']=='OECD' else 'FIGARO64' if p['family']=='FIGARO' else 'WIOD2016' if p['family']=='WIOD' else 'GTAP12POWERI' if p['family']=='GTAP' and p['release'].endswith('Power') else 'GTAP12I' if p['family']=='GTAP' else None
                values=native[known_ns] if known_ns else []
                # Reuse only if the actual set labels match the complete pilot vocabulary.
                if {n['name'] for n in values}!=set(labels):values=[]
                column={'id':'-'.join([p['family'].lower().replace(' ','-'),p['units'].lower(),kind,signature]),
                        'family':p['family'],'units':p['units'],'kind':kind,'native_count':len(labels),
                        'namespace':known_ns if values else None,'native':values,'releases':[],'years':[],
                        'profile_ids':[],'formats':[],'guide':p['guide'],'source_url':p['source_url'] or ('https://zenodo.org/records/7244919' if known_ns=='EXIO3H' else None),'workbook':p['workbook'],
                        'note':'Shared activity identities reuse the monetary correspondence footprint. Hybrid gas subdivisions and secondary lead retain their own nxbase routes; reviewed electricity paths and pending cases stay explicit.' if known_ns=='EXIO3H' else 'Open CEDA supplies emission factors for 400 industries, without a separate native Commodity set. BEA/NAICS and EPA concordances support this producing-activity lookup.' if p['family']=='CEDA' else 'GLORIA detailed footprints are editorial nxbase links checked against source descriptors and official definitions. Qualified overlaps remain explicit; this is not a publisher-supplied detailed concordance.' if p['family']=='GLORIA' else 'GTAP is shown only as activities, reflecting its single Sector set in the ixi representation. Published CPC and ISIC definitions support the NACE concordance; they do not add a separate Commodity set.' if p['family']=='GTAP' else '',
                        'status':'documented' if values else 'unverified'}
                groups[key]=column;columns[kind].append(column)
            c=groups[key];c['releases']=sorted(set(c['releases']+[p['release']]),key=lambda s:[int(x) if x.isdigit() else x for x in s.replace('.',' ').split()]) if p['release'] else c['releases']
            c['years']=sorted(set(c['years']+p['years']));c['profile_ids'].append(p['id']);c['formats']=sorted(set(c['formats']+[p['format']]))
    for p in scope['profiles']:
        if len({r.get('iso3') or r['label'] for r in p['regions'] if r['kind']=='country'})<2:continue
        # GTAP and Open CEDA expose one sector/industry vocabulary. Product
        # concordances support the activity lookup, not a second native set.
        if p['family'] in ['GTAP','CEDA']:continue
        labels=p['sets'].get('Commodity')
        if labels is None and p['system'] in ['pxp','Product / service']:
            labels=p['sets'].get('Sector')
        if labels is None:continue
        signature=hashlib.sha256(json.dumps(sorted(labels),ensure_ascii=False).encode()).hexdigest()[:12]
        key=(p['family'],p['units'],'commodity',signature)
        if key not in groups:
            ns=('EXIO3HIOTP' if p['format']=='IOT' else 'EXIO3HSUTP') if p['family']=='EXIOBASE' and p['units']=='Hybrid' else 'EXIO3P' if p['family']=='EXIOBASE' else 'CEDA2024P' if p['family']=='CEDA' else 'GLORIA060P' if p['family']=='GLORIA' else 'FIGARO64P' if p['family']=='FIGARO' else 'WIOD2016P' if p['family']=='WIOD' else None
            if p['family']=='EMERGING':
                candidates=[s for s in ['EMERGP','EMERG1P','EMERG2P'] if {n['name'] for n in native[s]}==set(labels)]
                ns=candidates[0] if candidates else None
            indexed={n['name']:n for n in native[ns]} if ns else {}
            values=[copy.deepcopy(indexed.get(label,{'code':'','name':label,'links':{},'mapping_origin':'unverified'})) for label in labels]
            known=sum(bool(n['links']) for n in values)
            c={'id':'-'.join([p['family'].lower().replace(' ','-'),p['units'].lower(),'commodity',signature]),
               'family':p['family'],'units':p['units'],'kind':'commodity','native_count':len(labels),
               'namespace':ns,'native':values,'releases':[],'years':[],'profile_ids':[],'formats':[],
               'guide':p['guide'],'source_url':p['source_url'],'workbook':p['workbook'],
               'note':'Product-only correspondence footprint. Published binary links and revision joins can be partial; no allocation weights are inferred.',
               'status':'documented' if known else 'unverified'}
            groups[key]=c;columns['commodity'].append(c)
        c=groups[key]
        c['releases']=sorted(set(c['releases']+([p['release']] if p['release'] else [])))
        c['years']=sorted(set(c['years']+p['years']));c['profile_ids'].append(p['id']);c['formats']=sorted(set(c['formats']+[p['format']]))
    for kind,cs in columns.items():
        cs.sort(key=lambda c:({'EXIOBASE':0,'ADB':1,'CEDA':2}.get(c['family'],3),c['family'],c['status']!='documented',{'Monetary':0,'Hybrid':1}.get(c['units'],2),c['native_count']))
        family_counts=defaultdict(int)
        for c in cs:family_counts[c['family']]+=1
        for c in cs:
            c['label']=c['family']+(' · '+c['units'] if family_counts[c['family']]>1 else '')+(' · '+('/'.join(c['formats'])) if sum(d['family']==c['family'] and d['units']==c['units'] for d in cs)>1 else '')
            if sum(d['family']==c['family'] and d['units']==c['units'] and d['formats']==c['formats'] for d in cs)>1:
                c['label']+=' · '+('/'.join(c['releases']) or str(c['native_count'])+' categories')
            if c['family']=='GTAP':c['label']='GTAP · Power' if gtap_power(c) else 'GTAP'
            c['default_visible']=not (c['family']=='EXIOBASE' and c['units']=='Hybrid')
            valid=set(refs[kind]['leaves'])
            for n in c['native']:n['links']={k:v for k,v in n['links'].items() if k in valid}
    # Deduplicate source steps rather than repeating full provenance in every cell.
    route_steps=dict(products['route_steps'])
    country_variants={'WIOD2016A':native['WIOD2016A']}
    inventories=[c['native'] for cs in columns.values() for c in cs]+list(country_variants.values())
    for inventory in inventories:
        for n in inventory:
            for link in [*n['links'].values(),*([n['lineage']] if n.get('lineage') else []),*([n['pending']] if n.get('pending') else []),*n.get('coarse',{}).get('anchors',[]),*([n['unresolved']] if n.get('unresolved') else [])]:
                for route in [link,*link.get('alternatives',[])]:
                    ids=[]
                    for step in route['steps']:
                        if isinstance(step,str):
                            if step not in route_steps:raise ValueError('Missing compressed product source step')
                            ids.append(step);continue
                        sid=hashlib.sha256(json.dumps(step,sort_keys=True).encode()).hexdigest()[:12]
                        route_steps[sid]=step;ids.append(sid)
                    route['steps']=ids
    return {'schema_version':1,'as_of':'2026-10-11','references':refs,'columns':columns,
            'route_steps':route_steps,'country_variants':country_variants,'node_names':node_names,'sources':{k:v for k,v in sources.items() if v.get('url')},
            'input_checksums':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs.glob('*.json')},
            'note':'Classification metadata only. Published correspondences can be partial or imprecise; counts are linked reference classes, not economic allocation weights.'}


def gtap_power(column):
    return column['family']=='GTAP' and any('Power' in r for r in column['releases'])


def enrich_country_scope(scope,sectoral):
    """Country lookup shares the exact typed NACE and CPA heatmap routes."""
    scope['mapping_routes']={}
    scope['mapping_route_steps']=sectoral['route_steps']
    scope['mapping_sources']=sectoral['sources']
    scope['mapping_node_names']=sectoral['node_names']
    scope['mappings']={k:v for k,v in scope['mappings'].items() if not k.startswith('sectoral-')}
    for profile in scope['profiles']:
        profile['mapping_ids']=[m for m in profile.get('mapping_ids',[profile.get('mapping')]) if m and not m.startswith('sectoral-')]
    wiod=next(c for c in sectoral['columns']['activity'] if c['family']=='WIOD')
    code_profiles=[p['id'] for p in scope['profiles'] if p['id'] in wiod['profile_ids'] and p['format']=='SUT']
    for kind,reference in sectoral['references'].items():
        key='nace-2.1' if kind=='activity' else 'cpa-2.2'
        scope['classifications'][key]={'id':key,'label':reference['label'],
            'source_url':sectoral['sources'][reference['source']]['url'],
            'levels':list(range(1,reference['leaf_level']+1)),'nodes':reference['nodes']}
        sections_by_code={n['code']:n['section'] for n in reference['nodes']}
        columns=list(sectoral['columns'][kind])
        if kind=='activity':
            columns.append({**wiod,'id':wiod['id']+'-native-codes',
                'native':sectoral['country_variants']['WIOD2016A'],
                'profile_ids':code_profiles,'country_only':True})
        for column in columns:
            if not column['native']:continue
            mid='sectoral-'+column['id'];entries=[];sections={};details={};coarse_entries=[]
            for native in column['native']:
                for code,link in native['links'].items():
                    route={k:link[k] for k in ['nodes','steps']}
                    rid=hashlib.sha256(json.dumps(route,sort_keys=True).encode()).hexdigest()[:16]
                    scope['mapping_routes'][rid]=route
                    details[native['code']]={k:link.get(k,native.get('link_defaults',{}).get(k,'')) for k in ['mapping_origin','review_note']}
                    details[native['code']]['mapping_origin']=link.get('mapping_origin',native.get('link_defaults',{}).get('mapping_origin','published'))
                    if native.get('native_description'):details[native['code']]['native_description']=native['native_description']
                    if native.get('native_identity'):details[native['code']]['native_identity']=native['native_identity']
                    entry={'native_code':native['code'],'native_label':native['name'],'official_code':code,
                        'precision':link['status'],'route_id':rid}
                    entries.append(entry)
                    section=sections_by_code[code]
                    sections[native['code'],section]={**entry,'official_code':section}
                if native.get('coarse',{}).get('direct_nace') and kind=='activity':
                    for anchor in native['coarse']['anchors']:
                        route={k:anchor[k] for k in ['nodes','steps']}
                        rid=hashlib.sha256(json.dumps(route,sort_keys=True).encode()).hexdigest()[:16]
                        scope['mapping_routes'][rid]=route
                        entry={'native_code':native['code'],'native_label':native['name'],'official_code':anchor['code'],
                            'reference_candidates':native['coarse']['reference_candidates'],'precision':'coarse','route_id':rid,
                            'mapping_origin':'governed_nxbase','review_note':native['coarse']['note'],
                            'relation':'Within a broader NACE anchor; leaf membership unverified'}
                        coarse_entries.append(entry)
                        for section in native['coarse']['reference_sections']:
                            sections.setdefault((native['code'],section),{**entry,'official_code':section})
            if not entries and not coarse_entries:continue
            scope['mappings'][mid]={'classification':key,'dimensions':['Sector','Activity' if kind=='activity' else 'Commodity'],
                'depth':reference['leaf_level'],'complete':False,'entries':entries,'coarse_entries':coarse_entries,
                'native_details':details,'section_entries':list(sections.values()),'source_url':column['source_url'],
                'classification_url':scope['classifications'][key]['source_url'],
                'basis':'Explicit typed '+kind+' routes. Qualified/editorial correspondences are not exact economic allocation.'}
            for profile in scope['profiles']:
                if profile['id'] in column['profile_ids']:
                    if kind=='activity' and profile['id'] in code_profiles and not column.get('country_only'):continue
                    profile['mapping_ids']=[mid,*[m for m in profile['mapping_ids'] if m!=mid]]
    return scope


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=Path(__file__).resolve().parents[1]/'classifications/sectoral')
    parser.add_argument('--scope',type=Path,default=Path(__file__).resolve().parents[1]/'source/_static/data/economy/country-scope.json')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'source/_static/data/economy/sectoral-scope.json')
    parser.add_argument('--country-output',type=Path,help='Refresh the NACE 2.1 country lookup from the same routes.')
    args=parser.parse_args();full=build(args.inputs,json.loads(args.scope.read_text()))
    # The Database scopes heatmap compares GTAP Standard only; the country lookup keeps the Power routes.
    result={**full,'columns':{k:[c for c in cs if not gtap_power(c)] for k,cs in full['columns'].items()}}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({'leaf_rows':{k:len(v['leaves']) for k,v in result['references'].items()},'columns':{k:[(c['label'],c['status'],sum(bool(n['links']) for n in c['native'])) for c in cs] for k,cs in result['columns'].items()},'bytes':args.output.stat().st_size}))
    if args.country_output:
        updated=enrich_country_scope(json.loads(args.scope.read_text()),full)
        args.country_output.parent.mkdir(parents=True,exist_ok=True)
        args.country_output.write_text(json.dumps(updated,ensure_ascii=False,separators=(',',':'))+'\n')
