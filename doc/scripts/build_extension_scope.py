"""Group the native satellite accounts of every MRIO family into reviewed extension categories.

Reads only set labels from the published profile details; no numerical data. Every
loaded label must match exactly one rule in doc/classifications/extensions/rules.json,
otherwise the build stops. Run after refreshing database_profiles.json.
"""
from pathlib import Path
import argparse, hashlib, json, re

DOC = Path(__file__).resolve().parents[1]
DATA = DOC / 'source/_static/data'
RULES = DOC / 'classifications/extensions/rules.json'
DISPLAY = {'Asian Development Bank': 'ADB', 'OECD': 'OECD ICIO'}


def satellite_labels(profile, data):
    flags = (profile.get('set_flags') or {}).get('Satellite account', {})
    if flags.get('status') in ('not_loaded', 'not_provided') or not profile.get('detail'):
        return []
    detail = json.loads((data.parent.parent / profile['detail']).read_text())
    placeholders = set(flags.get('placeholder_labels', []))
    return [label for label in detail.get('sets', {}).get('Satellite account', []) if label not in placeholders]


def classify(label, family_rules):
    for rule in family_rules:
        category, pattern = rule[0], rule[1]
        if re.search(pattern, label, flags=re.IGNORECASE):
            return category, (rule[2] if len(rule) > 2 else {})
    return None, None


def gas_of(label, gases, fixed=None):
    if fixed:
        return fixed
    lowered = label.lower()
    return next((g['id'] for g in gases if re.search(g['pattern'], lowered)), 'total')


def system_of(p):
    options = (p.get('provenance') or {}).get('options') or {}
    mode = options.get('iot_mode')
    return options.get('system') or {'product': 'pxp', 'industry': 'ixi'}.get(mode) or p.get('table') or ''


def period(years):
    years, parts = sorted({int(y) for y in years}), []
    for y in years:
        if parts and y == parts[-1][1] + 1:
            parts[-1][1] = y
        else:
            parts.append([y, y])
    return ', '.join(str(a) if a == b else f'{a}–{b}' for a, b in parts)


def release_key(release):
    return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', release)]


def build(data=DATA, rules_path=RULES):
    """Each reading keeps its own label set: accounts change across releases, variants and year groups."""
    rules = json.loads(rules_path.read_text())
    profiles = json.loads((data / 'database_profiles.json').read_text())['profiles']
    profiles += json.loads((data / 'external_profiles.json').read_text())['profiles']
    profiles = [p for p in profiles if p.get('status') in ('parsed', 'source_verified') and (p.get('counts') or {}).get('Region', 0) > 1]
    units = {}
    for p in profiles:
        units.setdefault(p['source'], set()).add(((p.get('provenance') or {}).get('options') or {}).get('unit') or 'Monetary')
    families, sets, unmatched = {}, {}, []
    for p in profiles:
        source = p['source']
        family = families.setdefault(source, {'family': DISPLAY.get(source, source), 'source': source, 'variants': {}, 'without': set()})
        unit = ((p.get('provenance') or {}).get('options') or {}).get('unit') or 'Monetary'
        # Variants are distinct products of one publisher: monetary/hybrid units, or Eora1/Eora2.
        variant = unit if len(units[source]) > 1 else (str(p.get('release')) if source == 'EORA' else '')
        labels = satellite_labels(p, data)
        if not labels:
            family['without'].add(str(p.get('release') or ''))
            continue
        groups = {}
        for label in labels:
            category, options = classify(label, rules['families'].get(source, []))
            if category is None:
                unmatched.append((source, label))
                continue
            cell = groups.setdefault(category, {'labels': [], 'gases': set()})
            cell['labels'].append(label)
            if category == 'ghg':
                cell['gases'].add(gas_of(label, rules['gases'], options.get('gas')))
        gas_order = [g['id'] for g in rules['gases']]
        content = {c: {'labels': sorted(v['labels']), **({'gases': sorted(v['gases'], key=gas_order.index)} if c == 'ghg' else {})}
                   for c, v in sorted(groups.items())}
        key = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
        sets[key] = content
        years = p.get('years') or [p.get('year')]
        family['variants'].setdefault(variant, []).append({'id': p['id'], 'release': str(p.get('release') or ''), 'system': system_of(p),
                                                           'years': period(y for y in years if y is not None), 'set': key})
    if unmatched:
        raise ValueError(f'{len(unmatched)} satellite labels match no extension rule, e.g. {unmatched[:20]}')
    out = []
    for source, f in sorted(families.items(), key=lambda item: item[1]['family']):
        without = rules['without'].get(source)
        if not f['variants'] and not without:
            without = {'status': 'not_loaded', 'note': 'No satellite accounts are loaded by the MARIO parser for the published readings.'}
        with_releases = {r['release'] for rs in f['variants'].values() for r in rs}
        variants = [{'variant': v, 'readings': sorted(rs, key=lambda r: (release_key(r['release']), r['years'], r['system']), reverse=True)}
                    for v, rs in sorted(f['variants'].items())]
        out.append({'family': f['family'], 'source': source, 'variants': variants,
                    'releases_without': sorted(r for r in f['without'] - with_releases if r),
                    **({'status': without['status'], 'note': without['note']} if without else {'status': 'loaded'})})
    # One shared label dictionary: sets differ by few accounts, so they store indices.
    labels = sorted({label for content in sets.values() for cell in content.values() for label in cell['labels']})
    index = {label: i for i, label in enumerate(labels)}
    packed = {key: {c: {**cell, 'labels': [index[l] for l in cell['labels']]} for c, cell in content.items()} for key, content in sorted(sets.items())}
    return {'schema_version': 2, 'categories': rules['categories'], 'gases': [{'id': g['id'], 'label': g['label']} for g in rules['gases']],
            'families': out, 'labels': labels, 'sets': packed,
            'note': 'Native satellite labels grouped by reviewed rules, per published reading (release, system and year group). Identical label sets are stored once.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DATA / 'economy/extension-scope.json')
    args = parser.parse_args()
    result = build()
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps({f['family']: {(v['variant'] or '-'): len(v['readings']) for v in f['variants']} | {'_status': f['status']} for f in result['families']}, ensure_ascii=False))
