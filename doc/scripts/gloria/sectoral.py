"""Snapshot GLORIA's published section anchors before cloud-file eviction.

Keep original binary concordances and native labels. A section anchor does not
establish native membership of its descendant classes; no leaf links or weights
are inferred here. The snapshot is shared by all identical v060 annual sets.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import pandas as pd


def snapshot(readme, isic_structure):
    readme, isic_structure = Path(readme), Path(isic_structure)
    workbook = pd.ExcelFile(readme)
    sectors = workbook.parse('Sectors')['Sector_names'].astype(str).tolist()
    concordance = workbook.parse('GLORIA to ISIC concordance', header=None)
    if concordance.iloc[2:, 0].tolist() != sectors:
        raise ValueError('GLORIA concordance/native labels mismatch')
    letters = concordance.iloc[0, 1:].tolist()
    names = concordance.iloc[1, 1:].tolist()
    if letters != list('ABCDEFGHIJKLMNOPQRST'):
        raise ValueError('Unexpected published GLORIA section vocabulary')
    native = []
    for position, name in enumerate(sectors, 1):
        row = position + 2
        values = concordance.iloc[row - 1, 1:].tolist()
        if any(v not in [0, 1] for v in values) or sum(values) not in [1, 2]:
            raise ValueError('Non-binary or missing GLORIA section anchor')
        anchors = [{'code': letter, 'name': title,
                    'location': f"'GLORIA to ISIC concordance'!{chr(66+i)}{row}"}
                   for i, (letter, title, value) in enumerate(zip(letters, names, values)) if value]
        native.append({'code': str(position), 'name': name, 'anchors': anchors})
    if [n['name'] for n in native if len(n['anchors']) > 1] != ['Other services']:
        raise ValueError('Review changed GLORIA cross-section aggregates')
    old = workbook.parse('GLORIA 97-to-120 concordance', header=None)
    if old.shape != (98, 122):
        raise ValueError('Changed GLORIA historical concordance dimensions')
    historical = [{'code': str(int(row.iloc[0])), 'name': str(row.iloc[1]),
                   'native_positions': [int(old.iloc[0, i]) for i in range(2, 122) if row.iloc[i] == 1],
                   'location': f"'GLORIA 97-to-120 concordance'!A{position}:DR{position}"}
                  for position, (_, row) in enumerate(old.iloc[1:].iterrows(), 2)]
    raw = isic_structure.read_bytes()
    nodes = []; ancestors = {}
    for position, row in enumerate(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))), 2):
        code = row['Code']; level = 1 if code.isalpha() else len(code)
        parent = None if level == 1 else ancestors[level-1]
        nodes.append({'code': code, 'name': row['Description'], 'level': level,
                      'parent': parent, 'section': code if level == 1 else ancestors[1],
                      'location': f'CSV row {position}'})
        ancestors[level] = code
    if len([n for n in nodes if n['level'] == 4]) != 419:
        raise ValueError('Unexpected ISIC Rev. 4 class count')
    return {'schema_version': 1, 'family': 'GLORIA', 'release': '060', 'dimension': 'Activity',
            'native': native, 'historical_concordance': historical, 'isic_nodes': nodes,
            'sources': [
                {'id': 'S18', 'title': 'GLORIA v060 · published ISIC section concordance',
                 'publisher': 'University of Sydney / UNEP International Resource Panel',
                 'filename': readme.name, 'url': 'https://ielab.info/resources/gloria/supportingdocs',
                 'sha256': hashlib.sha256(readme.read_bytes()).hexdigest(), 'retrieved': '2026-10-10',
                 'role': 'ReadMe, GLORIA to ISIC concordance and GLORIA 97-to-120 concordance. Section anchors only; no detailed class equivalence.'},
                {'id': 'S19', 'title': 'UN Statistics Division · ISIC Rev. 4 structure',
                 'publisher': 'UN Statistics Division', 'filename': isic_structure.name,
                 'url': 'https://unstats.un.org/unsd/classifications/Econ/Download/In%20Text/ISIC_Rev_4_english_structure.txt',
                 'sha256': hashlib.sha256(raw).hexdigest(), 'retrieved': '2026-10-10',
                 'role': 'Official hierarchy used to locate the broad section of intermediate ISIC classes, never to assert native leaf membership.'}],
            'note': 'Published GLORIA section anchors are preserved separately from confirmed NACE leaf links. Projected NACE sections are broad search context only; all fine-resolution cells stay unverified.'}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    for key in ['readme', 'isic-structure', 'output']:
        cli.add_argument('--'+key, type=Path, required=True)
    args = cli.parse_args(); result = snapshot(args.readme, args.isic_structure)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'))+'\n')
    print(json.dumps({'native': len(result['native']), 'historical': len(result['historical_concordance']), 'source_sha256': result['sources'][0]['sha256']}))
