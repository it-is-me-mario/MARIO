"""Regression coverage for session aliases over stable canonical matrix IDs."""

from copy import deepcopy
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys

import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongFormat
from mario.model.conventions import _ENUM
from mario.model.matrix_store import CanonicalMatrixDict, ScenarioMatrices
from mario.settings.settings import Nomenclature


ALIASES = {"E": "R", "EY": "Ry", "F": "Re", "e": "rho", "z": "A", "w": "L"}


@pytest.fixture(autouse=True)
def isolated_settings():
    original = mario.download_settings()
    mario.reset_settings()
    yield
    mario.upload_settings(original)


def rename_matrices():
    settings = mario.download_settings()
    settings["nomenclature"].update(ALIASES)
    mario.upload_settings(settings)


@pytest.mark.parametrize("table", ["IOT", "SUT"])
@pytest.mark.parametrize("rename_before_load", [False, True])
def test_rename_and_reset_preserve_existing_data_and_canonical_keys(table, rename_before_load):
    reference = mario.load_test(table)
    expected = {name: reference.query(name) for name in ALIASES}
    if rename_before_load:
        rename_matrices()
    database = mario.load_test(table)
    stored = database.matrices["baseline"]
    identities = {name: id(value) for name, value in stored.items()}
    if not rename_before_load:
        rename_matrices()

    assert _ENUM.E == "E"
    assert Nomenclature().E == "R"
    assert database.matrices["baseline"] is stored
    assert identities == {name: id(stored[name]) for name in identities}
    for canonical, alias in ALIASES.items():
        pd.testing.assert_frame_equal(database.query(alias), expected[canonical])
        pd.testing.assert_frame_equal(reference.query(alias), expected[canonical])
        assert alias in database.available_matrices()
        assert alias not in set(database.matrices["baseline"])

    renamed_again = mario.download_settings()
    renamed_again["nomenclature"]["E"] = "Emissions"
    mario.upload_settings(renamed_again)
    pd.testing.assert_frame_equal(database.Emissions, expected["E"])
    mario.reset_settings()
    for canonical in ALIASES:
        pd.testing.assert_frame_equal(database.query(canonical), expected[canonical])
    assert database.matrices["baseline"] is stored


@pytest.mark.parametrize("table", ["IOT", "SUT"])
@pytest.mark.parametrize("reset_method", ["reset_to_flows", "reset_to_coefficients"])
def test_reset_then_aggregate_reconstructs_matrices_after_rename(table, reset_method):
    database = mario.load_test(table)
    expected = {name: database.query(name) for name in ("E", "EY", "F", "e", "z")}
    rename_matrices()
    getattr(database, reset_method)("baseline")
    for name, frame in expected.items():
        pd.testing.assert_frame_equal(database.query(ALIASES[name]), frame)
    levels = ["Sector"] if table == "IOT" else ["Activity", "Commodity"]
    mapping = {
        level: pd.DataFrame({"Aggregation": "All"}, index=database.get_index(level))
        for level in levels
    }
    aggregated = database.aggregate(mapping, levels=levels, inplace=False)
    assert aggregated.R.to_numpy().sum() == pytest.approx(expected["E"].to_numpy().sum())
    assert aggregated.Ry.to_numpy().sum() == pytest.approx(expected["EY"].to_numpy().sum())
    mario.reset_settings()
    assert aggregated.E.to_numpy().sum() == pytest.approx(expected["E"].to_numpy().sum())


@pytest.mark.parametrize("inplace", [False, True])
def test_sut_to_iot_is_independent_of_active_aliases(inplace):
    source = mario.load_test("SUT")
    reference = source.to_iot(method="D", inplace=False)
    rename_matrices()
    result = source.to_iot(method="D", inplace=inplace)
    result = source if inplace else result
    for canonical, alias in ALIASES.items():
        pd.testing.assert_frame_equal(result.query(alias), reference.query(canonical))
    mario.reset_settings()
    pd.testing.assert_frame_equal(result.E, reference.E)


def test_copy_backup_scenario_and_serialized_storage_survive_settings_reset():
    database = mario.load_test("IOT")
    expected = database.E.copy()
    rename_matrices()
    database.clone_scenario("baseline", "policy")
    database.backup()
    cloned = database.copy()
    serialized_storage = pickle.dumps(database.matrices)
    mario.reset_settings()
    restored = pickle.loads(serialized_storage)
    for matrices in (cloned.matrices, database._backup.matrices, restored):
        pd.testing.assert_frame_equal(matrices["baseline"]["E"], expected)
        pd.testing.assert_frame_equal(matrices["policy"]["E"], expected)
        assert "R" not in set(matrices["baseline"])


def test_direct_mapping_access_normalizes_aliases_without_renaming_data():
    rename_matrices()
    matrices = ScenarioMatrices({"baseline": {"R": 1}})
    values = matrices["baseline"]
    values.update({"Ry": 2})
    values |= {"Re": 3}
    assert values.setdefault("R", 4) == 1
    assert values.get("Ry") == 2
    assert set(values) == {"E", "EY", "F"}
    assert values.pop("Re") == 3
    del values["Ry"]
    matrices.update({"policy": {"R": 5}})
    assert isinstance(matrices["policy"], CanonicalMatrixDict)
    assert matrices["policy"]["E"] == 5
    mario.reset_settings()
    assert values["E"] == 1
    assert dict(deepcopy(values)) == {"E": 1}


def test_settings_are_process_local_and_yaml_reuse_is_explicit(tmp_path):
    package_settings = Path(mario.__file__).parent / "settings" / "settings.yaml"
    original_bytes = package_settings.read_bytes()
    default = mario.download_settings()
    rename_matrices()
    mario.set_compute_method("solve")
    configured = mario.download_settings(tmp_path)
    assert package_settings.read_bytes() == original_bytes

    script = """
import json, mario, sys
print(json.dumps(mario.download_settings()))
mario.upload_settings(sys.argv[1])
print(json.dumps(mario.download_settings()))
"""
    child = subprocess.run(
        [sys.executable, "-P", "-c", script, str(tmp_path / "settings.yaml")],
        cwd=Path(mario.__file__).parents[1], text=True, capture_output=True, check=True,
        env={**os.environ, "PYTHONPATH": str(Path(mario.__file__).parents[1])},
    )
    fresh, imported = map(json.loads, child.stdout.splitlines())
    assert fresh == default
    assert imported == configured
    assert mario.download_settings() == configured
    mario.reset_settings()
    assert mario.download_settings() == default
    assert package_settings.read_bytes() == original_bytes
    mario.upload_settings(tmp_path / "settings.yaml")
    assert mario.download_settings() == configured


def test_settings_do_not_read_or_write_the_package_configuration(monkeypatch):
    # This also covers read-only installations and package files left modified
    # by older MARIO versions. Only an explicit upload reads a YAML file.
    def forbidden(*args, **kwargs):
        raise AssertionError("Settings must not access the filesystem")

    monkeypatch.setattr("builtins.open", forbidden)
    rename_matrices()
    assert Nomenclature().E == "R"
    mario.set_compute_method("solve")
    mario.reset_settings()
    assert Nomenclature().E == "E"


@pytest.mark.parametrize("payload", [
    {"nomenclature": {"E": None}},
    {"nomenclature": {"E": 42}},
    {"nomenclature": {"E": "  "}},
    {"nomenclature": {"E": "same", "EY": "same"}},
    {"nomenclature": {"E": "z"}},
    {"nomenclature": {"Typo": "R"}},
    {"nomenclature": []},
    {"unknown": {}},
    {"index_aliases": {"r": None}},
    {"index": {"r": [123]}},
    {"compute": {"compute_method": "typo"}},
    {"compute": {"linear_solver": "typo"}},
    {"compute": {"linear_strategy": "typo"}},
    {"compute": {"compute_method": None}},
    {"compute": {"auto_w_memory_fraction": 0}},
    {"compute": {"auto_w_memory_fraction": 1.1}},
    {"compute": {"auto_w_memory_fraction": True}},
    {"compute": {"auto_w_overhead_factor": -1}},
    {"compute": {"auto_w_overhead_factor": float("nan")}},
    {"compute": {"auto_w_overhead_factor": float("inf")}},
])
def test_invalid_settings_leave_active_configuration_unchanged(payload):
    rename_matrices()
    previous = mario.download_settings()
    with pytest.raises(WrongFormat):
        mario.upload_settings(payload)
    assert mario.download_settings() == previous


def test_alias_whitespace_is_normalized_and_input_is_not_mutated():
    payload = {"nomenclature": {"E": " R "}, "compute": {"compute_method": " SOLVE "}}
    original = deepcopy(payload)
    mario.upload_settings(payload)
    assert Nomenclature().E == "R"
    assert mario.download_settings()["compute"]["compute_method"] == "solve"
    assert payload == original


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_all_configurable_names_survive_excel_roundtrip_and_reset(table, tmp_path):
    reference = mario.load_test(table)
    settings = mario.download_settings()
    settings["nomenclature"] = {key: "alias_" + key for key in settings["nomenclature"]}
    mario.upload_settings(settings)
    database = mario.load_test(table)
    database.reset_to_coefficients("baseline")
    database.reset_to_flows("baseline")
    for name in ("E", "EY", "V", "VY", "Z", "Y", "X", "e", "v", "z", "F", "M"):
        pd.testing.assert_frame_equal(database.query("alias_" + name), reference.query(name))

    workbook = tmp_path / "database.xlsx"
    database.to_excel(path=str(workbook), flows=True, coefficients=True)
    mario.reset_settings()
    restored = mario.parse_from_excel(path=str(workbook), table=table, mode="flows")
    for name in ("Z", "Y", "E", "EY", "V", "VY", "F"):
        expected = reference.query(name)
        actual = restored.query(name).reindex(index=expected.index, columns=expected.columns)
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, check_names=False)
