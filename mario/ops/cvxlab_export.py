"""Populate CVXLab model inputs from explicitly mapped MARIO coordinates."""

from collections.abc import Mapping
from contextlib import contextmanager
from copy import copy
import logging
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

import numpy as np
from openpyxl import load_workbook
import pandas as pd

from mario.log_exc.exceptions import WrongInput
from mario.ops import cvxlab_bridge
from mario.ops.export import _matrix_flat_with_units, _trim_flat_with_units, _unit_lookup
from mario.ops.export_specs import FLAT_AXIS_SETS


logger = logging.getLogger(__name__)


def _key(value):
    """Normalize nonempty workbook coordinates for matching."""
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    return str(value)


def _headers(sheet):
    headers = {cell.value: cell.column for cell in sheet[1] if cell.value is not None}
    if len(headers) != sum(cell.value is not None for cell in sheet[1]):
        raise WrongInput(f"CVXLab sheet {sheet.title} contains duplicate column headers.")
    return headers


def _payloads(database, mapping, scenarios):
    if not isinstance(mapping, Mapping) or set(mapping) != {"sets", "matrices"}:
        raise WrongInput("mapping must contain 'sets' and 'matrices' dictionaries.")
    if not all(isinstance(mapping[name], Mapping) for name in mapping):
        raise WrongInput("mapping['sets'] and mapping['matrices'] must be dictionaries.")
    matrices = mapping["matrices"]
    if not matrices or any(
        not isinstance(key, str) or not key or not isinstance(value, str) or not value
        for key, value in matrices.items()
    ):
        raise WrongInput("Matrix mappings require nonempty MARIO and CVXLab table names.")
    try:
        selected = [scenarios] if isinstance(scenarios, str) else list(dict.fromkeys(scenarios))
    except TypeError as error:
        raise WrongInput("scenarios must name one scenario or an iterable of scenario names.") from error
    if not selected or any(name not in database.scenarios for name in selected):
        raise WrongInput(f"Select existing scenarios from {database.scenarios}.")
    valid_sets = {"Scenario", *FLAT_AXIS_SETS}
    valid_sets.update(f"{name}_{side}" for name in FLAT_AXIS_SETS for side in ("from", "to"))
    set_map = []
    for source, targets in mapping["sets"].items():
        if source not in valid_sets:
            raise WrongInput(f"Unknown MARIO set coordinate {source!r}.")
        targets = [targets] if isinstance(targets, str) else targets
        if not isinstance(targets, (list, tuple)) or not targets or any(
            not isinstance(target, str) or not target for target in targets
        ):
            raise WrongInput("Set mappings require a CVXLab set name or a nonempty list of names.")
        set_map.extend((source, target) for target in targets)
    lookups = _unit_lookup(database)
    payloads = {}
    for matrix in matrices:
        frames = [_matrix_flat_with_units(database, matrix, scenario, lookups, {}) for scenario in selected]
        frame = _trim_flat_with_units(pd.concat(frames, ignore_index=True))
        values = pd.to_numeric(frame["Value"], errors="raise")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise WrongInput(f"Matrix {matrix} contains non-finite values.")
        payloads[matrix] = frame
    return selected, set_map, payloads


def _source_fields(source, frame):
    if source in frame:
        return [source]
    return [f"{source}_{side}" for side in ("from", "to") if f"{source}_{side}" in frame]


def _set_chain(sets, name):
    chain = [name]
    while sets[name].copy_from:
        name = sets[name].copy_from
        if name in chain:
            raise WrongInput(f"Circular CVXLab copy_from declaration for {name}.")
        chain.append(name)
    return chain


def _order_set_definitions(path, order):
    """Write dependencies before copy_from aliases in the exported settings."""
    book = load_workbook(path)
    sheet = book[cvxlab_bridge.cl.Defaults.ConfigFiles.SETUP_INFO[0]]
    rows = [[copy(cell) for cell in row] for row in sheet.iter_rows(min_row=2)]
    positions = {name: position for position, name in enumerate(order)}
    ordered = sorted(rows, key=lambda row: positions.get(row[0].value, len(positions)))
    for row_number, row in enumerate(ordered, start=2):
        for source in row:
            cell = sheet.cell(row_number, source.column)
            cell.value = source.value
            cell._style = copy(source._style)
            cell.comment = copy(source.comment)
            cell.hyperlink = copy(source.hyperlink)
    book.save(path)
    book.close()


def _populate_sets(database, model, existing, path, set_map, matrix_map, payloads, scenarios):
    sets = model.core.index.sets
    unknown = [target for _, target in set_map if target not in sets]
    if unknown:
        raise WrongInput(f"Unknown CVXLab sets {unknown}.")
    template = load_workbook(path)
    book = load_workbook(existing) if existing.is_file() else template
    members = {}
    for source, target in set_map:
        values = []
        for matrix, frame in payloads.items():
            if target not in model.core.index.data[matrix_map[matrix]].coordinates:
                continue
            for field in _source_fields(source, frame):
                values.extend(value for value in frame[field].map(_key) if value is not None)
        if source == "Scenario":
            values = scenarios
        if not values:
            base = source.removesuffix("_from").removesuffix("_to")
            values = database.get_index(base, flat=True)
        root = _set_chain(sets, target)[-1]
        members.setdefault(root, []).extend(values)
    for name, table in sets.items():
        if table.copy_from:
            continue
        sheet_name = table.table_name
        if sheet_name not in book.sheetnames:
            sheet = book.create_sheet(sheet_name)
        else:
            sheet = book[sheet_name]
        headers = _headers(sheet)
        for header in table.set_excel_file_headers:
            if header not in headers:
                column = max(headers.values(), default=0) + 1
                sheet.cell(1, column, header)
                headers[header] = column
        column = headers[table.set_name_header]
        labels = [_key(sheet.cell(row, column).value) for row in range(2, sheet.max_row + 1)]
        present = [value for value in labels if value is not None]
        if len(present) != len(set(present)):
            raise WrongInput(f"CVXLab set {name} contains duplicate members.")
        known = set(present)
        for value in members.get(name, []):
            label = _key(value)
            if label is not None and label not in known:
                sheet.cell(sheet.max_row + 1, column, label)
                known.add(label)
    book.save(path)
    book.close()
    if book is not template:
        template.close()
    ordered = {}
    for name in sets:
        for dependency in reversed(_set_chain(sets, name)):
            ordered[dependency] = sets[dependency]
    model.core.index.sets = ordered
    _order_set_definitions(path.parent / cvxlab_bridge.cl.Defaults.ConfigFiles.SETUP_XLSX_FILE, ordered)
    model.core.index.load_sets_data_to_index(excel_file_name=path.name, excel_file_dir_path=path.parent)
    pending_sets = []
    missing_attributes = {}
    for name, table in sets.items():
        if not table.set_items or any(_key(value) is None for value in table.set_items):
            pending_sets.append(name)
        missing = [column for column in table.set_excel_file_headers if column != table.set_name_header
                   and table.data[column].map(_key).isna().any()]
        if missing:
            missing_attributes[name] = missing
    return pending_sets, missing_attributes


def _generate_inputs(model, pending_sets):
    """Use CVXLab's coordinate and file APIs, including partially filled models."""
    index = model.core.index
    index.load_coordinates_to_data_index()
    index.load_all_coordinates_to_variables_index()
    index.filter_coordinates_in_variables_index()
    exogenous = {name: table for name, table in index.data.items() if table.type == "exogenous"}
    populated = {variable.related_table for variable in index.variables.values()
                 if all(values is not None and len(values) > 0
                        for values in variable.all_coordinates_w_headers.values())}
    ready = {name: table for name, table in exogenous.items()
             if name in populated and not set(table.coordinates).intersection(pending_sets)}
    original_data = index.data
    original_variables = index.variables
    try:
        index.data = ready
        index.variables = {name: variable for name, variable in original_variables.items()
                           if variable.related_table in ready}
        if ready:
            model.core.database.generate_blank_sqlite_data_tables()
            model.core.database.sets_data_to_sql_data_tables()
            model.core.database.generate_blank_data_input_files(table_key_list=list(ready))
    finally:
        index.data = original_data
        index.variables = original_variables
    directory = Path(model.paths.input_data_dir)
    directory.mkdir(exist_ok=True)
    filename = cvxlab_bridge._single_input_file_name("xlsx")
    for name, table in exogenous.items():
        if name not in ready:
            model.files.dataframe_to_excel(
                dataframe=pd.DataFrame(columns=["id", *table.coordinates_headers.values(), "values"]),
                excel_filename=filename, excel_dir_path=directory, sheet_name=name, force_overwrite=True,
            )
    return directory / filename, exogenous


def _mapped_values(matrix, frame, table, sets, set_map):
    coordinates = {}
    consumed = set()
    for source, target in set_map:
        if target not in table.coordinates_headers:
            continue
        header = table.coordinates_headers[target]
        for field in _source_fields(source, frame):
            labels = frame[field].map(_key)
            if labels.isna().any():
                raise WrongInput(f"Matrix {matrix} has empty labels in mapped coordinate {field}.")
            if header in coordinates and not coordinates[header].equals(labels):
                raise WrongInput(f"Matrix {matrix} maps distinct axes to the same CVXLab coordinate {target}.")
            coordinates[header] = labels
            consumed.add(field)
    for field in frame.columns.difference(["Matrix", "Unit", "Value", *consumed]):
        if frame[field].map(_key).nunique() > 1:
            raise WrongInput(f"Matrix {matrix} requires a set mapping for {field}.")
    pending = []
    for name, header in table.coordinates_headers.items():
        if header not in coordinates:
            items = sets[name].set_items or []
            if len(items) == 1 and _key(items[0]) is not None:
                coordinates[header] = pd.Series(_key(items[0]), index=frame.index)
            else:
                pending.append(name)
    if pending:
        return None, pending
    updates = pd.DataFrame(coordinates)
    if updates.duplicated().any():
        raise WrongInput(f"Matrix {matrix} has ambiguous CVXLab coordinates. Map all varying axes.")
    updates["values"] = frame["Value"]
    return updates, []


def _merge_inputs(generated, existing, exogenous, updates):
    template = load_workbook(generated)
    book = load_workbook(existing) if existing.is_file() else template
    counts = {}
    unmatched = {}
    missing_values = {}
    extra_input_rows = {}
    for name, table in exogenous.items():
        if name in book.sheetnames and name not in updates and book is not template:
            continue
        sheet = book[name] if name in book.sheetnames else book.create_sheet(name)
        headers = _headers(sheet)
        source = template[name]
        for cell in source[1]:
            if cell.value is not None and cell.value not in headers:
                column = max(headers.values(), default=0) + 1
                sheet.cell(1, column, cell.value)
                headers[cell.value] = column
        keys = list(table.coordinates_headers.values())
        rows = {}
        for row in range(2, sheet.max_row + 1):
            key = tuple(_key(sheet.cell(row, headers[field]).value) for field in keys)
            if all(value is None for value in key):
                continue
            if key in rows:
                raise WrongInput(f"CVXLab input table {name} contains duplicate coordinates.")
            rows[key] = row
        source_headers = {cell.value: cell.column for cell in source[1] if cell.value is not None}
        allowed = set()
        for cells in source.iter_rows(min_row=2, values_only=True):
            key = tuple(_key(cells[source_headers[field] - 1]) for field in keys)
            allowed.add(key)
            if key not in rows:
                row = sheet.max_row + 1
                for header, column in source_headers.items():
                    sheet.cell(row, headers[header], cells[column - 1])
                rows[key] = row
            elif "id" in source_headers:
                sheet.cell(rows[key], headers["id"], cells[source_headers["id"] - 1])
        count = 0
        extra = 0
        payload = updates.get(name)
        if payload is not None:
            for record in payload[[*keys, "values"]].itertuples(index=False, name=None):
                key = tuple(record[:-1])
                if key in allowed:
                    sheet.cell(rows[key], headers["values"], float(record[-1]))
                    count += 1
                else:
                    extra += 1
        counts[name] = count
        if extra:
            unmatched[name] = extra
        outside = len(set(rows).difference(allowed))
        if outside:
            extra_input_rows[name] = outside
        missing = sum(_key(sheet.cell(rows[key], headers["values"]).value) is None for key in allowed)
        if missing:
            missing_values[name] = missing
    book.save(generated)
    book.close()
    if book is not template:
        template.close()
    return counts, unmatched, missing_values, extra_input_rows


@contextmanager
def _destination_lock(destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock = destination.parent / f".{destination.name}.mario-cvxlab-lock"
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise WrongInput(f"Another MARIO CVXLab export is using {destination}.") from error
    try:
        yield
    finally:
        lock.rmdir()


def _fingerprint(path):
    return (path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else None


def _commit_files(files, destination, originals, backup):
    if any(_fingerprint(destination / name) != stamp for name, stamp in originals.items()):
        raise WrongInput("CVXLab files changed during export. Retry with the current files.")
    attempted = []
    try:
        for name, source in files.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                saved = backup / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            attempted.append(name)
            os.replace(source, target)
    except BaseException:
        for name in reversed(attempted):
            target = destination / name
            saved = backup / name
            if saved.exists():
                os.replace(saved, target)
            else:
                target.unlink(missing_ok=True)
        raise


def export_to_cvxlab(database, *, model_settings, path, mapping, scenarios="baseline"):
    """Prepare mapped CVXLab workbooks in isolation, then commit their updates."""
    if cvxlab_bridge.cl is None:
        raise ImportError("to_cvxlab() requires the optional 'cvxlab' package.")
    source = Path(model_settings).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".xlsx":
        raise WrongInput("model_settings must point to a CVXLab settings .xlsx workbook.")
    destination = Path(path).expanduser().resolve()
    selected, set_map, payloads = _payloads(database, mapping, scenarios)
    config = cvxlab_bridge.cl.Defaults.ConfigFiles
    relative_inputs = Path(config.INPUT_DATA_DIR) / cvxlab_bridge._single_input_file_name("xlsx")
    names = [Path(config.SETUP_XLSX_FILE), Path(config.SETS_FILE), relative_inputs]
    with _destination_lock(destination), TemporaryDirectory(prefix=".mario-cvxlab-", dir=destination.parent) as temporary:
        root = Path(temporary)
        stage = root / "model"
        stage.mkdir()
        originals = {name: _fingerprint(destination / name) for name in names}
        shutil.copy2(source, stage / names[0])
        model = cvxlab_bridge._build_cvxlab_model(
            main_dir_path=root, model_dir_name="model", input_data_files_type="xlsx", import_custom=False,
        )
        exogenous = {name: table for name, table in model.core.index.data.items() if table.type == "exogenous"}
        unknown = set(mapping["matrices"].values()).difference(exogenous)
        if unknown:
            raise WrongInput(f"Map matrices to CVXLab exogenous input tables. Unknown tables {sorted(unknown)}.")
        pending_sets, missing_attributes = _populate_sets(
            database, model, destination / names[1], stage / names[1], set_map,
            mapping["matrices"], payloads, selected,
        )
        generated, exogenous = _generate_inputs(model, pending_sets)
        grouped = {}
        pending_matrices = {}
        for matrix, target in mapping["matrices"].items():
            values, pending = _mapped_values(
                matrix, payloads[matrix], exogenous[target], model.core.index.sets, set_map,
            )
            grouped.setdefault(target, [])
            if pending:
                pending_matrices[matrix] = pending
            else:
                grouped[target].append(values)
        updates = {}
        for target, frames in grouped.items():
            if not frames:
                updates[target] = None
                continue
            combined = pd.concat(frames, ignore_index=True)
            keys = list(exogenous[target].coordinates_headers.values())
            duplicates = combined.duplicated(subset=keys, keep=False)
            if duplicates.any():
                coordinate = combined.loc[duplicates, keys].iloc[0].to_dict()
                raise WrongInput(f"Matrices mapped to CVXLab table {target} overlap at {coordinate}.")
            updates[target] = combined
        counts, unmatched, missing_values, extra_input_rows = _merge_inputs(
            generated, destination / relative_inputs, exogenous, updates,
        )
        _commit_files({name: stage / name for name in names}, destination, originals, root / "backup")
    report = {
        "path": destination,
        "sets_file": destination / names[1],
        "input_files": [destination / relative_inputs],
        "written_cells": counts,
        "pending_sets": pending_sets,
        "missing_attributes": missing_attributes,
        "pending_matrices": pending_matrices,
        "unmapped_tables": sorted(set(exogenous).difference(mapping["matrices"].values())),
        "unmatched_coordinates": unmatched,
        "missing_values": missing_values,
        "extra_input_rows": extra_input_rows,
    }
    if pending_sets or pending_matrices or missing_attributes or unmatched or missing_values or extra_input_rows:
        logger.warning("CVXLab export needs additional data. Inspect the returned export report.")
    return report
