"""Satellite selection preserves accounting values and existing model structure."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

import mario
from mario.compute import sum_operator
from mario.compute.types import ComputeOptions
from mario.log_exc.exceptions import WrongInput
from tests.api.test_trade_content_loading import regional_model


@pytest.mark.parametrize("table", ["IOT", "SUT"])
@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("coefficients_only", [False, True])
def test_selection_filters_all_cached_satellite_blocks_and_scenarios(
    table, sparse, coefficients_only, monkeypatch
):
    db = mario.load_test(table)
    if sparse:
        for name, frame in list(db.matrices["baseline"].items()):
            db.set_block(name, frame.astype(pd.SparseDtype(float, 0)))
    names = (
        ["e", "f", "F"] if table == "IOT" else ["ea", "ec", "fa", "fc", "Fc", "E", "e", "f", "F"]
    )
    db.calc_all(names, compute_options=ComputeOptions(backend_override="sparse_direct"))
    if coefficients_only:
        db.reset_to_coefficients("baseline")
    db.clone_scenario("baseline", "alternative")
    before = {scenario: dict(blocks) for scenario, blocks in db.matrices.items()}
    units = db.units["Satellite account"].loc[["CO2"]].copy()
    db.set_clusters(
        {"Satellite account": {"all chosen": ["Employment", "CO2"], "jobs": ["Employment"]}}
    )
    db._indeces["k"]["aggregated"] = pd.DataFrame(
        {"Aggregation": ["Jobs", "Carbon"]}, index=["Employment", "CO2"]
    )

    def no_compute(*args, **kwargs):
        raise AssertionError("Filtering must not calculate missing matrices")

    monkeypatch.setattr(db, "calc_all", no_compute)
    assert db.keep_extensions(["CO2"]) is None
    assert db.get_index("Satellite account") == ["CO2"]
    pd.testing.assert_frame_equal(db.units["Satellite account"], units)
    assert db._indeces["k"]["aggregated"].index.tolist() == ["CO2"]
    assert db.available_clusters["Satellite account"]["jobs"] == []
    assert db.clusters["Satellite account"]["all chosen"] == ["CO2"]
    assert db.scenarios == ["baseline", "alternative"]
    for scenario, blocks in before.items():
        assert blocks.keys() == db.matrices[scenario].keys()
        for name, frame in blocks.items():
            axes = db.get_block_spec(name).row_axes
            actual = db.get_block(name, scenario=scenario)
            if any(axis.base == "Satellite account" for axis in axes):
                pd.testing.assert_frame_equal(actual, frame.loc[["CO2"]])
            else:
                assert actual is frame


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_reduced_multipliers_match_full_model_with_one_rhs(table, monkeypatch):
    import mario.compute.sut_formulas as sut
    import mario.compute.iot_formulas as iot

    db = mario.load_test(table)
    name = "f" if table == "IOT" else "fc"
    options = ComputeOptions(backend_override="sparse_direct")
    expected = db.copy().resolve(name, compute_options=options).loc[["CO2"]]
    module = iot if table == "IOT" else sut
    function = "_solve_iot_system" if table == "IOT" else "_solve_sut_system"
    original = getattr(module, function)
    calls = []

    def recording_solver(matrix, rhs, **kwargs):
        calls.append(rhs.shape)
        return original(matrix, rhs, **kwargs)

    monkeypatch.setattr(module, function, recording_solver)
    db.keep_extensions(["CO2"])
    actual = db.resolve(name, compute_options=options)
    pd.testing.assert_frame_equal(actual, expected)
    assert calls and all(shape[1] == 1 for shape in calls)
    assert not db.has_matrix("w") and not db.has_matrix("wcc")


@pytest.mark.parametrize("table", ["IOT", "SUT"])
@pytest.mark.parametrize("strategy", ["sparse_direct", "sparse_iterative"])
def test_empty_selection_preserves_economic_axes_and_sparse_storage(table, strategy, monkeypatch):
    import scipy.sparse.linalg

    db = mario.load_test(table)
    for name, frame in list(db.matrices["baseline"].items()):
        db.set_block(name, frame.astype(pd.SparseDtype(float, 0)))
    db.keep_extensions([])
    assert db.get_index("Satellite account") == []
    assert db.units["Satellite account"].empty
    for name in ["E", "EY"] if table == "IOT" else ["Ea", "Ec", "EY"]:
        frame = db.get_block(name)
        assert frame.shape[0] == 0 and frame.shape[1] > 0
        assert all(isinstance(dtype, pd.SparseDtype) for dtype in frame.dtypes)

    def no_factorization(*args, **kwargs):
        raise AssertionError("An empty indicator set needs no factorization")

    monkeypatch.setattr(scipy.sparse.linalg, "factorized", no_factorization)
    result = db.resolve(
        "f" if table == "IOT" else "fc", compute_options=ComputeOptions(backend_override=strategy)
    )
    assert result.shape[0] == 0 and result.shape[1] > 0


def test_copy_and_noop_keep_original_order_and_are_independent():
    db = mario.load_test("IOT")
    original = db.E.copy()
    result = db.keep_extensions("CO2", inplace=False)
    assert result.get_index("Satellite account") == ["CO2"]
    assert db.get_index("Satellite account") == ["Employment", "CO2"]
    result.E.iloc[0, 0] = -100
    pd.testing.assert_frame_equal(db.E, original)
    identities = {name: id(frame) for name, frame in db.matrices["baseline"].items()}
    db.keep_extensions(["CO2", "Employment"])
    assert db.get_index("Satellite account") == ["Employment", "CO2"]
    assert identities == {name: id(frame) for name, frame in db.matrices["baseline"].items()}


@pytest.mark.parametrize(
    "selection", [["CO2", "missing"], ["CO2", "CO2"], None, 42, [["CO2"]], {"CO2": True}]
)
def test_invalid_selection_is_atomic(selection):
    db = mario.load_test("SUT")
    before = dict(db.matrices["baseline"])
    indexes, history = deepcopy(db._indeces), list(db.meta._history)
    with pytest.raises(WrongInput):
        db.keep_extensions(selection)
    assert db._indeces == indexes
    assert db.meta._history == history
    assert all(db.get_block(name) is frame for name, frame in before.items())


def test_structured_rows_and_custom_satellite_axes():
    db = mario.load_test("IOT")
    for name in ["E", "EY"]:
        original = db.get_block(name)
        index = pd.MultiIndex.from_tuples(
            [(region, "TOTAL", label) for region in ["IT", "DE"] for label in original.index],
            names=["Region", "Sector", "Satellite account"],
        )
        db.set_block(
            name,
            pd.DataFrame(np.vstack([original, original]), index=index, columns=original.columns),
        )
    db.register_block_spec(
        name="cross_accounts",
        row_axes=[("source", "k")],
        col_axes=[("destination", "k")],
    )
    cross = pd.DataFrame(
        [[1.0, 2.0], [3.0, 4.0]], index=["Employment", "CO2"], columns=["Employment", "CO2"]
    )
    db.set_block("cross_accounts", cross)
    db.keep_extensions(["CO2"])
    for name in ["E", "EY"]:
        assert db.get_block(name).index.tolist() == [
            ("IT", "TOTAL", "CO2"),
            ("DE", "TOTAL", "CO2"),
        ]
    pd.testing.assert_frame_equal(db.get_block("cross_accounts"), cross.loc[["CO2"], ["CO2"]])


def test_custom_totals_are_invalidated_transitively_and_recomputed():
    db = mario.load_test("IOT")
    db.register_operator(sum_operator(name="satellite_total", source="E", over="rows"))
    db.register_operator(sum_operator(name="grand_total", source="satellite_total"))
    db.register_operator(sum_operator(name="economic_total", source="Y"))
    db.resolve_many(["satellite_total", "grand_total", "economic_total"])
    independent = db.get_block("economic_total")
    db.keep_extensions(["CO2"])
    assert not db.has_matrix("satellite_total") and not db.has_matrix("grand_total")
    assert db.get_block("economic_total") is independent
    actual = db.resolve("satellite_total")
    np.testing.assert_allclose(actual.to_numpy().ravel(), db.E.loc["CO2"].to_numpy())


def test_regional_sparse_sut_retains_memberships_without_unified_views():
    db = regional_model(True)
    before = db.get_index("all")
    assert isinstance(before["Activity"], dict)
    for name in ["Ea", "Ec", "EY"]:
        frame = db.get_block(name)
        extra = frame.copy() * 0.2
        extra.index = pd.Index(["CH4"], name=frame.index.name)
        db.set_block(name, pd.concat([frame, extra]))
    db._indeces["k"]["main"].append("CH4")
    db.units["Satellite account"] = pd.DataFrame({"unit": ["kg", "kg"]}, index=["CO2", "CH4"])
    db.keep_extensions(["CO2"])
    assert db.get_index("all") == before
    assert db.Ea.index.tolist() == ["CO2"]
    assert not db.has_matrix("Z") and not db.has_matrix("z")


def test_malformed_satellite_block_fails_without_partial_filtering():
    db = mario.load_test("IOT")
    before = db.E
    db.set_block("EY", np.zeros_like(db.EY))
    with pytest.raises(WrongInput, match="pandas DataFrame"):
        db.keep_extensions(["CO2"])
    assert db.E is before
    assert db.get_index("Satellite account") == ["Employment", "CO2"]
