"""Publish REX3 source-label scope, without reading the economic matrices.

The source nomenclature is distinct from a fresh MARIO parse. REX3 remains in
EXIOBASE's Overview family and gets its own geography Version and native
classification identity. No standard EXIOBASE concordances are inherited.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import xlsxwriter

DOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DOC.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mario.parsers.exiobase_rex import (
    REX3Layout, REX3_GHG_LABELS, _read_labels, _read_hdf5_cellstr, _split_label_and_unit,
)
from mario.parsers.specs import REX3_ZENODO_URL, REX3_GHG_ZENODO_URL
from database_geography import add_geography
from build_country_scope import source_only_profile


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_profile(labels, year=2022):
    labels = Path(labels)
    if not 1995 <= year <= 2022:
        raise ValueError('The pinned REX3 release covers 1995–2022')
    countries, sectors, _ = _read_labels(REX3Layout(labels, labels, labels, labels, year))
    q = [_split_label_and_unit(s) for s in _read_hdf5_cellstr(labels/'Labels_Q_REX3.mat', 'Labels_Q_REX3').ravel(order='F')]
    factors = [s for s, _ in q if s.casefold().startswith('value added')]
    satellites = [s for s, _ in q if s not in factors] + list(REX3_GHG_LABELS)
    household = _read_hdf5_cellstr(labels/'Labels_Sectors_REX3.mat', 'Labels_Sectors_REX3').ravel(order='F')[-1]
    sets = {'Region': countries, 'Sector': sectors, 'Satellite account': satellites,
            'Factor of production': factors, 'Consumption category': [household]}
    profile = {
        'schema_version': 1, 'id': 'exiobase-rex3-source-scope', 'source': 'EXIOBASE',
        'guide': 'exiobase-rex3', 'label': 'EXIOBASE REX3 · published nomenclature',
        'release': 'REX3', 'version': 'REX3', 'variant': 'REX3', 'year': year,
        'years': list(range(1995, 2023)), 'table': 'IOT', 'status': 'source_verified',
        'parser_supported': True, 'environmental': True, 'numeric_publication': False,
        'counts': {key: len(value) for key, value in sets.items()}, 'sets': sets,
        'region_counts': [{'region': region, 'set': 'Sector', 'count': len(sectors)} for region in countries],
        'set_flags': {}, 'classifications': {'status': 'native_labels', 'mappings': [],
            'native_classification': 'REX3 native activities; no inherited standard EXIOBASE concordances.'},
        'coverage_signatures': {'geography': digest(sorted(countries)), 'economic': digest(sorted(sectors))},
        'provenance': {'method': 'public_source_labels', 'source_url': REX3_ZENODO_URL,
            'source_checksums': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(labels.glob('*.mat'))},
            'options': {'unit': 'Monetary', 'variant': 'REX3', 'system': 'ixi'},
            'reading_scope': 'Published economic labels and documented mandatory GHG companion. No economic matrices read or numerical indicators calculated.'},
        'source_url': 'https://zenodo.org/records/10354283',
        'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'attribution': 'Livia Cabernard, Stephan Pfister and Stefanie Hellweg; GHG extension with Clemens Schwingshackl. CC BY 4.0.',
        'scope_note': 'Source-verified nomenclature, not a new parse of the 2022 MRIO. Six detailed GHG/LULUCF labels follow the documented companion at '+REX3_GHG_ZENODO_URL+'. Historical regions and unmatched territorial labels retain their source identities.',
        'workbook': '_static/data/external_profiles/exiobase-rex3-source-scope-sets.xlsx',
        'detail': '_static/data/external_profiles/exiobase-rex3-source-scope.json',
        'website_years': [],
    }
    return add_geography(profile)


def workbook(profile, path):
    with xlsxwriter.Workbook(path, {'strings_to_formulas': False, 'strings_to_urls': False}) as book:
        header = book.add_format({'bold': True, 'bg_color': '#FFF1BD'})
        def sheet(name, columns, rows):
            ws = book.add_worksheet(name); ws.freeze_panes(1, 0)
            ws.write_row(0, 0, columns, header)
            for i, row in enumerate(rows, 1): ws.write_row(i, 0, row)
            ws.autofilter(0, 0, len(rows), len(columns)-1); ws.set_column(0, len(columns)-1, 34)
        sheet('Provenance', ['Field', 'Value'], [
            ['Database', profile['label']], ['Status', 'Source-verified labels; no numerical MRIO parse'],
            ['Source', profile['source_url']], ['Licence', profile['license_url']], ['Attribution', profile['attribution']],
            ['Scope', profile['scope_note']], ['Source checksums', json.dumps(profile['provenance']['source_checksums'])]])
        for key, values in profile['sets'].items():
            sheet({'Region':'Regions','Sector':'Sectors','Satellite account':'Satellite accounts','Factor of production':'Factors','Consumption category':'Final demand'}[key],
                  ['Position', 'Label'], [[i, v] for i, v in enumerate(values, 1)])
        sheet('Country mapping', ['Original label', 'Representation', 'ISO3'],
              [[r['label'], r['kind'], r.get('iso3', '')] for r in profile['geography']['regions']])


def publish(labels, data=DOC/'source/_static/data'):
    data = Path(data); profile = source_profile(labels)
    detail = data.parent.parent/profile['detail']; detail.parent.mkdir(exist_ok=True, parents=True)
    detail.write_text(json.dumps(profile, ensure_ascii=False, separators=(',', ':'))+'\n')
    workbook(profile, data.parent.parent/profile['workbook'])
    registry = data/'external_profiles.json'; external = json.loads(registry.read_text())
    summary = {k: v for k, v in profile.items() if k != 'sets'}
    external['profiles'] = [p for p in external['profiles'] if p['id'] != profile['id']] + [summary]
    registry.write_text(json.dumps(external, ensure_ascii=False, separators=(',', ':'))+'\n')
    scope_path = data/'economy/country-scope.json'; scope = json.loads(scope_path.read_text())
    catalogue = json.loads((data/'database_profiles.json').read_text())
    scope['profiles'] = [p for p in scope['profiles'] if p['id'] != profile['id']] + [source_only_profile(profile, profile, catalogue['guides'])]
    scope_path.write_text(json.dumps(scope, ensure_ascii=False, separators=(',', ':'))+'\n')
    return profile


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--labels', type=Path, required=True)
    cli.add_argument('--data', type=Path, default=DOC/'source/_static/data')
    args = cli.parse_args(); p = publish(args.labels, args.data)
    print(json.dumps({'status': p['status'], 'counts': p['counts'], 'unresolved': [r['label'] for r in p['geography']['regions'] if r['kind']=='unresolved']}))
