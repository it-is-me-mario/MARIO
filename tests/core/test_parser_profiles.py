"""Public parsers select optional defaults from the shared profile registry."""

import inspect

import pytest

import mario
from mario.log_exc.exceptions import WrongFormat
from mario.settings.parser_profiles import PARSER_COMPUTE_PROFILES
from tests.parsers.test_bonsai_parser import _bundle


pytestmark = pytest.mark.usefixtures("bonsai_without_umfpack")


@pytest.mark.parametrize("profile", [None, {}, {"compute_method": "solve", "linear_solver": "scipy"}])
def test_bonsai_uses_current_registry_entry(tmp_path, monkeypatch, profile):
    before = mario.download_settings()
    if profile is None:
        monkeypatch.delitem(PARSER_COMPUTE_PROFILES, "bonsai")
    else:
        monkeypatch.setitem(PARSER_COMPUTE_PROFILES, "bonsai", profile)

    database = mario.parse_bonsai(_bundle(tmp_path / "Balanced"))

    expected = {**before, "compute": {**before["compute"], **(profile or {})}}
    assert mario.download_settings() == expected
    assert database.table_type == "SUT"


def test_adding_a_profile_enables_defaults_for_another_public_parser(monkeypatch):
    before = mario.download_settings()
    profile = {"compute_method": "solve", "linear_solver": "scipy", "linear_strategy": "direct"}
    monkeypatch.setitem(PARSER_COMPUTE_PROFILES, "from_excel", profile)

    database = mario.load_test("IOT")

    assert database.table_type == "IOT"
    assert mario.download_settings() == {**before, "compute": {**before["compute"], **profile}}


def test_invalid_profile_is_rejected_before_reading_and_preserves_settings(tmp_path, monkeypatch):
    from mario.parsers import entrypoints

    before = mario.download_settings()
    monkeypatch.setitem(PARSER_COMPUTE_PROFILES, "bonsai", {"compute_method": "invalid"})
    monkeypatch.setattr(entrypoints, "parse_bonsai_hsut", lambda *a, **k: pytest.fail("Read an invalid profile"))

    with pytest.raises(WrongFormat, match="compute_method"):
        mario.parse_bonsai(tmp_path)
    assert mario.download_settings() == before


def test_profiled_parser_retains_signature_and_scenario_import(tmp_path):
    path = _bundle(tmp_path / "Balanced")
    parser = mario.parse_bonsai
    assert inspect.signature(parser) == inspect.signature(parser.__wrapped__)
    assert parser.__name__ == "parse_bonsai"
    assert parser.__doc__ == parser.__wrapped__.__doc__

    database = parser(path)
    database.parse_scenario(parser, path, new_scenario="second")
    assert database.scenarios == ["baseline", "second"]
