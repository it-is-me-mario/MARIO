"""Projected content compared with independent small inverse calculations."""

import numpy as np
import pandas as pd
import pytest

from mario.test.mario_test import load_test
from mario.ops.trade_content import TradeContentProjection
from tests.api.test_direct_trade_breakdown import dense
from tests.api.test_trade_content_loading import regional_model, indicator_for


def reference(
    database,
    indicator,
    item,
    *,
    activity_side=False,
    upstream=False,
    intermediate=True,
    final=True
):
    """Apply an explicit tiny inverse to each physical flow edge."""
    factor = indicator == "total value added" or indicator in database.get_index(
        "Factor of production"
    )

    def row(name):
        frame = database.query(name)
        return (
            frame.sum(axis=0)
            if indicator == "total value added"
            else frame.loc[indicator]
        )

    if database.table_type == "IOT":
        z = database.query("z")
        weights = row("v" if factor else "e")
        contributors = weights.index
        total = np.diag(weights.to_numpy()) @ np.linalg.inv(
            np.eye(len(z)) - z.to_numpy()
        )
        direct = np.diag(weights.to_numpy())
        flows = ([database.query("Z")] if intermediate else []) + (
            [database.query("Y")] if final else []
        )
    else:
        u, s = database.query("u"), database.query("s")
        a, c = row("va" if factor else "ea"), row("vc" if factor else "ec")
        contributors = a.index.append(c.index)
        if activity_side:
            w = np.linalg.inv(np.eye(len(s)) - s.to_numpy() @ u.to_numpy())
            total = np.vstack(
                (np.diag(a.to_numpy()) @ w, np.diag(c.to_numpy()) @ u.to_numpy() @ w)
            )
            direct = np.vstack((np.diag(a.to_numpy()), np.zeros((len(c), len(a)))))
            flows = [database.query("S")]
        else:
            w = np.linalg.inv(np.eye(len(u)) - u.to_numpy() @ s.to_numpy())
            total = np.vstack(
                (np.diag(a.to_numpy()) @ s.to_numpy() @ w, np.diag(c.to_numpy()) @ w)
            )
            direct = np.vstack((np.zeros((len(a), len(c))), np.diag(c.to_numpy())))
            flows = ([database.query("U")] if intermediate else []) + (
                [database.query("Yc")] if final else []
            )
    weights = total - direct if upstream else total
    regions = database.get_index("Region")
    index = pd.MultiIndex.from_tuples(
        [(r, *node) for r in regions for node in contributors],
        names=["Region", *contributors.names],
    )
    values_out = np.zeros((len(index), len(regions)))
    for flow in flows:
        for i, (origin, values) in enumerate(zip(flow.index, flow.to_numpy())):
            for destination, value in zip(flow.columns, values):
                if item is None or (
                    destination[-1] if activity_side else origin[-1]
                ) in ([item] if isinstance(item, str) else item):
                    start = regions.index(origin[0]) * len(contributors)
                    values_out[
                        start : start + len(contributors), regions.index(destination[0])
                    ] += (weights[:, i] * value)
    result = pd.DataFrame(
        values_out, index=index, columns=pd.Index(regions, name="Region")
    )
    if upstream and database.table_type == "SUT":
        # Legacy total-minus-direct aligns contributor axes with an outer join.
        order = contributors.join(s.index if activity_side else u.index, how="outer")
        expected_index = pd.MultiIndex.from_tuples(
            [(r, *node) for r in regions for node in order], names=index.names
        )
        result = result.reindex(expected_index)
    return result


@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("method", ["total", "upstream"])
@pytest.mark.parametrize("kind", ["satellite", "factor", "total_va"])
@pytest.mark.parametrize("activity_side", [False, True])
def test_ragged_sut_matches_independent_inverse(sparse, method, kind, activity_side):
    database = regional_model(sparse)
    database._indeces["r"]["main"].append("Global")
    if activity_side:
        supply = database.query("S")
        values = supply.to_numpy(copy=True)
        values[0, 1] = 2.0
        supply = pd.DataFrame(values, index=supply.index, columns=supply.columns)
        database.matrices["baseline"]["S"] = (
            supply.astype(pd.SparseDtype(float, 0)) if sparse else supply
        )
    indicator = indicator_for(database, kind)
    expected = reference(
        database,
        indicator,
        ["C1", "C2"],
        activity_side=activity_side,
        upstream=method == "upstream",
    )
    result = database.calc_trades_content(
        indicator, item=["C1", "C2"], method=method, breakdown=True
    )
    pd.testing.assert_frame_equal(dense(result), expected)
    collapsed = database.calc_trades_content(
        indicator, item=["C1", "C2"], method=method
    )
    pd.testing.assert_frame_equal(
        dense(result.groupby(level=0, sort=False).sum()), collapsed
    )
    assert (
        result.index.droplevel(0).unique().equals(expected.index.droplevel(0).unique())
    )
    if sparse:
        assert all(
            isinstance(t, pd.SparseDtype) and t.fill_value == 0 for t in result.dtypes
        )


@pytest.mark.parametrize("method", ["total", "upstream"])
@pytest.mark.parametrize("kind", ["satellite", "factor", "total_va"])
def test_sparse_iot_matches_independent_inverse(method, kind):
    database = load_test("IOT")
    for name, frame in list(database.matrices["baseline"].items()):
        database.matrices["baseline"][name] = frame.astype(pd.SparseDtype(float, 0))
    indicator = indicator_for(database, kind)
    expected = reference(
        database, indicator, "Agriculture", upstream=method == "upstream"
    )
    result = database.calc_trades_content(
        indicator, item="Agriculture", method=method, breakdown=True
    )
    pd.testing.assert_frame_equal(dense(result), expected)


@pytest.mark.parametrize("direction", ["origin", "destination", "both"])
@pytest.mark.parametrize("method", ["total", "upstream"])
def test_clusters_and_split_components(direction, method):
    database = regional_model(True)
    expected = reference(database, "CO2", "C1", upstream=method == "upstream")
    if direction in {"origin", "both"}:
        expected.index = pd.MultiIndex.from_tuples(
            [("EU", *x[1:]) for x in expected.index], names=expected.index.names
        )
        expected = expected.groupby(
            level=list(range(expected.index.nlevels)), sort=False
        ).sum()
    if direction in {"destination", "both"}:
        expected = expected.T.groupby(np.array(["EU", "EU"]), sort=False).sum().T
        expected.columns.name = "Region"
    components = database.calc_trades_content(
        "CO2",
        item="C1",
        method=method,
        breakdown=True,
        aggregate=False,
        clusters={"EU": ["IT", "DE"]},
        clusters_direction=direction,
    )
    pd.testing.assert_frame_equal(
        dense(components["Intermediate"] + components["Final"]), expected
    )


@pytest.mark.parametrize("strategy", ["direct", "iterative"])
def test_projected_solver_without_cached_inverse(monkeypatch, strategy):
    import mario.ops.trade_content as module

    database = regional_model(True)
    expected = reference(database, "CO2", "C1")
    monkeypatch.setattr(module, "choose_linear_strategy", lambda **kw: strategy)

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "An inverse, diagonal or exploded multiplier was requested"
        )

    original = database.query

    def query(matrices=None, *args, **kwargs):
        names = [matrices] if isinstance(matrices, str) else list(matrices or [])
        assert not any(
            str(n).lower().startswith("w") or n in {"fc", "fa", "mc", "ma", "f", "m"}
            for n in names
        )
        return original(matrices, *args, **kwargs)

    monkeypatch.setattr(database, "query", query)
    monkeypatch.setattr(database, "_explode_trade_content_direct_row", forbidden)
    monkeypatch.setattr(database, "_resolve_trade_content_total_exploded", forbidden)
    monkeypatch.setattr(np.linalg, "inv", forbidden)
    monkeypatch.setattr(np, "diag", forbidden)
    result = database.calc_trades_content(
        "CO2", item="C1", method="total", breakdown=True
    )
    pd.testing.assert_frame_equal(dense(result), expected)
    assert not any(n.lower().startswith("w") for n in database.matrices["baseline"])


def test_renamed_baseline_and_scenarios():
    database = regional_model(True)
    database.clone_scenario("baseline", "policy")
    database.matrices["policy"]["Ea"] = database.matrices["policy"]["Ea"] * 2
    database.rename_baseline_scenario("reference")
    result = database.calc_trades_content(
        "CO2", item="C1", method="upstream", scenario="all", breakdown=True
    )
    for scenario in database.scenarios:
        simple = database.calc_trades_content(
            "CO2", item="C1", method="upstream", scenario=scenario
        )
        pd.testing.assert_frame_equal(
            dense(result[scenario].groupby(level=0, sort=False).sum()), simple
        )
    assert not dense(result["reference"]).equals(dense(result["policy"]))
    via_alias = database.calc_trades_content(
        "CO2", item="C1", method="upstream", scenario="baseline", breakdown=True
    )
    pd.testing.assert_frame_equal(via_alias, result["reference"])


@pytest.mark.parametrize("method", ["total", "upstream"])
def test_iterative_projection_never_densifies_sparse_blocks_or_forms_split_product(
    monkeypatch, method
):
    import mario.ops.trade_content as module
    from scipy import sparse

    database = regional_model(True)
    expected = reference(database, "CO2", "C1", upstream=method == "upstream")
    original_numpy = pd.DataFrame.to_numpy
    original_matmul = sparse.csr_matrix.__matmul__

    def no_dense(frame, *args, **kwargs):
        if isinstance(frame.index, pd.MultiIndex) and all(
            isinstance(t, pd.SparseDtype) for t in frame.dtypes
        ):
            raise AssertionError("A sparse flow or coefficient block was densified")
        return original_numpy(frame, *args, **kwargs)

    def no_product(left, right):
        if sparse.issparse(right):
            raise AssertionError("The split coefficient product was materialized")
        return original_matmul(left, right)

    monkeypatch.setattr(module, "choose_linear_strategy", lambda **kwargs: "iterative")
    monkeypatch.setattr(pd.DataFrame, "to_numpy", no_dense)
    monkeypatch.setattr(sparse.csr_matrix, "__matmul__", no_product)
    result = database.calc_trades_content(
        "CO2", item="C1", method=method, breakdown=True
    )
    pd.testing.assert_frame_equal(dense(result), expected)


def test_total_minus_direct_is_upstream_with_activity_and_commodity_contributors():
    database = regional_model(True)
    outputs = {
        method: dense(
            database.calc_trades_content(
                "CO2", item="C1", method=method, breakdown=True
            )
        )
        for method in ["total", "direct", "upstream"]
    }
    direct = outputs["direct"].reindex(outputs["total"].index, fill_value=0.0)
    pd.testing.assert_frame_equal(
        (outputs["total"] - direct).reindex(outputs["upstream"].index),
        outputs["upstream"],
    )
    assert set(outputs["total"].index.get_level_values(2)) == {"Activity", "Commodity"}
    assert outputs["total"].to_numpy().sum() > direct.to_numpy().sum() > 0


def test_zero_indicator_and_empty_final_demand_do_not_solve(monkeypatch):
    database = regional_model(True)
    for name in ["Ea", "Ec"]:
        database.matrices["baseline"][name] = database.matrices["baseline"][name] * 0

    def no_solve(*args, **kwargs):
        raise AssertionError("Zero content triggered a solve")

    monkeypatch.setattr(TradeContentProjection, "_solve", no_solve)
    result = database.calc_trades_content(
        "CO2", item="C1", method="total", breakdown=True
    )
    assert result.sparse.to_coo().nnz == 0
    projection, _ = database._prepare_trade_content_projection(
        "CO2", scenario="baseline", use_activity_side=False
    )
    result = projection.aggregate(
        database.query("Yc").iloc[:, :0],
        method="total",
        breakdown=True,
        regions=database.get_index("Region"),
    )
    assert result.sparse.to_coo().nnz == 0


def test_singular_consistent_projection_and_failed_solve(monkeypatch):
    import mario.ops.trade_content as module
    from mario.log_exc.exceptions import WrongInput

    index = pd.MultiIndex.from_tuples(
        [("IT", "Sector", "a"), ("IT", "Sector", "b")],
        names=["Region", "Level", "Item"],
    )
    matrix = pd.DataFrame([[1.0, 0.0], [0.0, 0.2]], index=index, columns=index)
    monkeypatch.setattr(module, "choose_linear_strategy", lambda **kwargs: "iterative")
    projection = TradeContentProjection([pd.Series([1.0, 1.0], index=index)], matrix)
    np.testing.assert_allclose(
        projection._contribution(np.array([0.0, 1.0]), upstream=False), [0.0, 1.25]
    )
    with pytest.raises(WrongInput, match="did not converge"):
        projection._contribution(np.array([1.0, 0.0]), upstream=False)


def test_proportional_trade_vectors_share_a_solve_without_approximating(monkeypatch):
    database = regional_model(True)
    projection, _ = database._prepare_trade_content_projection(
        "CO2", scenario="baseline", use_activity_side=False
    )
    expected = reference(database, "CO2", "C1")
    original = projection._solve
    calls = []

    def counted(rhs):
        calls.append(rhs.copy())
        return original(rhs)

    monkeypatch.setattr(projection, "_solve", counted)
    actual = projection.aggregate(
        database.query("U"),
        "C1",
        method="total",
        breakdown=True,
        regions=database.get_index("Region"),
    )
    expected = reference(database, "CO2", "C1", final=False)
    pd.testing.assert_frame_equal(dense(actual), expected)
    assert (
        len(calls) == 1
    )  # One real origin node, two differently sized destination flows.
    # An additional commodity changes the RHS proportions; it must not reuse that solve.
    calls.clear()
    projection.aggregate(
        database.query("U"),
        ["C1", "C2"],
        method="total",
        breakdown=True,
        regions=database.get_index("Region"),
        region_aggregation=pd.DataFrame(
            {"Aggregation": ["EU", "EU"]}, index=["IT", "DE"]
        ),
        clusters_direction="origin",
    )
    assert len(calls) == 2
