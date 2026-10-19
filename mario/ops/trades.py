"""Region-level flow sums without densifying sparse transaction blocks."""

import numpy as np
import pandas as pd

from mario.compute.helpers import sparse_frame_from_spmatrix
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


def direct_trade_breakdown(
    matrix,
    direct_row,
    item=None,
    *,
    supply=False,
    regions=None,
    region_aggregation=None,
    clusters_direction="both",
):
    """Weight real flow entries directly, keeping the legacy contributor index.

    The output grid is trade origin x actual contributor nodes x destination;
    no contributor-by-contributor matrix is constructed.
    """
    from scipy import sparse

    item_axis = matrix.columns if supply else matrix.index
    if not isinstance(item_axis, pd.MultiIndex) or item_axis.nlevels < 3:
        raise WrongInput("Trade calculation requires a 3-level item MultiIndex.")
    selected = np.ones(len(item_axis), dtype=bool)
    if item is not None:
        items = item if isinstance(item, list) else [item]
        missing = set(items).difference(item_axis.get_level_values(-1))
        if missing:
            raise WrongInput(
                f"Items {sorted(missing)!r} do not exist in the matrix item index."
            )
        selected = item_axis.get_level_values(-1).isin(items)

    contributors = direct_row.index
    if not contributors.is_unique:
        raise WrongInput("Direct trade contributor labels must be unique.")
    positions = contributors.get_indexer(matrix.index)
    relevant = np.ones(len(matrix.index), dtype=bool) if supply else selected
    if (positions[relevant] < 0).any():
        raise WrongInput("Trade content weights could not be aligned to trade rows.")
    weights = direct_row.reindex(matrix.index).to_numpy(dtype=float, na_value=np.nan)
    if pd.isna(weights[relevant]).any():
        raise WrongInput("Trade content weights could not be aligned to trade rows.")

    row_regions = matrix.index.get_level_values(0)
    column_regions = matrix.columns.get_level_values(0)
    if regions is None:
        regions = list(dict.fromkeys([*row_regions, *column_regions]))
    targets = (
        {}
        if region_aggregation is None
        else region_aggregation["Aggregation"].to_dict()
    )
    origin_targets = {
        r: targets.get(r, r) if clusters_direction in {"origin", "both"} else r
        for r in regions
    }
    destination_targets = {
        r: targets.get(r, r) if clusters_direction in {"destination", "both"} else r
        for r in regions
    }
    origins = pd.Index(list(dict.fromkeys(origin_targets.values())), name=MI["r"])
    destinations = pd.Index(
        list(dict.fromkeys(destination_targets.values())), name=MI["r"]
    )
    origin_codes = origins.get_indexer([origin_targets.get(r, r) for r in row_regions])
    destination_codes = destinations.get_indexer(
        [destination_targets.get(r, r) for r in column_regions]
    )
    if (origin_codes < 0).any() or (destination_codes < 0).any():
        raise WrongInput(
            "Trade regions could not be aligned to the database Region index."
        )

    sparse_input = (
        len(matrix.columns) > 0 or isinstance(direct_row.dtype, pd.SparseDtype)
    ) and all(
        isinstance(dtype, pd.SparseDtype) and dtype.fill_value == 0
        for dtype in matrix.dtypes
    )
    if sparse_input:
        entries = (
            matrix.sparse.to_coo()
            if len(matrix.columns)
            else sparse.coo_matrix(matrix.shape, dtype=float)
        )
        rows, columns, values = entries.row, entries.col, entries.data
    else:
        values = matrix.to_numpy(dtype=float)
        rows, columns = np.nonzero(values)
        values = values[rows, columns]
    keep = selected[columns if supply else rows]
    rows, columns, values = rows[keep], columns[keep], values[keep]
    values = values * weights[rows]
    nonzero = (values != 0) & ~pd.isna(values)
    output_rows = (
        origin_codes[rows[nonzero]] * len(contributors) + positions[rows[nonzero]]
    )
    output_columns = destination_codes[columns[nonzero]]
    result = sparse.coo_matrix(
        (values[nonzero], (output_rows, output_columns)),
        shape=(len(origins) * len(contributors), len(destinations)),
    ).tocsc()

    if isinstance(contributors, pd.MultiIndex):
        levels, codes, names = (
            contributors.levels,
            contributors.codes,
            contributors.names,
        )
    else:
        levels, codes, names = (
            [contributors],
            [np.arange(len(contributors))],
            [contributors.name],
        )
    index = pd.MultiIndex(
        levels=[origins, *levels],
        codes=[
            np.repeat(np.arange(len(origins), dtype=np.int32), len(contributors)),
            *[np.tile(code, len(origins)) for code in codes],
        ],
        names=[MI["r"], *names],
        verify_integrity=False,
    )
    if sparse_input:
        return sparse_frame_from_spmatrix(result, index=index, columns=destinations)
    return pd.DataFrame(result.toarray(), index=index, columns=destinations)
