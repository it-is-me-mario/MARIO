"""Small Balanced graph exports exercise identities, units and sparse routing."""

from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.bonsai import parse_bonsai_hsut


pytestmark = pytest.mark.usefixtures("bonsai_without_umfpack")


def _bundle(root, *, unmatched=False):
    root.mkdir(parents=True)
    rows = [
        ("a1", "A_FARM", "AT", "process", {"reference_product": "c1"}),
        ("a2", "A_MILL", "DE", "process", {"reference_product": "c3"}),
        ("a3", "F_REAL", "AT", "process", {}),
        ("n1", "consumer", "DE", "process", {"activity_type": "final_demand"}),
        ("n2", "I_CHIN", "AT", "process", {"activity_type": "final_demand"}),
        ("c1", "C_GRAIN", "AT", "object", {"object_type": "product"}),
        ("c2", "C_SERVICE", "DE", "object", {"object_type": "product"}),
        ("c3", "C_GRAIN", "DE", "object", {"object_type": "product"}),
        ("raw-substance", "dust", "AT", "object", {"object_type": "substance"}),
    ]
    classification = pd.DataFrame(
        rows, columns=["id", "name", "location", "type", "property"]
    )
    classification["property"] = classification["property"].map(repr)
    classification["time"] = 2016
    # The parser must not evaluate this separate exporter field.
    classification["isbalance"] = "{'MASS': np.True_}"
    classification.to_csv(root / "classification.csv", index=False)
    supply = [
        ("a1", "c1", 10, "tonnes"),
        ("a1", "c1", 2, "tonnes"),
        ("a2", "c3", 8, "tonnes"),
        ("a3", "c2", 7, "Meuro"),
        ("a2", "raw-substance", 20, "tonnes"),
    ]
    use = [
        ("c1", "a2", 4, "tonnes"),
        ("c2", "a1", 1, "Meuro"),
        ("c3", "a3", 2, "tonnes"),
        ("c1", "n1", 5, "tonnes"),
        ("c2", "n2", -1, "Meuro"),
        ("c3", "n2", 3, "tonnes"),
        ("raw-substance", "a1", 6, "tonnes"),
        ("c1", "a1", 0, "tonnes"),
    ]
    for name, values in (("supply", supply), ("use", use)):
        pd.DataFrame(values, columns=["from_node", "to_node", "value", "unit"]).to_csv(
            root / f"hybrid_{name}_w_characteristic_unit.csv", index=False
        )
    elementary = [
        ("dust-id", "AT", "A_FARM", "Air", "tonnes", 2, "Dust"),
        ("dust-id", "AT", "A_FARM", "Air", "tonnes", 3, ""),
        ("dust-id", "AT", "A_FARM", "Air", "tonnes", -1, "Dust"),
        ("dust-id", "DE", "consumer", "Air", "tonnes", 7, "Dust"),
        ("dust-id", "AT", "I_CHIN", "Air", "tonnes", -2, "Dust"),
        ("dust-id", "AT", "A_FARM", "Water", "tonnes", 4, "Dust"),
        ("other-id", "AT", "F_REAL", "Air", "tonnes", 1, "Dust"),
        ("unnamed-id", "DE", "A_MILL", "", "cubic meter", 8, ""),
    ]
    if unmatched:
        elementary.append(("dust-id", "XX", "A_UNKNOWN", "Air", "tonnes", 9, "Dust"))
    pd.DataFrame(
        elementary,
        columns=[
            "Exio substance",
            "Exio country code",
            "Exio act code",
            "Exio compartment",
            "unit",
            "Value",
            "substance_name",
        ],
    ).to_csv(root / "all_elementary_flows_AB_and_BB.csv", index=False)
    return root


@pytest.fixture
def balanced(tmp_path):
    return _bundle(tmp_path / "20260615")


def _key(region, kind, code):
    return region, _MASTER_INDEX[kind], code


def _edit(root, filename, mutate):
    path = root / filename
    frame = pd.read_csv(path, keep_default_na=False)
    if "value" in frame:
        frame["value"] = frame["value"].astype(float)
    mutate(frame)
    frame.to_csv(path, index=False)


def test_sparse_economic_blocks_and_native_units(balanced):
    matrices, indexes, units, layout = parse_bonsai_hsut(balanced, chunksize=2)
    b = matrices["baseline"]
    assert set(b) == {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"}
    assert all(
        all(isinstance(t, pd.SparseDtype) and t.fill_value == 0 for t in frame.dtypes)
        for frame in b.values()
    )
    assert b["S"].shape == (3, 3)
    assert b["U"].at[_key("AT", "c", "C_GRAIN"), _key("DE", "a", "A_MILL")] == 4
    assert b["S"].at[_key("AT", "a", "A_FARM"), _key("AT", "c", "C_GRAIN")] == 12
    assert b["Yc"].at[_key("DE", "c", "C_SERVICE"), _key("AT", "n", "I_CHIN")] == -1
    assert b["Yc"].at[_key("AT", "c", "C_GRAIN"), _key("DE", "n", "consumer")] == 5
    assert b["S"].sparse.to_coo().sum() == 27  # excludes raw substance edges
    assert b["U"].sparse.to_coo().sum() == 7
    assert b["Yc"].shape == (3, 2)  # no Cartesian region expansion
    assert indexes["a"]["main"] == ["A_FARM", "A_MILL", "F_REAL"]
    assert units[_MASTER_INDEX["c"]].unit.to_dict() == {
        "C_GRAIN": "tonnes",
        "C_SERVICE": "Meuro",
    }
    assert units[_MASTER_INDEX["a"]].unit.eq("None").all()
    assert all(b[key].sparse.to_coo().nnz == 0 for key in ("Ya", "Va", "Vc", "Ec"))
    assert layout.year == 2016  # not the release date 20260615


def test_extensions_keep_final_demand_signs_and_distinct_identities(balanced):
    b = parse_bonsai_hsut(balanced)[0]["baseline"]
    dust = "Dust | Air | dust-id"
    assert b["Ea"].at[dust, _key("AT", "a", "A_FARM")] == 4
    assert b["EY"].at[dust, _key("DE", "n", "consumer")] == 7
    assert b["EY"].at[dust, _key("AT", "n", "I_CHIN")] == -2
    assert len(b["Ea"].index) == 4
    assert b["Ea"].at["Dust | Air | other-id", _key("AT", "a", "F_REAL")] == 1
    assert b["Ea"].at["Dust | Water", _key("AT", "a", "A_FARM")] == 4
    assert (
        b["Ea"].at[
            "unnamed-id | unspecified",
            _key("DE", "a", "A_MILL"),
        ]
        == 8
    )


def test_short_satellite_labels_preserve_units_and_native_identities(balanced):
    matrices, _, units, layout = parse_bonsai_hsut(balanced)
    labels = matrices["baseline"]["Ea"].index
    assert units["Satellite account"].index.equals(labels)
    report = {row["label"]: row for row in layout.report["satellites"]}
    assert report["Dust | Water"]["Exio substance"] == "dust-id"
    assert report["Dust | Water"]["unit"] == "tonnes"
    assert report["Dust | Air | other-id"]["Exio substance"] == "other-id"
    assert units["Satellite account"].loc["unnamed-id | unspecified", "unit"] == "cubic meter"


def test_identical_substances_in_different_units_remain_separate(balanced):
    filename = balanced / "all_elementary_flows_AB_and_BB.csv"
    frame = pd.read_csv(filename, keep_default_na=False)
    extra = frame.iloc[[0]].assign(unit="kg", Value=500)
    pd.concat([frame, extra]).to_csv(filename, index=False)
    matrices, _, units, _ = parse_bonsai_hsut(balanced)
    ea = matrices["baseline"]["Ea"]
    a = _key("AT", "a", "A_FARM")
    assert ea.loc["Dust | Air | dust-id | tonnes", a] == 4
    assert ea.loc["Dust | Air | dust-id | kg", a] == 500
    assert units["Satellite account"].loc["Dust | Air | dust-id | kg", "unit"] == "kg"
    assert ea.index.is_unique


def test_zip_nested_directory_and_public_models(balanced, tmp_path):
    archive = tmp_path / "balanced.zip"
    with ZipFile(archive, "w") as handle:
        for path in balanced.iterdir():
            handle.write(path, "release/20260615/" + path.name)
        handle.writestr("release/20260615/unused.pkl", b"not a pickle")
    database = mario.parse_bonsai(archive, name="My BONSAI")
    state = mario.parse_bonsai(balanced.parent, model="ModelState")
    assert database.meta.year == state.metadata.year == 2016
    assert database.meta.name == "My BONSAI"
    assert database.is_hybrid
    assert state.metadata.extra["bonsai"]["extensions_loaded"]
    assert (
        database.info["bonsai"]["economic_flows"][
            "hybrid_use_w_characteristic_unit.csv"
        ]["substance_rows"]
        == 1
    )
    for name, frame in database.matrices["baseline"].items():
        pd.testing.assert_frame_equal(frame, state.get_block(name))
    mario.reset_settings()
    database.parse_scenario("bonsai", path=balanced, new_scenario="second")
    assert "second" in database.scenarios
    current = mario.download_settings()["compute"]
    assert {key: current[key] for key in BONSAI_COMPUTE} == BONSAI_COMPUTE
    from mario.parsers import parse_bonsai

    assert parse_bonsai is mario.parse_bonsai
    assert not (tmp_path / "release").exists()


def test_unmatched_extensions_are_reported_and_optionally_rejected(tmp_path):
    root = _bundle(tmp_path / "balanced", unmatched=True)
    with pytest.warns(UserWarning, match="1 elementary-flow rows"):
        result = mario.parse_bonsai(root)
    report = result.info["bonsai"]
    assert report["unmatched_extensions"][0]["Exio act code"] == "A_UNKNOWN"
    assert report["unmatched_extensions"][0]["Value"] == "9"
    assert result.matrices["baseline"]["Ea"].sparse.to_coo().sum() == 17
    with pytest.raises(WrongInput, match="no classified activity"):
        mario.parse_bonsai(root, unmatched_extensions="raise")


def test_extensions_can_be_explicitly_skipped(balanced):
    (balanced / "all_elementary_flows_AB_and_BB.csv").unlink()
    with pytest.raises(WrongInput, match="Missing BONSAI Balanced file"):
        mario.parse_bonsai(balanced)
    result = mario.parse_bonsai(balanced, extensions=False)
    assert not result.info["bonsai"]["extensions_loaded"]
    assert all(
        result.matrices["baseline"][key].sparse.to_coo().nnz == 0
        for key in ("Ea", "Ec", "EY")
    )


def test_na_region_code_is_preserved(balanced):
    _edit(
        balanced,
        "classification.csv",
        lambda f: f.__setitem__("location", f.location.replace("AT", "NA")),
    )
    _edit(
        balanced,
        "all_elementary_flows_AB_and_BB.csv",
        lambda f: f.__setitem__(
            "Exio country code", f["Exio country code"].replace("AT", "NA")
        ),
    )
    result = mario.parse_bonsai(balanced)
    assert "NA" in result._indeces["r"]["main"]
    assert (
        result.matrices["baseline"]["S"].at[
            _key("NA", "a", "A_FARM"), _key("NA", "c", "C_GRAIN")
        ]
        == 12
    )


def test_empty_extensions_have_zero_placeholders(balanced):
    filename = balanced / "all_elementary_flows_AB_and_BB.csv"
    pd.read_csv(filename).iloc[:0].to_csv(filename, index=False)
    result = mario.parse_bonsai(balanced)
    assert result.info["bonsai"]["elementary_flow_rows"] == 0
    assert result.matrices["baseline"]["Ea"].sparse.to_coo().nnz == 0


def test_commodity_units_must_agree_between_regions(balanced):
    _edit(
        balanced,
        "hybrid_supply_w_characteristic_unit.csv",
        lambda f: f.loc.__setitem__((2, "unit"), "kg"),
    )
    with pytest.raises(WrongInput, match="conflicting BONSAI commodity unit"):
        mario.parse_bonsai(balanced)


@pytest.mark.parametrize(
    "filename, mutate, message",
    [
        (
            "classification.csv",
            lambda f: f.__setitem__("id", "same"),
            "unique nonempty",
        ),
        (
            "classification.csv",
            lambda f: f.loc.__setitem__((0, "time"), 2020),
            "exactly one reference year",
        ),
        (
            "classification.csv",
            lambda f: f.loc.__setitem__(
                (0, "property"), "__import__('os').system('false')"
            ),
            "dictionary literal",
        ),
        (
            "hybrid_use_w_characteristic_unit.csv",
            lambda f: f.loc.__setitem__((0, "from_node"), "unknown"),
            "Unknown node",
        ),
        (
            "hybrid_use_w_characteristic_unit.csv",
            lambda f: f.loc.__setitem__((0, "value"), np.inf),
            "Non-finite",
        ),
        (
            "hybrid_use_w_characteristic_unit.csv",
            lambda f: f.loc.__setitem__((0, "unit"), "kg"),
            "conflicting BONSAI commodity unit",
        ),
        (
            "hybrid_supply_w_characteristic_unit.csv",
            lambda f: f.loc.__setitem__((0, "from_node"), "n1"),
            "final-demand supply",
        ),
    ],
)
def test_malformed_graphs_fail_clearly(balanced, filename, mutate, message):
    _edit(balanced, filename, mutate)
    with pytest.raises(WrongInput, match=message):
        mario.parse_bonsai(balanced)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"chunksize": 0},
        {"chunksize": True},
        {"extensions": "all"},
        {"unmatched_extensions": "ignore"},
        {"model": "bad"},
    ],
)
def test_invalid_options(balanced, kwargs):
    with pytest.raises(WrongInput):
        mario.parse_bonsai(balanced, **kwargs)


def test_invalid_bundle_and_table(balanced, tmp_path):
    broken = tmp_path / "partial.zip"
    broken.write_bytes(b"PK incomplete")
    with pytest.raises(WrongInput, match="complete, valid ZIP"):
        mario.parse_bonsai(broken)
    with pytest.raises(WrongInput, match="HIOT b2"):
        mario.parse_bonsai(balanced, table="IOT")
    _bundle(tmp_path / "another")
    with pytest.raises(WrongInput, match="exactly one BONSAI"):
        mario.parse_bonsai(tmp_path)


BONSAI_COMPUTE = {
    "compute_method": "solve", "linear_solver": "umfpack",
    "linear_strategy": "direct", "singular_policy": "partial",
}


@pytest.mark.parametrize("model", ["Database", "ModelState"])
@pytest.mark.parametrize("extensions", [True, False])
def test_bonsai_sets_session_defaults_without_changing_other_or_saved_settings(
    balanced, tmp_path, monkeypatch, model, extensions,
):
    monkeypatch.setenv("MARIO_CONFIG_DIR", str(tmp_path / "profile"))
    before = mario.download_settings()
    before["nomenclature"]["E"] = "Emissions"
    before["compute"].update(linear_strategy="iterative", auto_w_memory_fraction=0.1)
    mario.upload_settings(before, persist=True)
    saved = mario.get_settings_path().read_bytes()

    mario.parse_bonsai(balanced, model=model, extensions=extensions)

    expected = {**before, "compute": {**before["compute"], **BONSAI_COMPUTE}}
    assert mario.download_settings() == expected
    assert mario.get_settings_path().read_bytes() == saved
    mario.set_compute_method("inverse")
    assert mario.download_settings()["compute"]["compute_method"] == "inverse"


def test_bonsai_defaults_are_active_during_eager_calculations(balanced, monkeypatch):
    observed = []

    def calculate(self, *args, **kwargs):
        observed.append(mario.download_settings()["compute"])

    monkeypatch.setattr(mario.Database, "calc_all", calculate)
    mario.parse_bonsai(balanced, calc_all=True)
    assert observed
    for settings in observed:
        assert {key: settings[key] for key in BONSAI_COMPUTE} == BONSAI_COMPUTE


@pytest.mark.parametrize("failure", ["read", "construct", "interrupt"])
def test_failed_bonsai_import_restores_session_defaults(balanced, monkeypatch, failure):
    from mario.parsers import entrypoints

    before = mario.download_settings()
    error = KeyboardInterrupt if failure == "interrupt" else RuntimeError

    def fail(*args, **kwargs):
        current = mario.download_settings()["compute"]
        assert {key: current[key] for key in BONSAI_COMPUTE} == BONSAI_COMPUTE
        raise error("Import interrupted")

    if failure == "read":
        monkeypatch.setattr(entrypoints, "parse_bonsai_hsut", fail)
    else:
        monkeypatch.setitem(entrypoints.models, "Database", fail)
    with pytest.raises(error, match="Import interrupted"):
        mario.parse_bonsai(balanced)
    assert mario.download_settings() == before


def test_missing_bonsai_solver_fails_before_reading_and_preserves_settings(balanced, monkeypatch):
    from mario.compute import linear_solvers
    from mario.parsers import entrypoints

    before = mario.download_settings()

    def missing():
        raise ImportError("Install scikit-umfpack and SuiteSparse")

    def forbidden(*args, **kwargs):
        pytest.fail("A missing solver must be detected before reading a large bundle")

    monkeypatch.setattr(linear_solvers, "load_umfpack", missing)
    monkeypatch.setattr(entrypoints, "parse_bonsai_hsut", forbidden)
    with pytest.raises(ImportError, match="scikit-umfpack and SuiteSparse"):
        mario.parse_bonsai(balanced)
    assert mario.download_settings() == before


def test_raw_bonsai_reader_does_not_change_session_defaults(balanced):
    before = mario.download_settings()
    parse_bonsai_hsut(balanced)
    assert mario.download_settings() == before


def test_other_parser_does_not_select_bonsai_defaults():
    before = mario.download_settings()
    mario.load_test("IOT")
    assert mario.download_settings() == before
