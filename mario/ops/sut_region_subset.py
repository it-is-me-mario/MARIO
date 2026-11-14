"""Externalize a SUT boundary using native, sparse flow blocks."""

from copy import deepcopy

import numpy as np
import pandas as pd
from scipy import sparse

from mario.compute.helpers import _is_sparse_backed_dataframe, sparse_frame_from_spmatrix
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from mario.ops.chenery_moses import read_flows
from mario.ops.import_accounts import (
    _align, _export_columns, _exports,
    combine_factor_accounts, register_factor_layout,
)


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
        list(dict.fromkeys((commodities if by == "commodity" else activities)
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
        if by == "commodity":
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
    if by == "commodity":
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
        nodes = commodities[~c_local] if by == "commodity" else activities[~a_local]
        used[positions(nodes.get_level_values(0), nodes.get_level_values(2))] = True
    retained_keys = [key for key, keep in zip(keys, used) if keep]
    return retained_keys, imports_a[used], imports_c[used], imports_y[used]


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
    native = {"S": _align(blocks["S"], activities, commodities),
              "U": _align(blocks["U"], commodities, activities),
              "Ya": _align(blocks["Ya"], activities, fd),
              "Yc": _align(blocks["Yc"], commodities, fd)}
    for prefix, rows in (("V", rows_f), ("E", rows_e)):
        for suffix, axis in (("a", activities), ("c", commodities), ("Y", fd)):
            name = prefix + suffix
            native[name] = _align(blocks[name], rows, axis)

    by = imports_by or ("commodity" if layout == "sectorized" else None)
    import_keys, import_a, import_c, import_y = _imports(
        *(native[name] for name in ("S", "U", "Ya", "Yc")),
        activities, commodities, fd, selected, by, trade_mode,
    )
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

    classification = {"commodity": MI["c"], "activity": MI["a"]}.get(by)
    target_f, accounts = combine_factor_accounts(
        database, rows_f,
        {"Va": (native["Va"][:, a], local_a),
         "Vc": (native["Vc"][:, c], local_c),
         "VY": (native["VY"][:, n], local_n)},
        {"Va": import_a, "Vc": import_c, "VY": import_y}, import_keys,
        selected=selected, classification=classification,
        by_region=trade_mode == "by_region",
    )
    output["Va"], output["Vc"] = accounts["Va"], accounts["Vc"]
    output["VY"] = sparse.hstack([
        accounts["VY"],
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
            sparse_frame_from_spmatrix(matrix, index=index, columns=columns)
            if sparse_output else pd.DataFrame(matrix.toarray(), index=index, columns=columns)
        )

    indexes = deepcopy(dict(database._indeces))
    for code, values in (("r", selected), ("a", local_a.get_level_values(2)),
                         ("c", local_c.get_level_values(2)),
                         ("n", target_n.get_level_values(2)),
                         ("f", database.get_index(MI["f"], flat=True) + ["imports"])):
        indexes[code] = {"main": list(dict.fromkeys(values))}
    units = {key: value.copy(deep=True) for key, value in database.units.items()}
    monetary_unit = database.units[MI["a"]]["unit"].iloc[0]
    units[MI["f"]].loc["imports", "unit"] = monetary_unit

    database.matrices = {"baseline": frames}
    database._indeces = indexes
    database.units = units
    from mario.model.configuration import update_configuration
    update_configuration(database, imports_by=by, import_origins=trade_mode,
                         import_representation="factor-accounts")
    register_factor_layout(database, target_f)
    database.meta._add_history(
        f"Transformation: SUT region subset {selected}; imports by {by or 'total'}, "
        f"trade_mode={trade_mode}. Imported final demand is retained in VY."
    )
