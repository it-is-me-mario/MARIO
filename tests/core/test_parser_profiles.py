"""Public parsers select optional defaults from the shared profile registry."""

import inspect

import pytest

import mario
from mario.log_exc.exceptions import WrongFormat
from mario.settings.parser_profiles import (
    PARSER_COMPUTE_PROFILES,
    with_parser_compute_profile,
)
from tests.parsers.test_bonsai_parser import _bundle


pytestmark = pytest.mark.usefixtures("bonsai_without_umfpack")


@pytest.mark.parametrize(
    "profile", [None, {}, {"compute_method": "solve", "linear_solver": "scipy"}]
)
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
    profile = {
        "compute_method": "solve",
        "linear_solver": "scipy",
        "linear_strategy": "direct",
    }
    monkeypatch.setitem(PARSER_COMPUTE_PROFILES, "from_excel", profile)

    database = mario.load_test("IOT")

    assert database.table_type == "IOT"
    assert mario.download_settings() == {
        **before,
        "compute": {**before["compute"], **profile},
    }


def test_invalid_profile_is_rejected_before_reading_and_preserves_settings(
    tmp_path, monkeypatch
):
    from mario.parsers import entrypoints

    before = mario.download_settings()
    monkeypatch.setitem(
        PARSER_COMPUTE_PROFILES, "bonsai", {"compute_method": "invalid"}
    )
    monkeypatch.setattr(
        entrypoints,
        "parse_bonsai_hsut",
        lambda *a, **k: pytest.fail("Read an invalid profile"),
    )

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


@pytest.mark.parametrize("name", ["bonsai", "gloria", "emerging"])
@pytest.mark.parametrize("available", [True, False])
def test_large_database_profiles_choose_an_available_solver_without_persisting(
    name, available, tmp_path, monkeypatch
):
    monkeypatch.setenv("MARIO_CONFIG_DIR", str(tmp_path / "config"))
    before = mario.download_settings()
    mario.upload_settings(before, persist=True)
    saved = mario.get_settings_path().read_bytes()

    def backend():
        if not available:
            raise ImportError("Optional native library unavailable")

    monkeypatch.setattr("mario.compute.linear_solvers.load_umfpack", backend)

    def parse():
        return mario.download_settings()["compute"]

    parse.__name__ = "parse_" + name
    active = with_parser_compute_profile(parse)()
    assert active["compute_method"] == "solve"
    assert active["linear_strategy"] == "direct"
    assert active["linear_solver"] == ("umfpack" if available else "scipy")
    assert active["singular_policy"] == ("partial" if name == "bonsai" else "raise")
    assert "linear_solver_fallback" not in active
    assert mario.get_settings_path().read_bytes() == saved


def test_numerical_failures_are_not_retried_and_restore_the_previous_profile():
    import numpy as np

    before = mario.download_settings()
    calls = []

    def parse_gloria():
        calls.append(mario.download_settings()["compute"])
        raise np.linalg.LinAlgError("Singular production system")

    with pytest.raises(np.linalg.LinAlgError, match="Singular production"):
        with_parser_compute_profile(parse_gloria)()
    assert len(calls) == 1
    assert calls[0]["singular_policy"] == "raise"
    assert mario.download_settings() == before
