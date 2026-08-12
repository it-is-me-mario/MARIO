"""Source-only scope stays separate from parsed REX3 numerical inventories."""
import importlib.util
import json
from pathlib import Path

from tests.parsers.test_exiobase_rex_parser import _write_rex3_bundle

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('rex3_scope',ROOT/'doc/scripts/build_rex3_scope.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_source_scope_uses_labels_without_economic_or_ghg_matrices(tmp_path):
    _write_rex3_bundle(tmp_path,year=2022)
    for directory in [tmp_path/'REX3_2022',tmp_path/'GHG_data_REX3']:
        import shutil
        shutil.rmtree(directory)
    p=module.source_profile(tmp_path/'REX3_Labels')
    assert p['counts']['Region']==2 and p['counts']['Sector']==2
    assert p['counts']['Satellite account']==8
    assert p['source']=='EXIOBASE' and p['variant']=='REX3'
    assert p['status']=='source_verified' and p['numeric_publication'] is False
    assert p['classifications']['mappings']==[]
    assert len(p['provenance']['source_checksums'])==4


def test_source_scope_does_not_fabricate_country_codes_for_ambiguous_or_historical_regions():
    p=json.loads((ROOT/'doc/source/_static/data/external_profiles/exiobase-rex3-source-scope.json').read_text())
    assert p['counts']['Region']==len(p['sets']['Region'])==189
    assert len(p['sets']['Sector'])==163
    historical=[r for r in p['geography']['regions'] if r.get('historical')]
    assert {r['label'] for r in historical}=={'Former USSR','Netherlands Antilles'}
    assert all(r['kind']=='aggregate' and not r.get('members') for r in historical)
    assert {r['label'] for r in p['geography']['regions'] if r['kind']=='unresolved'}=={'Antigua','Gaza Strip'}
