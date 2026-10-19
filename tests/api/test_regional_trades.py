"""Trade totals respect actual regional nodes and sparse storage."""

import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from tests.api.test_regional_indexes import regional_database


@pytest.fixture(params=[False, True], ids=["dense", "sparse"])
def database(request):
    database = regional_database(
        {"IT": ["A1", "A2"], "DE": ["A3"], "FR": ["A4"], "Global": []},
        {"IT": ["C1"], "DE": ["C2"], "FR": ["C2", "C3"], "Global": []},
        {"IT": ["HH"], "DE": ["HH", "GOV"], "FR": ["HH"], "Global": []},
    )
    edges = {
        "S": [(0, 0, 10), (2, 1, 20), (3, 2, 30), (3, 3, 40)],
        "U": [(0, 2, 7), (0, 3, 5), (0, 0, 2), (1, 0, 3), (2, 2, 4), (3, 1, 6)],
        "Yc": [(0, 1, 11), (0, 3, 13), (0, 0, 1), (1, 3, 17), (3, 2, 19)],
    }
    for name, values in edges.items():
        source = database.matrices["baseline"][name]
        frame = pd.DataFrame(0.0, index=source.index, columns=source.columns)
        for row, column, value in values:
            frame.iloc[row, column] = value
        if request.param:
            frame = frame.astype(pd.SparseDtype(float, 0.0))
        database.matrices["baseline"][name] = frame
    return database


def reference(matrix, item, regions, *, supply=False):
    """Independent edge sum on the tiny test model."""
    items = None if item is None else {item} if isinstance(item, str) else set(item)
    result = pd.DataFrame(0.0, index=regions, columns=regions)
    for row, values in zip(matrix.index, matrix.to_numpy()):
        for column, value in zip(matrix.columns, values):
            source_item = column[-1] if supply else row[-1]
            if items is None or source_item in items:
                result.loc[row[0], column[0]] += value
    result.index.name = result.columns.name = MI["r"]
    return result


@pytest.mark.parametrize(
    "intermediate,final", [(True, True), (True, False), (False, True)]
)
def test_commodity_in_one_region_can_be_imported_by_other_regions(
    database, intermediate, final
):
    regions = database.get_index("Region")
    blocks = database.matrices["baseline"]
    expected = pd.DataFrame(0.0, index=regions, columns=regions)
    expected.index.name = expected.columns.name = MI["r"]
    if intermediate:
        expected += reference(blocks["U"], "C1", regions)
    if final:
        expected += reference(blocks["Yc"], "C1", regions)
    before = {name: frame.copy() for name, frame in blocks.items()}
    result = database.calc_trades("C1", intermediate=intermediate, final=final)
    pd.testing.assert_frame_equal(result, expected)
    assert result.loc["IT", "DE"] > 0
    assert result.loc["IT", "FR"] > 0
    assert not result.loc[["DE", "FR", "Global"]].to_numpy().any()
    assert not result.loc[:, "Global"].to_numpy().any()
    assert set(database.matrices["baseline"]) == set(before)
    for name, frame in before.items():
        pd.testing.assert_frame_equal(database.matrices["baseline"][name], frame)


def test_components_totals_multiple_items_and_all_items(database):
    blocks = database.matrices["baseline"]
    regions = database.get_index("Region")
    for item in ("C1", ["C1", "C3"], None):
        intermediate = reference(blocks["U"], item, regions)
        final = reference(blocks["Yc"], item, regions)
        pd.testing.assert_frame_equal(database.calc_trades(item), intermediate + final)
        pd.testing.assert_frame_equal(
            database.calc_trades(item, aggregate=False),
            pd.concat({"Intermediate": intermediate, "Final": final}, axis=1),
        )
    base = database.calc_trades("C1")
    totals = database.calc_trades("C1", total=True)
    np.testing.assert_allclose(totals.loc["Total", "Total"], base.to_numpy().sum())
    pd.testing.assert_frame_equal(totals.iloc[:-1, :-1], base)


def test_invalid_items_and_heterogeneous_all_items_are_rejected(database):
    for item in ("missing", "IT", ["C1", "missing"], []):
        with pytest.raises(WrongInput):
            database.calc_trades(item)
    database.units["Commodity"].loc["C2", "unit"] = "MJ"
    with pytest.raises(WrongInput, match="heterogeneous units"):
        database.calc_trades()
    assert database.calc_trades("C1").loc["IT", "DE"] == 18


@pytest.mark.parametrize("direction", ["origin", "destination", "both"])
def test_region_clustering_sums_trade_results_without_changing_the_database(
    database, direction
):
    base = database.calc_trades("C1")
    result = database.calc_trades(
        "C1",
        clusters={"World": database.get_index("Region")},
        clusters_direction=direction,
    )
    np.testing.assert_allclose(result.to_numpy().sum(), base.to_numpy().sum())
    assert result.index.tolist() == (
        ["World"] if direction != "destination" else base.index.tolist()
    )
    assert result.columns.tolist() == (
        ["World"] if direction != "origin" else base.columns.tolist()
    )
    assert database.get_index("Region") == ["IT", "DE", "FR", "Global"]


def test_multiple_and_renamed_scenarios_keep_their_own_flows(database):
    baseline = database.calc_trades("C1")
    database.clone_scenario("baseline", "policy")
    database.matrices["policy"]["U"] = database.matrices["policy"]["U"] * 2
    database.matrices["policy"]["Yc"] = database.matrices["policy"]["Yc"] * 3
    database.rename_baseline_scenario("reference")
    results = database.calc_trades("C1", scenario="all")
    pd.testing.assert_frame_equal(results["reference"], baseline)
    regions = database.get_index("Region")
    expected = reference(database.matrices["policy"]["U"], "C1", regions) + reference(
        database.matrices["policy"]["Yc"], "C1", regions
    )
    pd.testing.assert_frame_equal(results["policy"], expected)
    pd.testing.assert_frame_equal(
        database.calc_trades("C1", scenario="baseline"), baseline
    )


def test_ragged_chenery_supply_uses_actual_activity_to_commodity_pairs(database):
    source = database.matrices["baseline"]["S"]
    supply = pd.DataFrame(source.to_numpy(), index=source.index, columns=source.columns)
    supply.iloc[0, 1] = 9.0  # IT exports C2 without an IT-C2 commodity node.
    if isinstance(source.dtypes.iloc[0], pd.SparseDtype):
        supply = supply.astype(pd.SparseDtype(float, 0))
    database.matrices["baseline"]["S"] = supply
    assert database.is_chenerymoses()
    result = database.calc_trades("C2")
    expected = reference(supply, "C2", database.get_index("Region"), supply=True)
    pd.testing.assert_frame_equal(result, expected)
    assert result.loc["IT", "DE"] == 9
    with pytest.raises(NotImplementable, match="Chenery-Moses"):
        database.calc_trades("C2", aggregate=False)


def test_sparse_trades_do_not_convert_transaction_blocks_to_dense(monkeypatch):
    database = regional_database(
        {"IT": ["A"], "DE": ["B"]},
        {"IT": ["C1"], "DE": ["C2"]},
    )
    for name, value in (("U", 7.0), ("Yc", 2.5)):
        source = database.matrices["baseline"][name]
        frame = pd.DataFrame(
            [[0.0, value], [0.0, 0.0]], index=source.index, columns=source.columns
        )
        database.matrices["baseline"][name] = frame.astype(pd.SparseDtype(float, 0))
    original = pd.DataFrame.to_numpy

    def guarded(frame, *args, **kwargs):
        if isinstance(frame.index, pd.MultiIndex) and any(
            isinstance(dtype, pd.SparseDtype) for dtype in frame.dtypes
        ):
            raise AssertionError("A transaction block was densified")
        return original(frame, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_numpy", guarded)

    def no_concat(*args, **kwargs):
        raise AssertionError("A unified SUT view was requested")

    monkeypatch.setattr("mario.compute.views.concat_sut_Z", no_concat)
    monkeypatch.setattr("mario.compute.views.concat_sut_z", no_concat)
    assert not database.is_chenerymoses()
    assert database.calc_trades("C1", total=True).loc["Total", "Total"] == 9.5
    assert not database.has_matrix("Z")
    assert not database.has_matrix("z")


def test_supply_format_detection_compares_region_labels_not_axis_positions(database):
    source = database.matrices["baseline"]["S"]
    database.matrices["baseline"]["S"] = source.iloc[:, ::-1]
    assert not database.is_chenerymoses()
    assert database.calc_trades("C1").loc["IT", "DE"] == 18


def test_sparse_and_dense_weighted_trade_helpers_preserve_selected_rows(database):
    source = database.matrices["baseline"]["U"]
    selected = source.index[source.index.get_level_values(-1) == "C1"]
    weights = pd.Series(2.5, index=selected)
    expected = reference(source, "C1", database.get_index("Region")) * 2.5
    result = database._aggregate_trade_matrix_by_region(
        source, ["C1"], row_weights=weights, regions=database.get_index("Region")
    )
    pd.testing.assert_frame_equal(result, expected)
    with pytest.raises(WrongInput, match="weights could not be aligned"):
        database._aggregate_trade_matrix_by_region(
            source, ["C1"], row_weights=weights.iloc[:0]
        )
