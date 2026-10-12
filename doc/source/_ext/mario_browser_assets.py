"""Build deduplicated whole-economy browser data from published snapshots.

Only already-published regional aggregates are used. Native sector vectors stay
in the individual reading files and are fetched when a sector is selected.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


class _Pool:
    def __init__(self):
        self.values = []
        self.indices = {}

    def add(self, value):
        key = _encoded(value)
        if key not in self.indices:
            self.indices[key] = len(self.values)
            self.values.append(value)
        return self.indices[key]


def _total(values):
    if not isinstance(values, list) or not values:
        return None
    # Match the browser's left-to-right JS reduce, including floating-point order.
    result = 0.0
    for value in values:
        result += value
    return result


def build_browser_index(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'manifest.json').read_text())
    sections = json.loads((folder / 'sector-sections.json').read_text())
    recipe_pools, geography_pool, mapping_pool = {}, _Pool(), _Pool()
    readings = []
    metrics = {'gdp', 'value_added', 'ghg', 'household_ghg', 'net_product_taxes'}
    for entry in manifest['datasets']:
        snapshot = json.loads((folder / (entry['id'] + '.json')).read_text())
        recipe = {}
        for field, value in snapshot['recipe'].items():
            recipe[field] = recipe_pools.setdefault(field, _Pool()).add(value)
        geography = [{key: value for key, value in r.items() if key not in metrics}
                     for r in snapshot['regions']]
        totals = [[r.get('gdp'), _total(r.get('value_added')), _total(r.get('ghg')),
                   r.get('household_ghg')] for r in snapshot['regions']]
        reading = {'recipe': recipe, 'geography': geography_pool.add(geography),
                   'availability': entry['availability'], 'totals': totals}
        validation = snapshot.get('provenance', {}).get('gdp_bridge', {}).get('validation')
        if validation:
            reading['gdp_validation'] = validation
        readings.append(reading)
    mappings = {key: mapping_pool.add(value) for key, value in sections['mappings'].items()}
    return {'schema_version': 1,
            'recipe_values': {field: pool.values for field, pool in recipe_pools.items()},
            'geographies': geography_pool.values, 'readings': readings,
            'mapping_values': mapping_pool.values, 'mappings': mappings}


def remove_private_preview(srcdir, outdir):
    """Clean numerical assets left by the superseded private-preview overlay."""
    marker = Path(outdir) / '.mario-private-browser.json'
    if not marker.is_file():
        return
    source = Path(srcdir) / '_static/data/economy'
    public = {d['id'] + '.json' for d in json.loads((source / 'manifest.json').read_text())['datasets']}
    for name in json.loads(marker.read_text())['assets']:
        path = Path(name)
        if path.parent != Path('_static/data/economy') or path.name in public:
            continue
        (Path(outdir) / path).unlink(missing_ok=True)
    shutil.copyfile(source / 'country-scope.json', Path(outdir) / '_static/data/economy/country-scope.json')
    marker.unlink()


def write_browser_assets(srcdir, outdir):
    remove_private_preview(srcdir, outdir)
    source = Path(srcdir) / '_static/data/economy'
    target = Path(outdir) / '_static/data/economy/browser-index.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(_encoded(build_browser_index(source)) + '\n', encoding='utf-8')
    temporary.replace(target)
