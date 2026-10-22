"""Native SUT conversion preserves real nodes, final demand and both accounts."""

from copy import deepcopy
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.test.mario_test import load_test
from tests.api.test_regional_indexes import regional_database


def dense(frame):
    if all(isinstance(t, pd.SparseDtype) for t in frame.dtypes):
        return frame.sparse.to_dense()
    return frame.copy()


@pytest.fixture(params=[False, True], ids=["dense", "sparse"])
def database(request):
    db = regional_database(
        {"IT": ["A", "B"], "DE": ["D"], "Global": []},
        {"IT": ["X"], "DE": ["Y", "Z"], "Global": ["unused"]},
        {"IT": ["HH"], "DE": ["HH", "GOV"], "Global": []},
    )
    entries = {
        "S": [[12, 3, 0, 0], [4, 0, 6, 0], [0, 10, 5, 0]],
        "U": [[2, 3, 1], [1, 2, 4], [3, 0, 1], [0, 0, 0]],
        "Ya": [[2, 0, 1], [0, 2, 0], [1, 0, 0]],
        "Yc": [[9, 1, 0], [3, 0, 5], [0, 9, 2], [0, 0, 0]],
        "Ea": [[4, 7, 9]],
        "Ec": [[2, 3, 5, 0]],
        "Va": [[8, 1, 3]],
        "Vc": [[4, 2, 1, 0]],
        "EY": [[1, 2, 3]],
        "VY": [[5, 6, 7]],
    }
    for name, values in entries.items():
        like = db.matrices["baseline"].get(name, db.matrices["baseline"]["EY"])
        rows = db.matrices["baseline"]["Va"].index if name == "VY" else like.index
        value = pd.DataFrame(values, index=rows, columns=like.columns, dtype=float)
        if request.param:
            value = value.astype(pd.SparseDtype(float, 0.0))
        db.matrices["baseline"][name] = value
    return db


def scalar_reference(blocks, method):
    """Allocate each individual flow/account over the eliminated node's uses."""
    b = {k: dense(v).to_numpy() for k, v in blocks.items()}
    S, U, Ya, Yc = (b[k] for k in ("S", "U", "Ya", "Yc"))
    na, nc = S.shape
    output = (
        S.sum(axis=1) + Ya.sum(axis=1)
        if method == "B"
        else U.sum(axis=1) + Yc.sum(axis=1)
    )
    n = nc if method == "B" else na
    Z, Y = np.zeros((n, n)), (Yc if method == "B" else Ya).copy()
    E, V = (b[k].copy() for k in (("Ec", "Vc") if method == "B" else ("Ea", "Va")))
    EY, VY = b["EY"].copy(), b["VY"].copy()
    for eliminated, total in enumerate(output):
        if not total:
            continue
        outgoing = S[eliminated] if method == "B" else U[eliminated]
        final = Ya[eliminated] if method == "B" else Yc[eliminated]
        incoming = U[:, eliminated] if method == "B" else S[:, eliminated]
        for i, amount in enumerate(incoming):
            for j, flow in enumerate(outgoing):
                Z[i, j] += amount * flow / total
            for j, flow in enumerate(final):
                Y[i, j] += amount * flow / total
        for prefix, account, direct in (("E", E, EY), ("V", V, VY)):
            values = b[prefix + ("a" if method == "B" else "c")][:, eliminated]
            for row, amount in enumerate(values):
                for j, flow in enumerate(outgoing):
                    account[row, j] += amount * flow / total
                for j, flow in enumerate(final):
                    direct[row, j] += amount * flow / total
    return dict(Z=Z, Y=Y, E=E, V=V, EY=EY, VY=VY)


@pytest.mark.parametrize("method", ["B", "D"])
def test_regional_values_accounts_and_actual_nodes_match_scalar_reference(
    database, method
):
    source = {k: v.copy() for k, v in database.matrices["baseline"].items()}
    wanted = scalar_reference(source, method)
    converted = database.to_iot(method, inplace=False)
    assert converted.table_type == "IOT"
    assert converted.scenarios == ["baseline"]
    assert set(converted.matrices["baseline"]) == {"Z", "Y", "X", "E", "V", "EY", "VY"}
    for name, values in wanted.items():
        result = converted.query(name)
        np.testing.assert_allclose(dense(result).to_numpy(), values)
        assert all(isinstance(t, pd.SparseDtype) for t in result.dtypes) == all(
            isinstance(t, pd.SparseDtype) for t in source["S"].dtypes
        )
    source_axis = source["U"].index if method == "B" else source["S"].index
    expected_pairs = [(r, "Sector", code) for r, _, code in source_axis]
    assert converted.query("Z").index.tolist() == expected_pairs
    assert converted.query("Z").columns.tolist() == expected_pairs
    assert converted.query("Y").columns.equals(source["Yc"].columns)
    level = "Commodity" if method == "B" else "Activity"
    assert converted.get_index("Sector") == database.get_index(level)
    assert converted.get_index("Consumption category") == database.get_index(
        "Consumption category"
    )
    pd.testing.assert_frame_equal(converted.units["Sector"], database.units[level])
    for prefix in ("E", "V"):
        before = sum(dense(source[prefix + s]).sum(axis=1) for s in ("a", "c", "Y"))
        after = sum(dense(converted.query(prefix + s)).sum(axis=1) for s in ("", "Y"))
        np.testing.assert_allclose(before, after)
    production = (
        dense(source["U"]).sum(axis=1) + dense(source["Yc"]).sum(axis=1)
        if method == "B"
        else dense(source["S"]).sum(axis=1) + dense(source["Ya"]).sum(axis=1)
    )
    np.testing.assert_allclose(converted.query("X").iloc[:, 0], production)
    for name, frame in source.items():
        pd.testing.assert_frame_equal(database.matrices["baseline"][name], frame)


@pytest.mark.parametrize("method", ["A", "B", "C", "D"])
def test_uniform_legacy_values_and_dense_layout_are_preserved(method):
    db = load_test("SUT")
    S, U, X, Y, E, V = (db.query(k).to_numpy() for k in ("S", "U", "X", "Y", "E", "V"))
    # Legacy unified ordering is activities, then commodities.
    na = S.shape[0]
    g, q = X[:na, 0], X[na:, 0]
    Ea, Va, Yc = E[:, :na], V[:, :na], Y[na:]
    if method in ("A", "B"):
        T = np.linalg.inv(S.T) @ np.diag(q) if method == "A" else S / g[:, None]
        expected = {"Z": U @ T, "Y": Yc, "E": Ea @ T, "V": Va @ T}
    else:
        T = np.diag(g) @ np.linalg.inv(S.T) if method == "C" else S / q
        expected = {"Z": T @ U, "Y": T @ Yc, "E": Ea, "V": Va}
    converted = db.to_iot(method, inplace=False)
    for name, values in expected.items():
        np.testing.assert_allclose(
            converted.query(name).to_numpy(), values, rtol=1e-12, atol=1e-12
        )
        assert not any(
            isinstance(t, pd.SparseDtype) for t in converted.query(name).dtypes
        )


@pytest.mark.parametrize("method", ["B", "D"])
def test_elimination_preserves_final_demand_impacts_with_ya_and_commodity_accounts(
    database, method
):
    b = {k: dense(v).to_numpy() for k, v in database.matrices["baseline"].items()}
    S, U, Ya, Yc = (b[k] for k in ("S", "U", "Ya", "Yc"))
    g, q = S.sum(axis=1) + Ya.sum(axis=1), U.sum(axis=1) + Yc.sum(axis=1)
    iq = np.divide(1, q, out=np.zeros_like(q), where=q != 0)
    s, u = S * iq, U / g
    coefficients = np.block(
        [[np.zeros((len(g), len(g))), s], [u, np.zeros((len(q), len(q)))]]
    )
    required = np.linalg.solve(
        np.eye(len(g) + len(q)) - coefficients, np.vstack([Ya, Yc])
    )
    result = database.to_iot(method, inplace=False)
    out = {
        k: dense(result.query(k)).to_numpy()
        for k in ("Z", "Y", "X", "E", "V", "EY", "VY")
    }
    x = out["X"][:, 0]
    ix = np.divide(1, x, out=np.zeros_like(x), where=x != 0)
    productive = np.linalg.solve(np.eye(len(x)) - out["Z"] * ix, out["Y"])
    for prefix in ("E", "V"):
        expected = (
            np.hstack([b[prefix + "a"] / g, b[prefix + "c"] * iq]) @ required
            + b[prefix + "Y"]
        )
        actual = (out[prefix] * ix) @ productive + out[prefix + "Y"]
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize("method", ["A", "C"])
def test_inverse_methods_include_commodity_accounts_on_regional_square_supply(
    database, method
):
    # Remove the unused Global commodity: the remaining observed S is invertible.
    source = {k: dense(v) for k, v in database.matrices["baseline"].items()}
    for name in ("U", "Yc"):
        source[name] = source[name].iloc[:3, :]
    for name in ("S", "Ec", "Vc"):
        source[name] = source[name].iloc[:, :3]
    source["Ya"].iloc[:, :] = 0
    # Commodity supply/use totals agree; this is a source fixture, not a repair
    # performed by the conversion.
    source["Yc"].iloc[:, :] = 0
    source["Yc"].iloc[:, 0] = (
        source["S"].sum(axis=0).to_numpy() - source["U"].sum(axis=1).to_numpy()
    )
    database.matrices["baseline"] = source
    S, U, Yc = (source[k].to_numpy() for k in ("S", "U", "Yc"))
    g, q = S.sum(axis=1), U.sum(axis=1) + Yc.sum(axis=1)
    result = database.to_iot(method, inplace=False)
    if method == "A":
        T = np.linalg.inv(S.T) @ np.diag(q)
        expected_z, expected_y = U @ T, Yc
    else:
        T = np.diag(g) @ np.linalg.inv(S.T)
        expected_z, expected_y = T @ U, T @ Yc
    np.testing.assert_allclose(dense(result.query("Z")), expected_z, atol=1e-12)
    np.testing.assert_allclose(dense(result.query("Y")), expected_y, atol=1e-12)
    for prefix in ("E", "V"):
        a, c, y = (source[prefix + suffix].to_numpy() for suffix in ("a", "c", "Y"))
        expected = a @ T + c if method == "A" else a + (c / q) @ U
        expected_direct = y if method == "A" else y + (c / q) @ Yc
        np.testing.assert_allclose(dense(result.query(prefix)), expected, atol=1e-12)
        np.testing.assert_allclose(
            dense(result.query(prefix + "Y")), expected_direct, atol=1e-12
        )
        np.testing.assert_allclose(
            expected.sum(axis=1) + expected_direct.sum(axis=1),
            a.sum(axis=1) + c.sum(axis=1) + y.sum(axis=1),
        )


def test_fully_inactive_activity_is_allowed_by_b_without_a_pseudoinverse():
    db = regional_database({"IT": ["active", "inactive"]}, {"IT": ["X"]})
    for name, frame in list(db.matrices["baseline"].items()):
        value = frame.sparse.to_dense()
        if name == "S":
            value.iloc[0, 0] = 5
        elif name == "Yc":
            value.iloc[0, 0] = 5
        db.matrices["baseline"][name] = value
    with patch.object(np.linalg, "pinv", side_effect=AssertionError("pseudoinverse")):
        result = db.to_iot("B", inplace=False)
    np.testing.assert_allclose(result.query("Y"), [[5]])
    assert result.query("Z").shape == (1, 1)


@pytest.mark.parametrize("method", ["B", "D"])
def test_sparse_conversion_never_queries_unified_views_or_dense_inverse(
    database, method
):
    for name, frame in list(database.matrices["baseline"].items()):
        database.matrices["baseline"][name] = frame.astype(pd.SparseDtype(float, 0.0))
    query = database.query

    def native(matrices=None, *args, **kwargs):
        names = [matrices] if isinstance(matrices, str) else matrices
        assert not set(names) & {"Z", "Y", "X", "E", "V", "w", "u", "s"}
        return query(matrices, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected dense allocation or inverse")

    with patch.object(database, "query", side_effect=native), patch.object(
        pd.DataFrame, "to_numpy", side_effect=forbidden
    ), patch.object(np.linalg, "inv", side_effect=forbidden), patch.object(
        np.linalg, "pinv", side_effect=forbidden
    ), patch.object(
        np, "diagflat", side_effect=forbidden
    ):
        database.to_iot(method)
    assert database.table_type == "IOT"


@pytest.mark.parametrize("method", ["A", "C"])
def test_rectangular_supply_fails_before_large_queries(database, method):
    original = database.query

    def supply_only(matrices=None, *args, **kwargs):
        assert matrices == "S"
        return original(matrices, *args, **kwargs)

    with patch.object(database, "query", side_effect=supply_only):
        with pytest.raises(NotImplementable, match="square supply"):
            database.to_iot(method)
    assert database.table_type == "SUT"


@pytest.mark.parametrize("method", ["A", "C"])
def test_singular_supply_errors_without_pseudoinverse_or_mutation(method):
    db = load_test("SUT")
    db.reset_to_flows("baseline")
    S = db.query("S")
    S.iloc[:, :] = 0
    db.update_scenarios("baseline", S=S)
    source = {k: v.copy() for k, v in db.matrices["baseline"].items()}
    history = deepcopy(db.meta._history)
    with patch.object(np.linalg, "pinv", side_effect=AssertionError("pseudoinverse")):
        with pytest.raises(WrongInput, match="supply is singular"):
            db.to_iot(method)
    assert db.table_type == "SUT"
    assert db.meta._history == history
    for name, frame in source.items():
        pd.testing.assert_frame_equal(db.matrices["baseline"][name], frame)


@pytest.mark.parametrize("method", ["A", "C"])
def test_inverse_methods_refuse_nonzero_activity_final_demand(method):
    db = load_test("SUT")
    Ya = db.query("Ya")
    Ya.iloc[0, 0] = 1
    db.update_scenarios("baseline", Ya=Ya)
    with pytest.raises(NotImplementable, match="zero activity final demand"):
        db.to_iot(method)


@pytest.mark.parametrize("method", ["B", "D"])
def test_zero_net_output_with_nonzero_flows_names_nodes_and_preserves_input(
    database, method
):
    source = {k: dense(v) for k, v in database.matrices["baseline"].items()}
    if method == "B":
        source["S"].iloc[0, :] = 0
        source["Ya"].iloc[0, :] = 0
        node = "IT.*Activity.*A"
    else:
        source["U"].iloc[0, :] = 0
        source["Yc"].iloc[0, :] = 0
        source["Yc"].iloc[0, 0:2] = [3, -3]
        node = "IT.*Commodity.*X"
    database.matrices["baseline"] = source
    with pytest.raises(WrongInput, match=f"zero output.*Nodes:.*{node}"):
        database.to_iot(method)
    assert database.table_type == "SUT"
    for name, frame in source.items():
        pd.testing.assert_frame_equal(database.matrices["baseline"][name], frame)


@pytest.mark.parametrize("method", ["B", "D"])
def test_missing_direct_final_accounts_are_zero_not_unified_fallback(database, method):
    for name in ("EY", "VY"):
        database.matrices["baseline"].pop(name)
    result = database.to_iot(method, inplace=False)
    assert result.query("EY").columns.equals(database.query("Yc").columns)
    assert not {"E", "V", "Z", "Y"}.intersection(database.matrices["baseline"])


def test_renamed_baseline_and_other_scenarios_keep_existing_conversion_contract(
    database,
):
    database.clone_scenario("baseline", "policy")
    database.rename_baseline_scenario("reference")
    result = database.to_iot("D", inplace=False)
    assert result.scenarios == ["reference"]
    assert result.query("Z", scenarios="reference").shape == (3, 3)
    assert database.scenarios == ["reference", "policy"]


def test_nonfinite_flows_fail_without_changing_table(database):
    U = dense(database.query("U"))
    U.iloc[0, 0] = np.nan
    database.matrices["baseline"]["U"] = U
    with pytest.raises(WrongInput, match="finite flow"):
        database.to_iot("D")
    assert database.table_type == "SUT"


def test_fully_stored_sparse_accounts_can_have_nan_fill_metadata(database):
    for name in ("Ea", "Va", "EY", "VY"):
        database.matrices["baseline"][name] = dense(database.query(name)).astype(
            pd.SparseDtype(float, np.nan)
        )
    with patch.object(pd.DataFrame, "to_numpy", side_effect=AssertionError("dense")):
        # Make every other block sparse too, so no dense frame is read.
        for name, value in list(database.matrices["baseline"].items()):
            if not all(isinstance(t, pd.SparseDtype) for t in value.dtypes):
                database.matrices["baseline"][name] = value.astype(
                    pd.SparseDtype(float, 0.0)
                )
        database.to_iot("D")
    assert database.table_type == "IOT"


def test_missing_sparse_values_are_not_silently_zeroed(database):
    value = dense(database.query("Ea"))
    value.iloc[0, 0] = np.nan
    database.matrices["baseline"]["Ea"] = value.astype(pd.SparseDtype(float, np.nan))
    with pytest.raises(WrongInput, match="finite flows"):
        database.to_iot("D")
    assert database.table_type == "SUT"


@pytest.mark.parametrize("method", ["B", "D"])
def test_reordered_native_axes_align_by_labels(database, method):
    expected = database.to_iot(method, inplace=False)
    for name in ("U", "Ya", "Ea", "Ec", "Va", "Vc", "EY", "VY"):
        value = database.matrices["baseline"][name]
        database.matrices["baseline"][name] = value.iloc[::-1, ::-1]
    result = database.to_iot(method, inplace=False)
    for name in ("Z", "Y", "X", "E", "V", "EY", "VY"):
        pd.testing.assert_frame_equal(
            dense(result.query(name)), dense(expected.query(name))
        )


@pytest.mark.parametrize("method", ["A", "B", "C", "D"])
def test_sparse_square_supply_supports_all_four_methods_without_inverse(method):
    db = load_test("SUT")
    expected = db.to_iot(method, inplace=False)
    db.reset_to_flows("baseline")
    for name, frame in list(db.matrices["baseline"].items()):
        db.matrices["baseline"][name] = frame.astype(pd.SparseDtype(float, 0.0))
    with patch.object(np.linalg, "inv", side_effect=AssertionError("inverse")):
        result = db.to_iot(method, inplace=False)
    for name in ("Z", "Y", "E", "V", "EY", "VY", "X"):
        np.testing.assert_allclose(
            dense(result.query(name)),
            dense(expected.query(name)),
            rtol=1e-12,
            atol=1e-12,
        )
