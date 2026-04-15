"""Pure IOT compute formulas for MARIO 2."""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd

from mario.compute.ghosh_formulas import build_iot_b_from_X_Z, build_iot_g_from_b
from mario.compute.helpers import (
    as_column_frame,
    identity_like,
    inverse_vector,
    require_same_columns,
    require_same_index,
    safe_inverse,
    safe_solve,
    scale_columns,
    sum_final_demand,
    sum_rows,
    validate_square,
)
from mario.compute.runtime import choose_linear_strategy, effective_compute_options
from mario.log_exc.logger import log_time
from mario.model.labels import PRICE_INDEX_LABEL, PRODUCTION_LABEL

logger = logging.getLogger(__name__)


def _resolver_linear_cache(resolver) -> dict | None:
    """Return the per-resolver linear solver cache when available."""
    if resolver is None:
        return None
    cache = getattr(resolver, "_linear_solver_cache", None)
    if cache is None:
        cache = {}
        resolver._linear_solver_cache = cache
    return cache


def _solve_iot_system(
    z: pd.DataFrame,
    rhs: pd.DataFrame | pd.Series,
    *,
    transpose: bool = False,
    context=None,
    resolver=None,
) -> pd.DataFrame | pd.Series:
    """Solve one IOT linear system without materializing the Leontief inverse.

    Depending on the active runtime options, this uses the configured linear
    solver backend and optionally reuses a per-resolver factorization cache.
    When ``transpose=True``, the system ``(I - z.T) x = rhs`` is solved
    instead, which is the form needed by multipliers and prices.
    """
    validate_square(z)
    options = effective_compute_options(context)
    if options.linear_solver == "scipy":
        from scipy import sparse
        from scipy.sparse.linalg import LinearOperator, factorized, lgmres, lsmr

        if all(isinstance(dtype, pd.SparseDtype) for dtype in z.dtypes):
            system = z.sparse.to_coo().tocsc()
        else:
            system = sparse.csc_matrix(z.to_numpy(dtype=float))

        lhs_sparse = sparse.identity(z.shape[0], format="csc") - (system.T if transpose else system)
        rhs_count = 1 if isinstance(rhs, pd.Series) else int(rhs.shape[1])
        linear_strategy = choose_linear_strategy(size=z.shape[0], rhs_count=rhs_count, context=context)
        diagonal = np.asarray(lhs_sparse.diagonal(), dtype=float)
        safe_diagonal = diagonal.copy()
        safe_diagonal[np.abs(safe_diagonal) < 1e-12] = 1.0
        preconditioner = LinearOperator(
            lhs_sparse.shape,
            matvec=lambda x: np.asarray(x, dtype=float) / safe_diagonal,
            rmatvec=lambda x: np.asarray(x, dtype=float) / safe_diagonal,
            dtype=float,
        )
        log_time(
            logger,
            (
                "Compute: solving IOT linear system "
                f"(linear_solver={options.linear_solver}, linear_strategy={linear_strategy}, "
                f"requested_strategy={options.linear_strategy}, size={z.shape[0]}, rhs={rhs_count})."
            ),
            "debug",
        )
        cache = _resolver_linear_cache(resolver)
        cache_key = ("iot", id(z), bool(transpose), options.linear_solver)

        def _get_factor():
            factor = cache.get(cache_key) if cache is not None else None
            if factor is None:
                factor = factorized(lhs_sparse)
                if cache is not None:
                    cache[cache_key] = factor
            return factor

        def _solve_least_squares(rhs_array):
            def _solve_one(vector):
                vector = np.asarray(vector, dtype=float)
                if not np.any(vector):
                    return np.zeros_like(vector)
                solved, istop, *_ = lsmr(
                    lhs_sparse,
                    vector,
                    atol=1e-8,
                    btol=1e-8,
                    maxiter=4000,
                )
                if istop not in {0, 1, 2}:
                    raise RuntimeError(
                        "Sparse least-squares IOT solve did not converge to an acceptable solution."
                    )
                return solved

            if rhs_array.ndim == 1:
                return _solve_one(rhs_array)
            return np.column_stack([_solve_one(rhs_array[:, idx]) for idx in range(rhs_array.shape[1])])

        def _solve_direct(
            rhs_array,
            *,
            allow_iterative_fallback: bool = True,
            allow_least_squares_fallback: bool = True,
        ):
            try:
                factor = _get_factor()
            except Exception as exc:
                if allow_iterative_fallback:
                    log_time(
                        logger,
                        (
                            "Compute: sparse direct IOT factorization failed; "
                            f"falling back to iterative solve ({exc})."
                        ),
                        "warning",
                    )
                    return _solve_iterative(
                        rhs_array,
                        allow_direct_fallback=False,
                        allow_least_squares_fallback=allow_least_squares_fallback,
                    )
                if allow_least_squares_fallback:
                    log_time(
                        logger,
                        (
                            "Compute: sparse direct IOT factorization failed and iterative fallback is disabled; "
                            f"falling back to sparse least-squares solve ({exc})."
                        ),
                        "warning",
                    )
                    return _solve_least_squares(rhs_array)
                raise
            if rhs_array.ndim == 1:
                return factor(rhs_array)
            return np.column_stack([factor(rhs_array[:, idx]) for idx in range(rhs_array.shape[1])])

        def _solve_iterative(
            rhs_array,
            *,
            allow_direct_fallback: bool = True,
            allow_least_squares_fallback: bool = True,
        ):
            def _solve_one(vector):
                solved, info = lgmres(
                    lhs_sparse,
                    vector,
                    M=preconditioner,
                    atol=0.0,
                    rtol=1e-8,
                    maxiter=500,
                )
                if info != 0:
                    log_time(
                        logger,
                        (
                            "Compute: iterative IOT linear solve did not converge cleanly; "
                            f"falling back to sparse direct factorization (info={info})."
                        ),
                        "warning",
                    )
                    if allow_direct_fallback:
                        try:
                            return _solve_direct(
                                vector,
                                allow_iterative_fallback=False,
                                allow_least_squares_fallback=allow_least_squares_fallback,
                            )
                        except Exception as exc:
                            if allow_least_squares_fallback:
                                log_time(
                                    logger,
                                    (
                                        "Compute: sparse direct IOT fallback also failed; "
                                        f"falling back to sparse least-squares solve ({exc})."
                                    ),
                                    "warning",
                                )
                                return _solve_least_squares(vector)
                            raise
                    if allow_least_squares_fallback:
                        log_time(
                            logger,
                            (
                                "Compute: iterative IOT linear solve did not converge and direct fallback is disabled; "
                                "falling back to sparse least-squares solve."
                            ),
                            "warning",
                        )
                        return _solve_least_squares(vector)
                    raise RuntimeError(
                        "Iterative IOT linear solve did not converge and no fallback is enabled."
                    )
                return solved

            if rhs_array.ndim == 1:
                return _solve_one(rhs_array)
            return np.column_stack([_solve_one(rhs_array[:, idx]) for idx in range(rhs_array.shape[1])])

        rhs_values = rhs.to_numpy(dtype=float) if isinstance(rhs, (pd.DataFrame, pd.Series)) else np.asarray(rhs, dtype=float)
        solved = _solve_iterative(rhs_values) if linear_strategy == "iterative" else _solve_direct(rhs_values)

        if isinstance(rhs, pd.DataFrame):
            return pd.DataFrame(solved, index=z.index, columns=rhs.columns)
        if isinstance(rhs, pd.Series):
            return pd.Series(solved, index=z.index)

    lhs = identity_like(z) - z
    if transpose:
        lhs = lhs.T
    return safe_solve(
        lhs,
        rhs,
        solver=options.linear_solver,
        cache=_resolver_linear_cache(resolver),
        cache_key=("iot", id(z), bool(transpose), options.linear_solver),
    )


def build_iot_Z_from_z_X(z: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    """Build inter-industry flows ``Z`` from coefficients ``z`` and production ``X``.

    The implementation scales columns directly instead of materializing
    ``diag(X)``.
    """
    validate_square(z)
    require_same_index(z, X, lhs_name="z", rhs_name="X")
    return scale_columns(z, X)


def build_iot_z_from_Z_X(Z: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    """Build technical coefficients ``z`` from flows ``Z`` and production ``X``.

    The implementation scales columns directly by ``1 / X`` instead of
    materializing ``diag(1 / X)``.
    """
    validate_square(Z)
    require_same_index(Z, X, lhs_name="Z", rhs_name="X")
    return scale_columns(Z, inverse_vector(X))


def build_iot_w_from_z(z: pd.DataFrame) -> pd.DataFrame:
    """Build the Leontief inverse ``w = (I - z)^-1``."""
    validate_square(z)
    return safe_inverse(identity_like(z) - z)


def build_iot_X_from_z_Y(
    z: pd.DataFrame,
    Y: pd.DataFrame,
    *,
    context=None,
    resolver=None,
) -> pd.DataFrame:
    """Build production totals from coefficients and final demand.

    This is the direct ``z + Y -> X`` path. Under the solve-based runtime mode
    it avoids materializing the explicit Leontief inverse ``w``.
    """
    validate_square(z)
    y_total = sum_final_demand(Y)
    require_same_index(z, y_total, lhs_name="z", rhs_name="Y_total")
    total = _solve_iot_system(z, y_total, context=context, resolver=resolver)
    return as_column_frame(total, PRODUCTION_LABEL)


def build_iot_X_from_Z_Y(Z: pd.DataFrame, Y: pd.DataFrame) -> pd.DataFrame:
    """Build production totals from flows ``Z`` and final demand ``Y``."""
    validate_square(Z)
    require_same_index(Z, Y, lhs_name="Z", rhs_name="Y")
    total = sum_rows(Z) + sum_final_demand(Y)
    return as_column_frame(total, PRODUCTION_LABEL)


def build_iot_X_from_w_Y(w: pd.DataFrame, Y: pd.DataFrame) -> pd.DataFrame:
    """Build production totals from the Leontief inverse and final demand."""
    validate_square(w)
    y_total = sum_final_demand(Y)
    require_same_index(w, y_total, lhs_name="w", rhs_name="Y_total")
    total = w.dot(y_total)
    return as_column_frame(total, PRODUCTION_LABEL)


def build_iot_V_from_v_X(v: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    """Build value-added flows from coefficients and production.

    The implementation scales columns directly instead of materializing
    ``diag(X)``.
    """
    require_same_columns(v, X.index, lhs_name="v", rhs_name="X")
    return scale_columns(v, X)


def build_iot_v_from_V_X(V: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    """Build value-added coefficients from flows and production.

    The implementation scales columns directly by ``1 / X`` instead of
    materializing ``diag(1 / X)``.
    """
    require_same_columns(V, X.index, lhs_name="V", rhs_name="X")
    return scale_columns(V, inverse_vector(X))


def build_iot_E_from_e_X(e: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    """Build extension flows from coefficients and production.

    The implementation scales columns directly instead of materializing
    ``diag(X)``.
    """
    require_same_columns(e, X.index, lhs_name="e", rhs_name="X")
    return scale_columns(e, X)


def build_iot_e_from_E_X(E: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    """Build extension coefficients from flows and production.

    The implementation scales columns directly by ``1 / X`` instead of
    materializing ``diag(1 / X)``.
    """
    require_same_columns(E, X.index, lhs_name="E", rhs_name="X")
    return scale_columns(E, inverse_vector(X))


def build_iot_m_from_v_w(v: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    """Build total value-added multipliers from direct coefficients and ``w``."""
    validate_square(w)
    require_same_columns(v, w.index, lhs_name="v", rhs_name="w")
    return v.dot(w)


def build_iot_m_from_v_z(
    v: pd.DataFrame,
    z: pd.DataFrame,
    *,
    context=None,
    resolver=None,
) -> pd.DataFrame:
    """Build total value-added multipliers directly from ``v`` and ``z``.

    This solves the transposed IOT system instead of first building the full
    Leontief inverse ``w``.
    """
    validate_square(z)
    require_same_columns(v, z.index, lhs_name="v", rhs_name="z")
    solved = _solve_iot_system(z, v.T, transpose=True, context=context, resolver=resolver)
    return solved.T


def build_iot_M_from_m_Y(m: pd.DataFrame, Y: pd.DataFrame) -> pd.DataFrame:
    """Build value-added footprints from multipliers and final demand.

    The implementation scales columns directly by final-demand totals instead
    of materializing ``diag(Y_total)``.
    """
    y_total = sum_final_demand(Y)
    require_same_columns(m, y_total.index, lhs_name="m", rhs_name="Y_total")
    return scale_columns(m, y_total)


def build_iot_f_from_e_w(e: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    """Build total satellite multipliers from direct coefficients and ``w``."""
    validate_square(w)
    require_same_columns(e, w.index, lhs_name="e", rhs_name="w")
    return e.dot(w)


def build_iot_f_from_e_z(
    e: pd.DataFrame,
    z: pd.DataFrame,
    *,
    context=None,
    resolver=None,
) -> pd.DataFrame:
    """Build total satellite multipliers directly from ``e`` and ``z``.

    This solves the transposed IOT system instead of first building the full
    Leontief inverse ``w``.
    """
    validate_square(z)
    require_same_columns(e, z.index, lhs_name="e", rhs_name="z")
    solved = _solve_iot_system(z, e.T, transpose=True, context=context, resolver=resolver)
    return solved.T


def build_iot_F_from_f_Y(f: pd.DataFrame, Y: pd.DataFrame) -> pd.DataFrame:
    """Build satellite footprints from multipliers and final demand.

    The implementation scales columns directly by final-demand totals instead
    of materializing ``diag(Y_total)``.
    """
    y_total = sum_final_demand(Y)
    require_same_columns(f, y_total.index, lhs_name="f", rhs_name="Y_total")
    return scale_columns(f, y_total)


def build_iot_p_from_v_w(v: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    """Build the price index from direct value-added coefficients and ``w``."""
    validate_square(w)
    require_same_columns(v, w.index, lhs_name="v", rhs_name="w")
    direct_value_added = v.sum(axis=0)
    values = w.T.dot(direct_value_added)
    return pd.DataFrame(values.to_numpy(dtype=float), index=w.columns, columns=[PRICE_INDEX_LABEL])


def build_iot_p_from_v_z(
    v: pd.DataFrame,
    z: pd.DataFrame,
    *,
    context=None,
    resolver=None,
) -> pd.DataFrame:
    """Build the price index directly from ``v`` and ``z``.

    This solves the transposed IOT system instead of first building the full
    Leontief inverse ``w``.
    """
    validate_square(z)
    require_same_columns(v, z.index, lhs_name="v", rhs_name="z")
    direct_value_added = v.sum(axis=0)
    values = _solve_iot_system(z, direct_value_added, transpose=True, context=context, resolver=resolver)
    return pd.DataFrame(values.to_numpy(dtype=float), index=z.columns, columns=[PRICE_INDEX_LABEL])
