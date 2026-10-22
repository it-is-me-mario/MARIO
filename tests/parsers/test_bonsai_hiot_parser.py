"""BONSAI HIOT imports preserve the original model and its normalization."""

from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

import mario
from mario.compute.resolver import resolve
from mario.compute.types import ResolutionContext
from mario.log_exc.exceptions import WrongInput
from mario.parsers.bonsai_hiot import (
    ACTIVITY,
    DEMAND,
    DESTINATION,
    EXTENSIONS,
    FLOW_COLUMNS,
    ORIGIN,
    PRODUCT,
    REQUIRED,
    TECHNOSPHERE,
    parse_bonsai_hiot,
)


pytestmark = pytest.mark.usefixtures("bonsai_without_umfpack")


def _write(root):
    root.mkdir(parents=True)
    # Native row/column order intentionally differs from lexical order.
    t = pd.DataFrame(
        [[90.0, -4.0, 4.0], [-3.0, 49.0, -3.0], [-6.0, -2.0, 60.0]],
        index=["AT;P_WHEAT;tonnes", "DE;P_WHEAT;tonnes", "AT;P_SERVICE;Meuro"],
        columns=["AT;A_WHEAT", "DE;A_WHEAT", "AT;A_SERVICE"],
        dtype=pd.SparseDtype("float64", 0),
    )
    t.to_pickle(root / TECHNOSPHERE)
    fd = [
        ("AT", "P_WHEAT", "AT", "F_HOUS", "tonnes", 80.0),
        ("DE", "P_WHEAT", "DE", "I_CHIN", "tonnes", -1.0),
        ("AT", "P_SERVICE", "AT", "F_HOUS", "Meuro", 52.0),
    ]
    pd.DataFrame(fd, columns=FLOW_COLUMNS).to_csv(root / DEMAND, index=False)
    pd.DataFrame(
        [
            (
                "co2",
                "AT",
                "A_WHEAT",
                "Air",
                "tonnes",
                10.0,
                "Carbon dioxide, fossil",
                "2016.0",
            ),
            ("co2", "DE", "A_WHEAT", "Air", "tonnes", 20.0, "", "2016.0"),
            ("co2", "AT", "A_SERVICE", "Air", "tonnes", 3.0, "", "2016.0"),
            ("co2", "AT", "F_HOUS", "Air", "tonnes", 7.0, "", "2016.0"),
            ("ch4", "DE", "A_WHEAT", "Air", "tonnes", 0.1, "Methane, fossil", ""),
            ("co2", "AT", "A_SERVICE", "Water", "tonnes", -2.0, "", "2016.0"),
        ],
        columns=[
            "Exio substance",
            "Exio country code",
            ACTIVITY,
            "Exio compartment",
            "unit",
            "Value",
            "substance_name",
            "time",
        ],
    ).to_csv(root / EXTENSIONS, index=False)
    return root


@pytest.fixture
def hiot(tmp_path):
    return _write(tmp_path / "release" / "20260615")


def _edit(root, filename, mutate):
    path = root / filename
    frame = pd.read_csv(path, keep_default_na=False)
    mutate(frame)
    frame.to_csv(path, index=False)


def test_get_mix_uses_native_output_and_only_observed_regional_sectors(hiot):
    db = mario.parse_bonsai(hiot, table="IOT")
    before = dict(db.matrices["baseline"])
    assert db.get_mix(["P_WHEAT"]) == {"AT": {"P_WHEAT": 1.0}, "DE": {"P_WHEAT": 1.0}}
    assert db.get_mix(["P_SERVICE"]) == {"AT": {"P_SERVICE": 1.0}, "DE": {}}
    assert db.mix == {"AT": {"P_SERVICE": 1.0}, "DE": {}}
    assert all(db.get_block(name) is frame for name, frame in before.items())
    with pytest.raises(WrongInput, match="unknown sectors"):
        db.get_mix(["missing"])
    output = db.X.copy()
    output.loc[("AT", "Sector", "P_SERVICE"), :] = 0
    db.set_block("X", output)
    assert db.get_mix(["P_SERVICE"]) == {"AT": {"P_SERVICE": 0.0}, "DE": {}}


def test_native_units_regions_credits_and_source_output(hiot):
    db = mario.parse_bonsai(hiot, table="IOT", chunksize=2)
    b = db.matrices["baseline"]
    expected = np.array([[0.0, 4.0, -4.0], [3.0, 0.0, 3.0], [6.0, 2.0, 0.0]])
    np.testing.assert_allclose(b["Z"].sparse.to_dense(), expected)
    np.testing.assert_allclose(b["X"].iloc[:, 0], [90.0, 49.0, 60.0])
    assert not np.allclose(
        b["X"].iloc[:, 0], expected.sum(axis=1) + b["Y"].sparse.to_dense().sum(axis=1)
    )
    assert db.get_index("Sector") == {"AT": ["P_WHEAT", "P_SERVICE"], "DE": ["P_WHEAT"]}
    assert db.get_index("Consumption category") == {"AT": ["F_HOUS"], "DE": ["I_CHIN"]}
    assert db.units["Sector"].unit.to_dict() == {
        "P_WHEAT": "tonnes",
        "P_SERVICE": "Meuro",
    }
    assert db.meta.year == 2016
    assert db.is_hybrid
    assert (
        b["Y"].at[("DE", "Sector", "P_WHEAT"), ("DE", "Consumption category", "I_CHIN")]
        == -1
    )
    assert b["E"].loc["Carbon dioxide, fossil | Air"].sum() == 33
    assert b["EY"].loc["Carbon dioxide, fossil | Air"].sum() == 7
    assert b["E"].loc["Carbon dioxide, fossil | Water"].sum() == -2
    for name in ("Z", "Y", "E", "EY", "VY"):
        assert all(
            isinstance(dtype, pd.SparseDtype) and dtype.fill_value == 0
            for dtype in b[name].dtypes
        )
    assert len(db.info["bonsai"]["reference_products"]) == 3


@pytest.mark.parametrize("model", ["Database", "ModelState"])
def test_footprints_equal_original_absolute_bonsai_system(hiot, model):
    db = mario.parse_bonsai(hiot, table="IOT", model=model)
    np.testing.assert_allclose(db.get_block("X").iloc[:, 0], [90.0, 49.0, 60.0])
    # Independently specified physical net-supply system, including self use
    # and avoided production; demand deliberately does not balance source X.
    t = np.array([[90.0, -4.0, 4.0], [-3.0, 49.0, -3.0], [-6.0, -2.0, 60.0]])
    expected = np.linalg.solve(t.T, [10.0, 20.0, 3.0])
    f = resolve(
        "f",
        db,
        context=ResolutionContext(compute_method="solve", linear_solver="scipy"),
    )
    np.testing.assert_allclose(f.loc["Carbon dioxide, fossil | Air"], expected)
    mario.set_linear_solver("scipy")
    if model == "Database":
        db.calc_ghg()
        np.testing.assert_allclose(
            db.f.loc["GHG AR6 GWP-100"],
            np.linalg.solve(t.T, [10.0, 20.0 + 0.1 * 29.8, 3.0]),
        )


def test_zip_and_extracted_bundle_read_only_native_pickle(hiot, tmp_path, monkeypatch):
    archive = tmp_path / "hiot.zip"
    with ZipFile(archive, "w") as z:
        for file in hiot.iterdir():
            z.write(file, "HIOT/20260615/" + file.name)
        z.writestr(
            "HIOT/20260615/inverse_of_leontief.b2.pkl", b"invalid unused inverse"
        )
    original = pd.read_pickle
    reads = []

    def read(handle, *args, **kwargs):
        reads.append(getattr(handle, "name", ""))
        return original(handle, *args, **kwargs)

    monkeypatch.setattr(pd, "read_pickle", read)
    db = mario.parse_bonsai(archive, table="IOT")
    state = mario.parse_bonsai(hiot.parent, table="IOT", model="ModelState")
    for name, value in db.matrices["baseline"].items():
        pd.testing.assert_frame_equal(value, state.get_block(name))
    assert len(reads) == 2
    assert all(name.endswith(TECHNOSPHERE) for name in reads)
    assert not (tmp_path / "HIOT").exists()


def test_year_is_metadata_not_release_date_and_extensions_can_be_skipped(hiot):
    (hiot / EXTENSIONS).unlink()
    with pytest.raises(WrongInput, match="pass year="):
        mario.parse_bonsai(hiot, table="IOT", extensions=False)
    db = mario.parse_bonsai(hiot, table="IOT", year=2016, extensions=False)
    assert db.meta.year == 2016
    assert db.get_block("E").sparse.to_coo().nnz == 0
    assert not db.info["bonsai"]["extensions_loaded"]
    with pytest.raises(WrongInput, match="Missing BONSAI HIOT b2 file"):
        mario.parse_bonsai(hiot, table="IOT", year=2016)


@pytest.mark.parametrize("year", [True, 2016.5, "2016", 0, 2020])
def test_invalid_or_inconsistent_year(hiot, year):
    with pytest.raises(WrongInput, match="year"):
        mario.parse_bonsai(hiot, table="IOT", year=year)


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda f: f.__setitem__(f.columns[0], [np.inf, 0.0, 0.0]), "Non-finite"),
        (lambda f: f.__setitem__(f.columns[0], [0.0, 0.0, 0.0]), "strictly positive"),
        (
            lambda f: setattr(f, "index", ["bad", *f.index[1:]]),
            "Invalid BONSAI HIOT labels",
        ),
        (
            lambda f: setattr(f, "index", [f.index[1], *f.index[1:]]),
            "unique native flat labels",
        ),
        (
            lambda f: setattr(f, "index", ["AT;P_WHEAT;kg", *f.index[1:]]),
            "sector units",
        ),
        (
            lambda f: setattr(f, "columns", ["FR;A_WHEAT", *f.columns[1:]]),
            "share a region",
        ),
    ],
)
def test_malformed_native_matrix_fails_without_repair(hiot, mutation, message):
    frame = pd.read_pickle(hiot / TECHNOSPHERE).sparse.to_dense()
    mutation(frame)
    frame.to_pickle(hiot / TECHNOSPHERE)
    with pytest.raises(WrongInput, match=message):
        mario.parse_bonsai(hiot, table="IOT")


def test_invalid_demand_units_and_unknown_products(hiot):
    _edit(hiot, DEMAND, lambda f: f.loc.__setitem__((0, "unit"), "kg"))
    with pytest.raises(WrongInput, match="product unit"):
        mario.parse_bonsai(hiot, table="IOT")
    _edit(hiot, DEMAND, lambda f: f.loc.__setitem__((0, PRODUCT), "absent"))
    with pytest.warns(UserWarning, match="1 final-demand rows"):
        db = mario.parse_bonsai(hiot, table="IOT")
    assert len(db.info["bonsai"]["unmatched_final_demand"]) == 1
    with pytest.raises(WrongInput, match="1 final-demand rows"):
        mario.parse_bonsai(hiot, table="IOT", unmatched_final_demand="raise")


def test_unmatched_satellites_are_reported_or_rejected(hiot):
    _edit(hiot, EXTENSIONS, lambda f: f.loc.__setitem__((0, ACTIVITY), "missing"))
    with pytest.warns(UserWarning, match="1 elementary-flow rows"):
        db = mario.parse_bonsai(hiot, table="IOT")
    assert db.info["bonsai"]["unmatched_extensions"][0][ACTIVITY] == "missing"
    with pytest.raises(WrongInput, match="no classified activity"):
        mario.parse_bonsai(hiot, table="IOT", unmatched_extensions="raise")


def test_unmatched_demand_retains_all_source_columns(hiot):
    frame = pd.read_csv(hiot / DEMAND, keep_default_na=False)
    frame["from_node"] = ["native-uuid", "other-uuid", "third-uuid"]
    frame.loc[0, PRODUCT] = "absent"
    frame.to_csv(hiot / DEMAND, index=False)
    with pytest.warns(UserWarning, match="1 final-demand rows"):
        db = mario.parse_bonsai(hiot, table="IOT")
    assert db.info["bonsai"]["unmatched_final_demand"][0]["from_node"] == "native-uuid"


def test_invalid_native_pickle_and_missing_demand_column(hiot):
    path = hiot / TECHNOSPHERE
    original = path.read_bytes()
    path.write_bytes(b"incomplete pickle")
    with pytest.raises(WrongInput, match="Invalid native BONSAI HIOT file"):
        mario.parse_bonsai(hiot, table="IOT")
    path.write_bytes(original)
    frame = pd.read_csv(hiot / DEMAND).drop(columns="unit")
    frame.to_csv(hiot / DEMAND, index=False)
    with pytest.raises(WrongInput, match="missing columns"):
        mario.parse_bonsai(hiot, table="IOT")


def test_eager_calculation_observes_source_production(hiot, monkeypatch):
    observed = []

    def calculate(self, *args, **kwargs):
        observed.append(self.get_block("X").iloc[:, 0].to_list())

    monkeypatch.setattr(mario.Database, "calc_all", calculate)
    mario.parse_bonsai(hiot, table="IOT", calc_all=True)
    assert observed == [[90.0, 49.0, 60.0]]


def test_raw_reader_does_not_change_settings_and_retains_na_region(hiot):
    frame = pd.read_pickle(hiot / TECHNOSPHERE)
    frame.index = frame.index.str.replace("^AT;", "NA;", regex=True)
    frame.columns = frame.columns.str.replace("^AT;", "NA;", regex=True)
    frame.to_pickle(hiot / TECHNOSPHERE)
    for filename in (DEMAND, EXTENSIONS):
        path = hiot / filename
        frame = pd.read_csv(path, keep_default_na=False).replace("AT", "NA")
        frame.to_csv(path, index=False)
    before = mario.download_settings()
    matrices, indexes, _, _ = parse_bonsai_hiot(hiot)
    assert mario.download_settings() == before
    assert "NA" in indexes["r"]["main"]
    assert matrices["baseline"]["Z"].shape == (3, 3)
