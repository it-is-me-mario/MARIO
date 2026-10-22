"""Linkages retain dense semantics on sparse and regional classifications."""

import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from scipy.sparse.linalg import splu

import mario
from mario.ops.linkages import SparseLinkageSystem, selected_inverse_diagonal
from tests.api.test_trade_content_loading import regional_model


def reference(database, *, cut_diag, multi_mode, normalized):
    if database.table_type == "SUT":
        u, s, bu, bs = (database.query(name) for name in ["u", "s", "bu", "bs"])
        index = s.index.append(u.index)
        a = np.block(
            [
                [np.zeros((len(s), len(s))), s.to_numpy()],
                [u.to_numpy(), np.zeros((len(u), len(u)))],
            ]
        )
        b = np.block(
            [
                [np.zeros((len(s), len(s))), bs.to_numpy()],
                [bu.to_numpy(), np.zeros((len(u), len(u)))],
            ]
        )
    else:
        af, bf = database.query("z"), database.query("b")
        index = af.index
        a, b = af.to_numpy(), bf.to_numpy()
    w = np.linalg.inv(np.eye(len(a)) - a)
    g = np.linalg.inv(np.eye(len(b)) - b)
    a, b, w, g = (frame.copy() for frame in (a, b, w, g))
    if cut_diag:
        for frame in (a, b, w, g):
            np.fill_diagonal(frame, 0.0)
    oriented = [g, w.T, b, a.T]
    totals = np.column_stack([matrix.sum(axis=1) for matrix in oriented])
    names = ["Total Forward", "Total Backward", "Direct Forward", "Direct Backward"]
    if not multi_mode:
        result = pd.DataFrame(totals, index=index, columns=names)
        ratios = pd.DataFrame(
            {
                "Forward Amplification": result["Total Forward"]
                / result["Direct Forward"].where(result["Direct Forward"] != 0),
                "Backward Amplification": result["Total Backward"]
                / result["Direct Backward"].where(result["Direct Backward"] != 0),
            },
            index=index,
        )
        if normalized:
            result = result / result.mean()
        return pd.concat([result, ratios], axis=1)
    regions = index.get_level_values(0).to_numpy()
    local = np.array(
        [
            [matrix[i, regions == regions[i]].sum() for matrix in oriented]
            for i in range(len(index))
        ]
    )
    values = np.empty((len(index), 8))
    values[:, ::2] = local
    values[:, 1::2] = totals - local
    result = pd.DataFrame(
        values,
        index=index,
        columns=pd.MultiIndex.from_product([names, ["Local", "Foreign"]]),
    )
    for i, name in enumerate(names):
        denominator = pd.Series(totals[:, i], index=index).where(totals[:, i] != 0)
        result[name, "Local Share"] = result[name, "Local"] / denominator
        result[name, "Foreign Share"] = result[name, "Foreign"] / denominator
    return result


def model(layout, sparse_storage):
    db = regional_model(False) if layout == "ragged" else mario.load_test(layout)
    if sparse_storage:
        for name, frame in list(db.matrices["baseline"].items()):
            db.matrices["baseline"][name] = frame.astype(pd.SparseDtype(float, 0))
    return db


@pytest.mark.parametrize("layout", ["IOT", "SUT", "ragged"])
@pytest.mark.parametrize("sparse_storage", [False, True])
@pytest.mark.parametrize("multi_mode", [False, True])
@pytest.mark.parametrize("cut_diag", [False, True])
@pytest.mark.parametrize("normalized", [False, True])
def test_linkages_match_independent_inverse(
    layout, sparse_storage, multi_mode, cut_diag, normalized
):
    db = model(layout, sparse_storage)
    expected = reference(
        db, cut_diag=cut_diag, multi_mode=multi_mode, normalized=normalized
    )
    before = {name: frame.copy() for name, frame in db.matrices["baseline"].items()}
    actual = db.calc_linkages(
        multi_mode=multi_mode, cut_diag=cut_diag, normalized=normalized
    )
    pd.testing.assert_frame_equal(actual, expected, rtol=1e-7, atol=1e-10)
    for name, frame in before.items():
        pd.testing.assert_frame_equal(frame, db.matrices["baseline"][name])


@pytest.mark.parametrize("seed", range(8))
def test_selected_inverse_diagonal_matches_permuted_nonsymmetric_inverse(seed):
    rng = np.random.default_rng(seed)
    n = 35
    a = rng.random((n, n)) * (rng.random((n, n)) < 0.15) / n
    lhs = sparse.csc_matrix(np.eye(n) - a)
    factor = splu(
        lhs,
        permc_spec="MMD_AT_PLUS_A",
        diag_pivot_thresh=0.0,
        options={"SymmetricMode": True},
    )
    actual = selected_inverse_diagonal(factor, lhs)
    np.testing.assert_allclose(
        actual, np.linalg.inv(lhs.toarray()).diagonal(), rtol=1e-10, atol=1e-10
    )


@pytest.mark.parametrize("strategy", ["direct", "iterative"])
def test_sparse_path_requests_no_inverse_or_dense_unified_blocks(monkeypatch, strategy):
    import mario.ops.linkages as module

    db = regional_model(True)
    expected = reference(db, cut_diag=True, multi_mode=True, normalized=False)
    original_query = db.query
    original_numpy = pd.DataFrame.to_numpy

    def query(matrices=None, *args, **kwargs):
        names = [matrices] if isinstance(matrices, str) else list(matrices or [])
        assert not set(names).intersection(
            {"w", "g", "z", "Z", "b", "waa", "wcc", "gcc", "gaa", "gac", "gca"}
        )
        return original_query(matrices, *args, **kwargs)

    def numpy(frame, *args, **kwargs):
        if isinstance(frame.index, pd.MultiIndex) and all(
            isinstance(t, pd.SparseDtype) for t in frame.dtypes
        ):
            raise AssertionError("A sparse transaction/coefficient block was densified")
        return original_numpy(frame, *args, **kwargs)

    def no_inverse(*args, **kwargs):
        raise AssertionError("A full inverse was requested")

    monkeypatch.setattr(module, "choose_linear_strategy", lambda **kwargs: strategy)
    monkeypatch.setattr(db, "query", query)
    monkeypatch.setattr(pd.DataFrame, "to_numpy", numpy)
    monkeypatch.setattr(np.linalg, "inv", no_inverse)
    actual = db.calc_linkages(normalized=False)
    pd.testing.assert_frame_equal(actual, expected)
    assert not set(db.matrices["baseline"]).intersection(
        {"w", "g", "gcc", "gaa", "z", "Z"}
    )


def test_acyclic_graph_diagonal_needs_no_basis_solves(monkeypatch):
    system = SparseLinkageSystem(
        sparse.csr_matrix([[0.2, 0.1, 0], [0, 0, 0.4], [0, 0, 0.1]])
    )
    monkeypatch.setattr(
        system,
        "solve",
        lambda *args, **kwargs: pytest.fail("An acyclic diagonal requested a solve"),
    )
    np.testing.assert_allclose(system.diagonal(np.arange(3)), [1 / 0.8, 1, 1 / 0.9])


def test_renamed_baseline_preserves_sparse_linkages():
    db = regional_model(True)
    db.rename_baseline_scenario("reference")
    pd.testing.assert_frame_equal(
        db.calc_linkages(scenario="reference"), db.calc_linkages(scenario="baseline")
    )


@pytest.mark.parametrize("sparse_storage", [False, True])
@pytest.mark.parametrize("layout", ["IOT", "ragged"])
@pytest.mark.parametrize("cut_diag", [False, True])
def test_singular_system_reports_actual_nodes_without_changing_data(
    monkeypatch, sparse_storage, layout, cut_diag
):
    from mario.log_exc.exceptions import WrongInput

    db = model(layout, sparse_storage)
    if layout == "IOT":
        old = db.query("Z")
        block = pd.DataFrame(np.eye(len(old)), index=old.index, columns=old.columns)
        db.matrices["baseline"]["Z"] = (
            block.astype(pd.SparseDtype(float, 0)) if sparse_storage else block
        )
        db.matrices["baseline"]["Y"] = db.query("Y") * 0
        expected_node = old.index[0][-1]
    else:
        for name in ["S", "U"]:
            old = db.query(name)
            block = pd.DataFrame(np.eye(3), index=old.index, columns=old.columns)
            db.matrices["baseline"][name] = (
                block.astype(pd.SparseDtype(float, 0)) if sparse_storage else block
            )
        for name in ["Ya", "Yc"]:
            db.matrices["baseline"][name] = db.query(name) * 0
        expected_node = "A1"
    before = {name: frame.copy() for name, frame in db.matrices["baseline"].items()}
    original = db.query

    def query(matrices=None, *args, **kwargs):
        names = [matrices] if isinstance(matrices, str) else list(matrices or [])
        assert not set(names).intersection(
            {"w", "g", "waa", "wcc", "gcc", "gaa", "gac", "gca"}
        )
        return original(matrices, *args, **kwargs)

    monkeypatch.setattr(db, "query", query)
    monkeypatch.setattr(
        np.linalg,
        "pinv",
        lambda *args, **kwargs: pytest.fail("A pseudoinverse was substituted"),
    )
    with pytest.raises(WrongInput, match="Ghosh.*singular") as error:
        db.calc_linkages(cut_diag=cut_diag, normalized=False)
    assert expected_node in str(error.value)
    for name, frame in before.items():
        pd.testing.assert_frame_equal(frame, db.matrices["baseline"][name])


def test_generic_feedback_detection_retains_small_leaking_cycles():
    from mario.ops.linkages import check_linkage_system

    index = pd.MultiIndex.from_tuples(
        [("AA", "Sector", "x"), ("BB", "Sector", "y")],
        names=["Region", "Level", "Item"],
    )
    matrix = sparse.csr_matrix([[0.0, 1.0], [0.99, 0.0]])
    system = check_linkage_system(matrix, index, name="Ghosh")
    np.testing.assert_allclose(system.solve(np.ones(2)), [200.0, 199.0])


def test_large_singular_feedback_block_is_diagnosed_without_dense_rank_or_solve(
    monkeypatch,
):
    from mario.ops.linkages import check_linkage_system
    from mario.log_exc.exceptions import WrongInput
    import mario.ops.linkages as module

    n = 150
    cycle = sparse.csr_matrix(
        (np.ones(n), (np.arange(n), (np.arange(n) + 1) % n)), shape=(n, n)
    )
    index = pd.MultiIndex.from_tuples(
        [("Any region", "Sector", f"node-{i}") for i in range(n)],
        names=["Region", "Level", "Item"],
    )
    monkeypatch.setattr(
        np.linalg,
        "svd",
        lambda *args, **kwargs: pytest.fail(
            "A large dense rank calculation was attempted"
        ),
    )
    monkeypatch.setattr(
        module,
        "lgmres",
        lambda *args, **kwargs: pytest.fail("A singular system was sent to the solver"),
    )
    with pytest.raises(WrongInput, match="Ghosh.*singular") as error:
        check_linkage_system(cycle, index, name="Ghosh")
    assert "'count': 150" in str(error.value)


def test_pivoted_lu_diagonal_uses_streamed_solves():
    coefficients = sparse.csr_matrix([[1.0, -1.0], [-2.0, 1.0]])
    system = SparseLinkageSystem(coefficients)
    expected = np.linalg.inv(np.eye(2) - coefficients.toarray())
    np.testing.assert_allclose(system.solve(np.ones(2)), expected @ np.ones(2))
    assert selected_inverse_diagonal(system.factor, system.lhs) is None
    np.testing.assert_allclose(system.diagonal(np.arange(2)), expected.diagonal())


def test_existing_sparse_inverse_inputs_clear_diagonal_without_mutation():
    from mario.compute.primitives import linkages_calculation

    db = regional_model(False)
    index = db.query("S").index.append(db.query("U").index)
    frames = {
        name: pd.DataFrame(
            np.eye(len(index)) + 0.02, index=index, columns=index
        ).astype(pd.SparseDtype(float, 0))
        for name in ["w", "g", "z", "b"]
    }
    before = {name: frame.copy() for name, frame in frames.items()}
    actual = linkages_calculation(True, frames, False, False)
    assert len(actual) == len(index)
    np.testing.assert_allclose(actual["Total Forward"], (len(index) - 1) * 0.02)
    for name, frame in before.items():
        pd.testing.assert_frame_equal(frame, frames[name])
