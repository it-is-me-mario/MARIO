"""Optional native solvers for sparse demand-driven linear systems."""

from __future__ import annotations

import importlib
import logging
import warnings

import numpy as np
import pandas as pd
from scipy import sparse

from mario.compute.helpers import dense_values, require_same_index, validate_square
from mario.compute.sparse_diagnostics import (
    PartialResultWarning, component_details, dependent_positions,
    raise_singular_system, singular_components,
)
from mario.log_exc.logger import log_time

logger = logging.getLogger(__name__)


class _UmfpackFactorization:
    """Keep the native context and its matrix together for repeated solves."""

    def __init__(self, matrix, umfpack):
        self.matrix = matrix
        self.umfpack = umfpack
        self.context = umfpack.UmfpackContext("dl")
        # The int32 variant limits individual factor allocations to about 2 GB,
        # even on a 64-bit machine with enough RAM. Sparse input nnz does not
        # predict the size of its LU factors, so always use 64-bit indices.
        self.context.control[umfpack.UMFPACK_PRL] = 0
        self.context.control[umfpack.UMFPACK_ORDERING] = umfpack.UMFPACK_ORDERING_BEST
        self.context.symbolic(matrix)
        estimated_bytes = (
            self.context.info[umfpack.UMFPACK_PEAK_MEMORY_ESTIMATE]
            * self.context.info[umfpack.UMFPACK_SIZE_OF_UNIT]
        )
        log_time(
            logger,
            "Compute: UMFPACK symbolic analysis "
            f"(index_bits=64, ordering=best, estimated_peak_gib={estimated_bytes / 1024**3:.3f}).",
            "debug",
        )
        self.context.numeric(matrix)

    def solve(self, values):
        def solve_column(vector):
            return self.context.solve(self.umfpack.UMFPACK_A, self.matrix, vector)

        if values.ndim == 1:
            return solve_column(values)
        return np.column_stack([solve_column(values[:, i]) for i in range(values.shape[1])])


def factorize_umfpack(matrix):
    """Factor a CSC float64 matrix with 64-bit sparse indices."""
    matrix.indices = matrix.indices.astype(np.int64, copy=False)
    matrix.indptr = matrix.indptr.astype(np.int64, copy=False)
    return _UmfpackFactorization(matrix, load_umfpack())


def load_umfpack():
    """Load the optional UMFPACK wrapper, with actionable installation guidance."""
    try:
        return importlib.import_module("scikits.umfpack")
    except (ImportError, OSError) as exc:
        raise ImportError(
            "The 'umfpack' solver requires scikit-umfpack and SuiteSparse. "
            "Install them in the active Python environment with "
            "'conda install -c conda-forge scikit-umfpack', or install "
            "SuiteSparse first and then 'pip install mariopy[umfpack]'."
        ) from exc


class _PartialFactorization:
    """Factor only the equations independent of singular production blocks."""

    def __init__(self, system, index, components, factorize):
        self.components = component_details(index, components)
        self.affected = dependent_positions(system, np.concatenate(components))
        self.retained = np.setdiff1d(np.arange(system.shape[0]), self.affected)
        self.undefined_nodes = list(index.take(self.affected))
        self.system = system[self.retained, :][:, self.retained].tocsc()
        self.factorize = factorize
        self.factor = None

    def warn(self):
        warnings.warn(
            "Partial linear-system result: "
            f"{len(self.affected)} of {len(self.affected) + len(self.retained)} "
            "coefficients per right-hand side are NaN because they belong to, "
            "or depend on, singular production components. "
            f"Singular components: {self.components!r}. "
            "Only independent equations are solved; the full system may be "
            "inconsistent or have nonunique solutions. Source matrices are unchanged. "
            "Totals including undefined coefficients must propagate NaN "
            "(use skipna=False for pandas reductions).",
            PartialResultWarning,
            stacklevel=3,
        )

    def solve(self, values):
        self.warn()
        solved = np.full(values.shape, np.nan, dtype=float)
        if len(self.retained):
            if self.factor is None:
                self.factor = self.factorize(self.system)
            rhs = values[self.retained]
            result = np.asarray(self.factor.solve(rhs), dtype=float)
            _check_residual(self.system, result, rhs)
            solved[self.retained] = result
        return solved


def coefficient_system(coefficients, *, transpose=False):
    """Build a sparse float64 ``I - A`` with explicit 64-bit indices."""
    if all(isinstance(dtype, pd.SparseDtype) for dtype in coefficients.dtypes):
        product = coefficients.sparse.to_coo().tocsc().astype(np.float64, copy=False)
    else:
        product = sparse.csc_matrix(dense_values(coefficients), dtype=np.float64)
    system = sparse.eye(product.shape[0], format="csc") - (
        product.T if transpose else product
    )
    system = system.tocsc()
    system.sum_duplicates()
    system.eliminate_zeros()
    system.sort_indices()
    system.indices = system.indices.astype(np.int64, copy=False)
    system.indptr = system.indptr.astype(np.int64, copy=False)
    if not np.isfinite(system.data).all():
        raise np.linalg.LinAlgError("Linear-system coefficients must be finite.")
    return system


def require_nonsingular_coefficients(coefficients):
    """Reject a known singular inverse before allocating a dense identity."""
    system = coefficient_system(coefficients)
    components = singular_components(system)
    if components:
        raise_singular_system(coefficients.index, components)


def _check_residual(system, solved, rhs_values):
    residual_norm = np.linalg.norm(system @ solved - rhs_values, axis=0)
    rhs_norm = np.linalg.norm(rhs_values, axis=0)
    if not np.isfinite(solved).all() or np.any(residual_norm > 1e-8 * rhs_norm):
        raise np.linalg.LinAlgError(
            "The sparse solver did not solve the linear system to the requested relative residual (1e-8)."
        )


def solve_sparse_system(
    coefficients: pd.DataFrame,
    rhs: pd.DataFrame | pd.Series,
    *,
    solver="umfpack",
    transpose: bool = False,
    cache: dict | None = None,
    cache_key=None,
    singular_policy="raise",
) -> pd.DataFrame | pd.Series:
    """Solve a sparse system, optionally returning its independent coefficients.

    ``singular_policy='partial'`` conservatively marks singular components and
    all their dependent variables as NaN. The retained equations form a closed
    nonsingular subsystem; their original coefficients and RHS are unchanged.
    No complete solution or inverse of a singular system is claimed.
    """
    from mario.compute.runtime import normalize_singular_policy

    singular_policy = normalize_singular_policy(singular_policy)
    validate_square(coefficients)
    require_same_index(coefficients, rhs, lhs_name="coefficients", rhs_name="rhs")
    if isinstance(rhs, pd.DataFrame) and rhs.shape[1] == 0:
        return pd.DataFrame(index=coefficients.index, columns=rhs.columns, dtype=float)
    if solver == "umfpack":
        umfpack = load_umfpack()
        factorize = factorize_umfpack
        native_errors = (umfpack.UmfpackWarning, RuntimeError, ValueError)
    elif solver == "scipy":
        from scipy.sparse.linalg import splu
        factorize = splu
        native_errors = (RuntimeError, ValueError)
    else:
        raise ValueError(f"Unsupported sparse solver {solver!r}.")

    system = coefficient_system(coefficients, transpose=transpose)
    rhs_values = np.asarray(dense_values(rhs), dtype=np.float64)
    if not np.isfinite(rhs_values).all():
        raise np.linalg.LinAlgError("Linear-system right-hand sides must be finite.")
    rhs_count = 1 if rhs_values.ndim == 1 else rhs_values.shape[1]
    log_time(
        logger,
        "Compute: solving sparse linear system "
        f"(linear_solver={solver}, linear_strategy=direct, index_bits=64, "
        f"singular_policy={singular_policy}, size={system.shape[0]}, rhs={rhs_count}).",
        "debug",
    )
    # Keep the existing default cache keys; partial factors must never be reused
    # by a later strict solve against the same resolver.
    if singular_policy != "raise" and cache_key is not None:
        cache_key = (cache_key, singular_policy)
    try:
        with warnings.catch_warnings():
            if solver == "umfpack":
                warnings.simplefilter("error", umfpack.UmfpackWarning)
            factor = cache.get(cache_key) if cache is not None and cache_key is not None else None
            if factor is None:
                components = singular_components(system)
                if components:
                    if singular_policy == "raise":
                        raise_singular_system(coefficients.index, components)
                    factor = _PartialFactorization(system, coefficients.index, components, factorize)
                else:
                    factor = factorize(system)
                if cache is not None and cache_key is not None:
                    cache[cache_key] = factor
            solved = np.asarray(factor.solve(rhs_values), dtype=np.float64)
    except native_errors as exc:
        raise np.linalg.LinAlgError(
            f"{solver.upper()} could not solve the linear system of size {system.shape[0]}: {exc}"
        ) from exc

    if not isinstance(factor, _PartialFactorization):
        _check_residual(system, solved, rhs_values)
    if isinstance(rhs, pd.Series):
        result = pd.Series(solved, index=coefficients.index)
    else:
        result = pd.DataFrame(solved, index=coefficients.index, columns=rhs.columns)
    if isinstance(factor, _PartialFactorization):
        result.attrs["mario_partial"] = {
            "singular_components": factor.components,
            "undefined_nodes": factor.undefined_nodes,
        }
    return result


def solve_umfpack_system(coefficients, rhs, **kwargs):
    """Solve ``(I - coefficients) x = rhs`` with reusable 64-bit UMFPACK LU.

    Transposition and explicit partial singular results are supported by
    :func:`solve_sparse_system`. The default singular policy is ``'raise'``.
    """
    return solve_sparse_system(coefficients, rhs, solver="umfpack", **kwargs)
