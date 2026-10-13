"""Refresh the source notices shared by download workbooks and CSV exports.

Run after updating the database or concordance catalogues. This does not parse
databases or assign a blanket licence to material from different publishers.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'source/_static/data'


def build(data=DATA):
    licences = json.loads((data / 'database_licences.json').read_text())['guides']
    profiles = json.loads((data / 'database_profiles.json').read_text())['profiles']
    profiles += json.loads((data / 'external_profiles.json').read_text())['profiles']
    graph = json.loads((data / 'economy/sectoral-scope.json').read_text())
    metadata = {'schema_version': 1, 'profiles': {}, 'sources': {}}
    for p in profiles:
        notices = licences.get(p['guide'], [])
        if p['guide'] == 'exiobase-monetary':
            notices = [notices[0] if p['release'] == '3.8.2' else notices[1]]
        if p['guide'] == 'open-ceda' or p['source'] == 'CEDA':
            notices = [{'label': 'CC BY-SA 4.0', 'url': 'https://creativecommons.org/licenses/by-sa/4.0/',
                        'note': 'Attribute CEDA by Watershed, indicate changes, and retain ShareAlike terms.',
                        'sources': ['https://watershed.com/solutions/ceda']}]
        detail = json.loads((data.parent.parent / p['detail']).read_text())
        source = p.get('source_url') or p.get('provenance', {}).get('source_url')
        if not source:
            source = detail.get('source_url') or detail.get('provenance', {}).get('source_url') or next((u for n in notices for u in n.get('sources', [])), None)
        if not source:
            source = next((n['url'] for n in notices if n.get('url')), '')
        license_url = p.get('license_url') or '; '.join(n.get('url') or '' for n in notices)
        if p['guide'] == 'exiobase-monetary' and p['release'] != '3.8.2':
            license_url = source  # Read the licence attached to this release.
        metadata['profiles'][p['id']] = {
            'label': p['label'], 'guide': p['guide'], 'source_url': source,
            'license_url': license_url,
            'license': '; '.join(n['label'] for n in notices),
            'usage': ' '.join(n['note'] for n in notices),
            'attribution': p.get('attribution') or p['source'],
            'workbook_allowed': p.get('workbook_allowed', p['guide'] != 'eora'),
            'workbook': p['workbook'],
            'years': p.get('years', [p.get('year')]),
        }
    # These notices refer to the source, not to an invented universal licence.
    policies = {
        'eurostat': ('Eurostat data and metadata reuse policy', 'https://ec.europa.eu/eurostat/help/copyright-notice', 'Acknowledge Eurostat; indicate changes; respect third-party exceptions.'),
        'us': ('U.S. government source material', 'https://www.bea.gov/help/faq/147', 'Acknowledge the named U.S. agency; third-party material has separate rights.'),
        'un': ('UN Statistics Division terms', 'https://www.un.org/en/about-us/terms-of-use', 'Official classification facts and correspondence records; acknowledge UNSD. No blanket open licence is assigned to UN publications.'),
        'gtap': ('Public GTAP classification metadata; proprietary numerical database', 'https://www.gtap.agecon.purdue.edu/resources/faqs/faqs_display.asp?F_ID=198', 'Classification lookup only. No licensed MRIO observations, coefficients or multipliers are included.'),
        'exio': ('EXIOBASE source-specific terms', 'https://exiobase.eu/terms-of-use/', 'Public classification facts and reviewed correspondence records. Economic and environmental matrices and coefficients are excluded; numerical source access has separate terms.'),
        'nxbase': ('MARIO / nxbase editorial correspondence review', 'https://github.com/it-is-me-mario/MARIO', 'Attribute the review and its cited upstream sources. Editorial links do not change upstream rights or establish numerical allocation weights.'),
        'adb': ('ADB source terms', 'https://www.adb.org/terms-use', 'Acknowledge ADB. Classification definitions are used as lookup facts, not as a copy of the publication.'),
        'wiod': ('WIOD 2016 CC BY 4.0', 'https://www.rug.nl/ggdc/valuechain/wiod/wiod-2016-release?lang=en', 'Attribute WIOD and its user-guide paper; indicate changes.'),
        'gloria': ('GLORIA v060 CC BY-NC 3.0 Australia', 'https://creativecommons.org/licenses/by-nc/3.0/au/', 'Attribute GLORIA and its providers; non-commercial reuse.'),
    }
    for sid, s in graph['sources'].items():
        pub = s.get('publisher', '').lower()
        key = 'nxbase' if 'nxbase' in pub else 'gtap' if 'gtap' in pub else 'exio' if 'exiobase' in pub else 'adb' if 'development bank' in pub else 'wiod' if 'wiod' in pub else 'gloria' if 'gloria' in s.get('title', '') and 'unep' in pub else 'us' if pub.startswith('us ') else 'eurostat' if any(x in pub for x in ['eurostat', 'insee', 'ine /']) else 'un' if any(x in pub for x in ['un statistics', 'unsd']) else None
        if key:
            label, url, usage = policies[key]
        else:
            label, url, usage = 'Source-specific terms; open licence not verified', s['url'], 'Consult the publisher terms. No blanket licence or exact equivalence is inferred from a published link.'
        source_url = s['url'] if s['url'].startswith('https://') else 'https://www.marioproject.com/en/latest/_static/data/economy/' + s['url']
        metadata['sources'][sid] = {'source_url': source_url, 'license': label, 'license_url': url, 'usage': usage, 'attribution': s.get('publisher', '')}
    return metadata


def workbook_jobs(metadata, data=DATA):
    jobs = []
    source = data.parent.parent
    for p in metadata['profiles'].values():
        if not p['workbook_allowed']:
            continue
        jobs.append({'path': str(source / p['workbook']), 'name': Path(p['workbook']).name,
                     'title': p['label'], 'rows': [
            ['Contents', 'Native set labels and units. No economic observations, emission factors or coefficients.'],
            ['Verified years', ', '.join(map(str, p['years']))],
            ['How to use', 'Read Sets (or the named set tabs) for labels and units; Readings identifies source years. Identical inventories do not imply identical numerical results.'],
            ['Source', p['source_url']], ['Attribution', p['attribution']],
            ['Source terms', p['license']], ['Terms URL', p['license_url']], ['Reuse', p['usage']],
            ['Changes', 'Extracted and arranged with MARIO. Native labels and units are retained. Country names and ISO matches are documentation metadata.'],
            ['Limit', 'This inventory describes the parsed input; it does not grant rights to use the numerical source data.']]})
    for filename, title, content in [
        ('supporting_files/Nomenclature_and_formulas.xlsx', 'MARIO nomenclature and formulas',
         'MARIO names and calculations on the packaged demonstration IOT and SUT tables. No third-party MRIO observations.'),
        ('economy/sector-correspondence.xlsx', 'Native sector aggregates for the indicator browser',
         'Assign native categories once to broad source-classification sections. This is the indicator aggregation mapping, not the fine NACE Rev. 2.1 / CPA 2.2 concordance.')]:
        rows = [['Contents', content], ['How to use', 'Read the notes and column labels on each sheet. Preserve classification codes as text.'],
                ['Source', 'https://github.com/it-is-me-mario/MARIO'], ['Attribution', 'MARIO documentation and any source publishers listed on the individual sheets.'],
                ['Licence URL', 'https://github.com/it-is-me-mario/MARIO/blob/main/LICENSE']]
        if filename.startswith('economy/'):
            rows += [['Reuse', 'Upstream classification records retain their source-specific terms. No blanket licence replaces those conditions.'],
                     ['Limit', 'Section letters from different classification revisions are not interchangeable. Use classification-concordances.xlsx for qualified fine-code lookups. No numerical split weights are inferred.']]
            used = set()
            for p in metadata['profiles'].values():
                if p['guide'] not in ['adb', 'emerging', 'exiobase-monetary', 'exiobase-hybrid', 'figaro', 'gloria', 'oecd', 'wiod'] or p['source_url'] in used:
                    continue
                used.add(p['source_url'])
                rows.append([p['guide'] + ' source', p['source_url'] + ' · ' + p['license'] + ' · ' + p['license_url']])
        else:
            rows += [['Licence', 'GNU GPL version 3, as distributed in the MARIO repository.'],
                     ['Scope', 'Demonstration calculations, not observations of an actual economy. Original formulas and cached results are retained.']]
        jobs.append({'path': str(data / filename), 'name': Path(filename).name, 'title': title, 'rows': rows})
    return jobs


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=Path, help='Write an authoring manifest for the public workbooks')
    args = parser.parse_args()
    metadata = build()
    target = DATA / 'economy/download-metadata.json'
    target.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    if args.jobs:
        args.jobs.write_text(json.dumps(workbook_jobs(metadata), ensure_ascii=False, indent=2) + '\n')
    print(target)
