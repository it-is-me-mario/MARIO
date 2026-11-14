"""Convert national import accounts between two native accounting layouts."""

import pandas as pd

from mario.compute.helpers import sparse_frame_from_spmatrix

from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from mario.model.configuration import (
    configuration_values, import_blocks, separate_imports,
    update_configuration, validate_import_representation,
)
from mario.ops.import_accounts import (
    _csr, combine_factor_accounts, factor_row_values, register_factor_layout,
)


def _account_pairs(database):
    if database.table_type == "SUT":
        return (("Va", "IMP_a"), ("Vc", "IMP_c"), ("VY", "IMP_Y"))
    return (("V", "IMP"), ("VY", "IMP_Y"))


def _restore_import_detail(database):
    """Recover declared classifier levels from older factor-account exports."""
    values = configuration_values(database)
    reference = database.query(_account_pairs(database)[0][0])
    prefix, rows = factor_row_values(reference.index)
    imported = [dict(zip(prefix, row[:-1])) for row in rows if row[-1] == "imports"]
    classifiers = {MI["s"]: "sector", MI["a"]: "activity", MI["c"]: "commodity"}
    active = [label for label in classifiers if any(pd.notna(row.get(label)) for row in imported)]
    if len(active) > 1:
        raise WrongInput("Import rows require one declared productive classification.")
    if "imports_by" not in values:
        values["imports_by"] = classifiers[active[0]] if active else None
    if "import_origins" not in values:
        values["import_origins"] = (
            "by_region" if any(pd.notna(row.get(MI["r"])) for row in imported) else "aggregate"
        )
    update_configuration(database, **values)


def register_import_layout(database):
    """Declare observed import classifications without creating extra sets."""
    from mario.compute.import_catalog import import_catalog
    candidates = (*import_blocks(database), *import_blocks(database, "coefficients"))
    reference = next(database.get_block(name) for name in candidates if database.has_matrix(name))
    row_axes = tuple(name for name in reference.index.names if name not in (None, "Import account"))
    for name, spec in import_catalog(database.table_type).items():
        if name in {"p", "pa", "pc"}:
            continue
        database.register_block_spec(name=name, row_axes=row_axes, col_axes=spec.axes.cols, replace=True)


def _trim_factor_axis(axis):
    prefix, values = factor_row_values(axis)
    keep = [i for i in range(len(prefix)) if any(pd.notna(row[i]) for row in values)]
    names = tuple(prefix[i] for i in keep) + (MI["f"],)
    rows = [tuple(row[i] for i in keep) + (row[-1],) for row in values]
    if len(names) == 1:
        return pd.Index([row[-1] for row in rows], name="Item")
    return pd.MultiIndex.from_tuples(rows, names=names)


def _separate(database):
    output = {}
    factor_axis = None
    for scenario in database._storage_scenarios():
        database.reset_to_flows(scenario)
        frames = dict(database.matrices[scenario])
        for factor, imported in _account_pairs(database):
            frame = frames[factor]
            prefix, rows = factor_row_values(frame.index)
            mask = [row[-1] == "imports" for row in rows]
            if not any(mask):
                raise WrongInput("Separate imports require declared 'imports' accounts from regional extraction.")
            positions = [i for i, flag in enumerate(mask) if flag]
            imported_frame = frame.iloc[positions].copy()
            if prefix:
                labels = [rows[i][:-1] for i in positions]
                imported_frame.index = (
                    pd.Index([row[0] for row in labels], name=prefix[0])
                    if len(prefix) == 1 else pd.MultiIndex.from_tuples(labels, names=prefix)
                )
            else:
                imported_frame.index = pd.Index(["Total imports"], name="Import account")
            factors = frame.iloc[[i for i, flag in enumerate(mask) if not flag]].copy()
            factors.index = _trim_factor_axis(factors.index)
            factor_axis = factors.index
            frames[factor], frames[imported] = factors, imported_frame
        output[scenario] = frames
    database.matrices = output
    labels = list(dict.fromkeys(row[-1] for row in factor_row_values(factor_axis)[1]))
    database._indeces["f"] = {"main": labels}
    database.units[MI["f"]] = database.units[MI["f"]].reindex(labels)


def _combine(database):
    values = configuration_values(database)
    classification = {"commodity": MI["c"], "activity": MI["a"], "sector": MI["s"]}.get(values.get("imports_by"))
    by_region = values.get("import_origins") == "by_region"
    output = {}
    factor_axis = None
    for scenario in database._storage_scenarios():
        database.reset_to_flows(scenario)
        frames = dict(database.matrices[scenario])
        pairs = _account_pairs(database)
        imports = frames[pairs[0][1]]
        keys = []
        for row in imports.index:
            fields = dict(zip(imports.index.names, row if isinstance(row, tuple) else (row,)))
            keys.append((fields.get(MI["r"]) if by_region else None, fields.get(classification) if classification else None))
        originals = {name: (_csr(frames[name]), frames[name].columns) for name, _ in pairs}
        imported = {name: _csr(frames[block]) for name, block in pairs}
        factor_axis, accounts = combine_factor_accounts(
            database, frames[pairs[0][0]].index, originals, imported, keys,
            selected=database.get_index(MI["r"]), classification=classification, by_region=by_region,
        )
        for name, block in pairs:
            matrix = accounts[name]
            if any(isinstance(dtype, pd.SparseDtype) for dtype in frames[name].dtypes):
                frames[name] = sparse_frame_from_spmatrix(matrix, index=factor_axis, columns=frames[name].columns)
            else:
                frames[name] = pd.DataFrame(matrix.toarray(), index=factor_axis, columns=frames[name].columns)
            frames.pop(block)
        output[scenario] = frames
    database.matrices = output
    labels = list(dict.fromkeys(row[-1] for row in factor_row_values(factor_axis)[1]))
    database._indeces["f"] = {"main": labels}
    unit = values["import_unit"]
    database.units[MI["f"]].loc["imports", "unit"] = unit


def convert(database, representation):
    """Convert an isolated working copy, committing only validated flow states."""
    validate_import_representation(representation)
    if len(database.get_index(MI["r"])) != 1:
        raise WrongInput("Separate-import accounting is supported for single-region models.")
    current = "separate" if separate_imports(database) else "factor-accounts"
    if current == representation:
        return
    if representation == "separate":
        if "imports" not in database.units[MI["f"]].index:
            raise WrongInput("Separate imports require declared 'imports' accounts from regional extraction.")
        unit = database.units[MI["f"]].loc["imports", "unit"]
        _restore_import_detail(database)
        _separate(database)
        update_configuration(database, import_unit=unit, import_representation=representation)
    else:
        _combine(database)
        update_configuration(database, import_representation=representation)
    from mario.compute.import_catalog import import_catalog
    factor_names = {"V", "v", "VY", "m", "M", "Va", "Vc", "va", "vc", "ma", "mc", "Ma", "Mc"}
    for name in (*factor_names, *import_catalog(database.table_type)):
        database._custom_block_specs.pop(name, None)
    reference = database.get_block("Va" if database.table_type == "SUT" else "V")
    register_factor_layout(database, reference.index)
    if representation == "separate":
        register_import_layout(database)
    database.meta._add_history(f"Accounting: external imports use {representation}.")
