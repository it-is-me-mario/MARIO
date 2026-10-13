"""Build GTAP source-only scope inventories; never publish licensed indicators.

Input is committed public classification metadata plus a locally verified Power
Region/Sector index snapshot. The standard inventory requires no MARIO parser.
"""

import argparse
import hashlib
import json
from pathlib import Path


def build(metadata, data):
    source = json.loads(metadata.read_text())
    regions = source['regions']
    result = []
    digest = lambda x: hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    for variant, sectors, years, parser in [
        ('Standard', source['standard_sectors'], source['standard_years'], False),
        ('Power', source['power_sectors'], source['power_years'], True),
    ]:
        pid = 'gtap-12-' + variant.lower() + '-scope'
        labels = [s['name'] for s in sectors]
        counts = {'Region': len(regions), 'Sector': len(sectors)}
        profile = {
            'schema_version': 1, 'id': pid, 'source': 'GTAP', 'guide': 'gtap' if parser else 'gtap-standard',
            'version': '12', 'variant': variant, 'label': 'GTAP 12 · ' + variant, 'release': '12 · ' + variant, 'year': max(years), 'years': years, 'website_years': [],
            'table': 'IOT' if parser else 'Model sectors', 'status': 'source_verified', 'parser_supported': parser,
            'environmental': True, 'numeric_publication': False, 'counts': counts,
            'sets': {'Region': [r['label'] for r in regions], 'Sector': labels},
            'native_codes': {'Sector': {s['name']: s['code'] for s in sectors}},
            'region_counts': [{'region': r['label'], 'set': 'Sector', 'count': len(sectors)} for r in regions],
            'region_items': [], 'set_flags': {s: {'status': 'not_loaded'} for s in ['Satellite account', 'Factor of production', 'Consumption category']},
            'geography': {'status': 'source_verified_individual_regions', 'scope': 'global', 'regions': regions,
                          'individual_countries': sum(r['kind'] == 'country' for r in regions),
                          'aggregate_count': sum(r['kind'] == 'aggregate' for r in regions), 'unresolved_count': 0,
                          'country_memberships': [], 'method': 'Public GTAP 12 region codes and definitions. Power 2023 native index matches the complete published regional vocabulary.'},
            'coverage_signatures': {'geography': digest(sorted(r['label'] for r in regions)), 'economic': digest(sectors)},
            'classifications': {'status': 'documented', 'native_classification': 'GTAP GSC3' + (' with Power electricity/heat split' if parser else ''), 'mappings': []},
            'provenance': {'method': 'source_metadata', 'source_filename': source['power_index']['source_filename'] if parser else 'GTAP 12 public classification',
                           'source_sha256': source['power_index']['source_sha256'] if parser else source['source_checksums']['sectors.html'],
                           'source_url': 'https://www.gtap.agecon.purdue.edu/databases/Utilities/v12.aspx' if parser else 'https://www.gtap.agecon.purdue.edu/databases/v12/index.aspx',
                           'options': {'unit': 'Monetary', 'system': 'Industry'},
                           'reading_scope': 'Metadata only. No GDP, value added, GHG or economic matrices published.'},
            'source_url': 'https://www.gtap.agecon.purdue.edu/databases/Utilities/v12.aspx' if parser else 'https://www.gtap.agecon.purdue.edu/databases/v12/index.aspx',
            'license_url': 'https://www.gtap.agecon.purdue.edu/resources/faqs/faqs_display.asp?F_ID=198',
            'attribution': 'GTAP / Center for Global Trade Analysis, Purdue University. Public classification metadata.',
            'scope_note': 'GTAP is supplied under a proprietary licence. Only public scope and classification metadata are shown; numerical indicators are not published. ' + ('Power MRIO is supported by MARIO; this inventory verifies the 2023 native region/sector index, without rerunning the full parse. Satellite, factor and final-demand inventories were not loaded.' if parser else 'This standard GTAP inventory is source-only; MARIO does not currently support this distribution. Years refer to the publisher’s documented reference years.'),
            'workbook': '_static/data/external_profiles/' + pid + '-sets.xlsx',
            'detail': '_static/data/external_profiles/' + pid + '.json',
        }
        result.append(profile)
    output = data / 'external_profiles'
    output.mkdir(parents=True, exist_ok=True)
    for profile in result:
        (output / (profile['id'] + '.json')).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n')
    registry_path = data / 'external_profiles.json'
    registry = json.loads(registry_path.read_text())
    registry['profiles'] = [p for p in registry['profiles'] if p['source'] != 'GTAP'] + [
        {k: v for k, v in p.items() if k not in ['sets', 'native_codes', 'region_items']} for p in result]
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n')
    # Preserve all existing country classifications and readings when appending metadata-only profiles.
    scope_path = data / 'economy/country-scope.json'
    scope = json.loads(scope_path.read_text())
    scope['profiles'] = [p for p in scope['profiles'] if p['family'] != 'GTAP']
    for p in result:
        scope['profiles'].append({
            'id': p['id'], 'family': 'GTAP', 'version': '12', 'variant': p['variant'], 'release': p['release'], 'units': 'Monetary', 'format': p['table'],
            'system': 'Industry', 'price_basis': '', 'years': p['years'], 'counts': p['counts'], 'environmental': True,
            'region_counts': p['region_counts'], 'regions': regions, 'memberships': {}, 'sets': {'Sector': p['sets']['Sector']},
            'set_flags': p['set_flags'], 'reading_ids': [], 'reading_years': {}, 'indicator_flags': {}, 'availability': {},
            'status': p['status'], 'parser_supported': p['parser_supported'], 'native_codes': p['native_codes'],
            'source_url': p['source_url'], 'scope_note': p['scope_note'], 'license_url': p['license_url'], 'attribution': p['attribution'],
            'workbook': p['workbook'], 'guide': 'notebooks/parsers/gtap/walkthrough_gtap.html' if p['parser_supported'] else None,
            'mapping': None, 'mapping_ids': [], 'signature': p['coverage_signatures'], 'numeric_publication': False,
        })
    scope_path.write_text(json.dumps(scope, ensure_ascii=False, separators=(',', ':')) + '\n')
    return result


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--metadata', type=Path, default=Path(__file__).resolve().parents[1] / 'classifications/sectoral/gtap-scope-metadata.json')
    cli.add_argument('--data', type=Path, default=Path(__file__).resolve().parents[1] / 'source/_static/data')
    args = cli.parse_args()
    print(json.dumps([{'id': p['id'], 'counts': p['counts']} for p in build(args.metadata, args.data)]))
