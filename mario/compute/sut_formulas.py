"""Pure SUT compute formulas for MARIO 2."""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd

from mario.compute.helpers import (
    as_dense_series,
    as_column_frame,
    identity_like,
    inverse_vector,
    matmul,
    matvec,
    require_same_columns,
    require_same_index,
    safe_inverse,
    safe_solve,
    scale_columns,
    scale_rows,
    sum_final_demand,
    sum_columns,
    sum_rows,
    transpose_matvec,
    validate_square,
)
from mario.compute.runtime import choose_linear_strategy, effective_compute_options
from mario.log_exc.exceptions import NotImplementable
from mario.log_exc.logger import log_time
from mario.model.assumptions import (
    INDUSTRY_BASED_TECH,
    PRODUCT_BASED_TECH,
    normalize_tech_assumption,
)
from mario.model.labels import ITEM_LABEL, PRICE_INDEX_LABEL, PRODUCTION_LABEL

logger = logging.getLogger(__name__)


def _vector_series(vector: pd.DataFrame | pd.Series, *, label: str) -> pd.Series:
    """Coerce a split production block into a plain ``Series``."""
    if isinstance(vector, pd.Series):
        return vector.copy()

    if isinstance(vector, pd.DataFrame):
        if vector.shape[1] != 1:
            raise ValueError(f"{label} must be a single-column block.")
        return vector.iloc[:, 0].copy()

    raise TypeError(f"{label} must be a pandas Series or single-column DataFrame.")


def _production_frame(vector: pd.Series) -> pd.DataFrame:
    """Wrap a production vector using the canonical SUT production column label."""
    frame = as_column_frame(vector, PRODUCTION_LABEL)
    frame.columns = pd.Index([PRODUCTION_LABEL], name=ITEM_LABEL)
    return frame


def _resolver_linear_cache(resolver) -> dict | None:
    """Return the per-resolver linear solver cache when available."""
    if resolver is None:
        return None
    cache = getattr(resolver, "_linear_solver_cache", None)
    if cache is None:
        cache = {}
        resolver._linear_solver_cache = cache
    return cache


def _effective_sut_tech_assumption(*, tech_assumption=None, resolver=None) -> str:
    """Return the effective SUT technology assumption for one formula call."""
    if tech_assumption is None and resolver is not None:
        tech_assumption = getattr(resolver.dataset, "tech_assumption", None)
    return normalize_tech_assumption(tech_assumption) or INDUSTRY_BASED_TECH


def _require_product_based(assumption: str, matrix_name: str) -> None:
    """Raise a clear error when a PT-only SUT matrix is requested under IT."""
    if assumption != PRODUCT_BASED_TECH:
        raise NotImplementable(
            f"{matrix_name} is only defined for SUT databases using "
            "the product-based technology assumption."
        )


def _safe_inverse_swapped_axes(matrix: pd.DataFrame) -> pd.DataFrame:
    """Invert a square dataframe and swap row/column labels on the result."""
    if not isinstance(matrix, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame.")
    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Expected a square matrix.")
    values = matrix.to_numpy(dtype=float)
    try:
        inverse = np.linalg.inv(values)
    except np.linalg.LinAlgError:
        inverse = np.linalg.pinv(values)
    return pd.DataFrame(inverse, index=matrix.columns, columns=matrix.index)


def _solve_sut_system(
    product: pd.DataFrame,
    rhs: pd.DataFrame | pd.Series,
    *,
    transpose: bool = False,
    context=None,
    resolver=None,
) -> pd.DataFrame | pd.Series:
    """Solve one SUT linear system without materializing the full inverse block."""
    validate_square(product)
    options = effective_compute_options(context)
    if options.linear_solver == "scipy":
        from scipy import sparse
        from scipy.sparse.linalg import LinearOperator, factorized, lgmres, lsmr

        if all(isinstance(dtype, pd.SparseDtype) for dtype in product.dtypes):
            system = product.sparse.to_coo().tocsc()
        else:
            system = sparse.csc_matrix(product.to_numpy(dtype=float))

        lhs_sparse = sparse.identity(product.shape[0], format="csc") - (system.T if transpose else system)
        rhs_count = 1 if isinstance(rhs, pd.Series) else int(rhs.shape[1])
        linear_strategy = choose_linear_strategy(size=product.shape[0], rhs_count=rhs_count, context=context)
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
                "Compute: solving SUT linear system "
                f"(linear_solver={options.linear_solver}, linear_strategy={linear_strategy}, "
                f"requested_strategy={options.linear_strategy}, size={product.shape[0]}, rhs={rhs_count})."
            ),
            "debug",
        )
        cache = _resolver_linear_cache(resolver)
        cache_key = ("sut", id(product), bool(transpose), options.linear_solver)

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
                        "Sparse least-squares SUT solve did not converge to an acceptable solution."
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
                            "Compute: sparse direct SUT factorization failed; "
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
                            "Compute: sparse direct SUT factorization failed and iterative fallback is disabled; "
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
                            "Compute: iterative SUT linear solve did not converge cleanly; "
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
                                        "Compute: sparse direct SUT fallback also failed; "
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
                                "Compute: iterative SUT linear solve did not converge and direct fallback is disabled; "
                                "falling back to sparse least-squares solve."
                            ),
                            "warning",
                        )
                        return _solve_least_squares(vector)
                    raise RuntimeError(
                        "Iterative SUT linear solve did not converge and no fallback is enabled."
                    )
                return solved

            if rhs_array.ndim == 1:
                return _solve_one(rhs_array)
            return np.column_stack([_solve_one(rhs_array[:, idx]) for idx in range(rhs_array.shape[1])])

        rhs_values = rhs.to_numpy(dtype=float) if isinstance(rhs, (pd.DataFrame, pd.Series)) else np.asarray(rhs, dtype=float)
        solved = _solve_iterative(rhs_values) if linear_strategy == "iterative" else _solve_direct(rhs_values)

        if isinstance(rhs, pd.DataFrame):
            return pd.DataFrame(solved, index=product.index, columns=rhs.columns)
        if isinstance(rhs, pd.Series):
            return pd.Series(solved, index=product.index)

    lhs = identity_like(product) - product
    if transpose:
        lhs = lhs.T
    return safe_solve(
        lhs,
        rhs,
        solver=options.linear_solver,
        cache=_resolver_linear_cache(resolver),
        cache_key=("sut", id(product), bool(transpose), options.linear_solver),
    )


def build_sut_wcc_from_u_s(u: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    """Build the commodity-to-commodity Leontief quadrant ``wcc``."""
    require_same_columns(u, s.index, lhs_name="u", rhs_name="s.index")
    require_same_index(u, s.columns, lhs_name="u", rhs_name="s.columns")
    product = matmul(u, s)
    validate_square(product)
    return safe_inverse(identity_like(product) - product)


def build_sut_wca_from_u_s(u: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    """Build the commodity-to-activity quadrant ``wca`` from ``u`` and ``s``."""
    require_same_columns(u, s.index, lhs_name="u", rhs_name="s.index")
    return matmul(build_sut_wcc_from_u_s(u, s), u)


def build_sut_wac_from_s_u(s: pd.DataFrame, u: pd.DataFrame) -> pd.DataFrame:
    """Build the activity-to-commodity quadrant ``wac`` from ``s`` and ``u``."""
    require_same_columns(s, u.index, lhs_name="s", rhs_name="u.index")
    return matmul(build_sut_waa_from_s_u(s, u), s)


def build_sut_waa_from_s_u(s: pd.DataFrame, u: pd.DataFrame) -> pd.DataFrame:
    """Build the activity-to-activity Leontief quadrant ``waa``."""
    require_same_columns(s, u.index, lhs_name="s", rhs_name="u.index")
    require_same_index(s, u.columns, lhs_name="s", rhs_name="u.columns")
    product = matmul(s, u)
    validate_square(product)
    return safe_inverse(identity_like(product) - product)


def build_sut_bu_from_Xc_U(Xc: pd.DataFrame | pd.Series, U: pd.DataFrame) -> pd.DataFrame:
    """Build use-side direct-output coefficients ``bu``.

    This is algebraically equivalent to ``inv(diag(Xc)) @ U``.
    """
    x_c = _vector_series(Xc, label="Xc")
    require_same_index(U, x_c, lhs_name="U", rhs_name="Xc")
    return scale_rows(U, inverse_vector(x_c))


def build_sut_bs_from_Xa_S(Xa: pd.DataFrame | pd.Series, S: pd.DataFrame) -> pd.DataFrame:
    """Build supply-side direct-output coefficients ``bs``.

    This is algebraically equivalent to ``inv(diag(Xa)) @ S``.
    """
    x_a = _vector_series(Xa, label="Xa")
    require_same_index(S, x_a, lhs_name="S", rhs_name="Xa")
    return scale_rows(S, inverse_vector(x_a))


def build_sut_gcc_from_bu_bs(bu: pd.DataFrame, bs: pd.DataFrame) -> pd.DataFrame:
    """Build the commodity-to-commodity Ghosh quadrant ``gcc``."""
    require_same_columns(bu, bs.index, lhs_name="bu", rhs_name="bs.index")
    require_same_index(bu, bs.columns, lhs_name="bu", rhs_name="bs.columns")
    product = matmul(bu, bs)
    validate_square(product)
    return safe_inverse(identity_like(product) - product)


def build_sut_gca_from_gcc_bu(gcc: pd.DataFrame, bu: pd.DataFrame) -> pd.DataFrame:
    """Build the commodity-to-activity Ghosh quadrant ``gca``."""
    require_same_columns(gcc, bu.index, lhs_name="gcc", rhs_name="bu.index")
    return matmul(gcc, bu)


def build_sut_gaa_from_bs_bu(bs: pd.DataFrame, bu: pd.DataFrame) -> pd.DataFrame:
    """Build the activity-to-activity Ghosh quadrant ``gaa``."""
    require_same_columns(bs, bu.index, lhs_name="bs", rhs_name="bu.index")
    require_same_index(bs, bu.columns, lhs_name="bs", rhs_name="bu.columns")
    product = matmul(bs, bu)
    validate_square(product)
    return safe_inverse(identity_like(product) - product)


def build_sut_gac_from_gaa_bs(gaa: pd.DataFrame, bs: pd.DataFrame) -> pd.DataFrame:
    """Build the activity-to-commodity Ghosh quadrant ``gac``."""
    require_same_columns(gaa, bs.index, lhs_name="gaa", rhs_name="bs.index")
    return matmul(gaa, bs)


def build_sut_Xa_from_S_Ya(S: pd.DataFrame, Ya: pd.DataFrame) -> pd.DataFrame:
    """Build activity output from supply flows and activity final demand."""
    y_total = sum_final_demand(Ya)
    require_same_index(S, y_total, lhs_name="S", rhs_name="Ya_total")
    s_total = sum_rows(S)
    total = pd.Series(
        s_total.to_numpy(dtype=float) + y_total.to_numpy(dtype=float),
        index=S.index,
    )
    return _production_frame(total)


def build_sut_Xa_from_s_Xc(s: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Build activity output from supply coefficients and commodity output."""
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(s, x_c.index, lhs_name="s", rhs_name="Xc")
    total = matvec(s, x_c)
    return _production_frame(total)


def build_sut_Xc_from_U_Yc(U: pd.DataFrame, Yc: pd.DataFrame) -> pd.DataFrame:
    """Build commodity output from use flows and commodity final demand."""
    y_total = sum_final_demand(Yc)
    require_same_index(U, y_total, lhs_name="U", rhs_name="Yc_total")
    u_total = sum_rows(U)
    total = pd.Series(
        u_total.to_numpy(dtype=float) + y_total.to_numpy(dtype=float),
        index=U.index,
    )
    return _production_frame(total)


def build_sut_Xc_from_wcc_Yc(wcc: pd.DataFrame, Yc: pd.DataFrame) -> pd.DataFrame:
    """Build commodity output from the commodity Leontief block and final demand."""
    validate_square(wcc)
    y_total = sum_final_demand(Yc)
    require_same_index(wcc, y_total, lhs_name="wcc", rhs_name="Yc_total")
    total = matvec(wcc, y_total)
    return _production_frame(total)


def build_sut_Xc_from_u_s_Yc(
    u: pd.DataFrame,
    s: pd.DataFrame,
    Yc: pd.DataFrame,
    *,
    context=None,
    resolver=None,
) -> pd.DataFrame:
    """Build commodity output directly from coefficients and final demand.

    This solves the commodity-side SUT system ``(I - u @ s) Xc = Yc_total``
    instead of materializing ``wcc = (I - u @ s)^-1``.
    """
    require_same_columns(u, s.index, lhs_name="u", rhs_name="s.index")
    require_same_index(u, s.columns, lhs_name="u", rhs_name="s.columns")
    product = matmul(u, s)
    y_total = sum_final_demand(Yc)
    require_same_index(product, y_total, lhs_name="u@s", rhs_name="Yc_total")
    total = _solve_sut_system(product, y_total, context=context, resolver=resolver)
    return _production_frame(total)


def build_sut_U_from_u_Xa(u: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Build use flows from use coefficients and activity output.

    The implementation scales columns directly instead of materializing
    ``diag(Xa)``.
    """
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(u, x_a.index, lhs_name="u", rhs_name="Xa")
    return scale_columns(u, x_a)


def build_sut_u_from_U_Xa(U: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Build use coefficients from use flows and activity output.

    The implementation scales columns directly by ``1 / Xa`` instead of
    materializing ``diag(1 / Xa)``.
    """
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(U, x_a.index, lhs_name="U", rhs_name="Xa")
    return scale_columns(U, inverse_vector(x_a))


def build_sut_c_from_S_Xa(
    S: pd.DataFrame,
    Xa: pd.DataFrame | pd.Series,
    *,
    tech_assumption: str | None = None,
    resolver=None,
) -> pd.DataFrame:
    """Build product-based commodity technology coefficients from supply flows."""
    assumption = _effective_sut_tech_assumption(
        tech_assumption=tech_assumption,
        resolver=resolver,
    )
    _require_product_based(assumption, "c")
    x_a = _vector_series(Xa, label="Xa")
    require_same_index(S, x_a.index, lhs_name="S", rhs_name="Xa")
    return scale_columns(S.T, inverse_vector(x_a))


def build_sut_c_from_s(
    s: pd.DataFrame,
    *,
    tech_assumption: str | None = None,
    resolver=None,
) -> pd.DataFrame:
    """Build product-based commodity technology coefficients from ``s``."""
    assumption = _effective_sut_tech_assumption(
        tech_assumption=tech_assumption,
        resolver=resolver,
    )
    _require_product_based(assumption, "c")
    return _safe_inverse_swapped_axes(s)


def build_sut_s_from_c(
    c: pd.DataFrame,
    *,
    tech_assumption: str | None = None,
    resolver=None,
) -> pd.DataFrame:
    """Build supply coefficients from product-based commodity technology coefficients."""
    assumption = _effective_sut_tech_assumption(
        tech_assumption=tech_assumption,
        resolver=resolver,
    )
    _require_product_based(assumption, "s")
    return _safe_inverse_swapped_axes(c)


def build_sut_S_from_c_Xa(
    c: pd.DataFrame,
    Xa: pd.DataFrame | pd.Series,
    *,
    tech_assumption: str | None = None,
    resolver=None,
) -> pd.DataFrame:
    """Build supply flows from product-based commodity technology coefficients."""
    assumption = _effective_sut_tech_assumption(
        tech_assumption=tech_assumption,
        resolver=resolver,
    )
    _require_product_based(assumption, "S")
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(c, x_a.index, lhs_name="c", rhs_name="Xa")
    return scale_columns(c, x_a).T


def build_sut_S_from_s_Xc(
    s: pd.DataFrame,
    Xc: pd.DataFrame | pd.Series,
    Xa: pd.DataFrame | pd.Series | None = None,
    *,
    tech_assumption: str | None = None,
    resolver=None,
) -> pd.DataFrame:
    """Build supply flows from coefficients and output.

    Under the industry-based assumption this uses the historical ``S = s @ diag(Xc)``
    definition. Under the product-based assumption it reconstructs ``c = s^-1``
    and then uses ``S = transpose(c @ diag(Xa))``.

    The implementation scales columns directly instead of materializing
    dense diagonal matrices.
    """
    assumption = _effective_sut_tech_assumption(
        tech_assumption=tech_assumption,
        resolver=resolver,
    )
    if assumption == PRODUCT_BASED_TECH:
        if Xa is None:
            if resolver is not None:
                Xa = resolver.resolve("Xa")
            else:
                raise ValueError("Xa is required to build S under product-based technology assumption.")
        return build_sut_S_from_c_Xa(
            build_sut_c_from_s(s, tech_assumption=assumption),
            Xa,
            tech_assumption=assumption,
        )

    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(s, x_c.index, lhs_name="s", rhs_name="Xc")
    return scale_columns(s, x_c)


def build_sut_s_from_S_Xc(
    S: pd.DataFrame,
    Xc: pd.DataFrame | pd.Series,
    Xa: pd.DataFrame | pd.Series | None = None,
    *,
    tech_assumption: str | None = None,
    resolver=None,
) -> pd.DataFrame:
    """Build supply coefficients from supply flows and output.

    Under the industry-based assumption this uses the historical
    ``s = S @ minverse(diag(Xc))`` definition. Under the product-based
    assumption it first builds ``c = transpose(S) @ minverse(diag(Xa))`` and
    then returns ``s = c^-1``.

    The implementation scales columns directly by ``1 / Xc`` instead of
    dense diagonal matrices.
    """
    assumption = _effective_sut_tech_assumption(
        tech_assumption=tech_assumption,
        resolver=resolver,
    )
    if assumption == PRODUCT_BASED_TECH:
        if Xa is None:
            if resolver is not None:
                Xa = resolver.resolve("Xa")
            else:
                raise ValueError("Xa is required to build s under product-based technology assumption.")
        return build_sut_s_from_c(
            build_sut_c_from_S_Xa(S, Xa, tech_assumption=assumption),
            tech_assumption=assumption,
        )

    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(S, x_c.index, lhs_name="S", rhs_name="Xc")
    return scale_columns(S, inverse_vector(x_c))


def build_sut_Va_from_va_Xa(va: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Build activity-side value-added flows from coefficients and output.

    The implementation scales columns directly instead of materializing
    ``diag(Xa)``.
    """
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(va, x_a.index, lhs_name="va", rhs_name="Xa")
    return scale_columns(va, x_a)


def build_sut_Vc_from_vc_Xc(vc: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Build commodity-side value-added flows from coefficients and output.

    The implementation scales columns directly instead of materializing
    ``diag(Xc)``.
    """
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(vc, x_c.index, lhs_name="vc", rhs_name="Xc")
    return scale_columns(vc, x_c)


def build_sut_va_from_Va_Xa(Va: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Build activity-side value-added coefficients from flows and output.

    The implementation scales columns directly by ``1 / Xa`` instead of
    materializing ``diag(1 / Xa)``.
    """
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(Va, x_a.index, lhs_name="Va", rhs_name="Xa")
    return scale_columns(Va, inverse_vector(x_a))


def build_sut_vc_from_Vc_Xc(Vc: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Build commodity-side value-added coefficients from flows and output.

    The implementation scales columns directly by ``1 / Xc`` instead of
    materializing ``diag(1 / Xc)``.
    """
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(Vc, x_c.index, lhs_name="Vc", rhs_name="Xc")
    return scale_columns(Vc, inverse_vector(x_c))


def build_sut_Ea_from_ea_Xa(ea: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Build activity-side extension flows from coefficients and output.

    The implementation scales columns directly instead of materializing
    ``diag(Xa)``.
    """
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(ea, x_a.index, lhs_name="ea", rhs_name="Xa")
    return scale_columns(ea, x_a)


def build_sut_Ec_from_ec_Xc(ec: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Build commodity-side extension flows from coefficients and output.

    The implementation scales columns directly instead of materializing
    ``diag(Xc)``.
    """
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(ec, x_c.index, lhs_name="ec", rhs_name="Xc")
    return scale_columns(ec, x_c)


def build_sut_ea_from_Ea_Xa(Ea: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Build activity-side extension coefficients from flows and output.

    The implementation scales columns directly by ``1 / Xa`` instead of
    materializing ``diag(1 / Xa)``.
    """
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(Ea, x_a.index, lhs_name="Ea", rhs_name="Xa")
    return scale_columns(Ea, inverse_vector(x_a))


def build_sut_ec_from_Ec_Xc(Ec: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Build commodity-side extension coefficients from flows and output.

    The implementation scales columns directly by ``1 / Xc`` instead of
    materializing ``diag(1 / Xc)``.
    """
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(Ec, x_c.index, lhs_name="Ec", rhs_name="Xc")
    return scale_columns(Ec, inverse_vector(x_c))


def build_sut_Mc_from_mc_Yc(mc: pd.DataFrame, Yc: pd.DataFrame) -> pd.DataFrame:
    """Build commodity-side value-added footprints from multipliers and demand.

    The implementation scales columns directly by final-demand totals instead
    of materializing ``diag(Yc_total)``.
    """
    y_total = sum_final_demand(Yc)
    require_same_columns(mc, y_total.index, lhs_name="mc", rhs_name="Yc_total")
    return scale_columns(mc, y_total)


def build_sut_Ma_from_ma_Ya(ma: pd.DataFrame, Ya: pd.DataFrame) -> pd.DataFrame:
    """Build activity-side value-added footprints from multipliers and demand.

    The implementation scales columns directly by final-demand totals instead
    of materializing ``diag(Ya_total)``.
    """
    y_total = sum_final_demand(Ya)
    require_same_columns(ma, y_total.index, lhs_name="ma", rhs_name="Ya_total")
    return scale_columns(ma, y_total)


def build_sut_ma_from_va_waa(va: pd.DataFrame, waa: pd.DataFrame) -> pd.DataFrame:
    """Build activity-side value-added multipliers from direct coefficients."""
    validate_square(waa)
    require_same_columns(va, waa.index, lhs_name="va", rhs_name="waa")
    return matmul(va, waa)


def build_sut_ma_from_va_s_u(
    va: pd.DataFrame,
    s: pd.DataFrame,
    u: pd.DataFrame,
    *,
    context=None,
    resolver=None,
) -> pd.DataFrame:
    """Build activity-side value-added multipliers without materializing ``waa``."""
    require_same_columns(s, u.index, lhs_name="s", rhs_name="u.index")
    require_same_index(s, u.columns, lhs_name="s", rhs_name="u.columns")
    require_same_columns(va, s.index, lhs_name="va", rhs_name="s.index")
    product = matmul(s, u)
    solved = _solve_sut_system(product, va.T, transpose=True, context=context, resolver=resolver)
    return solved.T


def build_sut_mc_from_va_s_wcc(va: pd.DataFrame, s: pd.DataFrame, wcc: pd.DataFrame) -> pd.DataFrame:
    """Build commodity-side value-added multipliers from activity-side inputs."""
    validate_square(wcc)
    require_same_columns(va, s.index, lhs_name="va", rhs_name="s.index")
    require_same_columns(s, wcc.index, lhs_name="s", rhs_name="wcc")
    return matmul(matmul(va, s), wcc)


def build_sut_mc_from_va_s_u(
    va: pd.DataFrame,
    s: pd.DataFrame,
    u: pd.DataFrame,
    *,
    context=None,
    resolver=None,
) -> pd.DataFrame:
    """Build commodity-side value-added multipliers without materializing ``wcc``."""
    require_same_columns(va, s.index, lhs_name="va", rhs_name="s.index")
    require_same_columns(u, s.index, lhs_name="u", rhs_name="s.index")
    require_same_index(u, s.columns, lhs_name="u", rhs_name="s.columns")
    product = matmul(u, s)
    direct = matmul(va, s)
    solved = _solve_sut_system(product, direct.T, transpose=True, context=context, resolver=resolver)
    return solved.T


def build_sut_Fc_from_fc_Yc(fc: pd.DataFrame, Yc: pd.DataFrame) -> pd.DataFrame:
    """Build commodity-side satellite footprints from multipliers and demand.

    The implementation scales columns directly by final-demand totals instead
    of materializing ``diag(Yc_total)``.
    """
    y_total = sum_final_demand(Yc)
    require_same_columns(fc, y_total.index, lhs_name="fc", rhs_name="Yc_total")
    return scale_columns(fc, y_total)


def build_sut_Fa_from_fa_Ya(fa: pd.DataFrame, Ya: pd.DataFrame) -> pd.DataFrame:
    """Build activity-side satellite footprints from multipliers and demand.

    The implementation scales columns directly by final-demand totals instead
    of materializing ``diag(Ya_total)``.
    """
    y_total = sum_final_demand(Ya)
    require_same_columns(fa, y_total.index, lhs_name="fa", rhs_name="Ya_total")
    return scale_columns(fa, y_total)


def build_sut_fa_from_ea_waa(ea: pd.DataFrame, waa: pd.DataFrame) -> pd.DataFrame:
    """Build activity-side satellite multipliers from direct coefficients."""
    validate_square(waa)
    require_same_columns(ea, waa.index, lhs_name="ea", rhs_name="waa")
    return matmul(ea, waa)


def build_sut_fa_from_ea_s_u(
    ea: pd.DataFrame,
    s: pd.DataFrame,
    u: pd.DataFrame,
    *,
    context=None,
    resolver=None,
) -> pd.DataFrame:
    """Build activity-side satellite multipliers without materializing ``waa``."""
    require_same_columns(s, u.index, lhs_name="s", rhs_name="u.index")
    require_same_index(s, u.columns, lhs_name="s", rhs_name="u.columns")
    require_same_columns(ea, s.index, lhs_name="ea", rhs_name="s.index")
    product = matmul(s, u)
    solved = _solve_sut_system(product, ea.T, transpose=True, context=context, resolver=resolver)
    return solved.T


def build_sut_fc_from_ea_s_wcc(ea: pd.DataFrame, s: pd.DataFrame, wcc: pd.DataFrame) -> pd.DataFrame:
    """Build commodity-side satellite multipliers from activity-side inputs."""
    validate_square(wcc)
    require_same_columns(ea, s.index, lhs_name="ea", rhs_name="s.index")
    require_same_columns(s, wcc.index, lhs_name="s", rhs_name="wcc")
    return matmul(matmul(ea, s), wcc)


def build_sut_fc_from_ea_s_u(
    ea: pd.DataFrame,
    s: pd.DataFrame,
    u: pd.DataFrame,
    *,
    context=None,
    resolver=None,
) -> pd.DataFrame:
    """Build commodity-side satellite multipliers without materializing ``wcc``."""
    require_same_columns(ea, s.index, lhs_name="ea", rhs_name="s.index")
    require_same_columns(u, s.index, lhs_name="u", rhs_name="s.index")
    require_same_index(u, s.columns, lhs_name="u", rhs_name="s.columns")
    product = matmul(u, s)
    direct = matmul(ea, s)
    solved = _solve_sut_system(product, direct.T, transpose=True, context=context, resolver=resolver)
    return solved.T


def build_sut_pc_from_vc(
    va: pd.DataFrame,
    vc: pd.DataFrame,
    wac: pd.DataFrame,
    wcc: pd.DataFrame,
) -> pd.DataFrame:
    """Build the commodity-side price index from split direct value-added blocks."""
    direct_a = sum_columns(va)
    direct_c = sum_columns(vc)
    require_same_index(wac, direct_a, lhs_name="wac", rhs_name="va.sum(0)")
    require_same_index(wcc, direct_c, lhs_name="wcc", rhs_name="vc.sum(0)")
    values = transpose_matvec(wac, direct_a) + transpose_matvec(wcc, direct_c)
    return as_column_frame(values, PRICE_INDEX_LABEL)


def build_sut_pc_from_v_s_u(
    va: pd.DataFrame,
    vc: pd.DataFrame,
    s: pd.DataFrame,
    u: pd.DataFrame,
    *,
    context=None,
    resolver=None,
) -> pd.DataFrame:
    """Build the commodity-side price index without materializing ``wac`` or ``wcc``."""
    require_same_columns(va, s.index, lhs_name="va", rhs_name="s.index")
    require_same_columns(u, s.index, lhs_name="u", rhs_name="s.index")
    require_same_index(u, s.columns, lhs_name="u", rhs_name="s.columns")
    direct_a = sum_columns(va)
    direct_c = sum_columns(vc)
    rhs = transpose_matvec(s, direct_a) + direct_c
    product = matmul(u, s)
    values = _solve_sut_system(product, rhs, transpose=True, context=context, resolver=resolver)
    return as_column_frame(values, PRICE_INDEX_LABEL)


def build_sut_pa_from_va(
    va: pd.DataFrame,
    vc: pd.DataFrame,
    waa: pd.DataFrame,
    wca: pd.DataFrame,
) -> pd.DataFrame:
    """Build the activity-side price index from split direct value-added blocks."""
    direct_a = sum_columns(va)
    direct_c = sum_columns(vc)
    require_same_index(waa, direct_a, lhs_name="waa", rhs_name="va.sum(0)")
    require_same_index(wca, direct_c, lhs_name="wca", rhs_name="vc.sum(0)")
    values = transpose_matvec(waa, direct_a) + transpose_matvec(wca, direct_c)
    return as_column_frame(values, PRICE_INDEX_LABEL)


def build_sut_pa_from_v_s_u(
    va: pd.DataFrame,
    vc: pd.DataFrame,
    s: pd.DataFrame,
    u: pd.DataFrame,
    *,
    context=None,
    resolver=None,
) -> pd.DataFrame:
    """Build the activity-side price index without materializing ``waa`` or ``wca``."""
    require_same_columns(s, u.index, lhs_name="s", rhs_name="u.index")
    require_same_index(s, u.columns, lhs_name="s", rhs_name="u.columns")
    require_same_columns(va, s.index, lhs_name="va", rhs_name="s.index")
    direct_a = sum_columns(va)
    direct_c = sum_columns(vc)
    rhs = direct_a + transpose_matvec(u, direct_c)
    product = matmul(s, u)
    values = _solve_sut_system(product, rhs, transpose=True, context=context, resolver=resolver)
    return as_column_frame(values, PRICE_INDEX_LABEL)
