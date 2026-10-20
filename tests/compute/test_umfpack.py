"""Numerical and integration checks for the optional UMFPACK backend."""

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest
from scipy import sparse

from mario.compute import linear_solvers
from mario.compute.linear_solvers import solve_umfpack_system
from mario.compute.resolver import resolve
from mario.compute.runtime import choose_linear_strategy, normalize_linear_solver
from mario.compute.types import ResolutionContext
from mario.log_exc.exceptions import WrongInput
from mario.settings.settings import Compute, set_linear_solver
from mario.test.mario_test import load_test


@pytest.fixture
def umfpack():
    return pytest.importorskip("scikits.umfpack")


def _system(sparse_backed=False):
    axis = pd.MultiIndex.from_tuples([("IT", "a"), ("GB", "b"), ("GB", "c")])
    values = np.array([[0.1, 0.2, 0.0], [0.0, 0.3, 0.1], [0.2, 0.0, 0.1]])
    if sparse_backed:
        return pd.DataFrame.sparse.from_spmatrix(sparse.csc_matrix(values), index=axis, columns=axis)
    return pd.DataFrame(values, index=axis, columns=axis)


@pytest.mark.parametrize("sparse_backed", [False, True])
@pytest.mark.parametrize("transpose", [False, True])
@pytest.mark.parametrize("rhs_columns", [None, 1, 3])
def test_umfpack_matches_dense_solve_and_preserves_axes(umfpack, sparse_backed, transpose, rhs_columns):
    coefficients = _system(sparse_backed)
    values = np.eye(3) - coefficients.to_numpy()
    if transpose:
        values = values.T
    if rhs_columns is None:
        rhs = pd.Series([2.0, 4.0, 1.0], index=coefficients.index)
        expected = pd.Series(np.linalg.solve(values, rhs.to_numpy()), index=rhs.index)
    else:
        rhs = pd.DataFrame(np.arange(3 * rhs_columns).reshape(3, rhs_columns), index=coefficients.index)
        rhs.columns = pd.Index([f"extension {i}" for i in range(rhs_columns)], name="Extension")
        expected = pd.DataFrame(np.linalg.solve(values, rhs.to_numpy()), index=rhs.index, columns=rhs.columns)

    result = solve_umfpack_system(coefficients, rhs, transpose=transpose)

    if rhs_columns is None:
        pdt.assert_series_equal(result, expected)
    else:
        pdt.assert_frame_equal(result, expected)


def test_umfpack_reuses_factorization_for_new_rhs(umfpack, monkeypatch):
    coefficients = _system(True)
    rhs = pd.Series([1.0, 2.0, 3.0], index=coefficients.index)
    original = linear_solvers.factorize_umfpack
    systems = []

    def factorize(system):
        systems.append(system)
        return original(system)

    monkeypatch.setattr(linear_solvers, "factorize_umfpack", factorize)
    cache = {}
    first = solve_umfpack_system(coefficients, rhs, cache=cache, cache_key=("system",))
    second = solve_umfpack_system(coefficients, rhs * 2, cache=cache, cache_key=("system",))

    assert len(systems) == 1
    assert systems[0].indices.dtype == np.int64
    assert systems[0].indptr.dtype == np.int64
    assert cache[("system",)].context.family == "dl"
    pdt.assert_series_equal(second, first * 2)


def test_umfpack_keeps_sparse_coefficients_sparse(umfpack, monkeypatch):
    coefficients = _system(True)
    rhs = pd.Series([1.0, 0.0, 0.0], index=coefficients.index)
    original = linear_solvers.dense_values

    def guarded_dense(block, **kwargs):
        assert block is not coefficients, "Sparse coefficient matrix was densified"
        return original(block, **kwargs)

    monkeypatch.setattr(linear_solvers, "dense_values", guarded_dense)
    result = solve_umfpack_system(coefficients, rhs)
    assert np.isfinite(result).all()


def test_umfpack_singular_system_raises_without_pseudoinverse(umfpack, monkeypatch):
    coefficients = pd.DataFrame.sparse.from_spmatrix(
        sparse.eye(3), index=_system().index, columns=_system().columns
    )
    rhs = pd.Series([1.0, 1.0, 1.0], index=coefficients.index)

    def forbidden(*args, **kwargs):
        raise AssertionError("A singular system must not use a pseudo-inverse")

    monkeypatch.setattr(np.linalg, "pinv", forbidden)
    with pytest.raises(np.linalg.LinAlgError, match="UMFPACK"):
        solve_umfpack_system(coefficients, rhs)


@pytest.mark.parametrize("zero_rhs", [False, True])
def test_umfpack_closed_cycle_reports_nodes_before_factorization(umfpack, monkeypatch, zero_rhs):
    axis = pd.MultiIndex.from_tuples([
        ("TW", "Commodity", "C_Beany"), ("TW", "Commodity", "M_Beany"),
    ])
    coefficients = pd.DataFrame([[0.0, 22.5], [1 / 22.5, 0.0]], index=axis, columns=axis)
    coefficients = coefficients.astype(pd.SparseDtype(float, 0))
    before = coefficients.copy()
    rhs = pd.Series(0.0 if zero_rhs else 1.0, index=axis)

    def forbidden(*args, **kwargs):
        raise AssertionError("A singular component must be rejected before native LU")

    monkeypatch.setattr(linear_solvers, "factorize_umfpack", forbidden)
    with pytest.raises(np.linalg.LinAlgError, match="singular") as error:
        solve_umfpack_system(coefficients, rhs)
    assert all(name in str(error.value) for name in ["TW", "C_Beany", "M_Beany"])
    pdt.assert_frame_equal(coefficients, before)


def test_umfpack_bad_solution_fails_residual_check(umfpack, monkeypatch):
    class IncorrectFactor:
        def solve(self, values):
            return np.zeros_like(values)

    monkeypatch.setattr(linear_solvers, "factorize_umfpack", lambda system: IncorrectFactor())
    coefficients = _system()
    with pytest.raises(np.linalg.LinAlgError, match="relative residual"):
        solve_umfpack_system(coefficients, pd.Series(1.0, index=coefficients.index))


@pytest.mark.parametrize("table,target", [
    ("IOT", "X"), ("IOT", "f"), ("IOT", "m"), ("IOT", "p"), ("IOT", "w"),
    ("SUT", "Xc"), ("SUT", "fa"), ("SUT", "fc"), ("SUT", "ma"), ("SUT", "mc"),
    ("SUT", "pa"), ("SUT", "pc"), ("SUT", "wcc"), ("SUT", "waa"),
])
def test_umfpack_iot_sut_targets_match_inverse(umfpack, table, target):
    expected = resolve(target, load_test(table), context=ResolutionContext(compute_method="inverse"))
    database = load_test(table)
    result = resolve(target, database, context=ResolutionContext(
        compute_method="solve", linear_solver="umfpack", linear_strategy="auto",
    ))
    pdt.assert_frame_equal(result, expected, rtol=1e-8, atol=1e-10)
    if target in {"f", "fc", "fa"}:
        assert not {"w", "wcc", "waa"}.intersection(database["baseline"])


@pytest.mark.parametrize("strategy", ["auto", "direct"])
def test_umfpack_selects_direct_even_for_large_systems(strategy):
    context = ResolutionContext(linear_solver="umfpack", linear_strategy=strategy)
    assert choose_linear_strategy(size=100_000, rhs_count=1, context=context) == "direct"


def test_umfpack_iterative_is_explicitly_rejected():
    with pytest.raises(WrongInput, match="UMFPACK is a direct solver"):
        choose_linear_strategy(size=3, rhs_count=1, context=ResolutionContext(
            linear_solver="umfpack", linear_strategy="iterative",
        ))


def test_umfpack_missing_dependency_has_installation_guidance(monkeypatch):
    def missing(name):
        raise ModuleNotFoundError("No module named 'scikits'")

    monkeypatch.setattr(linear_solvers.importlib, "import_module", missing)
    with pytest.raises(ImportError, match="conda install -c conda-forge scikit-umfpack"):
        linear_solvers.load_umfpack()


def test_selecting_unavailable_umfpack_does_not_change_settings(monkeypatch):
    before = Compute().linear_solver

    def missing():
        raise ImportError("scikit-umfpack is missing")

    monkeypatch.setattr(linear_solvers, "load_umfpack", missing)
    with pytest.raises(ImportError, match="scikit-umfpack is missing"):
        set_linear_solver("umfpack")
    assert Compute().linear_solver == before
    assert normalize_linear_solver(" UMFPACK ") == "umfpack"


def test_empty_extension_selection_does_not_load_umfpack(monkeypatch):
    coefficients = _system(True)

    def forbidden():
        raise AssertionError("No solver is needed for an empty RHS")

    monkeypatch.setattr(linear_solvers, "load_umfpack", forbidden)
    result = solve_umfpack_system(coefficients, pd.DataFrame(index=coefficients.index))
    assert result.shape == (3, 0)


def test_public_settings_and_dotted_sut_access(umfpack, monkeypatch, tmp_path):
    import mario

    monkeypatch.setenv("MARIO_CONFIG_DIR", str(tmp_path))
    mario.set_compute_method("solve")
    mario.set_linear_solver("umfpack")
    mario.set_linear_strategy("direct")
    database = load_test("SUT")
    database.keep_extensions(database.get_index("Satellite account")[:1])

    result = database.fc

    assert result.shape[0] == 1
    assert np.isfinite(result.to_numpy()).all()
    assert Compute().linear_solver == "umfpack"
    assert not {"w", "wcc", "waa"}.intersection(database["baseline"])


def test_umfpack_bonsai_parser_with_different_regional_classifications(umfpack, tmp_path):
    import mario
    from tests.parsers.test_bonsai_parser import _bundle

    path = _bundle(tmp_path / "Balanced")
    expected = resolve("fc", mario.parse_bonsai(path), context=ResolutionContext(compute_method="inverse"))
    database = mario.parse_bonsai(path)
    assert isinstance(database.get_index("Activity"), dict)
    assert isinstance(database.get_index("Commodity"), dict)
    extension = database.get_index("Satellite account")[0]
    database.keep_extensions(extension)

    result = resolve("fc", database, context=ResolutionContext(
        compute_method="solve", linear_solver="umfpack", linear_strategy="direct",
    ))

    pdt.assert_frame_equal(result, expected.loc[[extension]], rtol=1e-8, atol=1e-10)
    assert not {"w", "wcc", "waa"}.intersection(database["baseline"])
