"""Snapshot local BONSAI classification facts without parsing an IO database.

Only the frozen HIOT row/column identities are read from its pickle. Numerical
flows, personal source metadata and local paths never enter the snapshot.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot(bonsai, technosphere):
    sources = []

    def source(sid, relative, title, note=''):
        path = bonsai / relative
        sources.append(dict(id=sid, title=title, filename=path.name,
                            sha256=digest(path), publisher='BONSAI',
                            url='https://bonsai.uno/', retrieved='2026-10-22',
                            role=note or 'Source correspondence supplied in the local BONSAI classification bundle; the homepage is attribution, not a verified public download of this file.'))
        return path

    def records(sid, relative, title):
        path = source(sid, relative, title)
        with path.open(encoding='utf-8-sig', newline='') as stream:
            return [(i, row) for i, row in enumerate(csv.DictReader(stream), 2)]

    classification = source('B03', '_b Next version/Balanced/20260615/classification.csv',
                            'BONSAI Balanced 20260615 · native descriptions')
    descriptions = {}
    with classification.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            descriptions.setdefault(row['name'], row['description'])

    def name(code):
        if code in descriptions:
            return descriptions[code]
        if '|' in code:
            return '; '.join(descriptions.get(part, part) for part in code.split('|'))
        return code

    frame = pd.read_pickle(technosphere)
    references = {}
    for product_label, activity_label in zip(frame.index, frame.columns):
        region, product, unit = product_label.split(';')
        activity_region, activity = activity_label.split(';')
        if region != activity_region:
            raise ValueError('Reference activity and product regions differ')
        own = references.setdefault(product, dict(product=product, activity=activity,
            product_name=name(product), activity_name=name(activity), regions=[]))
        if own['activity'] != activity:
            raise ValueError('Country activity lookup requires an unambiguous reference producer: '+product)
        own['regions'].append(region)
    del frame
    sources.append(dict(id='B02', title='BONSAI native b2 HIOT · reference identities',
                        filename=technosphere.name, sha256=digest(technosphere),
                        publisher='BONSAI', url='https://bonsai.uno/', retrieved='2026-10-22',
                        role='Only observed row/column identities are snapshotted. The supplied reference-product / process association is not an activity/product equivalence or an economic allocation.'))

    nace = [dict(native=r['exiobase code'], code=r['nace2'], location=f'CSV row {i}')
            for i, r in records('B01', '_b Next version/Classification/exiobase4_nace2.csv',
                                'BONSAI · detailed native process / NACE Rev. 2 correspondence')]
    official = records('B10', 'Classification and other data/NACE_REV2_20210924_143357.csv',
                       'Eurostat NACE Rev. 2 structure supplied with BONSAI')
    sources[-1]['publisher'] = 'Eurostat (supplied by BONSAI)'
    nace_nodes = [dict(code=r['Code'], level=int(r['Level']), name=r['Description']) for _, r in official]
    corr = 'Classification and other data/corrspondence/'
    cpa = [dict(native=r['code'], code=r['source_code'], location=f'CSV row {i}')
           for i, r in records('B04', corr+'revised_cpa_bonsut_cpa_based.csv',
                               'BONSAI · revised detailed product / CPA correspondence')]
    sources[-1]['role'] = ('All 1,664 source codes validate against CPA 2.1, including 45 records absent from CPA 2008. '
                          'The edition is checked against the complete official structures during snapshot build. Binary product footprints do not supply allocation weights.')
    old_cpa = [dict(native=r['Exiobase'], code=r['Code'], location=f'CSV row {i}')
               for i, r in records('B05', corr+'CPA/CPA_2_1_vs_exiobase.csv',
                                   'BONSAI · CPA 2.1 product classification annotations')
               if r['Exiobase'] and r['Level'] == '6']
    aggregates = {}
    for kind, sid, file, column in [('activity', 'B07', '_NACE_rev2_vs_BONSUT_v2.csv', 'bonsut act code'),
                                    ('commodity', 'B08', '_CPA_2008_vs_BONSUT_v2.csv', 'bonsut prod code')]:
        aggregates[kind] = [dict(native=r[column], code=next(iter(r.values())), location=f'CSV row {i}')
                            for i, r in records(sid, corr+'exio4_other/'+file,
                                                'BONSAI · aggregated '+('NACE Rev. 2 activity' if kind=='activity' else 'CPA 2008 product')+' correspondence')]

    path = source('B09', corr+'exio4_other/exiov4_prod_vs_markets_20261022.xlsx',
                  'BONSAI · explicit product / market correspondence (22 October 2026)')
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook['Sheet1']
    markets = [dict(product=str(p), market=str(m), location=f'Sheet1!A{i}:B{i}')
               for i, (p, m) in enumerate(sheet.iter_rows(min_row=2, max_col=2, values_only=True), 2)
               if p and m]
    workbook.close()
    return dict(schema_version=1, as_of='2026-10-22', profile_id='bonsai-b2-2016-hiot-20261021',
                sources=sources, references=sorted(references.values(), key=lambda r:r['product']),
                nace=nace, nace_nodes=nace_nodes, cpa=cpa, cpa_legacy=old_cpa,
                markets=markets, aggregates=aggregates)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bonsai', type=Path, required=True)
    parser.add_argument('--technosphere', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1]/'classifications/sectoral/bonsai-native-correspondences.json')
    args = parser.parse_args()
    result = snapshot(args.bonsai, args.technosphere)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'))+'\n')
    print(json.dumps(dict(native_references=len(result['references']), nace_rows=len(result['nace']),
                          cpa_rows=len(result['cpa']), market_rows=len(result['markets']))))
