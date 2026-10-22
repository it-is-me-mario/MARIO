"""The central metadata view reuses live registries and never changes settings."""
from copy import deepcopy

import pytest

import mario
from mario.database_profiles.compute import PARSER_COMPUTE_PROFILES
from mario.database_profiles.ghg import GHG_PROFILES
from mario.database_profiles.registry import DATABASE_PROFILES
from mario.log_exc.exceptions import WrongInput
from tests.api.test_concordances import sut


def test_legacy_import_paths_are_the_same_live_registries():
    from mario.ops.ghg import GHG_PROFILES as legacy_ghg
    from mario.settings.parser_profiles import PARSER_COMPUTE_PROFILES as legacy_compute
    assert legacy_ghg is GHG_PROFILES
    assert legacy_compute is PARSER_COMPUTE_PROFILES
    assert {p for row in DATABASE_PROFILES.values() for p in row['ghg_profile_ids']} == set(GHG_PROFILES)
    assert set(PARSER_COMPUTE_PROFILES) <= {p for row in DATABASE_PROFILES.values() for p in row['parsers']}


def test_named_inspection_and_discovery_require_no_database_parse(monkeypatch):
    monkeypatch.setattr(mario, 'parse_gloria', lambda *a, **k: pytest.fail('Unexpected parse'))
    before = deepcopy(mario.download_settings())
    profiles = mario.get_database_profile()
    assert set(profiles) == set(DATABASE_PROFILES)
    gloria = mario.get_database_profile('GLORIA')
    assert gloria['id'] == 'gloria' and gloria['database'] is None
    assert gloria['compute']['parser_presets']['gloria']['linear_solver'] == 'umfpack'
    assert 'gloria' in gloria['ghg']['profiles']
    assert 'NACE2.1' in gloria['concordances']['classifications']
    assert mario.download_settings() == before


def test_instance_view_identifies_ghg_profile_and_actual_native_sets(monkeypatch):
    db = sut()
    monkeypatch.setattr('mario.compute.linear_solvers.load_umfpack', lambda: pytest.fail('Metadata lookup must not load a solver'))
    profile = db.database_profile
    assert profile == mario.get_database_profile(db)
    assert profile['ghg']['selected_profile'] == 'gloria'
    assert profile['concordances']['available'] == db.available_concordances
    assert profile['database']['table'] == 'SUT'
    assert profile['database']['source'] == db.meta.source


def test_inspection_copies_cannot_mutate_profiles_but_registry_updates_are_visible(monkeypatch):
    original = deepcopy(GHG_PROFILES['gloria'])
    profile = mario.get_database_profile('gloria')
    profile['ghg']['profiles']['gloria']['gwp'].clear()
    profile['compute']['parser_presets']['gloria']['compute_method'] = 'inverse'
    assert GHG_PROFILES['gloria'] == original
    assert PARSER_COMPUTE_PROFILES['gloria']['compute_method'] == 'solve'
    monkeypatch.setitem(PARSER_COMPUTE_PROFILES, 'gloria', {'compute_method': 'inverse'})
    assert mario.get_database_profile('gloria')['compute']['parser_presets']['gloria'] == {'compute_method': 'inverse'}
    monkeypatch.setitem(GHG_PROFILES, 'gloria', {**original, 'unit': 'custom unit'})
    assert mario.get_database_profile('gloria')['ghg']['profiles']['gloria']['unit'] == 'custom unit'


def test_domains_can_be_unavailable_independently():
    assert mario.get_database_profile('eora')['ghg']['profiles']
    assert not mario.get_database_profile('eora')['concordances']['supported']
    assert not mario.get_database_profile('figaro')['ghg']['profiles']
    assert mario.get_database_profile('figaro')['concordances']['supported']
    old = sut('GLORIA (release 057)').database_profile
    assert old['concordances']['available'] == {}
    assert 'release 060' in old['concordances']['unavailable_reason']
    with pytest.raises(WrongInput, match='source metadata'):
        mario.get_database_profile('not a database')
