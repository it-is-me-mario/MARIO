"""Balancing helpers for IOT flow matrices."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongInput


def _coerce_target_vector(values, *, size: int, axis_name: str, labels=None) -> np.ndarray:
    """Normalize one target margin vector and optionally align it to labels."""
    if isinstance(values, pd.DataFrame):
        if values.shape[1] == 1:
            values = values.iloc[:, 0]
        elif values.shape[0] == 1:
            values = values.iloc[0, :]
        else:
            raise WrongInput(f"{axis_name} should be one-dimensional.")

    if isinstance(values, pd.Series):
        if labels is None:
            array = values.to_numpy(dtype=float, copy=False)
        else:
            missing = labels.difference(values.index)
            extra = values.index.difference(labels)
            if len(missing) or len(extra):
                raise WrongInput(
                    f"{axis_name} labels do not match the matrix axis. "
                    f"Missing: {list(missing)}. Extra: {list(extra)}."
                )
            array = values.reindex(labels).to_numpy(dtype=float, copy=False)
    else:
        array = np.asarray(values, dtype=float)
        if array.ndim == 2 and 1 in array.shape:
            array = array.reshape(-1)
        elif array.ndim != 1:
            raise WrongInput(f"{axis_name} should be one-dimensional.")

    if array.size != size:
        raise WrongInput(f"{axis_name} should have length {size}.")

    if not np.isfinite(array).all():
        raise WrongInput(f"{axis_name} contains non-finite values.")

    return array.astype(float, copy=False)


def ras(matrix, target_rows, target_cols, tol: float = 1e-8, max_iter: int = 1000):
    """Balance one matrix with the RAS biproportional fitting algorithm.

    Parameters
    ----------
    matrix:
        Prior matrix to balance. Accepts a numpy array or pandas DataFrame.
    target_rows:
        Desired row sums. When ``matrix`` is a DataFrame, pandas targets are
        aligned by row labels.
    target_cols:
        Desired column sums. When ``matrix`` is a DataFrame, pandas targets are
        aligned by column labels.
    tol:
        Absolute convergence tolerance on row and column sums.
    max_iter:
        Maximum number of row/column scaling iterations.

    Returns
    -------
    numpy.ndarray | pandas.DataFrame
        Balanced matrix with the same type and labels as the input matrix.
    """
    if tol <= 0:
        raise WrongInput("tol should be strictly positive.")
    if int(max_iter) < 1:
        raise WrongInput("max_iter should be a positive integer.")

    is_dataframe = isinstance(matrix, pd.DataFrame)
    if is_dataframe:
        row_labels = matrix.index
        col_labels = matrix.columns
        values = matrix.to_numpy(dtype=float, copy=True)
    else:
        row_labels = None
        col_labels = None
        values = np.asarray(matrix, dtype=float)
        if values.ndim != 2:
            raise WrongInput("matrix should be two-dimensional.")
        values = values.copy()

    if not np.isfinite(values).all():
        raise WrongInput("matrix contains non-finite values.")
    if np.any(values < 0):
        raise WrongInput("matrix contains negative values.")

    target_rows = _coerce_target_vector(
        target_rows,
        size=values.shape[0],
        axis_name="target_rows",
        labels=row_labels,
    )
    target_cols = _coerce_target_vector(
        target_cols,
        size=values.shape[1],
        axis_name="target_cols",
        labels=col_labels,
    )

    if np.any(target_rows < 0) or np.any(target_cols < 0):
        raise WrongInput("RAS targets should be non-negative.")

    if not np.isclose(target_rows.sum(), target_cols.sum(), atol=tol, rtol=tol):
        raise WrongInput("target_rows and target_cols should have the same total.")

    zero_rows = values.sum(axis=1) == 0
    zero_cols = values.sum(axis=0) == 0
    if np.any(zero_rows & (target_rows > tol)):
        raise WrongInput("RAS cannot assign a positive target to an all-zero row.")
    if np.any(zero_cols & (target_cols > tol)):
        raise WrongInput("RAS cannot assign a positive target to an all-zero column.")

    for _ in range(int(max_iter)):
        row_sums = values.sum(axis=1)
        row_factors = np.ones_like(target_rows)
        nonzero_rows = row_sums != 0
        row_factors[nonzero_rows] = target_rows[nonzero_rows] / row_sums[nonzero_rows]
        values = (values.T * row_factors).T

        col_sums = values.sum(axis=0)
        col_factors = np.ones_like(target_cols)
        nonzero_cols = col_sums != 0
        col_factors[nonzero_cols] = target_cols[nonzero_cols] / col_sums[nonzero_cols]
        values = values * col_factors

        if np.allclose(values.sum(axis=1), target_rows, atol=tol, rtol=tol) and np.allclose(
            values.sum(axis=0),
            target_cols,
            atol=tol,
            rtol=tol,
        ):
            if is_dataframe:
                return pd.DataFrame(values, index=row_labels, columns=col_labels)
            return values

    raise WrongInput("RAS did not converge within max_iter iterations.")


__all__ = ["ras"]
