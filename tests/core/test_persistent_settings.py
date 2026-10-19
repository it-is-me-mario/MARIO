"""User profiles are opt-in, atomic, and independent of running kernels."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest
import yaml

import mario
from mario.log_exc.exceptions import WrongFormat


settings_module = importlib.import_module("mario.settings.settings")
CUSTOM = {"nomenclature": {"E": "R", "F": "Re", "z": "A"},
          "compute": {"compute_method": "solve"}}


@pytest.fixture(autouse=True)
def isolated_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("MARIO_CONFIG_DIR", str(tmp_path / "profile"))
    monkeypatch.setattr(settings_module, "_ACTIVE_SETTINGS", None)


def child_settings(script="", *args):
    result = subprocess.run(
        [sys.executable, "-P", "-c",
         "import json, mario, sys\n" + script + "\nprint(json.dumps(mario.download_settings()))",
         *map(str, args)],
        env={**os.environ, "PYTHONPATH": str(Path(mario.__file__).parents[1])},
        text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout.splitlines()[-1])


def test_session_changes_and_exports_do_not_create_a_profile(tmp_path):
    defaults = mario.download_settings()
    mario.upload_settings(CUSTOM)
    mario.download_settings(tmp_path)
    assert not mario.get_settings_path().exists()
    assert child_settings() == defaults


@pytest.mark.parametrize("source_type", ["dict", "yaml"])
def test_persistent_defaults_load_in_fresh_processes_without_changing_package(tmp_path, source_type):
    package_file = Path(mario.__file__).parent / "settings" / "settings.yaml"
    package_bytes = package_file.read_bytes()
    source = CUSTOM
    if source_type == "yaml":
        source = tmp_path / "custom.yaml"
        source.write_text(yaml.safe_dump(CUSTOM))
    mario.upload_settings(source, persist=True)
    expected = mario.download_settings()
    assert child_settings() == expected
    assert yaml.safe_load(mario.get_settings_path().read_text()) == expected
    assert package_file.read_bytes() == package_bytes


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_fresh_database_uses_saved_aliases_with_canonical_storage(table):
    mario.upload_settings(CUSTOM, persist=True)
    result = child_settings(f"""
mario.set_log_verbosity('critical')
db = mario.load_test({table!r})
assert db.query('R').equals(db.query('E'))
assert db.query('Re').equals(db.query('F'))
assert 'R' in db.available_matrices()
assert 'E' in set(db.matrices['baseline'])
assert 'R' not in set(db.matrices['baseline'])
mario.reset_settings()
assert db.query('E').equals(db.E)
""")
    assert result["nomenclature"]["E"] == "E"
    assert child_settings()["nomenclature"]["E"] == "R"


def test_session_override_and_reset_do_not_replace_saved_defaults():
    mario.upload_settings(CUSTOM, persist=True)
    saved = mario.get_settings_path().read_bytes()
    mario.upload_settings({"nomenclature": {"E": "Emissions"}})
    assert mario.download_settings()["nomenclature"]["E"] == "Emissions"
    mario.set_compute_method("inverse")
    mario.reset_settings()
    assert mario.download_settings()["nomenclature"]["E"] == "E"
    assert mario.get_settings_path().read_bytes() == saved
    assert child_settings()["nomenclature"]["E"] == "R"


def test_unicode_profile_can_be_reloaded_explicitly_and_exported(tmp_path):
    mario.upload_settings({"nomenclature": {"E": "Émissions"}}, persist=True)
    expected = mario.download_settings()
    mario.reset_settings()
    mario.upload_settings(mario.get_settings_path())
    assert mario.download_settings() == expected
    mario.download_settings(tmp_path)
    assert yaml.safe_load((tmp_path / "settings.yaml").read_text(encoding="utf-8")) == expected


def test_another_process_saving_or_removing_defaults_does_not_change_active_session():
    defaults = mario.download_settings()
    child_settings(f"mario.upload_settings({CUSTOM!r}, persist=True)")
    assert mario.download_settings() == defaults
    mario.upload_settings(CUSTOM)
    active = mario.download_settings()
    child_settings("mario.reset_settings(persist=True)")
    assert mario.download_settings() == active
    assert child_settings() == defaults


def test_persistent_reset_removes_profile_and_preserves_loaded_data():
    db = mario.load_test("IOT")
    emissions = db.E.copy()
    mario.upload_settings(CUSTOM, persist=True)
    pd.testing.assert_frame_equal(db.R, emissions)
    unrelated = mario.get_settings_path().parent / "keep.txt"
    unrelated.write_text("keep")
    mario.reset_settings(persist=True)
    pd.testing.assert_frame_equal(db.E, emissions)
    assert not mario.get_settings_path().exists()
    assert unrelated.read_text() == "keep"
    assert child_settings() == mario.download_settings()
    mario.reset_settings(persist=True)  # idempotent if no profile exists


@pytest.mark.parametrize("content", ["nomenclature: [", "null", "nomenclature:\n  E: F", b"\xff"])
def test_invalid_saved_profile_warns_once_and_can_be_removed(content):
    target = mario.get_settings_path()
    target.parent.mkdir(parents=True)
    target.write_bytes(content if isinstance(content, bytes) else content.encode())
    with pytest.warns(UserWarning, match="Cannot load MARIO user settings") as captured:
        defaults = mario.download_settings()
        assert mario.download_settings() == defaults
    assert len(captured) == 1
    assert defaults["nomenclature"]["E"] == "E"
    assert target.exists()
    mario.reset_settings(persist=True)
    assert not target.exists()


def test_reset_at_notebook_start_bypasses_even_invalid_saved_settings():
    target = mario.get_settings_path()
    target.parent.mkdir(parents=True)
    target.write_text("not: valid")
    mario.reset_settings()
    assert mario.download_settings()["nomenclature"]["E"] == "E"
    assert target.read_text() == "not: valid"


def test_failed_validation_or_write_leaves_profile_and_active_settings_intact(monkeypatch):
    mario.upload_settings(CUSTOM, persist=True)
    active = mario.download_settings()
    target = mario.get_settings_path()
    saved = target.read_bytes()
    with pytest.raises(WrongFormat):
        mario.upload_settings({"nomenclature": {"E": "F"}}, persist=True)

    def fail_replace(*args):
        raise PermissionError("read-only profile")

    monkeypatch.setattr(settings_module.os, "replace", fail_replace)
    with pytest.raises(PermissionError):
        mario.upload_settings({}, persist=True)
    assert mario.download_settings() == active
    assert target.read_bytes() == saved
    assert list(target.parent.iterdir()) == [target]


def test_failed_profile_removal_does_not_reset_active_settings(monkeypatch):
    mario.upload_settings(CUSTOM, persist=True)
    active = mario.download_settings()
    target = mario.get_settings_path()
    saved = target.read_bytes()

    def fail_unlink(*args, **kwargs):
        raise PermissionError("read-only profile")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(PermissionError):
        mario.reset_settings(persist=True)
    assert mario.download_settings() == active
    assert target.read_bytes() == saved


@pytest.mark.parametrize("value", ["False", None, 1])
def test_persist_requires_an_explicit_boolean(value):
    for method, args in [(mario.upload_settings, ({},)), (mario.reset_settings, ())]:
        with pytest.raises(WrongFormat, match="persist must"):
            method(*args, persist=value)
    assert not mario.get_settings_path().exists()


@pytest.mark.parametrize("platform, relative", [
    ("darwin", "Library/Application Support/MARIO/settings.yaml"),
    ("win32", "AppData/Roaming/MARIO/settings.yaml"),
    ("linux", ".config/mario/settings.yaml"),
])
def test_default_profile_location_is_platform_specific(tmp_path, monkeypatch, platform, relative):
    for variable in ("MARIO_CONFIG_DIR", "APPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(settings_module.sys, "platform", platform)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert mario.get_settings_path() == tmp_path / relative
    assert not mario.get_settings_path().parent.exists()


@pytest.mark.parametrize("platform, variable, suffix", [
    ("win32", "APPDATA", "MARIO"), ("linux", "XDG_CONFIG_HOME", "mario"),
])
def test_platform_config_directory_and_explicit_override(tmp_path, monkeypatch, platform, variable, suffix):
    monkeypatch.delenv("MARIO_CONFIG_DIR")
    monkeypatch.setattr(settings_module.sys, "platform", platform)
    monkeypatch.setenv(variable, str(tmp_path / "platform"))
    assert mario.get_settings_path() == tmp_path / "platform" / suffix / "settings.yaml"
    monkeypatch.setenv("MARIO_CONFIG_DIR", str(tmp_path / "custom"))
    assert mario.get_settings_path() == tmp_path / "custom" / "settings.yaml"
