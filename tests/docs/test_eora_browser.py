"""Keep Eora1's identity, local publication boundary and native GHG characterisation."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('eora_prepare', ROOT / 'doc/scripts/eora/prepare.py')
eora = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eora)


def example():
    profile = json.loads((ROOT / 'doc/source/_static/data/database_profiles/eora26-2017-bp.json').read_text())
    row = next(x for x in profile['sets']['Satellite account'] if 'PRIMAPv2.4|KYOTOGHG (AR4GWP100)|TOTALexcludingLULUCF' in x)
    recipe = {'id': profile['id'], 'source': 'EORA', 'year': 2017, 'release': 'Eora26',
              'sectors': profile['sets']['Sector'], 'value_added_rows': [x for x in profile['sets']['Factor of production'] if x != 'Import from ROW'],
              'ghg_factors': {row: 1000}}
    regions = [{'code': r['label'], 'name': r['name'], 'kind': 'country', 'iso3': r.get('iso3'),
                'value_added': [10.0] * 26, 'ghg': [2.0] * 26, 'household_ghg': 3.0}
               for r in profile['geography']['regions']]
    return {'recipe': recipe, 'regions': regions}, profile


def test_local_preparation_preserves_aggregates_and_reports_unverified_gdp():
    snapshot, profile = example()
    result, validation = eora.prepare(snapshot, profile)
    assert result['recipe']['release'] == 'Eora1 26'
    assert result['recipe']['license_url'] == 'https://worldmrio.com/licensing.jsp'
    assert result['recipe']['parser_options'] == {'multi_region': True, 'calc_all': False}
    assert result['recipe']['gwp_basis'] == 'IPCC AR4 (source-characterised)'
    assert validation['availability'] == {'gdp': False, 'value_added': True, 'ghg': True}
    assert validation['publication_status'] == 'local_only'
    assert validation['world_value_added_usd'] == 189 * 260
    assert validation['world_ghg_tonnes'] == 189 * 55
    for before, after in zip(snapshot['regions'], result['regions']):
        assert before['value_added'] == after['value_added']
        assert before['ghg'] == after['ghg']
        assert 'gdp' not in after
    historical = [r for r in result['regions'] if r['kind'] == 'aggregate']
    assert sorted(r['code'] for r in historical) == ['ANT', 'USR']
    assert all(r['iso3'] is None for r in historical)


def test_wrong_year_import_row_or_already_characterised_ghg_weight_is_rejected():
    for field in ['year', 'imports', 'ghg']:
        snapshot, profile = example()
        if field == 'year':
            snapshot['recipe']['year'] = 2018
        elif field == 'imports':
            snapshot['recipe']['value_added_rows'].append('Import from ROW')
        else:
            snapshot['recipe']['ghg_factors'][next(iter(snapshot['recipe']['ghg_factors']))] = 29.8
        with pytest.raises(AssertionError):
            eora.prepare(snapshot, profile)


def test_eora_scope_metadata_retains_parser_without_browser_indicators():
    data = ROOT / 'doc/source/_static/data'
    catalogue = json.loads((data / 'database_profiles.json').read_text())
    p = next(p for p in catalogue['profiles'] if p['guide'] == 'eora')
    assert p['release'] == 'Eora1 26'
    assert p['years'] == [*range(1990, 2004), *range(2005, 2018)]
    assert p['local_index_overrides'] == {'2016': 2017}
    assert p['year_evidence']['parsed'] == [2017]
    assert p['year_evidence']['source_structure_checked'] == [year for year in p['years'] if year != 2017]
    assert '2016' in p['scope_note'] and 'indeces=' in p['scope_note']
    scope = json.loads((data / 'economy/country-scope.json').read_text())
    scope_row = next(row for row in scope['profiles'] if row['id'] == p['id'])
    assert scope_row['years'] == p['years'] and scope_row['reading_ids'] == []
    assert p['numeric_publication'] is False
    assert p['parser_supported'] is True
    assert p['license_url'] == 'https://worldmrio.com/licensing.jsp'
    licences=json.loads((data / 'database_licences.json').read_text())['guides']
    assert licences['eora'][0]['url'] == p['license_url']
    assert licences['eora2'][0]['url'] != p['license_url']
    manifest = json.loads((data / 'economy/manifest.json').read_text())
    assert all(s['source'] != 'EORA' for s in manifest['datasets'])
    assert not (data / 'economy/eora26-2017-bp.json').exists()


def test_old_private_overlay_is_removed_by_a_normal_build(tmp_path):
    spec = importlib.util.spec_from_file_location('browser_assets', ROOT / 'doc/source/_ext/mario_browser_assets.py')
    assets = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(assets)
    data = tmp_path / 'doc/source/_static/data/economy'
    target = tmp_path / 'html/_static/data/economy'
    data.mkdir(parents=True);target.mkdir(parents=True)
    (data / 'manifest.json').write_text(json.dumps({'datasets': [{'id':'fixture','availability':{'gdp':True,'value_added':True,'ghg':False}}]}))
    (data / 'fixture.json').write_text(json.dumps({'recipe':{'id':'fixture','source':'Example','year':2024},'regions':[{'code':'ITA','name':'Italy','kind':'country','gdp':10,'value_added':[3,4]}]}))
    (data / 'sector-sections.json').write_text('{"mappings":{}}')
    public_scope={'profiles':[{'id':'eora26-2017-bp','numeric_publication':False,'reading_ids':[],'availability':{}}]}
    (data / 'country-scope.json').write_text(json.dumps(public_scope))
    private=target/'eora26-2017-bp.json';private.write_text('{"ghg":100}')
    (target/'country-scope.json').write_text('{"profiles":[{"reading_ids":["eora26-2017-bp"]}]}')
    marker=tmp_path/'html/.mario-private-browser.json'
    marker.write_text(json.dumps({'assets':['_static/data/economy/eora26-2017-bp.json']}))
    assets.write_browser_assets(tmp_path/'doc/source',tmp_path/'html')
    assert not private.exists() and not marker.exists()
    assert json.loads((target/'country-scope.json').read_text())==public_scope
    assert len(json.loads((target/'browser-index.json').read_text())['readings'])==1
    assert not (data/'eora26-2017-bp.json').exists()
    assert not (ROOT/'doc/scripts/eora/private_preview.py').exists()
