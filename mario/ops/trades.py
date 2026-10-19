"""Region-level flow sums without densifying sparse transaction blocks."""

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX as MI


def sum_trade_regions(matrix, *, row_mask=None, column_mask=None, row_weights=None):
    """Sum existing origin/destination pairs, materializing only regional totals."""
    row_regions = matrix.index.get_level_values(0)
    column_regions = matrix.columns.get_level_values(0)
    row_codes, origins = pd.factorize(row_regions, sort=False)
    column_codes, destinations = pd.factorize(column_regions, sort=False)
    row_mask = np.ones(len(matrix.index), dtype=bool) if row_mask is None else row_mask
    column_mask = (
        np.ones(len(matrix.columns), dtype=bool) if column_mask is None else column_mask
    )

    weights = None
    if row_weights is not None:
        weights = row_weights.reindex(matrix.index)
        if weights.iloc[np.flatnonzero(row_mask)].isna().any():
            raise WrongInput(
                "Trade content weights could not be aligned to trade rows."
            )

    sparse = len(matrix.columns) > 0 and all(
        isinstance(dtype, pd.SparseDtype) and dtype.fill_value == 0
        for dtype in matrix.dtypes
    )
    if sparse:
        entries = matrix.sparse.to_coo()
        keep = row_mask[entries.row] & column_mask[entries.col]
        rows, columns, values = entries.row[keep], entries.col[keep], entries.data[keep]
        if weights is not None:
            values = values * weights.to_numpy(dtype=float, na_value=np.nan)[rows]
        # pandas groupby sums skip missing flow values.
        values = np.where(pd.isna(values), 0.0, values)
        totals = np.zeros((len(origins), len(destinations)), dtype=values.dtype)
        np.add.at(totals, (row_codes[rows], column_codes[columns]), values)
        frame = pd.DataFrame(totals, index=origins, columns=destinations)
    else:
        selected = matrix.iloc[row_mask, column_mask]
        if weights is not None:
            selected = selected.mul(weights.reindex(selected.index), axis=0)
        frame = (
            selected.T.groupby(level=0, sort=False)
            .sum()
            .T.groupby(level=0, sort=False)
            .sum()
        )
        frame = frame.reindex(index=origins, columns=destinations, fill_value=0.0)
    frame.index.name = MI["r"]
    frame.columns.name = MI["r"]
    return frame
