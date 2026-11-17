"""IOT boundary accounting with semantic import sectors and source regions."""

from copy import deepcopy

import numpy as np
import pandas as pd
from scipy import sparse

from mario.compute.helpers import _is_sparse_backed_dataframe, sparse_frame_from_spmatrix
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from mario.ops.import_accounts import (
    _align, _export_columns, _exports,
    combine_factor_accounts, register_factor_layout,
)


def transform(database, selected, *, trade_resolution, layout, imports_by):
    blocks = {name: database.query(name) for name in ("Z", "Y", "V", "E")}
    productive, fd = blocks["Z"].index, blocks["Y"].columns
    for axis in (productive, fd):
        if (not isinstance(axis, pd.MultiIndex) or axis.nlevels not in (2, 3)
                or not axis.is_unique):
            raise WrongInput("IOT extraction requires unique regional productive/final-demand axes.")
    regions = database.get_index(MI["r"])
    if any(not axis.get_level_values(0).isin(regions).all() for axis in (productive, fd)):
        raise WrongInput("IOT extraction found unknown regions in native axes.")
    for name, source in (("EY", "E"), ("VY", "V")):
        blocks[name] = database.query(name) if database.has_matrix(name) else pd.DataFrame(
            0.0, index=blocks[source].index, columns=fd,
        )
    p = productive.get_level_values(0).isin(selected)
    n = fd.get_level_values(0).isin(selected)
    local_p, local_n = productive[p], fd[n]
    excluded = [r for r in regions if r not in selected]
    rows_f, rows_e = blocks["V"].index, blocks["E"].index
    values = {
        "Z": _align(blocks["Z"], productive, productive),
        "Y": _align(blocks["Y"], productive, fd),
        "V": _align(blocks["V"], rows_f, productive),
        "E": _align(blocks["E"], rows_e, productive),
        "VY": _align(blocks["VY"], rows_f, fd),
        "EY": _align(blocks["EY"], rows_e, fd),
    }
    classification = MI["s"] if imports_by == "sector" or layout == "sectorized" else None
    foreign = productive[~p]
    source_keys = [(origin if trade_resolution == "by_region" else None,
                    sector if classification else None)
                   for origin, sector in zip(foreign.get_level_values(0),
                                             foreign.get_level_values(-1))]
    import_keys = list(dict.fromkeys(source_keys))
    if not import_keys and trade_resolution == "aggregate":
        import_keys = [(None, None)]
    positions = {key: i for i, key in enumerate(import_keys)}
    projection = sparse.coo_matrix(
        (np.ones(len(foreign)),
         ([positions[key] for key in source_keys], np.arange(len(foreign)))),
        shape=(len(import_keys), len(foreign)),
    ).tocsr()
    imports_v = projection @ values["Z"][~p, :][:, p]
    imports_y = projection @ values["Y"][~p, :][:, n]
    target_f, accounts = combine_factor_accounts(
        database, rows_f,
        {"V": (values["V"][:, p], local_p), "VY": (values["VY"][:, n], local_n)},
        {"V": imports_v, "VY": imports_y}, import_keys,
        selected=selected, classification=classification, by_region=trade_resolution == "by_region",
    )
    export_cols, export_labels = _export_columns(selected, excluded, fd, trade_resolution, layout)
    if set(export_labels) & set(database.get_index(MI["n"], flat=True)):
        raise WrongInput("Generated export labels collide with existing consumption categories.")
    exports = _exports(values["Z"][p], values["Y"][p], local_p,
                       productive, fd, selected, excluded, trade_resolution, layout, export_cols)
    target_n = local_n.append(export_cols)
    output = {
        "Z": values["Z"][p, :][:, p],
        "Y": sparse.hstack([values["Y"][p, :][:, n], exports], format="csr"),
        "V": accounts["V"], "E": values["E"][:, p],
        "VY": sparse.hstack([accounts["VY"], sparse.csr_matrix((len(target_f), len(export_cols)))], format="csr"),
        "EY": sparse.hstack([values["EY"][:, n], sparse.csr_matrix((len(rows_e), len(export_cols)))], format="csr"),
    }
    if layout == "sectorized":
        local_p = pd.MultiIndex.from_arrays(
            [local_p.get_level_values(0), local_p.get_level_values(-1)],
            names=[MI["r"], MI["s"]],
        )
        target_n = pd.MultiIndex.from_arrays(
            [target_n.get_level_values(0), target_n.get_level_values(-1)],
            names=[MI["r"], MI["n"]],
        )
    axes = {"Z": (local_p, local_p), "Y": (local_p, target_n),
            "V": (target_f, local_p), "E": (rows_e, local_p),
            "VY": (target_f, target_n), "EY": (rows_e, target_n)}
    sparse_output = any(_is_sparse_backed_dataframe(frame) for frame in blocks.values()
                        if len(frame.columns))
    frames = {}
    for name, matrix in output.items():
        matrix.eliminate_zeros()
        if not np.isfinite(matrix.data).all():
            raise WrongInput("IOT extraction produced non-finite flows.")
        index, columns = axes[name]
        frames[name] = (
            sparse_frame_from_spmatrix(matrix, index=index, columns=columns)
            if sparse_output else pd.DataFrame(matrix.toarray(), index=index, columns=columns)
        )
    frames["X"] = pd.DataFrame(
        np.asarray(output["Z"].sum(axis=1) + output["Y"].sum(axis=1)).ravel(),
        index=local_p, columns=["production"],
    )
    indexes = deepcopy(dict(database._indeces))
    for code, items in (("r", selected), ("s", local_p.get_level_values(-1)),
                        ("n", target_n.get_level_values(-1)),
                        ("f", database.get_index(MI["f"], flat=True) + ["imports"])):
        indexes[code] = {"main": list(dict.fromkeys(items))}
    units = {key: value.copy(deep=True) for key, value in database.units.items()}
    units[MI["f"]].loc["imports", "unit"] = database.units[MI["s"]]["unit"].iloc[0]
    database.matrices = {"baseline": frames}
    database._indeces = indexes
    database.units = units
    from mario.model.configuration import update_configuration
    update_configuration(database, imports_by="sector" if classification else None,
                         trade_resolution=trade_resolution, import_representation="factor-accounts")
    register_factor_layout(database, target_f)
    database.meta._add_history(
        f"Transformation: IOT region subset {selected}; semantic imports by "
        f"{classification or 'total'}, trade_resolution={trade_resolution}. Final-demand imports retained in VY."
    )
