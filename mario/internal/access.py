"""Internal block access adapters used behind the public ``Database`` API."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _is_sparse_dataframe(value) -> bool:
    """Return ``True`` when a dataframe uses pandas sparse dtypes."""
    return isinstance(value, pd.DataFrame) and any(isinstance(dtype, pd.SparseDtype) for dtype in value.dtypes)


def block_to_pandas(value):
    """Return a pandas copy of one block value.

    The public MARIO API still exposes pandas objects. This adapter is the
    single place where future non-pandas backends should be converted when a
    pandas result is explicitly required.
    """
    if isinstance(value, (pd.DataFrame, pd.Series)):
        return value.copy(deep=True)

    if hasattr(value, "to_pandas"):
        return value.to_pandas()

    raise TypeError(f"Unsupported block type for pandas conversion: {type(value)!r}")


def block_to_table(value, *, backend: str = "auto"):
    """Return one block as a tabular object for query/export operations."""
    if backend == "auto":
        return block_to_pandas(value)

    if backend == "pandas":
        return block_to_pandas(value)

    if backend == "polars":
        import polars as pl

        if isinstance(value, pl.DataFrame):
            return value.clone()

        pandas_value = block_to_pandas(value)
        if isinstance(pandas_value, pd.Series):
            pandas_value = pandas_value.to_frame(
                name=pandas_value.name if pandas_value.name is not None else "__value__"
            )
        return pl.from_pandas(pandas_value)

    raise ValueError(f"Unsupported table backend {backend!r}.")


def block_to_matrix(
    value,
    *,
    backend: str = "numpy",
    prefer_sparse: bool = False,
):
    """Return one block as a numeric matrix backend for compute code."""
    if backend not in {"numpy", "scipy"}:
        raise ValueError(f"Unsupported matrix backend {backend!r}.")

    if hasattr(value, "to_numpy"):
        pandas_value = value
    else:
        pandas_value = block_to_pandas(value)

    if isinstance(pandas_value, pd.Series):
        pandas_value = pandas_value.to_frame(
            name=pandas_value.name if pandas_value.name is not None else "__value__"
        )

    if backend == "numpy" and not prefer_sparse:
        return pandas_value.to_numpy(copy=False)

    from scipy import sparse

    if _is_sparse_dataframe(pandas_value):
        matrix = pandas_value.sparse.to_coo()
    else:
        matrix = sparse.csr_matrix(pandas_value.to_numpy(copy=False))

    if backend == "numpy":
        return matrix.toarray()
    return matrix.tocsr() if prefer_sparse else matrix
