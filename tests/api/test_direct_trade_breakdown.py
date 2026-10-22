"""Direct contributor breakdowns preserve labels and avoid square allocations."""

import numpy as np
import pandas as pd
import pytest

from mario.test.mario_test import load_test
from mario.ops.trades import direct_trade_breakdown
from tests.api.test_trade_content_loading import regional_model, indicator_for


def edge_reference(matrix, weights, item, regions, *, supply=False):
    items = None if item is None else set(item if isinstance(item, list) else [item])
    index = pd.MultiIndex.from_tuples(
        [(origin, *contributor) for origin in regions for contributor in weights.index],
        names=["Region", *weights.index.names],
    )
    expected = pd.DataFrame(0.0, index=index, columns=pd.Index(regions, name="Region"))
    for row, values in zip(matrix.index, matrix.to_numpy()):
        for column, value in zip(matrix.columns, values):
            code = column[-1] if supply else row[-1]
            if items is None or code in items:
                expected.loc[(row[0], *row), column[0]] += weights.loc[row] * value
    return expected


def dense(frame):
    return (
        frame.sparse.to_dense()
        if all(isinstance(t, pd.SparseDtype) for t in frame.dtypes)
        else frame
    )


@pytest.mark.parametrize("layout", ["IOT", "Isard", "Chenery"])
@pytest.mark.parametrize("kind", ["satellite", "factor", "total_va"])
def test_dense_uniform_output_keeps_all_legacy_rows_and_values(layout, kind):
    database = load_test("IOT" if layout == "IOT" else "SUT")
    if layout == "Chenery":
        database = database.to_chenery_moses(inplace=False)
    supply = layout == "Chenery"
    indicator = indicator_for(database, kind)
    weights, _ = database._resolve_trade_content_row(
        indicator, scenario="baseline", method="direct", use_activity_side=supply
    )
    item = "Agriculture" if layout == "IOT" else "Goods"
    names = ["S"] if supply else ["Z", "Y"] if layout == "IOT" else ["U", "Yc"]
    expected = sum(
        edge_reference(
            database.query(name),
            weights,
            item,
            database.get_index("Region"),
            supply=supply,
        )
        for name in names
    )
    result = database.calc_trades_content(
        indicator, item=item, method="direct", breakdown=True
    )
    pd.testing.assert_frame_equal(result, expected)
    assert result.index.names == ["Region", *weights.index.names]


@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize(
    "intermediate,final", [(True, True), (True, False), (False, True)]
)
@pytest.mark.parametrize("item", ["C1", ["C1", "C3"], None])
def test_ragged_breakdown_uses_real_nodes_and_sums_to_collapsed(
    sparse, intermediate, final, item
):
    database = regional_model(sparse)
    database._indeces["r"]["main"].append("Global")
    weights = database.query("ec").loc["CO2"]
    regions = database.get_index("Region")
    before = {
        name: frame.copy() for name, frame in database.matrices["baseline"].items()
    }
    names = (["U"] if intermediate else []) + (["Yc"] if final else [])
    expected = sum(
        edge_reference(database.query(name), weights, item, regions) for name in names
    )
    result = database.calc_trades_content(
        "CO2",
        item=item,
        method="direct",
        breakdown=True,
        intermediate=intermediate,
        final=final,
    )
    pd.testing.assert_frame_equal(dense(result), expected)
    collapsed = database.calc_trades_content(
        "CO2", item=item, method="direct", intermediate=intermediate, final=final
    )
    pd.testing.assert_frame_equal(
        dense(result.groupby(level=0, sort=False).sum()), collapsed
    )
    assert set(result.index.droplevel(0)) == set(weights.index)
    assert not dense(result.loc["Global"]).to_numpy().any()
    if sparse:
        assert all(
            isinstance(t, pd.SparseDtype) and t.fill_value == 0 for t in result.dtypes
        )
    for name, frame in before.items():
        pd.testing.assert_frame_equal(database.matrices["baseline"][name], frame)


@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("direction", ["origin", "destination", "both"])
def test_region_clusters_keep_original_contributor_labels(sparse, direction):
    database = regional_model(sparse)
    regions = database.get_index("Region")
    weights = database.query("ec").loc["CO2"]
    expected = sum(
        edge_reference(database.query(name), weights, "C1", regions)
        for name in ("U", "Yc")
    )
    if direction in {"origin", "both"}:
        expected.index = pd.MultiIndex.from_tuples(
            [("EU", *entry[1:]) for entry in expected.index], names=expected.index.names
        )
        expected = expected.groupby(
            level=list(range(expected.index.nlevels)), sort=False
        ).sum()
    if direction in {"destination", "both"}:
        expected = (
            expected.T.groupby(np.array(["EU"] * len(regions)), sort=False).sum().T
        )
        expected.columns.name = "Region"
    result = database.calc_trades_content(
        "CO2",
        item="C1",
        method="direct",
        breakdown=True,
        clusters={"EU": regions},
        clusters_direction=direction,
    )
    pd.testing.assert_frame_equal(dense(result), expected)
    assert set(result.index.droplevel(0)) == set(weights.index)


@pytest.mark.parametrize("sparse", [False, True])
def test_chenery_direct_contributors_are_activities(sparse):
    database = regional_model(sparse)
    source = database.query("S")
    supply = pd.DataFrame(source.to_numpy(), index=source.index, columns=source.columns)
    supply.iloc[0, 1] = 4.0
    if sparse:
        supply = supply.astype(pd.SparseDtype(float, 0))
    database.matrices["baseline"]["S"] = supply
    weights = database.query("ea").loc["CO2"]
    expected = edge_reference(
        supply, weights, "C2", database.get_index("Region"), supply=True
    )
    result = database.calc_trades_content(
        "CO2", item="C2", method="direct", breakdown=True
    )
    pd.testing.assert_frame_equal(dense(result), expected)
    assert result.loc[("IT", "IT", "Activity", "A1"), "DE"] > 0


@pytest.mark.parametrize("sparse", [False, True])
def test_components_and_multiple_scenarios(sparse):
    database = regional_model(sparse)
    database.clone_scenario("baseline", "policy")
    database.matrices["policy"]["Ec"] = database.matrices["policy"]["Ec"] * 2
    results = database.calc_trades_content(
        "CO2",
        item="C1",
        method="direct",
        breakdown=True,
        aggregate=False,
        scenario="all",
    )
    pd.testing.assert_frame_equal(
        dense(results["policy"]), dense(results["baseline"]) * 2
    )
    expected = database.calc_trades_content(
        "CO2", item="C1", method="direct", aggregate=False
    )
    pd.testing.assert_frame_equal(
        dense(results["baseline"].groupby(level=0, sort=False).sum()), expected
    )


def test_direct_path_never_builds_a_diagonal_or_densifies_sparse_flows(monkeypatch):
    database = regional_model(True)
    original = pd.DataFrame.to_numpy

    def no_square(*args, **kwargs):
        raise AssertionError("A direct contributor diagonal was constructed")

    def no_dense(frame, *args, **kwargs):
        if isinstance(frame.index, pd.MultiIndex) and all(
            isinstance(t, pd.SparseDtype) for t in frame.dtypes
        ):
            raise AssertionError("A sparse flow/breakdown was densified")
        return original(frame, *args, **kwargs)

    monkeypatch.setattr(database, "_explode_trade_content_direct_row", no_square)
    monkeypatch.setattr(np, "diag", no_square)
    monkeypatch.setattr(pd.DataFrame, "to_numpy", no_dense)
    result = database.calc_trades_content(
        "CO2", item="C1", method="direct", breakdown=True, clusters={"EU": ["IT", "DE"]}
    )
    assert all(isinstance(t, pd.SparseDtype) for t in result.dtypes)
    assert result.sparse.to_coo().data.sum() > 0
    assert not any(
        name.lower().startswith("w") or name in {"fc", "fa", "mc", "ma"}
        for name in database.matrices["baseline"]
    )


def test_reordered_coefficients_keep_their_contributor_order():
    database = regional_model(True)
    matrix = database.query("U")
    weights = database.query("ec").loc["CO2"].iloc[::-1]
    result = direct_trade_breakdown(
        matrix, weights, "C1", regions=database.get_index("Region")
    )
    expected = edge_reference(matrix, weights, "C1", database.get_index("Region"))
    pd.testing.assert_frame_equal(dense(result), expected)


def test_zero_direct_weights_keep_the_legacy_zero_rows():
    database = regional_model(True)
    source = database.query("Ec")
    database.matrices["baseline"]["Ec"] = source * 0
    result = database.calc_trades_content(
        "CO2", item="C1", method="direct", breakdown=True
    )
    assert len(result) == len(database.get_index("Region")) * len(source.columns)
    assert result.sparse.to_coo().nnz == 0


@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("kind", ["satellite", "factor", "total_va"])
def test_regional_indicator_kinds_preserve_signed_contributions(sparse, kind):
    database = regional_model(sparse)
    indicator = indicator_for(database, kind)
    flow = database.query("U").copy()
    # Negative transactions must retain their sign in the contributor result.
    signed = flow.to_numpy(copy=True)
    signed[0, -1] = -signed[0, -1]
    flow = pd.DataFrame(signed, index=flow.index, columns=flow.columns)
    if sparse:
        flow = flow.astype(pd.SparseDtype(float, 0))
    database.matrices["baseline"]["U"] = flow
    weights, _ = database._resolve_trade_content_row(
        indicator, scenario="baseline", method="direct", use_activity_side=False
    )
    expected = edge_reference(flow, weights, None, database.get_index("Region"))
    result = database.calc_trades_content(
        indicator, method="direct", breakdown=True, final=False
    )
    pd.testing.assert_frame_equal(dense(result), expected)
    assert (dense(result).to_numpy() < 0).any()


def test_empty_final_demand_keeps_sparse_zero_output():
    database = regional_model(True)
    flow = database.query("Yc").iloc[:, :0]
    weights = database.query("ec").loc["CO2"]
    result = direct_trade_breakdown(flow, weights, regions=database.get_index("Region"))
    assert result.shape == (len(weights) * 2, 2)
    assert all(isinstance(dtype, pd.SparseDtype) for dtype in result.dtypes)
    assert result.sparse.to_coo().nnz == 0
