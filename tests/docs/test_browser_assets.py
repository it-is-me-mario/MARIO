"""The compact browser index preserves published values and is rebuilt per build."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def module():
    spec = importlib.util.spec_from_file_location('browser_assets', ROOT / 'doc/source/_ext/mario_browser_assets.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_index_deduplicates_without_losing_source_terms_or_regions(tmp_path):
    assets = module()
    source = ROOT / 'doc/source/_static/data/economy'
    manifest = json.loads((source / 'manifest.json').read_text())
    expected_maps = json.loads((source / 'sector-sections.json').read_text())['mappings']
    assets.write_browser_assets(ROOT / 'doc/source', tmp_path)
    path = tmp_path / '_static/data/economy/browser-index.json'
    index = json.loads(path.read_text())
    assert len(index['readings']) == len(manifest['datasets'])
    assert path.stat().st_size < 5_000_000
    assert len(index['mapping_values']) < len(index['mappings']) / 10
    assert '/Users/' not in path.read_text()
    assert {key: index['mapping_values'][i] for key, i in index['mappings'].items()} == expected_maps
    for item, entry in zip(index['readings'], manifest['datasets']):
        full = json.loads((source / (entry['id'] + '.json')).read_text())
        recipe = {field: index['recipe_values'][field][i] for field, i in item['recipe'].items()}
        assert recipe == full['recipe']
        assert item['availability'] == entry['availability']
        geography = index['geographies'][item['geography']]
        assert len(geography) == len(full['regions']) == len(item['totals'])
        for original, region, values in zip(full['regions'], geography, item['totals']):
            assert region['kind'] == original['kind']
            assert region['name'] == original['name']
            assert values[0] == original.get('gdp')
            assert values[1] == assets._total(original.get('value_added'))
            assert values[2] == assets._total(original.get('ghg'))
            assert values[3] == original.get('household_ghg')
        validation = full.get('provenance', {}).get('gdp_bridge', {}).get('validation')
        assert item.get('gdp_validation') == validation


def test_summary_is_regenerated_when_published_values_change(tmp_path):
    assets = module()
    (tmp_path / 'manifest.json').write_text(json.dumps({'datasets': [{'id': 'test', 'availability': {'gdp': True}}]}))
    (tmp_path / 'sector-sections.json').write_text('{"mappings": {}}')
    snapshot = {'recipe': {'id': 'test', 'license_url': 'https://example.test/licence'},
                'regions': [{'code': 'ITA', 'name': 'Italy', 'kind': 'country', 'gdp': 10, 'value_added': [3, 4]}]}
    path = tmp_path / 'test.json'
    path.write_text(json.dumps(snapshot))
    before = assets.build_browser_index(tmp_path)
    snapshot['regions'][0]['gdp'] = 12
    path.write_text(json.dumps(snapshot))
    after = assets.build_browser_index(tmp_path)
    assert before['readings'][0]['totals'][0][0] == 10
    assert after['readings'][0]['totals'][0][0] == 12
