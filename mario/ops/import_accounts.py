"""Semantic factor-row layouts shared by IOT and SUT boundary transforms."""

import numpy as np
import pandas as pd
from scipy import sparse

from mario.compute.helpers import _is_sparse_backed_dataframe
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX as MI


def factor_row_values(rows):
    """Normalize legacy factor axes without interpreting factor label text."""
    if not rows.is_unique:
        raise WrongInput("Region extraction requires unique factor rows.")
    if not isinstance(rows, pd.MultiIndex):
        return (), [(value,) for value in rows]
    names = list(rows.names)
    values = list(rows)
    if names[-2:] == ["Level", "Item"]:
        if any(value[-2] != MI["f"] for value in values):
            raise WrongInput("Invalid factor-row Level markers.")
        names = names[:-2] + [MI["f"]]
        values = [value[:-2] + (value[-1],) for value in values]
    if names[-1] in (None, "Item"):
        names[-1] = MI["f"]
    if names[-1] != MI["f"] or len(set(names)) != len(names):
        raise WrongInput("Factor rows must terminate in Factor of production.")
    return tuple(names[:-1]), values


def combine_factor_accounts(database, rows, originals, imports, import_keys, *,
                            selected, classification, by_region):
    """Add import accounts with explicit classifier dimensions and empty padding.

    ``originals`` maps block names to (CSR values, column axis); ``imports``
    uses the same columns and one row per (origin, item) in ``import_keys``.
    Adding Region to common factors splits their domestic amounts by receiving
    region. Existing source row classifications are preserved.
    """
    old_prefix, old_values = factor_row_values(rows)
    required = set(old_prefix)
    if classification:
        required.add(classification)
    if by_region:
        required.add(MI["r"])
    order = (MI["r"], MI["s"], MI["a"], MI["c"])
    if required.difference(order):
        raise WrongInput(f"Unsupported factor dimensions: {sorted(required.difference(order))}")
    prefix = tuple(name for name in order if name in required)
    from mario.parsers.matrix_layouts import normalize_matrix_layouts

    normalize_matrix_layouts({"V": prefix, "VY": prefix}, table=database.table_type)
    regionalize = MI["r"] in prefix and MI["r"] not in old_prefix
    receivers = selected if regionalize else [None]
    expanded = []
    for receiver in receivers:
        for value in old_values:
            fields = dict(zip(old_prefix + (MI["f"],), value))
            if regionalize:
                fields[MI["r"]] = receiver
            expanded.append(tuple(fields.get(name) for name in prefix) + (value[-1],))
    imported = []
    for origin, item in import_keys:
        fields = {classification: item} if classification else {}
        if by_region:
            fields[MI["r"]] = origin
        imported.append(tuple(fields.get(name) for name in prefix) + ("imports",))
    names = prefix + (MI["f"],)
    axis = (
        pd.MultiIndex.from_tuples(expanded + imported, names=names)
        if prefix else pd.Index([value[-1] for value in expanded + imported], name=rows.name)
    )
    if not axis.is_unique:
        raise WrongInput("Generated import accounts collide with existing factor rows.")
    output = {}
    for name, (matrix, columns) in originals.items():
        if regionalize:
            coo = matrix.tocoo()
            owner = pd.Index(selected).get_indexer(columns.get_level_values(0))
            matrix = sparse.coo_matrix(
                (coo.data, (owner[coo.col] * len(rows) + coo.row, coo.col)),
                shape=(len(expanded), len(columns)),
            ).tocsr()
        output[name] = sparse.vstack([matrix, imports[name]], format="csr")
    return axis, output


def register_factor_layout(database, rows):
    """Publish the same row semantics on flows, coefficients and multipliers."""
    prefix, _ = factor_row_values(rows)
    if not prefix:
        return
    from mario.parsers.matrix_layouts import normalize_matrix_layouts

    normalize_matrix_layouts({"V": prefix, "VY": prefix}, table=database.table_type)
    names = ["V", "v", "VY", "m", "M"]
    if database.table_type == "SUT":
        names += ["Va", "Vc", "va", "vc", "ma", "mc", "Ma", "Mc"]
    for name in names:
        spec = database.get_block_spec(name)
        column_axes = spec.col_axes
        if database.table_type == "IOT":
            columns = database.matrices["baseline"]["VY" if name == "VY" else "Z"].columns
            if columns.nlevels == 2:
                column_axes = (MI["r"], MI["n"] if name == "VY" else MI["s"])
        database.register_block_spec(
            name=name, row_axes=prefix + (MI["f"],),
            col_axes=column_axes, replace=True,
        )


def _csr(frame):
    if not len(frame.columns):
        return sparse.csr_matrix(frame.shape, dtype=float)
    if _is_sparse_backed_dataframe(frame):
        if all(dtype.fill_value == 0 for dtype in frame.dtypes):
            result = frame.sparse.to_coo().tocsr()
            if not np.isfinite(result.data).all():
                raise WrongInput("Region extraction requires finite flow values.")
            result.eliminate_zeros()
            return result
        # Fully stored account columns can carry fill=NaN metadata. Actual
        # missing values, including implicit nonzero/NaN gaps, are invalid.
        values, rows, pointers = [], [], [0]
        for _, column in frame.items():
            array = column.array
            if array.fill_value != 0 and len(array.sp_values) != len(column):
                raise WrongInput("Region extraction requires finite, zero-fill sparse flows.")
            values.extend(array.sp_values)
            rows.extend(array.sp_index.indices)
            pointers.append(len(values))
        result = sparse.csc_matrix((values, rows, pointers), shape=frame.shape).tocsr()
    else:
        result = sparse.csr_matrix(frame.to_numpy(dtype=float))
    if not np.isfinite(result.data).all():
        raise WrongInput("Region extraction requires finite flow values.")
    result.eliminate_zeros()
    return result


def _align(frame, index, columns):
    if not frame.index.is_unique or not frame.columns.is_unique:
        raise WrongInput("Region extraction requires unique native block axes.")
    if frame.index.equals(index) and frame.columns.equals(columns):
        return _csr(frame)
    rows, cols = frame.index.get_indexer(index), frame.columns.get_indexer(columns)
    if (
        len(rows) != len(frame.index) or len(cols) != len(frame.columns)
        or (rows < 0).any() or (cols < 0).any()
    ):
        raise WrongInput("Region extraction found inconsistent native block axes.")
    return _csr(frame)[rows, :][:, cols]


def _export_columns(selected, excluded, fd, trade_mode, layout):
    types = ["Export"] if layout == "sectorized" else [
        "Final Demand exports", "Intermediate exports"
    ]
    labels = [f"{kind} to {r}" for kind in types for r in excluded] \
        if trade_mode == "by_region" else types
    columns = pd.MultiIndex.from_tuples(
        [(r, MI["n"], label) if fd.nlevels == 3 else (r, label)
         for r in selected for label in labels], names=fd.names
    )
    return columns, labels


def _exports(intermediate, final, rows, intermediate_axis, fd,
             selected, excluded, trade_mode, layout, columns):
    """Sum boundary flows into export columns owned by each exporting region."""
    owner = pd.Index(selected).get_indexer(rows.get_level_values(0))
    count = len(columns) // len(selected)
    matrices = []
    for source, axis, category in ((final, fd, 0), (intermediate, intermediate_axis, 1)):
        coo = source.tocoo()
        foreign = ~axis.get_level_values(0).isin(selected)[coo.col]
        rr, cc, data = coo.row[foreign], coo.col[foreign], coo.data[foreign]
        group = np.zeros(len(data), dtype=int)
        if trade_mode == "by_region":
            group = pd.Index(excluded).get_indexer(axis.get_level_values(0)[cc])
        if layout == "legacy":
            group += category * (len(excluded) if trade_mode == "by_region" else 1)
        matrices.append(sparse.coo_matrix(
            (data, (rr, owner[rr] * count + group)), shape=(len(rows), len(columns))
        ).tocsr())
    return matrices[0] + matrices[1]
