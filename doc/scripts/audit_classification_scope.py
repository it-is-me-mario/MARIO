"""Validate every primary and alternative classification route, offline.

This audits provenance and the typed graph, not numerical aggregation weights.
Run after build_sectoral_scope.py; failing evidence never becomes zero coverage.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def audit(data):
    steps, sources = data['route_steps'], data['sources']
    checks = Counter()
    inventories = []
    used = set()
    product_namespaces = {
        'EXIO3P','EXIO3HSUTP','EXIO3HIOTP','USEEIO2017P','CEDA2024P',
        'GLORIA060P','FIGARO64P','WIOD2016P','GTAP12P','CPC2.1',
        'CPA2002','CPA2008','CPA2.1','CPA2.2',
    }
    for kind, reference in data['references'].items():
        nodes = {n['code']:n for n in reference['nodes']}
        assert len(nodes) == len(reference['nodes']), 'Duplicate reference code'
        leaves = set(reference['leaves'])
        assert len(leaves) == (651 if kind == 'activity' else 3354)
        assert all(nodes[c]['level'] == reference['leaf_level'] for c in leaves)
        for node in nodes.values():
            if node['parent']:
                assert nodes[node['parent']]['level']==node['level']-1, 'Invalid reference parent level'
            seen = set()
            while node:
                assert node['code'] not in seen, 'Reference hierarchy cycle'
                seen.add(node['code'])
                node = nodes[node['parent']] if node['parent'] else None
        checks['reference_nodes'] += len(nodes)
        checks['reference_leaves'] += len(leaves)
        assert sum(reference['section_counts'].values()) == len(leaves)
        assert len({c['id'] for c in data['columns'][kind]}) == len(data['columns'][kind])
        assert len({c['label'] for c in data['columns'][kind]}) == len(data['columns'][kind])
        for column in data['columns'][kind]:
            assert column['native_count'] == len(column['native'])
            codes = [n['code'] or n['name'] for n in column['native']]
            assert len(codes) == len(set(codes)), 'Duplicate native identity'
            missing, statuses = [], Counter()
            for native in column['native']:
                if not native['links']:
                    missing.append({'code':native['code'],'name':native['name'],
                                    'reason':'pending' if native.get('pending') else 'No verified fine correspondence'})
                for code, own in native['links'].items():
                    link = {**native.get('link_defaults',{}), **own}
                    assert code in leaves, 'Invalid reference endpoint'
                    assert link['nodes'][-1] == [reference['namespace'],code]
                    assert link['nodes'][0][1] == native['code']
                    assert not (link.get('exclusive_reference') is True and
                                (len(native['links']) != 1 or link['status'] == 'partial'))
                    statuses[link['status']] += 1
                    routes = [link, *link.get('alternatives',[])]
                    routes += [{'steps':ids} for ids in link.get('alternative_steps',[])]
                    for route in routes:
                        ids = route['steps']
                        assert ids, 'Empty correspondence route'
                        route_nodes = route.get('nodes')
                        if route_nodes is None:
                            route_nodes = [steps[ids[0]]['source_left'],*[steps[s]['source_right'] for s in ids]]
                        assert len(route_nodes) == len(ids)+1
                        assert route_nodes[0] == link['nodes'][0]
                        assert route_nodes[-1] == link['nodes'][-1]
                        assert len({tuple(n) for n in route_nodes}) == len(route_nodes), 'Correspondence cycle'
                        if kind == 'commodity':
                            assert all(n[0] in product_namespaces for n in route_nodes), 'Activity leaked into product route'
                        for i, sid in enumerate(ids):
                            step = steps[sid]
                            assert {tuple(route_nodes[i]),tuple(route_nodes[i+1])} == {
                                tuple(step['source_left']),tuple(step['source_right'])}, 'Disconnected route'
                            assert sources[step['source']].get('url') and step.get('location')
                            if step.get('part_flags_origin'):
                                assert 'derived' in step['part_flags_origin'].lower() or 'published' in step['part_flags_origin'].lower()
                            used.add(sid)
                            checks['edge_visits'] += 1
                        checks['routes'] += 1
                    checks['native_reference_links'] += 1
                checks['native_categories'] += 1
            inventories.append({'id':column['id'],'label':column['label'],'kind':kind,
                'native':len(column['native']),'linked':len(column['native'])-len(missing),
                'statuses':dict(statuses),'unverified':missing})
    checks['unique_used_steps'] = len(used)
    checks['sources'] = len(sources)
    notes = [
        'A connected correspondence path is not proof of exact containment. Published binary links, revision joins and producer bridges retain qualified precision.',
        'Activity and commodity graphs are separate. Commodity routes never traverse an activity namespace. Explicit product-to-producer activity bridges remain typed and qualified.',
        'Workbook parents are retained as lineage context. Current reviewed membership overrides do not rewrite nxbase_sets.xlsx or materialise SQL.',
        'Raw milk includes cattle, sheep and goat farming; wastewater treatment is sewerage. EXIOBASE crops, metals, waste technologies and legacy source anomalies have explicit editorial reviews.',
        'Hybrid product coverage uses the published 200 SUT to 164 IOT product correspondence, including all seven monetary products without CPA 2002 links.',
        'CEDA and GLORIA product routes through EPA/BEA aggregates are qualified. Explicit producer-scope exclusion reviews remove incompatible candidates; this cannot prove every remaining fine product link.',
        'GTAP thermal electricity/heat co-production remains qualified. The historical technical note assigns no heat to wind, solar, hydro or nuclear; no licensed numerical data are exported.',
        'EMERGING has native product inventories but no verified fine CPA bridge. EORA has no verified current fine concordance. OECD and ADB IOT industry sets are activities, not inferred product sets.',
        'NACE 46.89 has no predecessor in the supplied NACE 2 revision table; an unverified cell is not absence. CPA 2002 codes 33.30.90, 34.10.25 and 34.10.43 are absent from the historical revision table.',
        'EXIOBASE fertiliser and six landfill products lack CPA 2002 publisher links. GTAP product definitions without CPC codes remain unverified. No fuzzy matching or economic allocation weights are used.',
    ]
    return {'as_of':data['as_of'],'checks':dict(checks),'inventories':inventories,
            'notes':notes,'sources':sources}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--doc',type=Path,default=Path(__file__).resolve().parents[1])
    args = cli.parse_args()
    path = args.doc/'source/_static/data/economy/sectoral-scope.json'
    data = json.loads(path.read_text())
    for name, digest in data['input_checksums'].items():
        source = args.doc/'classifications/sectoral'/name
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, 'Stale source snapshot: '+name
    report = audit(data)
    country = json.loads(path.with_name('country-scope.json').read_text())
    checked_routes = set()
    checked_entries = 0
    for mid, mapping in country['mappings'].items():
        if not mid.startswith('sectoral-'):
            continue
        reference = country['classifications'][mapping['classification']]
        leaves = {n['code'] for n in reference['nodes'] if n['level']==mapping['depth']}
        for entry in mapping['entries']:
            assert entry['official_code'] in leaves, 'Invalid country reference endpoint'
            route = country['mapping_routes'][entry['route_id']]
            assert route['nodes'][-1][1] == entry['official_code']
            assert len({tuple(n) for n in route['nodes']})==len(route['nodes'])
            assert len(route['nodes'])==len(route['steps'])+1
            for i, sid in enumerate(route['steps']):
                edge = country['mapping_route_steps'][sid]
                assert {tuple(route['nodes'][i]),tuple(route['nodes'][i+1])}=={
                    tuple(edge['source_left']),tuple(edge['source_right'])}
                assert country['mapping_sources'][edge['source']]['url'] and edge['location']
            checked_routes.add(entry['route_id'])
            checked_entries += 1
    for profile in country['profiles']:
        labels = set(label for values in profile['sets'].values() for label in values)
        for mid in profile.get('mapping_ids', []):
            if mid.startswith('sectoral-'):
                assert all(e['native_label'] in labels for e in country['mappings'][mid]['entries']), 'Country native identity mismatch'
    report['checks'].update(country_unique_routes=len(checked_routes),country_entries=checked_entries)
    report['notes'].append('Country lookups, including GTAP Power and the separate WIOD SUT activity vocabulary, are checked against the same current references and actual native profile labels.')
    report['notes'].append('GTAP and Open CEDA are displayed only in Activities: their catalogued sector/industry vocabularies do not supply a separate native Commodity set. CPC and EPA product concordances remain documented intermediate sources; Open CEDA provides emission factors rather than a raw IOT.')
    report['compiled_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    output = path.with_name('classification-audit.json')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines = ['# Concordance review — NACE Rev. 2.1 and CPA 2.2', '',
        f'Review completed {report["as_of"]}. Reproduce with `snapshot_nxbase_scope.py`, '
        '`build_sectoral_scope.py`, then `audit_classification_scope.py`.', '',
        'All primary and alternative routes were checked for typed dimensions, valid leaf endpoints, '
        'continuity, cycles, attributable sources and native identities. This is a classification '
        'lookup, not an allocation matrix.','', '| Dimension / database | Native categories | With fine links | Unverified / pending |',
        '|---|---:|---:|---:|']
    for row in report['inventories']:
        lines.append(f'| {row["kind"]} / {row["label"]} | {row["native"]} | {row["linked"]} | {len(row["unverified"])} |')
    lines += ['', '## Corrections and limits', '', *['- '+n for n in report['notes']], '',
        '## Full route checks', '', *[f'- {k}: {v:,}' for k,v in report['checks'].items()], '',
        '## Source register', '', '| ID | Source | URL | SHA-256 |', '|---|---|---|---|']
    for sid,s in sorted(report['sources'].items()):
        lines.append(f'| {sid} | {s.get("title",s.get("filename",sid))} | {s["url"]} | {s.get("sha256","")} |')
    lines += ['', '## Unverified native categories', '']
    for row in report['inventories']:
        if row['unverified']:
            lines += ['### '+row['kind']+' / '+row['label'], '',
                *[f'- `{n["code"]}` {n["name"]}: {n["reason"]}' for n in row['unverified']], '']
    (args.doc.parent/'CONCORDANCE_REVIEW.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(report['checks']))


if __name__ == '__main__':
    main()
