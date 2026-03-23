"""Small pure helpers shared by compute formula modules."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _as_series(vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...]) -> pd.Series:
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
    series = _as_series(vector)
    return pd.DataFrame(series.values, index=series.index, columns=[column_name])


def sum_final_demand(block: pd.DataFrame | pd.Series) -> pd.Series:
    if isinstance(block, pd.Series):
        return block.copy()

    if isinstance(block, pd.DataFrame):
        return block.sum(axis=1)

    raise TypeError("Final demand block must be a pandas Series or DataFrame.")


def diag_from_vector(
    vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...]
) -> np.ndarray:
    series = _as_series(vector)
    return np.diagflat(series.to_numpy(dtype=float))


def inverse_vector(
    vector: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...]
) -> pd.Series:
    series = _as_series(vector).astype(float)
    values = series.to_numpy(copy=True)
    mask = values != 0
    values[mask] = 1.0 / values[mask]
    values[~mask] = 0.0
    return pd.Series(values, index=series.index)


def identity_like(square_block: pd.DataFrame) -> pd.DataFrame:
    validate_square(square_block)
    return pd.DataFrame(
        np.eye(square_block.shape[0], dtype=float),
        index=square_block.index,
        columns=square_block.columns,
    )


def safe_inverse(matrix: pd.DataFrame) -> pd.DataFrame:
    validate_square(matrix)
    values = matrix.to_numpy(dtype=float)
    try:
        inverse = np.linalg.inv(values)
    except np.linalg.LinAlgError:
        inverse = np.linalg.pinv(values)

    return pd.DataFrame(inverse, index=matrix.index, columns=matrix.columns)


def safe_solve(
    lhs: pd.DataFrame,
    rhs: pd.DataFrame | pd.Series | np.ndarray | list[float] | tuple[float, ...],
) -> pd.DataFrame | pd.Series:
    validate_square(lhs)
    rhs_is_series = isinstance(rhs, pd.Series)

    if isinstance(rhs, pd.DataFrame):
        rhs_values = rhs.to_numpy(dtype=float)
        rhs_index = rhs.index
        rhs_columns = rhs.columns
    elif isinstance(rhs, pd.Series):
        rhs_values = rhs.to_numpy(dtype=float)
        rhs_index = rhs.index
        rhs_columns = None
    else:
        rhs_values = np.asarray(rhs, dtype=float)
        rhs_index = lhs.index
        rhs_columns = None

    try:
        solved = np.linalg.solve(lhs.to_numpy(dtype=float), rhs_values)
    except np.linalg.LinAlgError:
        solved = np.linalg.pinv(lhs.to_numpy(dtype=float)) @ rhs_values

    if rhs_is_series:
        return pd.Series(solved, index=rhs_index)

    if rhs_columns is not None:
        return pd.DataFrame(solved, index=lhs.index, columns=rhs_columns)

    return pd.Series(np.asarray(solved).reshape(-1), index=lhs.index)


def validate_square(block: pd.DataFrame) -> None:
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
    rhs_columns = rhs if isinstance(rhs, pd.Index) else rhs.columns
    if not lhs.columns.equals(rhs_columns):
        raise ValueError(f"{lhs_name} and {rhs_name} columns do not match.")
