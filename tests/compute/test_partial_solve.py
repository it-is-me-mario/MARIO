"""Partial solutions must certify independent equations and expose undefined ones."""

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest
from scipy import sparse

import mario
from mario.compute import linear_solvers
from mario.compute.helpers import (
    dense_values, matmul, matvec, transpose_matvec, sum_rows, sum_columns,
    sparse_frame_from_spmatrix, scale_columns,
)
from mario.compute.iot_formulas import _solve_iot_system, build_iot_w_from_z, build_iot_w_from_z_solve
from mario.compute.sut_formulas import _solve_sut_system, build_sut_wcc_from_u_s_solve
from mario.compute.runtime import effective_compute_options, choose_linear_strategy
from mario.compute.types import ComputeOptions, ResolutionContext
from mario.log_exc.exceptions import WrongInput, WrongFormat
from mario.ops.aggregation_engine import _aggregate_frame_values


def _problem(transpose=False):
    axis = pd.MultiIndex.from_tuples([(r, "Commodity", n) for r, n in [
        ("TW", "cycle a"), ("TW", "cycle b"), ("IT", "donor"),
        ("IT", "independent"), ("GB", "dependent"),
        ("GB", "dependent twice"), ("FR", "isolated"),
    ]])
    lhs = np.eye(7)
    lhs[0, 1] = lhs[1, 0] = -1
    lhs[0, 2] = -.2  # A donor does not itself depend on the singular cycle.
    lhs[4, 1] = -.5
    lhs[5, 4] = -.3  # Include indirect descendants.
    lhs[2, 3], lhs[3, 2] = -.2, -.3
    coefficients = np.eye(7) - (lhs.T if transpose else lhs)
    frame = pd.DataFrame.sparse.from_spmatrix(sparse.csc_matrix(coefficients), index=axis, columns=axis)
    rhs = pd.DataFrame(np.arange(14.).reshape(7, 2), index=axis, columns=["CO2", "water"])
    return frame, rhs, lhs


@pytest.mark.parametrize("solver", ["scipy", "umfpack"])
@pytest.mark.parametrize("transpose", [False, True])
@pytest.mark.parametrize("zero_rhs", [False, True])
def test_partial_retains_independent_equations_and_marks_all_descendants(solver, transpose, zero_rhs):
    if solver == "umfpack":
        pytest.importorskip("scikits.umfpack")
    coefficients, rhs, lhs = _problem(transpose)
    if zero_rhs:
        rhs *= 0
    before = coefficients.copy(deep=True)
    with pytest.warns(mario.PartialResultWarning, match="4 of 7") as recorded:
        result = linear_solvers.solve_sparse_system(
            coefficients, rhs, solver=solver, transpose=transpose, singular_policy="partial",
        )
    assert len(recorded) == 1
    assert all(label in str(recorded[0].message) for label in ["TW", "cycle a", "cycle b"])
    assert result.index.equals(rhs.index) and result.columns.equals(rhs.columns)
    assert result.iloc[[0, 1, 4, 5]].isna().all().all()
    keep = [2, 3, 6]
    expected = np.linalg.solve(lhs[np.ix_(keep, keep)], rhs.iloc[keep].to_numpy())
    np.testing.assert_allclose(result.iloc[keep], expected)
    np.testing.assert_allclose(lhs[np.ix_(keep, keep)] @ result.iloc[keep], rhs.iloc[keep], atol=1e-12)
    assert result.attrs["mario_partial"]["undefined_nodes"] == list(rhs.index.take([0, 1, 4, 5]))
    pdt.assert_frame_equal(coefficients, before)


@pytest.mark.parametrize("kind", ["IOT", "SUT"])
@pytest.mark.parametrize("solver", ["scipy", "umfpack"])
def test_runtime_partial_policy_and_default_error(kind, solver):
    if solver == "umfpack":
        pytest.importorskip("scikits.umfpack")
    coeff, rhs, _ = _problem()
    solve = _solve_iot_system if kind == "IOT" else _solve_sut_system
    with pytest.raises(np.linalg.LinAlgError, match="singular"):
        solve(coeff, rhs, context=ResolutionContext(linear_solver=solver))
    with pytest.warns(mario.PartialResultWarning):
        result = solve(coeff, rhs, context=ResolutionContext(
            linear_solver=solver, compute=ComputeOptions(singular_policy="partial"),
        ))
    assert result.iloc[2].notna().all()
    assert result.iloc[4].isna().all()


def test_partial_factor_reuse_keeps_warning_and_does_not_bypass_strict_policy(monkeypatch):
    pytest.importorskip("scikits.umfpack")
    coeff, rhs, _ = _problem()
    original = linear_solvers.factorize_umfpack
    matrices = []
    def factorize(matrix):
        matrices.append(matrix)
        return original(matrix)
    monkeypatch.setattr(linear_solvers, "factorize_umfpack", factorize)
    cache = {}
    with pytest.warns(mario.PartialResultWarning):
        first = linear_solvers.solve_umfpack_system(coeff, rhs, singular_policy="partial", cache=cache, cache_key="x")
    with pytest.warns(mario.PartialResultWarning):
        second = linear_solvers.solve_umfpack_system(coeff, rhs * 2, singular_policy="partial", cache=cache, cache_key="x")
    assert len(matrices) == 1
    assert matrices[0].shape == (3, 3)
    assert matrices[0].indices.dtype == np.int64
    pdt.assert_frame_equal(second, first * 2)
    with pytest.raises(np.linalg.LinAlgError, match="singular"):
        linear_solvers.solve_umfpack_system(coeff, rhs, cache=cache, cache_key="x")


def test_all_variables_undefined_and_series_rhs_need_no_factorization(monkeypatch):
    coeff = pd.DataFrame(np.eye(2))
    def forbidden(*args):
        pytest.fail("There is no retained system to factor")
    monkeypatch.setattr("scipy.sparse.linalg.splu", forbidden)
    with pytest.warns(mario.PartialResultWarning, match="2 of 2"):
        result = linear_solvers.solve_sparse_system(coeff, pd.Series([0., 1.]), solver="scipy", singular_policy="partial")
    assert isinstance(result, pd.Series) and result.isna().all()


@pytest.mark.parametrize("inverse", ["iot_inverse", "iot_solve", "sut_solve"])
def test_full_inverse_is_rejected_even_in_partial_mode_before_identity_allocation(monkeypatch, inverse):
    coeff, _, _ = _problem()
    def forbidden(*args):
        pytest.fail("A singular inverse must fail before dense identity allocation")
    monkeypatch.setattr("mario.compute.iot_formulas.identity_like", forbidden)
    monkeypatch.setattr("mario.compute.sut_formulas.identity_like", forbidden)
    context = ResolutionContext(singular_policy="partial", linear_solver="scipy")
    with pytest.raises(np.linalg.LinAlgError, match="full inverse does not exist"):
        if inverse == "iot_inverse":
            build_iot_w_from_z(coeff)
        elif inverse == "iot_solve":
            build_iot_w_from_z_solve(coeff, context=context)
        else:
            identity = pd.DataFrame.sparse.from_spmatrix(sparse.eye(len(coeff)), index=coeff.index, columns=coeff.columns)
            build_sut_wcc_from_u_s_solve(coeff, identity, context=context)


def test_public_setting_override_validation_and_iterative_rejection():
    original = mario.download_settings()
    try:
        mario.reset_settings()
        assert mario.Compute().singular_policy == "raise"
        mario.set_singular_policy(" PARTIAL ")
        assert effective_compute_options().singular_policy == "partial"
        strict = ResolutionContext(compute=ComputeOptions(singular_policy="raise"))
        assert effective_compute_options(strict).singular_policy == "raise"
        with pytest.raises(WrongInput):
            mario.set_singular_policy("pinv")
        with pytest.raises(WrongInput):
            effective_compute_options(ResolutionContext(compute=ComputeOptions(singular_policy="")))
        assert mario.Compute().singular_policy == "partial"
        invalid = mario.download_settings()
        invalid["compute"]["singular_policy"] = "pinv"
        with pytest.raises(WrongFormat):
            mario.upload_settings(invalid)
        with pytest.raises(WrongInput, match="requires linear_strategy"):
            choose_linear_strategy(size=10, rhs_count=1, context=ResolutionContext(linear_strategy="iterative"))
    finally:
        mario.upload_settings(original)


@pytest.mark.parametrize("sparse_left", [False, True])
@pytest.mark.parametrize("sparse_right", [False, True])
def test_products_and_reductions_propagate_only_actual_unknown_dependencies(sparse_left, sparse_right):
    left = pd.DataFrame([[2., np.nan, 3.], [4., 0., 5.]], index=["CO2", "water"])
    right = pd.DataFrame([[1., 0., 1.], [0., 2., 0.], [0., 0., np.nan]])
    if sparse_left:
        left = left.astype(pd.SparseDtype(float, 0))
    if sparse_right:
        right = right.astype(pd.SparseDtype(float, 0))
    result = matmul(left, right)
    np.testing.assert_allclose(dense_values(result), [[2., np.nan, np.nan], [4., 0., np.nan]], equal_nan=True)
    assert np.isnan(sum_rows(result)).all()
    assert sum_columns(result).iloc[0] == 6.
    assert sum_columns(result).iloc[1:].isna().all()
    vector = pd.Series([1., 0., 2.])
    np.testing.assert_allclose(matvec(left, vector), [8., 14.])
    transposed = transpose_matvec(right, vector)
    np.testing.assert_allclose(transposed, [1., 0., np.nan], equal_nan=True)
    scaled = scale_columns(left, pd.Series([1., 2., 3.]))
    assert np.isnan(dense_values(scaled)[0, 1])
    assert np.isnan(dense_values(left.iloc[0])[1])


@pytest.mark.parametrize("sparse_backed", [False, True])
def test_aggregation_does_not_turn_undefined_values_into_zero(sparse_backed):
    frame = pd.DataFrame([[1., np.nan, 3.], [2., 4., 5.]])
    if sparse_backed:
        frame = sparse_frame_from_spmatrix(sparse.csr_matrix(frame), index=frame.index, columns=frame.columns)
    result = _aggregate_frame_values(frame, pd.Index(["total", "total"]), pd.Index(["a", "a", "b"]))
    np.testing.assert_allclose(dense_values(result), [[np.nan, 8.]], equal_nan=True)


@pytest.mark.parametrize("per_call", [False, True])
def test_public_bonsai_fc_warns_and_footprints_and_custom_totals_preserve_nan(
    tmp_path, per_call, bonsai_without_umfpack,
):
    from mario.compute import sum_operator
    from tests.parsers.test_bonsai_parser import _bundle

    original = mario.download_settings()
    try:
        mario.reset_settings()
        mario.set_compute_method("solve")
        database = mario.parse_bonsai(_bundle(tmp_path / "Balanced"))
        mario.set_linear_solver("scipy")
        mario.set_singular_policy("raise")
        database.keep_extensions(database.get_index("Satellite account")[:1])
        u, s = database.resolve_many(["u", "s"]).values()
        u = pd.DataFrame(0., index=u.index, columns=u.columns)
        s = pd.DataFrame(0., index=s.index, columns=s.columns)
        u.iloc[0, 0] = s.iloc[0, 0] = 1.
        database.matrices["baseline"].update(u=u, s=s)
        if not per_call:
            mario.set_singular_policy("partial")
        with pytest.warns(mario.PartialResultWarning, match="1 of 3"):
            fc = (
                database.resolve("fc", compute_options=ComputeOptions(singular_policy="partial"))
                if per_call else database.fc
            )
        assert fc.iloc[:, 0].isna().all()
        assert fc.iloc[:, 1:].notna().all().all()
        assert database.Fc.iloc[:, 0].isna().all()
        database.register_operator(sum_operator(name="partial_total", source="Fc", over="columns", label="Total"))
        assert database.resolve("partial_total").isna().all().all()
        assert not {"w", "wcc", "waa"}.intersection(database["baseline"])
    finally:
        mario.upload_settings(original)


@pytest.mark.parametrize("solver", ["scipy", "umfpack"])
def test_nonsingular_partial_mode_is_a_normal_solution_without_warning(solver):
    import warnings

    if solver == "umfpack":
        pytest.importorskip("scikits.umfpack")
    coeff = pd.DataFrame([[.1, .2], [0., .3]])
    rhs = pd.Series([1., 2.])
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        result = linear_solvers.solve_sparse_system(coeff, rhs, solver=solver, singular_policy="partial")
    assert not recorded
    assert not result.attrs
    np.testing.assert_allclose(result, np.linalg.solve(np.eye(2) - coeff.to_numpy(), rhs))
