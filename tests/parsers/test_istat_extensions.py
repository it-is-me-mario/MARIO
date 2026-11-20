"""Optional ISTAT satellites: source alignment, caching and full workflows."""

from itertools import product
import json
import sqlite3
import zipfile

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.parsers import istat_extensions as satellites
from tests.parsers.test_istat_parser import (
    _istat_import_frame, _istat_supply_frame, _istat_use_frame, _write_xlsx,
)


def _payload(group, *, year=2020, dense=False):
    dataset, unit, dim, indicators = satellites._SOURCES[group]
    # Deliberately reorder both dimensions and NACE members. Values must align
    # by source codes even when the economic labels describe different sectors.
    categories = {dim: list(indicators), "time": [str(year)], "nace_r2": ["HH", "A02", "A01", "TOTAL"],
                  "geo": ["IT"], "unit": [unit], "freq": ["A"]}
    dimensions = list(categories)
    values, status = {}, {}
    for pos, coordinates in enumerate(product(*categories.values())):
        chosen = dict(zip(dimensions, coordinates))
        indicator_pos = list(indicators).index(chosen[dim])
        values[str(pos)] = {"A01": 10, "A02": 20, "HH": 5, "TOTAL": 99999}[chosen["nace_r2"]] + indicator_pos
        if chosen["nace_r2"] == "A01":
            status[str(pos)] = "p"
    return {
        "id": dimensions, "size": [len(x) for x in categories.values()], "updated": "source-vintage",
        "dimension": {k: {"category": {"index": {c: i for i, c in enumerate(codes)}, "label": {c: f"Description {c}" for c in codes}}} for k, codes in categories.items()},
        "value": list(values.values()) if dense else values, "status": status,
    }


def _snapshot(group, payload):
    dataset, unit, dim, indicators = satellites._SOURCES[group]
    query = {"geo": "IT", "time": "2020", "unit": unit, "freq": "A", "lang": "en"}
    if group != "emissions":
        query[dim] = indicators[0]
    return {"dataset": dataset, "query": query, "retrieved_at": "test-retrieval", "payload": payload}


def _cache(root, groups=satellites._GROUPS):
    (root / "extensions").mkdir(exist_ok=True)
    for group in groups:
        dataset = satellites._SOURCES[group][0]
        (root / "extensions" / f"{dataset}_IT_2020.json").write_text(json.dumps(_snapshot(group, _payload(group))), encoding="utf-8")


@pytest.fixture
def source(tmp_path, monkeypatch):
    # Network access is always explicit. An accidental request must fail here.
    monkeypatch.setattr(satellites.requests, "get", lambda *a, **k: pytest.fail("Unexpected network request"))
    for filename, sheet, frame in (
        ("SUPPLY_63B.xlsx", "sup20", _istat_supply_frame()),
        ("USEPB_63B.xlsx", "uspb20", _istat_use_frame()),
        ("IMPORT_63B.xlsx", "imprt20", _istat_import_frame()),
    ):
        _write_xlsx(tmp_path / filename, sheet, frame)
    return tmp_path


def test_default_never_loads_satellites(source):
    db = mario.parse_istat(source, year=2020, table="SUT")
    assert "istat_extensions" not in db.info
    assert db.query("Ea").eq(0).all().all()
    assert not (source / "extensions").exists()


@pytest.mark.parametrize("selection", [True, False, 1, ["unknown"], [None], "emission"])
def test_invalid_selection_rejected_before_io(selection):
    with pytest.raises(WrongInput, match="extensions"):
        mario.parse_istat("missing", year=2020, table="SUT", extensions=selection, download=True)


@pytest.mark.parametrize("table,level", [("IOT", "63"), ("SUT", "20")])
def test_unsupported_layout_rejected_before_io(table, level):
    with pytest.raises(WrongInput, match="extensions require"):
        mario.parse_istat("missing", year=2020, table=table, level=level, extensions="all", download=True)


def test_missing_cache_is_explicit_and_offline(source):
    with pytest.raises(WrongInput, match="download=True"):
        mario.parse_istat(source, year=2020, table="SUT", extensions="energy")


def test_all_accounts_match_codes_units_households_and_source_hours(source):
    _cache(source)
    db = mario.parse_istat(source, year=2020, table="SUT", import_representation="separate", extensions="all")
    ea, ey = db.query("Ea"), db.query("EY")
    assert ea.shape == (27, 2)
    np.testing.assert_allclose(ea.loc["AEA | GHG"], [10, 20])
    np.testing.assert_allclose(ea.loc["Employment | Total"], [10000, 20000])
    np.testing.assert_allclose(ea.loc["Employment | Hours worked"], [3000, 3000])
    np.testing.assert_allclose(ea.loc["Energy | Net domestic energy use"], [10, 20])
    np.testing.assert_allclose(ey.loc["AEA | GHG"], [5, 0])
    np.testing.assert_allclose(ey.loc["Energy | Net domestic energy use"], [5, 0])
    assert ey.loc["Employment | Total"].eq(0).all()
    assert db.query("Ec").eq(0).all().all()
    units = db.units["Satellite account"]["unit"]
    assert units["AEA | GHG"] == "t CO2-eq"
    assert units["AEA | CH4"] == "t"
    assert units["AEA | ACG"] == "t SO2-eq"
    assert units["AEA | O3PR"] == "t NMVOC-eq"
    assert units["Energy | Net domestic energy use"] == "TJ"
    assert db.info["istat_extensions"]["activity_mapping"] == {"V01": "A01", "V02": "A02"}
    assert db.info["istat_extensions"]["sources"][0]["status"]
    assert db.configuration.import_representation == "separate"
    np.testing.assert_allclose(db.query("IMP_a"), [[1, 0], [0, 2]])


def test_satellites_with_default_imports_and_model_state(source):
    _cache(source, ["energy"])
    db = mario.parse_istat(source, year=2020, table="SUT", extensions=["energy", "energy"])
    assert "Importazioni cif" in db.get_index("Factor of production")
    assert db.query("Ea").shape == (1, 2)
    state = mario.parse_istat(source, year=2020, table="SUT", model="ModelState", extensions="energy", import_representation="separate")
    assert state.metadata.extra["istat_extensions"]["groups"] == ["energy"]
    assert state.metadata.extra["model_configuration"]["import_representation"] == "separate"


@pytest.mark.parametrize("problem", ["missing", "confidential", "year", "country", "unit", "frequency", "nace", "nonfinite"])
def test_bad_snapshots_never_silently_fill_zero(source, problem):
    _cache(source, ["energy"])
    path = source / "extensions/env_ac_pefa04_IT_2020.json"
    snapshot = json.loads(path.read_text())
    data = snapshot["payload"]
    if problem == "missing":
        data["value"].pop("2")  # A01 is the third NACE member.
    elif problem == "confidential":
        data["status"]["2"] = "c"
    elif problem == "nonfinite":
        data["value"]["2"] = float("inf")
    else:
        dim, replacement = {"year": ("time", "2021"), "country": ("geo", "FR"), "unit": ("unit", "GJ"), "frequency": ("freq", "Q"), "nace": ("nace_r2", "NOT_A01")}[problem]
        index = data["dimension"][dim]["category"]["index"]
        old = "A01" if problem == "nace" else next(iter(index))
        index[replacement] = index.pop(old)
    path.write_text(json.dumps(snapshot))
    with pytest.raises(WrongFormat, match="snapshot|unavailable"):
        mario.parse_istat(source, year=2020, table="SUT", extensions="energy")


def test_zip_cache_survives_extraction_and_full_workflow(source):
    _cache(source)
    archive = source / "release.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        for path in source.glob("*.xlsx"):
            stream.write(path, arcname=path.name)
    db = mario.parse_istat(archive, year=2020, table="SUT", extensions="all", import_representation="separate")
    original_ea, original_ey = db.query("Ea"), db.query("EY")
    np.testing.assert_allclose(db.query("ea").to_numpy() * db.query("Xa").to_numpy().T, original_ea)
    restored = db.to_import_representation("factor-accounts", inplace=False).to_import_representation("separate", inplace=False)
    pd.testing.assert_frame_equal(restored.query("Ea"), original_ea)
    for name in ("IMP_a", "IMP_Y"):
        pd.testing.assert_frame_equal(restored.query(name), db.query(name))
    db.aggregate(io={level: pd.DataFrame({"Aggregation": ["All", "All"]}, index=db.get_index(level)) for level in ("Activity", "Commodity")}, levels=["Activity", "Commodity"], calc_all=False)
    np.testing.assert_allclose(db.query("Ea").iloc[:, 0], original_ea.sum(axis=1))
    pd.testing.assert_frame_equal(db.query("EY"), original_ey)
    assert db.query("IMP_a").iloc[0, 0] == 3
    output = source / "roundtrip.xlsx"
    db.to_excel(output, flows=True, coefficients=False)
    loaded = mario.parse_from_excel(str(output), table="SUT", mode="flows", data_sheet="flows")
    for name in ("Ea", "EY", "IMP_a", "IMP_Y"):
        np.testing.assert_allclose(loaded.query(name), db.query(name))
    pd.testing.assert_frame_equal(loaded.units["Satellite account"], db.units["Satellite account"], check_names=False)


def test_download_cache_validates_before_replacing_and_reuses_offline(source, monkeypatch):
    import mario.parsers.entrypoints as entrypoints
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs["params"]))
        group = next(g for g, spec in satellites._SOURCES.items() if url.endswith(spec[0]))
        class Response:
            def raise_for_status(self):
                pass
            def json(self):
                return _payload(group, dense=True)
        return Response()
    monkeypatch.setattr(satellites.requests, "get", get)
    monkeypatch.setattr(entrypoints, "download_istat_io", lambda *a, **k: {"extracted_path": source})
    db = mario.parse_istat(source, year=2020, table="SUT", extensions="energy", download=True)
    assert len(calls) == 1
    cached = source / "extensions/env_ac_pefa04_IT_2020.json"
    previous = cached.read_bytes()
    class Broken:
        def raise_for_status(self):
            pass
        def json(self):
            return _payload("energy", year=2021)
    monkeypatch.setattr(satellites.requests, "get", lambda *a, **k: Broken())
    with pytest.raises(WrongFormat):
        mario.parse_istat(source, year=2020, table="SUT", extensions="energy", download=True, overwrite_download=True)
    assert cached.read_bytes() == previous
    monkeypatch.setattr(satellites.requests, "get", lambda *a, **k: pytest.fail("Unexpected network request"))
    offline = mario.parse_istat(source, year=2020, table="SUT", extensions="energy")
    pd.testing.assert_frame_equal(offline.query("Ea"), db.query("Ea"))


def test_missing_native_hours_is_an_error_only_when_selected(source):
    use = _istat_use_frame()
    use.iat[14, 3] = None
    _write_xlsx(source / "USEPB_63B.xlsx", "uspb20", use)
    mario.parse_istat(source, year=2020, table="SUT")
    with pytest.raises(WrongFormat, match="Ore lavorate"):
        mario.parse_istat(source, year=2020, table="SUT", extensions="employment")


def test_zero_and_signed_energy_are_retained(source):
    _cache(source, ["energy"])
    path = source / "extensions/env_ac_pefa04_IT_2020.json"
    snapshot = json.loads(path.read_text())
    snapshot["payload"]["value"].update({"1": 0.0, "2": -2.0})
    path.write_text(json.dumps(snapshot))
    db = mario.parse_istat(source, year=2020, table="SUT", extensions="energy")
    np.testing.assert_allclose(db.query("Ea").iloc[0], [-2, 0])


def test_household_alignment_is_required_for_environment_only(source):
    _cache(source)
    use = _istat_use_frame()
    use.iat[4, 5] = "Not household consumption"
    _write_xlsx(source / "USEPB_63B.xlsx", "uspb20", use)
    # Default import representation does not require identical IMPORT/USE FD labels.
    mario.parse_istat(source, year=2020, table="SUT", extensions="employment")
    with pytest.raises(WrongFormat, match="household"):
        mario.parse_istat(source, year=2020, table="SUT", extensions="emissions")


def test_satellites_and_native_imports_reach_cvxlab_database(source, monkeypatch):
    pytest.importorskip("cvxlab")
    from mario.ops import cvxlab_export
    from tests.api.test_to_cvxlab import make_settings, SUT_AXES, assert_matrix_values

    _cache(source)
    db = mario.parse_istat(source, year=2020, table="SUT", extensions="all", import_representation="separate")
    db.aggregate(io={level: pd.DataFrame({"Aggregation": ["All", "All"]}, index=db.get_index(level)) for level in ("Activity", "Commodity")}, levels=["Activity", "Commodity"], calc_all=False)
    settings = source / "model_settings.xlsx"
    mapping = make_settings(settings, extra=False)
    report = db.to_cvxlab(model_settings=settings, path=source / "model", mapping=mapping)
    assert not report["pending_sets"]
    assert not report["pending_matrices"]
    assert not report["unmatched_coordinates"]
    for name, fields in SUT_AXES.items():
        assert_matrix_values(report["input_files"][0], db, name, fields, mapping)
    bridge = cvxlab_export.cvxlab_bridge
    with monkeypatch.context() as context:
        context.setattr("builtins.input", lambda *args: "n")
        model = bridge._build_cvxlab_model(main_dir_path=source, model_dir_name="model", input_data_files_type="xlsx", import_custom=False)
    bridge._call_model_method(model, "load_model_coordinates", "_load_model_coordinates")
    model.core.database.create_blank_sqlite_database()
    model.core.database.load_sets_to_sqlite_database()
    model.core.database.generate_blank_sqlite_data_tables()
    model.core.database.sets_data_to_sql_data_tables()
    model.core.database.load_data_input_files_to_database(table_key_list=list(mapping["matrices"].values()), force_overwrite=True)
    database_path = report["path"] / bridge.cl.Defaults.ConfigFiles.SQLITE_DATABASE_FILE
    with sqlite3.connect(database_path) as connection:
        for name in ("Ea", "EY", "IMP_a", "IMP_Y"):
            actual = pd.read_sql_query(f'SELECT * FROM "{mapping["matrices"][name]}"', connection)
            np.testing.assert_allclose(np.sort(actual["values"].to_numpy(dtype=float)), np.sort(db.query(name).to_numpy().ravel()))
