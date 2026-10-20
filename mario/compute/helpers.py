"""Small pure helpers shared by compute formula modules."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _is_sparse_backed_dataframe(frame: pd.DataFrame) -> bool:
    """Return whether a dataframe stores every column as pandas sparse dtype."""
    return isinstance(frame, pd.DataFrame) and all(
        isinstance(dtype, pd.SparseDtype) for dtype in frame.dtypes
    )


def _is_sparse_backed_series(series: pd.Series) -> bool:
    """Return whether a series stores values with pandas sparse dtype."""
    return isinstance(series, pd.Series) and isinstance(series.dtype, pd.SparseDtype)


def dense_values(
    block: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...],
    *,
    copy: bool = False,
) -> np.ndarray:
    """Return numeric values, preserving explicit NaN and zero-filled sparse gaps."""
    if isinstance(block, pd.DataFrame):
        if _is_sparse_backed_dataframe(block):
            return block.sparse.to_coo().toarray().astype(float, copy=copy)
        return block.to_numpy(dtype=float, copy=copy)

    if isinstance(block, pd.Series):
        if _is_sparse_backed_series(block):
            return block.sparse.to_dense().to_numpy(dtype=float, copy=copy)
        return block.to_numpy(dtype=float, copy=copy)

    if copy:
        return np.array(block, dtype=float, copy=True)
    return np.asarray(block, dtype=float)


def sparse_frame_from_spmatrix(matrix, *, index, columns) -> pd.DataFrame:
    """Build a pandas sparse dataframe whose implicit sparse value is zero."""
    return pd.DataFrame.sparse.from_spmatrix(
        matrix,
        index=index,
        columns=columns,
    )


def as_dense_series(vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...]) -> pd.Series:
    """Coerce a vector-like input to a dense float ``Series``."""
    series = _as_series(vector)
    return pd.Series(dense_values(series), index=series.index, name=series.name)


def _as_series(vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...]) -> pd.Series:
    """Coerce a 1D value container into a pandas ``Series``."""
    if isinstance(vector, pd.Series):
        return vector.copy()

    if isinstance(vector, pd.DataFrame):
        if vector.shape[1] != 1:
            raise ValueError("Expected a single-column DataFrame when coercing to a vector.")
        return vector.iloc[:, 0].copy()

    values = np.asarray(vector, dtype=float).reshape(-1)
    return pd.Series(values)


def as_column_frame(
    vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...],
    column_name: str,
) -> pd.DataFrame:
    """Return a single-column dataframe preserving the vector index."""
    series = _as_series(vector)
    return pd.DataFrame(dense_values(series), index=series.index, columns=[column_name])


def sum_final_demand(block: pd.DataFrame | pd.Series) -> pd.Series:
    """Collapse a final-demand block to one total per producing row."""
    return sum_rows(block)


def sum_rows(block: pd.DataFrame | pd.Series) -> pd.Series:
    """Return one total per row, preserving labels and sparse efficiency.

    For sparse-backed dataframes this avoids pandas' row-wise reduction path and
    performs the aggregation directly on the underlying SciPy sparse matrix.
    """
    if isinstance(block, pd.Series):
        return as_dense_series(block)

    if isinstance(block, pd.DataFrame):
        if _is_sparse_backed_dataframe(block):
            matrix = block.sparse.to_coo().tocsr()
            summed = np.asarray(matrix.sum(axis=1)).reshape(-1)
            return pd.Series(summed, index=block.index, dtype=float)

        return as_dense_series(block.sum(axis=1, skipna=False))

    raise TypeError("Final demand block must be a pandas Series or DataFrame.")


def sum_columns(block: pd.DataFrame | pd.Series) -> pd.Series:
    """Return one total per column, preserving labels and sparse efficiency."""
    if isinstance(block, pd.Series):
        return as_dense_series(block)

    if isinstance(block, pd.DataFrame):
        if _is_sparse_backed_dataframe(block):
            matrix = block.sparse.to_coo().tocsc()
            summed = np.asarray(matrix.sum(axis=0)).reshape(-1)
            return pd.Series(summed, index=block.columns, dtype=float)

        return as_dense_series(block.sum(axis=0, skipna=False))

    raise TypeError("Block must be a pandas Series or DataFrame.")


def diag_from_vector(
    vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...]
) -> np.ndarray:
    """Return a dense diagonal matrix built from a vector-like input."""
    series = _as_series(vector)
    return np.diagflat(dense_values(series))


def scale_columns(
    frame: pd.DataFrame,
    vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...],
) -> pd.DataFrame:
    """Scale each dataframe column by the matching vector element.

    This is algebraically equivalent to ``frame @ diag(vector)`` but avoids
    materializing a dense diagonal matrix. When ``frame`` is sparse-backed, the
    operation stays on sparse matrices.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame.")
    raw_series = _as_series(vector)
    series = pd.Series(dense_values(raw_series), index=raw_series.index, name=raw_series.name)
    if not frame.columns.equals(series.index):
        raise ValueError("frame columns and vector index do not match.")

    if _is_sparse_backed_dataframe(frame):
        from scipy import sparse

        matrix = frame.sparse.to_coo().tocsc()
        scaled = matrix @ sparse.diags(dense_values(series))
        return sparse_frame_from_spmatrix(scaled, index=frame.index, columns=frame.columns)

    return frame.mul(series, axis=1)


def scale_rows(
    frame: pd.DataFrame,
    vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...],
) -> pd.DataFrame:
    """Scale each dataframe row by the matching vector element.

    This is algebraically equivalent to ``diag(vector) @ frame`` but avoids
    materializing a dense diagonal matrix. When ``frame`` is sparse-backed, the
    operation stays on sparse matrices.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame.")
    raw_series = _as_series(vector)
    series = pd.Series(dense_values(raw_series), index=raw_series.index, name=raw_series.name)
    if not frame.index.equals(series.index):
        raise ValueError("frame index and vector index do not match.")

    if _is_sparse_backed_dataframe(frame):
        from scipy import sparse

        matrix = frame.sparse.to_coo().tocsc()
        scaled = sparse.diags(dense_values(series)) @ matrix
        return sparse_frame_from_spmatrix(scaled, index=frame.index, columns=frame.columns)

    return frame.mul(series, axis=0)


def _has_nan(values):
    from scipy import sparse

    return np.isnan(values.data if sparse.issparse(values) else values).any()


def _matmul_with_missing(left, right):
    """Propagate undefined terms only through nonzero dependencies.

    Temporary zeros are used only to evaluate the known part. Every output
    depending on an unknown term is explicitly restored to NaN. Thus unknown
    coefficients never become zeros, and multiplication by a known zero does
    not contaminate unrelated outputs.
    """
    from scipy import sparse

    left = sparse.csr_matrix(left, copy=True)
    right = sparse.csc_matrix(right, copy=True)

    def masks(matrix):
        unknown = matrix.copy()
        unknown.data = np.isnan(matrix.data)
        unknown.eliminate_zeros()
        support = matrix.astype(bool)
        support.eliminate_zeros()
        matrix.data[np.isnan(matrix.data)] = 0.0
        matrix.eliminate_zeros()
        return unknown, support

    left_unknown, left_support = masks(left)
    right_unknown, right_support = masks(right)
    affected = (left_unknown @ right_support + left_support @ right_unknown).tocoo()
    result = (left @ right).tolil()
    result[affected.row, affected.col] = np.nan
    return result.tocsr()


def matmul(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    """Multiply two labelled dataframes using a sparse-aware backend when useful."""
    if not isinstance(left, pd.DataFrame) or not isinstance(right, pd.DataFrame):
        raise TypeError("Expected pandas DataFrames.")
    if not left.columns.equals(right.index):
        raise ValueError("left columns and right index do not match.")

    left_is_sparse = _is_sparse_backed_dataframe(left)
    right_is_sparse = _is_sparse_backed_dataframe(right)

    if left_is_sparse or right_is_sparse:
        from scipy import sparse

        left_matrix = (
            left.sparse.to_coo().tocsr()
            if left_is_sparse
            else sparse.csr_matrix(dense_values(left))
        )
        right_matrix = (
            right.sparse.to_coo().tocsc()
            if right_is_sparse
            else dense_values(right)
        )
        product = (
            _matmul_with_missing(left_matrix, right_matrix)
            if _has_nan(left_matrix) or _has_nan(right_matrix)
            else left_matrix @ right_matrix
        )

        if sparse.issparse(product):
            return sparse_frame_from_spmatrix(
                product,
                index=left.index,
                columns=right.columns,
            )

        return pd.DataFrame(
            np.asarray(product, dtype=float),
            index=left.index,
            columns=right.columns,
        )

    left_values, right_values = dense_values(left), dense_values(right)
    product = (
        _matmul_with_missing(left_values, right_values).toarray()
        if _has_nan(left_values) or _has_nan(right_values)
        else left_values @ right_values
    )
    return pd.DataFrame(
        product,
        index=left.index,
        columns=right.columns,
    )


def matvec(
    frame: pd.DataFrame,
    vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...],
) -> pd.Series:
    """Multiply one labelled dataframe by one labelled vector."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame.")
    raw_series = _as_series(vector)
    series = pd.Series(dense_values(raw_series), index=raw_series.index, name=raw_series.name)
    if not frame.columns.equals(series.index):
        raise ValueError("frame columns and vector index do not match.")

    matrix = frame.sparse.to_coo().tocsr() if _is_sparse_backed_dataframe(frame) else dense_values(frame)
    if _has_nan(matrix) or _has_nan(dense_values(series)):
        values = _matmul_with_missing(matrix, dense_values(series).reshape(-1, 1)).toarray().ravel()
        return pd.Series(values, index=frame.index, dtype=float)

    values = matrix @ dense_values(series)
    return pd.Series(np.asarray(values).reshape(-1), index=frame.index, dtype=float)


def transpose_matvec(
    frame: pd.DataFrame,
    vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...],
) -> pd.Series:
    """Multiply the transpose of one labelled dataframe by one labelled vector."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame.")
    raw_series = _as_series(vector)
    series = pd.Series(dense_values(raw_series), index=raw_series.index, name=raw_series.name)
    if not frame.index.equals(series.index):
        raise ValueError("frame index and vector index do not match.")

    matrix = frame.sparse.to_coo().tocsc() if _is_sparse_backed_dataframe(frame) else dense_values(frame)
    if _has_nan(matrix) or _has_nan(dense_values(series)):
        values = _matmul_with_missing(matrix.T, dense_values(series).reshape(-1, 1)).toarray().ravel()
        return pd.Series(values, index=frame.columns, dtype=float)

    values = matrix.T @ dense_values(series)
    return pd.Series(np.asarray(values).reshape(-1), index=frame.columns, dtype=float)


def inverse_vector(
    vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...]
) -> pd.Series:
    """Return the element-wise inverse, preserving zeros as zeros."""
    series = _as_series(vector)
    values = dense_values(series, copy=True)
    mask = values != 0
    values[mask] = 1.0 / values[mask]
    values[~mask] = 0.0
    return pd.Series(values, index=series.index)


def identity_like(square_block: pd.DataFrame) -> pd.DataFrame:
    """Return an identity matrix with the same labels as ``square_block``."""
    validate_square(square_block)
    return pd.DataFrame(
        np.eye(square_block.shape[0], dtype=float),
        index=square_block.index,
        columns=square_block.columns,
    )


def leontief_inverse(coefficients: pd.DataFrame) -> pd.DataFrame:
    """Invert ``I - A`` strictly, diagnosing singularity before dense allocation."""
    from mario.compute.linear_solvers import require_nonsingular_coefficients

    validate_square(coefficients)
    require_nonsingular_coefficients(coefficients)
    values = np.eye(len(coefficients)) - dense_values(coefficients)
    inverse = np.linalg.inv(values)
    return pd.DataFrame(inverse, index=coefficients.index, columns=coefficients.columns)


def safe_inverse(matrix: pd.DataFrame) -> pd.DataFrame:
    """Invert a square dataframe, falling back to a pseudo-inverse if needed."""
    validate_square(matrix)
    values = dense_values(matrix)
    try:
        inverse = np.linalg.inv(values)
    except np.linalg.LinAlgError:
        inverse = np.linalg.pinv(values)

    return pd.DataFrame(inverse, index=matrix.index, columns=matrix.columns)


def safe_solve(
    lhs: pd.DataFrame,
    rhs: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...],
    *,
    solver: str = "numpy",
    cache: dict | None = None,
    cache_key=None,
) -> pd.DataFrame | pd.Series:
    """Solve ``lhs * x = rhs`` with a pseudo-inverse fallback for singular cases."""
    validate_square(lhs)
    rhs_is_series = isinstance(rhs, pd.Series)

    if isinstance(rhs, pd.DataFrame):
        rhs_values = dense_values(rhs)
        rhs_index = rhs.index
        rhs_columns = rhs.columns
    elif isinstance(rhs, pd.Series):
        rhs_values = dense_values(rhs)
        rhs_index = rhs.index
        rhs_columns = None
    else:
        rhs_values = np.asarray(rhs, dtype=float)
        rhs_index = lhs.index
        rhs_columns = None

    if solver == "numpy":
        try:
            solved = np.linalg.solve(dense_values(lhs), rhs_values)
        except np.linalg.LinAlgError:
            solved = np.linalg.pinv(dense_values(lhs)) @ rhs_values
    elif solver == "scipy":
        from scipy import sparse
        from scipy.sparse.linalg import factorized

        factor = None
        if cache is not None and cache_key is not None:
            factor = cache.get(cache_key)
        if factor is None:
            try:
                if all(isinstance(dtype, pd.SparseDtype) for dtype in lhs.dtypes):
                    lhs_sparse = lhs.sparse.to_coo().tocsc()
                else:
                    lhs_sparse = sparse.csc_matrix(dense_values(lhs))
                factor = factorized(lhs_sparse)
                if cache is not None and cache_key is not None:
                    cache[cache_key] = factor
            except Exception:
                solved = np.linalg.pinv(dense_values(lhs)) @ np.asarray(rhs_values, dtype=float)
                factor = None

        if factor is not None:
            rhs_array = np.asarray(rhs_values, dtype=float)
            if rhs_array.ndim == 1:
                solved = factor(rhs_array)
            else:
                solved = np.column_stack([factor(rhs_array[:, idx]) for idx in range(rhs_array.shape[1])])
    else:
        raise ValueError(f"Unsupported linear solver {solver!r}.")

    if rhs_is_series:
        return pd.Series(solved, index=rhs_index)

    if rhs_columns is not None:
        return pd.DataFrame(solved, index=lhs.index, columns=rhs_columns)

    return pd.Series(np.asarray(solved).reshape(-1), index=lhs.index)


def validate_square(block: pd.DataFrame) -> None:
    """Validate that a dataframe is square and perfectly label-aligned."""
    if not isinstance(block, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame.")

    if block.shape[0] != block.shape[1]:
        raise ValueError("Expected a square matrix.")

    if not block.index.equals(block.columns):
        raise ValueError("Square matrix index and columns must match exactly.")


def require_same_index(
    lhs: pd.DataFrame | pd.Series | pd.Index,
    rhs: pd.DataFrame | pd.Series | pd.Index,
    *,
    lhs_name: str = "lhs",
    rhs_name: str = "rhs",
) -> None:
    """Validate that two objects expose the same pandas index."""
    lhs_index = lhs if isinstance(lhs, pd.Index) else lhs.index
    rhs_index = rhs if isinstance(rhs, pd.Index) else rhs.index

    if not lhs_index.equals(rhs_index):
        raise ValueError(f"{lhs_name} and {rhs_name} indexes do not match.")


def require_same_columns(
    lhs: pd.DataFrame,
    rhs: pd.DataFrame | pd.Index,
    *,
    lhs_name: str = "lhs",
    rhs_name: str = "rhs",
) -> None:
    """Validate that two objects expose the same pandas column labels."""
    rhs_columns = rhs if isinstance(rhs, pd.Index) else rhs.columns
    if not lhs.columns.equals(rhs_columns):
        raise ValueError(f"{lhs_name} and {rhs_name} columns do not match.")
