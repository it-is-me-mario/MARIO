"""Optional native solvers for sparse demand-driven linear systems."""

from __future__ import annotations

import importlib
import logging
import warnings

import numpy as np
import pandas as pd
from scipy import sparse

from mario.compute.helpers import dense_values, require_same_index, validate_square
from mario.log_exc.logger import log_time

logger = logging.getLogger(__name__)


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


def solve_umfpack_system(
    coefficients: pd.DataFrame,
    rhs: pd.DataFrame | pd.Series,
    *,
    transpose: bool = False,
    cache: dict | None = None,
    cache_key=None,
) -> pd.DataFrame | pd.Series:
    """Solve ``(I - coefficients) x = rhs`` with sparse UMFPACK LU.

    The transposed system is used when ``transpose=True``. Inputs remain
    sparse, factors are reusable within a resolver, and calculations use
    float64. Singular systems and failed residual checks raise errors rather
    than falling back to a pseudo-inverse or another solver.
    """
    validate_square(coefficients)
    require_same_index(coefficients, rhs, lhs_name="coefficients", rhs_name="rhs")
    if isinstance(rhs, pd.DataFrame) and rhs.shape[1] == 0:
        return pd.DataFrame(index=coefficients.index, columns=rhs.columns, dtype=float)

    umfpack = load_umfpack()
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
    rhs_values = np.asarray(dense_values(rhs), dtype=np.float64)
    rhs_count = 1 if rhs_values.ndim == 1 else rhs_values.shape[1]
    log_time(
        logger,
        "Compute: solving sparse linear system "
        f"(linear_solver=umfpack, linear_strategy=direct, size={system.shape[0]}, rhs={rhs_count}).",
        "debug",
    )

    # UMFPACK can report singularity as a warning and return non-finite values.
    # Treat its numerical warnings as failures, preserving the original data.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", umfpack.UmfpackWarning)
            factor = cache.get(cache_key) if cache is not None and cache_key is not None else None
            if factor is None:
                factor = umfpack.splu(system)
                if cache is not None and cache_key is not None:
                    cache[cache_key] = factor
            solved = np.asarray(factor.solve(rhs_values), dtype=np.float64)
    except (umfpack.UmfpackWarning, RuntimeError, ValueError) as exc:
        raise np.linalg.LinAlgError(
            f"UMFPACK could not solve the linear system of size {system.shape[0]}: {exc}"
        ) from exc

    residual_norm = np.linalg.norm(system @ solved - rhs_values, axis=0)
    rhs_norm = np.linalg.norm(rhs_values, axis=0)
    if not np.isfinite(solved).all() or np.any(residual_norm > 1e-8 * rhs_norm):
        raise np.linalg.LinAlgError(
            "UMFPACK did not solve the linear system to the requested relative residual (1e-8)."
        )

    if isinstance(rhs, pd.Series):
        return pd.Series(solved, index=coefficients.index)
    return pd.DataFrame(solved, index=coefficients.index, columns=rhs.columns)
