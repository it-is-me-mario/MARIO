"""Prepare reviewed Eora1 26 indicators locally from the retained MARIO parse.

No numerical data is copied to documentation static assets by this command.
The source is a previous, licensed local parse; its aggregate arrays are retained
without pretending the basic-price value added is market-price GDP or changing
an already characterised AR4 inventory into AR5/AR6.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

DOC = Path(__file__).resolve().parents[2]
SOURCE_URL = 'https://worldmrio.com/eora26/'
LICENSE_URL = 'https://worldmrio.com/licensing.jsp'


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')


def prepare(snapshot, profile):
    snapshot, profile = deepcopy(snapshot), deepcopy(profile)
    r = snapshot['recipe']
    assert r['id'] == profile['id'] == 'eora26-2017-bp'
    assert r['year'] == profile['year'] == 2017
    assert len(snapshot['regions']) == profile['counts']['Region'] == 189
    assert len(r['sectors']) == profile['counts']['Sector'] == 26
    assert set(r['value_added_rows']) == set(profile['sets']['Factor of production']) - {'Import from ROW'}
    assert len(r['ghg_factors']) == 1
    row = next(iter(r['ghg_factors']))
    assert 'PRIMAPv2.4|KYOTOGHG (AR4GWP100)|TOTALexcludingLULUCF' in row
    assert r['ghg_factors'][row] == 1000
    geographic = {x['label']: x for x in profile['geography']['regions']}
    for region in snapshot['regions']:
        native = geographic[region['code']]
        region.update(name=native['name'], kind=native['kind'], iso3=native.get('iso3'))
        for metric in ['value_added', 'ghg']:
            assert len(region[metric]) == 26
            assert all(math.isfinite(value) for value in region[metric])
        assert math.isfinite(region['household_ghg'])
        assert 'gdp' not in region
    r.update(
        label='Eora1 26 · basic prices', release='Eora1 26', dimension='Sector',
        parser_options={'multi_region': True, 'calc_all': False},
        parser_guide='notebooks/parsers/eora/walkthrough_eora.html',
        source_url=SOURCE_URL, license_url=LICENSE_URL,
        world_total_available=True, final_demand_emissions_loaded=True,
        gdp_bridge_verified=False,
        gdp_note='GDP at market prices is unavailable: the basic-price input files do not establish a verified product-tax bridge. Value added is available; it is not relabelled as GDP.',
        value_added_basis='Six native primary-input rows; basic-price value added',
        value_added_note='Sum compensation of employees, other taxes and signed subsidies on production, net operating surplus, net mixed income and consumption of fixed capital. Exclude the MARIO-added Import from ROW row; retain the native sign of subsidies. Current thousand USD converted to USD once.',
        ghg_basis='PRIMAP-HIST v2.4 Kyoto GHG, AR4 GWP100, excluding LULUCF; producer plus direct final-demand accounts',
        gwp_basis='IPCC AR4 (source-characterised)', gwp_horizon=100,
        ghg_note='One native PRIMAP-HIST v2.4 Kyoto GHG total, excluding LULUCF; AR4 GWP100 is retained. Inventory revisions and overlapping subcategories are not added. It is not relabelled as AR5 or AR6.',
        scope_note='Eora1 26, 2017, basic prices: 189 retained native regions, including two historical groupings, and 26 sectors. MARIO removes the inconsistent source ROW account; ROW imports are excluded from value added. All other native regions are summed for World.',
        attribution='Eora MRIO, KGM & Associates; Lenzen et al. (2012, 2013). Local MARIO-derived value added and GHG aggregates; original data retain the applicable Eora1 licence.',
        publication_status='Local only: the Eora1 academic terms exclude website/software use; public publication requires a commercial licence or specific permission.',
        regions=list(geographic.values()),
    )
    snapshot['schema_version'] = 1
    validation = {
        'version': 'Eora1 26', 'year': 2017, 'table': 'IOT', 'price_basis': 'Basic prices',
        'availability': {'gdp': False, 'value_added': True, 'ghg': True},
        'regions': 189, 'sectors': 26, 'individual_regions': profile['geography']['individual_countries'],
        'ghg_method': r['ghg_basis'], 'source_url': SOURCE_URL, 'license_url': LICENSE_URL,
        'publication_status': 'local_only',
        'world_value_added_usd': sum(sum(x['value_added']) for x in snapshot['regions']),
        'world_ghg_tonnes': sum(sum(x['ghg']) + x['household_ghg'] for x in snapshot['regions']),
    }
    return snapshot, validation


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    local = DOC.parent / 'Output/database-browser-local'
    cli.add_argument('--snapshot', type=Path, default=local / 'eora26-2017-bp.json')
    cli.add_argument('--profile', type=Path, default=DOC / 'source/_static/data/database_profiles/eora26-2017-bp.json')
    cli.add_argument('--output', type=Path, default=local)
    args = cli.parse_args()
    raw = args.snapshot.read_bytes()
    snapshot, report = prepare(json.loads(raw), json.loads(args.profile.read_text()))
    report['input_snapshot_sha256'] = hashlib.sha256(raw).hexdigest()
    write(args.output / 'eora26-2017-bp.json', snapshot)
    write(args.output / 'eora26-2017-bp.validation.json', report)
    print('Eora1 26 · 2017: local value added and native AR4 GHG; GDP unavailable until a verified market-price bridge. No public numerical assets written.')


if __name__ == '__main__':
    main()
