"""Compose BONSAI's observed HIOT identities with its supplied concordances.

Activity and product paths stay separate. A source aggregate is expanded only
when the correspondence defines that native aggregate itself. A detailed child
inside a broad NACE anchor keeps context only, never all descendant memberships.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import defaultdict


def nace_code(raw, level=None):
    raw = str(raw).strip()
    if raw.isalpha():
        return raw
    if not re.fullmatch(r'\d{1,2}(?:\.\d{1,2})?', raw):
        return None
    head, dot, tail = raw.partition('.')
    if level == 4:
        tail = tail.ljust(2, '0')
    return head.zfill(2) + ('.'+tail if dot else '')


def step(left, right, source, location, relation, note=''):
    return dict(source_left=left, source_right=right, source=source,
                location=location, relation=relation, source_relation=relation, note=note)


def official_step(edge):
    return {**{k:v for k,v in edge.items() if k not in {'id','left','right'}},
            'source_left':edge['left'], 'source_right':edge['right'],
            'source_relation':edge['relation']}


def route(steps, note='', partial=False):
    return dict(nodes=[steps[0]['source_left'], *[s['source_right'] for s in steps]],
                steps=steps, relation='Supplied BONSAI classification footprint',
                status='partial' if partial or any('partial' in s['relation'].lower() or s.get('qualified') for s in steps) else 'documented',
                exclusive_reference=False, mapping_origin='published_bonsai', review_note=note)


def add(links, reference, value):
    if reference not in links:
        links[reference] = value
    elif value['steps'] != links[reference]['steps']:
        existing = links[reference]
        existing.setdefault('alternatives', []).append({k:value[k] for k in ['nodes','steps']})
        if value['status']=='partial':
            existing['status']='partial'


def build_bonsai(inputs, references, scope):
    data = json.loads((inputs/'bonsai-native-correspondences.json').read_text())
    products = json.loads((inputs/'commodity-correspondences.json').read_text())
    bridges = json.loads((inputs/'official-activity-bridges.json').read_text())
    review_path = inputs/'bonsai-current-reviews.json'
    reviews = json.loads(review_path.read_text())
    reviewed = {kind:{r['native']:r for r in rows} for kind,rows in reviews.items() if kind in {'activity','commodity'}}
    profile = next(p for p in scope['profiles'] if p['id']==data['profile_id'])
    if set(profile['sets']['Sector']) != {r['product'] for r in data['references']}:
        raise ValueError('Refresh BONSAI classification snapshot after changing native HIOT identities')
    memberships = {(region,code) for region,sets in profile['memberships'].items() for code in sets['Sector']}
    if memberships != {(region,r['product']) for r in data['references'] for region in r['regions']}:
        raise ValueError('Refresh BONSAI classification snapshot after changing regional HIOT memberships')
    names = {}
    for r in data['references']:
        names['BONSAIA:'+r['activity']] = r['activity_name']
        names['BONSAIP:'+r['product']] = r['product_name']
        names['BONSAIHIOT:'+r['product']] = r['product_name']
    for kind,ns in [('activity','BONSAIA'),('commodity','BONSAIP')]:
        valid = set(references[kind]['leaves'])
        for code,own in reviewed[kind].items():
            if names.get(ns+':'+code) != own['name'] or not set(own['references']) <= valid:
                raise ValueError('Refresh the explicit BONSAI current-definition review: '+code)

    old_nodes = {}
    for n in data['nace_nodes']:
        code = nace_code(n['code'], n['level'])
        old_nodes[code] = {**n, 'code':code}
        names['NACE2:'+code] = n['name']
    old_leaves = {c for c,n in old_nodes.items() if n['level']==4}
    # NACE's numeric hierarchy uses code prefixes. Section membership is taken
    # from the official structure order, not guessed from a native label.
    section = None
    for n in data['nace_nodes']:
        code = nace_code(n['code'], n['level'])
        if n['level']==1:
            section = code
        old_nodes[code]['section'] = section

    def old_members(code):
        if code not in old_nodes:
            return []
        if code in old_leaves:
            return [code]
        if code.isalpha():
            return sorted(c for c in old_leaves if old_nodes[c]['section']==code)
        prefix = code if '.' in code else code+'.'
        return sorted(c for c in old_leaves if c.startswith(prefix))

    revisions = defaultdict(list)
    for e in bridges['edges']:
        if e['source']=='S07':
            assert e['left'][0]=='NACE2' and e['right'][0]=='NACE2.1'
            revisions[e['left'][1]].append(e)
    direct = {r['native']:r for r in data['nace'] if r['code']}
    if len({r['native'] for r in data['nace']}) != len(data['nace']):
        raise ValueError('Review the changed BONSAI native/NACE correspondence cardinality')
    aggregates = {kind:{r['native']:r for r in rows} for kind,rows in data['aggregates'].items()}

    def aggregate_code(raw):
        # L68A/B are custom owner/non-owner subdivisions, not official nodes.
        if re.fullmatch(r'[A-U]\d{2}', raw):
            return raw[1:]
        return raw if re.fullmatch(r'[A-U]', raw) else None

    def activity(code):
        links = {}
        origin = ['BONSAIA', code]
        if '|' in code:
            for part in code.split('|'):
                component, _ = activity(part)
                prefix = step(origin, ['BONSAIA',part], 'B02',
                              'HIOT column identity '+code, 'Source combined process identity',
                              'Pipe-separated components are retained as a supplied aggregate; no new production nodes are added.')
                for ref, own in component.items():
                    add(links, ref, route([prefix,*own['steps']], own['review_note'], True))
            return links, None
        own = direct.get(code)
        anchor = nace_code(own['code']) if own else None
        members = old_members(anchor)
        source, location = ('B01', own['location']) if own else ('','')
        full_aggregate = False
        if code in aggregates['activity'] and len(members)!=1:
            aggregate = aggregates['activity'][code]
            declared = aggregate_code(aggregate['code'])
            complete = old_members(declared)
            if complete and (not members or set(complete)<=set(members)):
                anchor, members = declared, complete
                source, location = 'B07', aggregate['location']
                full_aggregate = True
        if not members:
            return links, None
        first = step(origin, ['NACE2',anchor], source, location,
                     'Supplied complete aggregate definition' if full_aggregate else 'Supplied native NACE anchor')
        market = code.startswith('M_')
        note = ('BONSAI assigns this market the producing-sector footprint of its traded product. '
                'This is a qualified producer lookup, not an assertion that market operation is manufacturing.' if market else
                'Native process footprint supplied by BONSAI, followed by the official revision. '
                'Regional vocabularies overlap; no exclusive partition or allocation weights are claimed.')
        if anchor not in old_leaves and len(members)>1 and not full_aggregate:
            candidates = sorted({e['right'][1] for c in members for e in revisions[c]})
            return links, dict(classification_label='NACE Rev. 2',
                reference_candidates=candidates,
                reference_sections=sorted({next(n['section'] for n in references['activity']['nodes'] if n['code']==c) for c in candidates}),
                anchors=[dict(code=anchor, **route([first], note, True))],
                note='The source gives a broader NACE anchor for this detailed process. Descendant classes are possible context only and do not enter the resolution index.')
        for old in members:
            path = [first]
            if old != anchor:
                path.append(step(['NACE2',anchor], ['NACE2',old], 'B10',
                                 'NACE Rev. 2 structure · '+old,
                                 'Member of supplied complete aggregate definition' if full_aggregate else 'Only leaf of supplied NACE anchor'))
            for edge in revisions[old]:
                add(links, edge['right'][1], route([*path,official_step(edge)], note, market))
        if code in reviewed['activity']:
            review = reviewed['activity'][code]
            if not set(review['references']) <= links.keys():
                raise ValueError('Reviewed activity lacks an official revision route: '+code)
            links = {k:v for k,v in links.items() if k in review['references']}
            for link in links.values():
                link.update(status='reviewed',mapping_origin='reviewed_editorial',
                            review_note=review['note'],evidence=['B11','B03','S14'])
        return links, None

    cpa21 = {n['code']:n for n in products['structures']['CPA2.1']}
    cpa08 = {n['code']:n for n in products['structures']['CPA2008']}
    if not all(r['code'] in cpa21 for r in data['cpa']):
        raise ValueError('The revised BONSAI CPA source does not match CPA 2.1')
    cpa_direct = defaultdict(list)
    for r in data['cpa']:
        cpa_direct[r['native']].append((r,'B04'))
    revised_natives = set(cpa_direct)
    for r in data['cpa_legacy']:
        if r['native'] not in revised_natives:
            code = r['code'].split('.')
            r = {**r,'code':'.'.join([code[0].zfill(2),*code[1:]])}
            if r['code'] in cpa21:
                cpa_direct[r['native']].append((r,'B05'))
    product_revisions = defaultdict(list)
    for e in products['edges']:
        if (e['source']=='P04' and e['left'][0]=='CPA2008' and e['right'][0]=='CPA2.1'
            or e['source']=='P05' and e['left'][0]=='CPA2.1' and e['right'][0]=='CPA2.2'):
            product_revisions[tuple(e['left'])].append(e)

    def terminals(node, path):
        if node[0]=='CPA2.2':
            if node[1] in references['commodity']['leaves']:
                yield node[1], path
            return
        for e in product_revisions[tuple(node)]:
            yield from terminals(e['right'], [*path, official_step(e)])

    markets = defaultdict(list)
    for row in data['markets']:
        markets[row['market']].append(row)

    def product(code, namespace='BONSAIP', trail=()):
        if code in trail:
            raise ValueError('Cyclic BONSAI product / market correspondence: '+code)
        trail = (*trail,code)
        links = {}
        origin = [namespace,code]
        if '|' in code:
            for part in code.split('|'):
                prefix = step(origin, [namespace,part], 'B02', 'HIOT row identity '+code,
                              'Source combined product identity')
                for ref, own in product(part, namespace, trail).items():
                    add(links,ref,route([prefix,*own['steps']], own['review_note'], True))
            return links
        if code.startswith('M_'):
            for row in markets[code]:
                if row['product']==code:
                    # A source identity row provides no product classification
                    # bridge and must not generate a self-referencing route.
                    continue
                prefix = step(origin, ['BONSAISUTP',row['product']], 'B09', row['location'],
                              'Supplied product / market correspondence',
                              'Qualified traded-product footprint; no product/market identity or allocation is asserted.')
                for ref, own in product(row['product'], 'BONSAISUTP',trail).items():
                    add(links,ref,route([prefix,*own['steps']], own['review_note'], True))
            return links
        note = 'Supplied BONSAI product correspondence and official CPA revisions. Binary and many-to-many links are qualified footprints, not allocation weights.'
        for row,source in cpa_direct[code]:
            first = step(origin, ['CPA2.1',row['code']], source,row['location'],
                         'Supplied detailed product correspondence')
            for ref, path in terminals(['CPA2.1',row['code']], [first]):
                add(links,ref,route(path,note,True))
        if code in reviewed['commodity']:
            review = reviewed['commodity'][code]
            if not links:
                first = step(origin,['CPA2.1',review['legacy_cpa21']], 'B11',
                             'commodity review · '+code,'Editorial product-definition correspondence',review['note'])
                for ref,path in terminals(['CPA2.1',review['legacy_cpa21']],[first]):
                    add(links,ref,route(path,review['note'],True))
            if not set(review['references']) <= links.keys():
                raise ValueError('Reviewed product lacks an official revision route: '+code)
            links = {k:v for k,v in links.items() if k in review['references']}
            for link in links.values():
                link.update(mapping_origin='reviewed_editorial',review_note=review['note'],
                            evidence=['B11','B03','P03','P05'])
        if links or code not in aggregates['commodity']:
            return links
        own = aggregates['commodity'][code]
        head = aggregate_code(own['code'])
        if head not in cpa08:
            return links
        def inside(n):
            while n:
                if n['code']==head:
                    return True
                n = cpa08.get(n['parent'])
            return False
        for leaf in (n for n in cpa08.values() if n['level']==6 and inside(n)):
            first = step(origin,['CPA2008',head],'B08',own['location'],'Supplied complete aggregate product definition')
            definition = step(['CPA2008',head],['CPA2008',leaf['code']], 'P04',leaf.get('uri',leaf['code']),
                              'Member of supplied complete aggregate definition')
            for ref, path in terminals(['CPA2008',leaf['code']], [first,definition]):
                add(links,ref,route(path,note,True))
        return links

    activity_native = {}
    for r in data['references']:
        code = r['activity']
        if code not in activity_native:
            links, coarse = activity(code)
            activity_native[code] = dict(code=code,name=r['activity_name'],links=links)
            if coarse:
                activity_native[code]['coarse']=coarse
    product_native = [dict(code=r['product'],name=r['product_name'],links=product(r['product'])) for r in data['references']]
    country_activity = []
    for r in data['references']:
        own = copy.deepcopy(activity_native[r['activity']])
        own.update(code=r['product'],name=r['product'],native_description=r['activity_name'])
        prefix = step(['BONSAIHIOT',r['product']],['BONSAIA',r['activity']], 'B02',
                      'HIOT reference pair '+r['product']+' / '+r['activity'],
                      'Supplied reference product / process association',
                      'This identifies the process of this HIOT sector; it is not an activity/product equivalence.')
        for link in own['links'].values():
            for path in [link,*link.get('alternatives',[])]:
                path['nodes'] = [prefix['source_left'], *path['nodes']]
                path['steps'] = [copy.deepcopy(prefix), *path['steps']]
        if own.get('coarse'):
            for anchor in own['coarse']['anchors']:
                anchor['nodes']=[prefix['source_left'],*anchor['nodes']]
                anchor['steps']=[copy.deepcopy(prefix),*anchor['steps']]
        country_activity.append(own)
    country_product = [dict(**{k:v for k,v in n.items() if k!='name'},name=n['code'],native_description=n['name']) for n in copy.deepcopy(product_native)]
    # Keep repeated precision notes once per native item, as in the existing
    # commodity snapshots. All consumers merge these defaults before use.
    for inventory in [list(activity_native.values()),product_native,country_activity,country_product]:
        for native in inventory:
            links = list(native['links'].values())
            if not links:
                continue
            defaults = {}
            for key in ['relation','status','exclusive_reference','mapping_origin','review_note','evidence']:
                if key in links[0] and all(link.get(key)==links[0][key] for link in links):
                    defaults[key] = links[0][key]
                    for link in links:
                        del link[key]
            if defaults:
                native['link_defaults'] = defaults
    columns = {}
    for kind,ns,inventory,variant in [('activity','BONSAIA',sorted(activity_native.values(),key=lambda n:n['code']),'BONSAIHIOTA'),
                                       ('commodity','BONSAIP',product_native,'BONSAIHIOTP')]:
        columns[kind] = dict(id='bonsai-hybrid-'+kind,family='BONSAI',label='BONSAI',units='Hybrid',kind=kind,
            native_count=len(inventory),namespace=ns,native=inventory,releases=[profile['release']],years=profile['years'],
            profile_ids=[profile['id']],formats=['IOT'],guide=profile['guide'],workbook=profile['workbook'],
            source_url=profile['source_url'],status='documented',country_variant=variant,
            scope_note='Regional union: 1,707 identities; each region has 355–1,332 sectors. Global contains 355 markets.',
            note='Union of observed regional HIOT '+('process' if kind=='activity' else 'reference-product')+' identities; 355–1,332 sectors per region. '
                 'The 355 Global nodes are markets and do not represent the complete classification. '
                 +('Market NACE links describe the publisher-supplied producing-sector footprint and remain qualified. Broad detailed-process anchors do not establish leaf membership.' if kind=='activity' else 'Markets follow explicit product/market correspondences. Capital, carrier and other products without supplied links remain unverified.'))
    review_source=dict(id='B11',title='MARIO · BONSAI current electricity-definition reviews',
        filename=review_path.name,sha256=hashlib.sha256(review_path.read_bytes()).hexdigest(),
        publisher='MARIO / nxbase editorial review',url=review_path.name,retrieved=reviews['as_of'],role=reviews['note'])
    return dict(columns=columns, sources=[*data['sources'],review_source], node_names=names,
                country_variants=dict(BONSAIHIOTA=country_activity,BONSAIHIOTP=country_product),as_of=data['as_of'])
