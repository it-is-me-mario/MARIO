"""Externalize a SUT boundary using native, sparse flow blocks."""

from copy import deepcopy

import numpy as np
import pandas as pd
from scipy import sparse

from mario.compute.helpers import _is_sparse_backed_dataframe
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from mario.ops.chenery_moses import read_flows


def _csr(frame):
    if not len(frame.columns):
        return sparse.csr_matrix(frame.shape, dtype=float)
    if _is_sparse_backed_dataframe(frame):
        if all(dtype.fill_value == 0 for dtype in frame.dtypes):
            result = frame.sparse.to_coo().tocsr()
            if not np.isfinite(result.data).all():
                raise WrongInput("SUT extraction requires finite flow values.")
            result.eliminate_zeros()
            return result
        # Fully stored account columns can carry fill=NaN metadata. Actual
        # missing values, including implicit nonzero/NaN gaps, are invalid.
        values, rows, pointers = [], [], [0]
        for _, column in frame.items():
            array = column.array
            if array.fill_value != 0 and len(array.sp_values) != len(column):
                raise WrongInput("SUT extraction requires finite, zero-fill sparse flows.")
            values.extend(array.sp_values)
            rows.extend(array.sp_index.indices)
            pointers.append(len(values))
        result = sparse.csc_matrix((values, rows, pointers), shape=frame.shape).tocsr()
    else:
        result = sparse.csr_matrix(frame.to_numpy(dtype=float))
    if not np.isfinite(result.data).all():
        raise WrongInput("SUT extraction requires finite flow values.")
    result.eliminate_zeros()
    return result


def _align(frame, index, columns):
    if not frame.index.is_unique or not frame.columns.is_unique:
        raise WrongInput("SUT extraction requires unique native block axes.")
    if frame.index.equals(index) and frame.columns.equals(columns):
        return _csr(frame)
    rows, cols = frame.index.get_indexer(index), frame.columns.get_indexer(columns)
    if (
        len(rows) != len(frame.index) or len(cols) != len(frame.columns)
        or (rows < 0).any() or (cols < 0).any()
    ):
        raise WrongInput("SUT extraction found inconsistent native block axes.")
    return _csr(frame)[rows, :][:, cols]


def _inverse_totals(matrix, axis, used, nodes):
    totals = np.asarray(matrix.sum(axis=axis)).ravel()
    if not np.isfinite(totals).all():
        raise WrongInput("SUT extraction requires finite supply totals.")
    undefined = (totals == 0) & used
    if undefined.any():
        raise WrongInput(
            "Import allocation is undefined for zero net supply with nonzero "
            f"imports. Nodes: {nodes[undefined].tolist()[:20]}"
        )
    return np.divide(1.0, totals, out=np.zeros_like(totals), where=totals != 0)


def _active_rows(matrix):
    return np.diff(matrix.tocsr().indptr) != 0


def _imports(S, U, Ya, Yc, activities, commodities, fd, selected, by, trade_mode):
    """Return import accounts on activities, commodities and final demand.

    Use-side trade is exact by product. Activity attribution uses the source
    commodity's producer shares in S. Supply-side trade is already observed by
    producer; product attribution uses the receiving commodity. Direct activity
    final demand uses the producer's output mix only for product attribution.
    """
    a_local = activities.get_level_values(0).isin(selected)
    c_local = commodities.get_level_values(0).isin(selected)
    n_local = fd.get_level_values(0).isin(selected)
    ua, yc, ya = U[:, a_local].copy(), Yc[:, n_local].copy(), Ya[:, n_local].copy()
    ua = sparse.diags((~c_local).astype(float), format="csr") @ ua
    yc = sparse.diags((~c_local).astype(float), format="csr") @ yc
    ya = sparse.diags((~a_local).astype(float), format="csr") @ ya
    supply_imports = S[:, c_local].tocoo()
    keep = ~a_local[supply_imports.row]
    sr, sc, sv = supply_imports.row[keep], supply_imports.col[keep], supply_imports.data[keep]

    regions = list(dict.fromkeys(activities.get_level_values(0).tolist()
                                 + commodities.get_level_values(0).tolist()))
    items = (
        list(dict.fromkeys((commodities if by == "product" else activities)
                          .get_level_values(2))) if by else [None]
    )
    partners = regions if trade_mode == "by_region" else [None]
    keys = [(origin, item) for origin in partners for item in items]
    key_position = {key: i for i, key in enumerate(keys)}

    def positions(origins, codes):
        return np.array([
            key_position[(origin if trade_mode == "by_region" else None,
                          code if by else None)]
            for origin, code in zip(origins, codes)
        ], dtype=int)

    def projection(nodes):
        return sparse.coo_matrix(
            (np.ones(len(nodes)), (positions(nodes.get_level_values(0),
                                            nodes.get_level_values(2)),
                                   np.arange(len(nodes)))),
            shape=(len(keys), len(nodes)),
        ).tocsr()

    if by == "activity":
        ha = projection(activities)
        used = _active_rows(ua) | _active_rows(yc)
        inv = _inverse_totals(S, 0, used, commodities)
        hc = ha @ S.multiply(inv)
    else:
        hc = projection(commodities)
        if by == "product":
            used = _active_rows(ya)
            if used.any():
                inv = _inverse_totals(S, 1, used, activities)
                mix = S.tocoo()
                row = positions(activities.get_level_values(0)[mix.row],
                                commodities.get_level_values(2)[mix.col])
                ha = sparse.coo_matrix(
                    (mix.data * inv[mix.row], (row, mix.row)),
                    shape=(len(keys), len(activities)),
                ).tocsr()
            else:
                ha = sparse.csr_matrix((len(keys), len(activities)))
        else:
            ha = projection(activities)

    imports_a = (hc @ ua).tocsr()
    imports_y = (hc @ yc + ha @ ya).tocsr()
    if by == "product":
        row = positions(activities.get_level_values(0)[sr],
                        commodities[c_local].get_level_values(2)[sc])
        imports_c = sparse.coo_matrix(
            (sv, (row, sc)), shape=(len(keys), int(c_local.sum()))
        ).tocsr()
    else:
        raw = sparse.coo_matrix((sv, (sr, sc)),
                                shape=(len(activities), int(c_local.sum())))
        imports_c = (ha @ raw).tocsr()

    used = _active_rows(imports_a) | _active_rows(imports_c) | _active_rows(imports_y)
    # Keep the actual external classification, including zero-import rows.
    # Additional rows can arise from supply-side trade or observed reimports.
    if by is None:
        used |= np.array([origin not in selected for origin, _ in keys])
    else:
        nodes = commodities[~c_local] if by == "product" else activities[~a_local]
        used[positions(nodes.get_level_values(0), nodes.get_level_values(2))] = True
    labels = []
    for origin, item in np.array(keys, dtype=object)[used]:
        label = "imports"
        if by == "product":
            label += f" of {item}"
        elif by == "activity":
            label += f" by {item}"
        if trade_mode == "by_region":
            label += f" from {origin}"
        labels.append(label)
    if len(set(labels)) != len(labels):
        raise WrongInput("Import labels are ambiguous; rename the source items first.")
    return labels, imports_a[used], imports_c[used], imports_y[used]


def _export_columns(selected, excluded, fd, trade_mode, layout):
    types = ["Export"] if layout == "sectorized" else [
        "Final Demand exports", "Intermediate exports"
    ]
    labels = [f"{kind} to {r}" for kind in types for r in excluded] \
        if trade_mode == "by_region" else types
    columns = pd.MultiIndex.from_tuples(
        [(r, MI["n"], label) for r in selected for label in labels], names=fd.names
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


def transform(database, selected, *, trade_mode, layout, imports_by):
    """Stage a complete national/subset SUT before replacing the baseline."""
    blocks = read_flows(database, "baseline")
    activities, commodities = blocks["S"].index, blocks["S"].columns
    fd = blocks["Yc"].columns
    for axis in (activities, commodities, fd):
        if not isinstance(axis, pd.MultiIndex) or axis.nlevels != 3 or not axis.is_unique:
            raise WrongInput("SUT extraction requires unique Region/Level/Item axes.")
    regions = database.get_index(MI["r"])
    if any(not axis.get_level_values(0).isin(regions).all()
           for axis in (activities, commodities, fd)):
        raise WrongInput("SUT extraction found unknown regions in native axes.")
    excluded = [r for r in regions if r not in selected]
    a = activities.get_level_values(0).isin(selected)
    c = commodities.get_level_values(0).isin(selected)
    n = fd.get_level_values(0).isin(selected)
    local_a, local_c, local_n = activities[a], commodities[c], fd[n]
    rows_f, rows_e = blocks["Va"].index, blocks["Ea"].index
    regional_factors = isinstance(rows_f, pd.MultiIndex)
    if regional_factors and (rows_f.nlevels != 2 or rows_f.names[0] != MI["r"]):
        raise WrongInput(
            "SUT extraction supports common factor rows or Region/Factor of production rows."
        )
    native = {"S": _align(blocks["S"], activities, commodities),
              "U": _align(blocks["U"], commodities, activities),
              "Ya": _align(blocks["Ya"], activities, fd),
              "Yc": _align(blocks["Yc"], commodities, fd)}
    for prefix, rows in (("V", rows_f), ("E", rows_e)):
        for suffix, axis in (("a", activities), ("c", commodities), ("Y", fd)):
            name = prefix + suffix
            native[name] = _align(blocks[name], rows, axis)

    by = imports_by or ("product" if layout == "sectorized" else None)
    labels, import_a, import_c, import_y = _imports(
        *(native[name] for name in ("S", "U", "Ya", "Yc")),
        activities, commodities, fd, selected, by, trade_mode,
    )
    if set(labels) & set(database.get_index(MI["f"], flat=True)):
        raise WrongInput("Generated import labels collide with existing factors of production.")
    export_cols, export_labels = _export_columns(selected, excluded, fd, trade_mode, layout)
    if set(export_labels) & set(database.get_index(MI["n"], flat=True)):
        raise WrongInput("Generated export labels collide with existing consumption categories.")
    target_n = local_n.append(export_cols)
    output = {"S": native["S"][a, :][:, c], "U": native["U"][c, :][:, a]}
    for name, mask, axis, intermediate, buyers in (
        ("Ya", a, local_a, "S", commodities),
        ("Yc", c, local_c, "U", activities),
    ):
        exports = _exports(native[intermediate][mask], native[name][mask], axis,
                           buyers, fd, selected, excluded, trade_mode, layout, export_cols)
        output[name] = sparse.hstack([native[name][mask, :][:, n], exports], format="csr")

    import_rows = pd.Index(labels, name=rows_f.name)
    if regional_factors:
        import_rows = pd.MultiIndex.from_product([selected, labels], names=rows_f.names)

        def regionalize(matrix, cols):
            coo = matrix.tocoo()
            owner = pd.Index(selected).get_indexer(cols.get_level_values(0))
            return sparse.coo_matrix(
                (coo.data, (owner[coo.col] * len(labels) + coo.row, coo.col)),
                shape=(len(import_rows), len(cols)),
            ).tocsr()

        import_a, import_c, import_y = (
            regionalize(matrix, axis) for matrix, axis in
            ((import_a, local_a), (import_c, local_c), (import_y, local_n))
        )
    target_f = rows_f.append(import_rows)
    for name, mask, imports in (("Va", a, import_a), ("Vc", c, import_c)):
        output[name] = sparse.vstack([native[name][:, mask], imports], format="csr")
    output["VY"] = sparse.hstack([
        sparse.vstack([native["VY"][:, n], import_y], format="csr"),
        sparse.csr_matrix((len(target_f), len(export_cols))),
    ], format="csr")
    output["Ea"], output["Ec"] = native["Ea"][:, a], native["Ec"][:, c]
    output["EY"] = sparse.hstack([
        native["EY"][:, n], sparse.csr_matrix((len(rows_e), len(export_cols)))
    ], format="csr")
    axes = {
        "S": (local_a, local_c), "U": (local_c, local_a),
        "Ya": (local_a, target_n), "Yc": (local_c, target_n),
        "Va": (target_f, local_a), "Vc": (target_f, local_c),
        "Ea": (rows_e, local_a), "Ec": (rows_e, local_c),
        "EY": (rows_e, target_n), "VY": (target_f, target_n),
    }
    sparse_output = any(_is_sparse_backed_dataframe(frame) for frame in blocks.values()
                        if len(frame.columns))
    frames = {}
    for name, matrix in output.items():
        matrix.eliminate_zeros()
        if not np.isfinite(matrix.data).all():
            raise WrongInput("SUT import allocation produced non-finite flows.")
        index, columns = axes[name]
        frames[name] = (
            pd.DataFrame.sparse.from_spmatrix(matrix, index=index, columns=columns)
            if sparse_output else pd.DataFrame(matrix.toarray(), index=index, columns=columns)
        )

    indexes = deepcopy(dict(database._indeces))
    for code, values in (("r", selected), ("a", local_a.get_level_values(2)),
                         ("c", local_c.get_level_values(2)),
                         ("n", target_n.get_level_values(2)),
                         ("f", database.get_index(MI["f"], flat=True) + labels)):
        indexes[code] = {"main": list(dict.fromkeys(values))}
    units = {key: value.copy(deep=True) for key, value in database.units.items()}
    for code in ("a", "c"):
        units[MI[code]] = units[MI[code]].reindex(indexes[code]["main"])
    monetary_unit = database.units[MI["a"]]["unit"].iloc[0]
    for label in labels:
        units[MI["f"]].loc[label, "unit"] = monetary_unit

    database.matrices = {"baseline": frames}
    database._indeces = indexes
    database.units = units
    database.meta._add_history(
        f"Transformation: SUT region subset {selected}; imports by {by or 'total'}, "
        f"trade_mode={trade_mode}. Imported final demand is retained in VY."
    )
