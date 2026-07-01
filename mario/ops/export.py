"""Export operations extracted from the ``Database`` class."""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from contextlib import contextmanager
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pymrio

from mario._optional import require_pyarrow
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.log_exc.logger import log_time
from mario.ops.export_specs import (
    FLAT_AXIS_SETS,
    FLAT_DATA_COLUMNS,
    FLAT_UNIT_COLUMNS,
    PYMRIO_EXPORT_LAYOUTS,
)
from mario.model.conventions import _ENUM, _MASTER_INDEX
from mario.ops.excel import database_excel, database_txt
from mario.utils import pymrio_styling

logger = logging.getLogger(__name__)


_MATRIX_EXPORT_MATRICES = {
    "flows": [_ENUM.V, _ENUM.E, _ENUM.Z, _ENUM.Y, _ENUM.X, _ENUM.EY, _ENUM.VY],
    "coefficients": [_ENUM.v, _ENUM.e, _ENUM.z, _ENUM.Y, _ENUM.EY, _ENUM.VY],
}

_FLAT_EXPORT_MATRICES = {
    "flows": [_ENUM.V, _ENUM.E, _ENUM.Z, _ENUM.Y, _ENUM.EY, _ENUM.VY],
    "coefficients": [_ENUM.v, _ENUM.e, _ENUM.z, _ENUM.Y, _ENUM.EY, _ENUM.VY],
}

_SUT_NATIVE_MATRIX_EXPORT_MATRICES = {
    "flows": ["U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", _ENUM.EY, _ENUM.VY],
    "coefficients": ["u", "s", "Ya", "Yc", "va", "vc", "ea", "ec", _ENUM.EY, _ENUM.VY],
}


def _matrix_export_names(database, mode: str) -> list[str]:
    """Return the matrix names to export for one database and mode."""
    if database.table_type == "SUT":
        return _SUT_NATIVE_MATRIX_EXPORT_MATRICES[mode]
    return _MATRIX_EXPORT_MATRICES[mode]


def _flat_export_names(database, mode: str) -> list[str]:
    """Return the flat matrix names to export for one database and mode."""
    if database.table_type == "SUT":
        return _SUT_NATIVE_MATRIX_EXPORT_MATRICES[mode]
    return _FLAT_EXPORT_MATRICES[mode]


class _AxisOneGroupBy:
    """Proxy for legacy pandas ``groupby(axis=1).sum()`` calls."""

    def __init__(self, grouped):
        self._grouped = grouped

    def sum(self, *args, **kwargs):
        return self._grouped.sum(*args, **kwargs).T

    def __getattr__(self, name):
        return getattr(self._grouped, name)


@contextmanager
def _pandas_groupby_axis_compat():
    """Temporarily support legacy ``DataFrame.groupby(axis=1)`` calls."""
    if "axis" in inspect.signature(pd.DataFrame.groupby).parameters:
        yield
        return

    original_groupby = pd.DataFrame.groupby

    def groupby_with_axis(self, by=None, axis=0, level=None, *args, **kwargs):
        if axis in (1, "columns"):
            grouped = original_groupby(self.T, by=by, level=level, *args, **kwargs)
            return _AxisOneGroupBy(grouped)
        return original_groupby(self, by=by, level=level, *args, **kwargs)

    pd.DataFrame.groupby = groupby_with_axis
    try:
        yield
    finally:
        pd.DataFrame.groupby = original_groupby


def _install_pymrio_pandas3_compat() -> None:
    """Patch pymrio extension calculations for pandas 3 when needed."""
    if "axis" in inspect.signature(pd.DataFrame.groupby).parameters:
        return
    if getattr(pymrio.Extension.calc_system, "_mario_pandas3_compat", False):
        return

    original_calc_system = pymrio.Extension.calc_system

    def calc_system_with_pandas3_groupby(self, *args, **kwargs):
        with _pandas_groupby_axis_compat():
            return original_calc_system(self, *args, **kwargs)

    calc_system_with_pandas3_groupby._mario_pandas3_compat = True
    pymrio.Extension.calc_system = calc_system_with_pandas3_groupby


def _unit_keys(database) -> list[str]:
    """Return the logical unit-bearing levels for one database."""
    if database.table_type == "SUT":
        return [
            _MASTER_INDEX["a"],
            _MASTER_INDEX["c"],
            _MASTER_INDEX["f"],
            _MASTER_INDEX["k"],
        ]
    return [_MASTER_INDEX["s"], _MASTER_INDEX["f"], _MASTER_INDEX["k"]]


def _matrix_units_frame(database) -> pd.DataFrame:
    """Build the historical multi-index unit frame used by txt exports."""
    units = database.units
    combined = pd.DataFrame()
    level_labels: list[str] = []

    for key in _unit_keys(database):
        value = units[key]
        level_labels.extend([key] * value.shape[0])
        combined = pd.concat([combined, value])

    combined.index = [level_labels, combined.index]
    return combined


def _flat_units_frame(database) -> pd.DataFrame:
    """Build the canonical flat unit table."""
    rows: list[tuple[str, object, object]] = []
    for key in _unit_keys(database):
        value = database.units[key]
        for item, unit in value.iloc[:, 0].items():
            rows.append((key, item, "" if pd.isna(unit) else unit))
    return pd.DataFrame(rows, columns=FLAT_UNIT_COLUMNS)


def _axis_column_names(side: str) -> list[str]:
    """Return the canonical flat column names for one matrix axis."""
    suffix = "from" if side == "from" else "to"
    return [f"{item}_{suffix}" for item in FLAT_AXIS_SETS]


def _infer_axis_mapping(index, *, matrix_name: str, side: str) -> list[dict[str, object]]:
    """Map one public axis to flat set-specific columns."""
    if isinstance(index, pd.MultiIndex):
        names = tuple(name if name is not None else "Item" for name in index.names)
        values = [tuple(item) for item in index.tolist()]
    else:
        names = (index.name if index.name is not None else "Item",)
        values = [(item,) for item in index.tolist()]

    rows: list[dict[str, object]] = []
    for item in values:
        mapping = {label: "" for label in FLAT_AXIS_SETS}
        if names == (_MASTER_INDEX["r"], "Level", "Item"):
            region, level_name, entry = item
            if region not in ("", None) and not pd.isna(region):
                mapping[_MASTER_INDEX["r"]] = region
            mapping[level_name] = entry
        elif names == ("Level", "Item"):
            mapping[item[0]] = item[1]
        else:
            for name, value in zip(names, item):
                if name in FLAT_AXIS_SETS and value not in ("", None) and not pd.isna(value):
                    mapping[name] = value
                elif name == "Item":
                    # Legacy simple axes, mostly factors/extensions.
                    if matrix_name in {_ENUM.V, _ENUM.v, "Va", "va", "Vc", "vc", "M", "m", _ENUM.VY} and side == "from":
                        mapping[_MASTER_INDEX["f"]] = value
                    elif matrix_name in {_ENUM.E, _ENUM.e, "Ea", "ea", "Ec", "ec", _ENUM.EY, _ENUM.F, _ENUM.f} and side == "from":
                        mapping[_MASTER_INDEX["k"]] = value
                    elif matrix_name in {_ENUM.Y, "Ya", "Yc", _ENUM.EY, _ENUM.VY} and side == "to":
                        mapping[_MASTER_INDEX["n"]] = value
                    else:
                        mapping["Item"] = value
        rows.append(mapping)
    return rows


def _flat_axis_index(index, *, side: str, matrix_name: str) -> pd.MultiIndex:
    """Normalize one matrix axis to the canonical flat set-specific schema."""
    names = _axis_column_names(side)
    mappings = _infer_axis_mapping(index, matrix_name=matrix_name, side=side)
    arrays = [[mapping[label] for mapping in mappings] for label in FLAT_AXIS_SETS]
    return pd.MultiIndex.from_arrays(arrays, names=names)


def _matrix_to_flat_frame(matrix_name: str, frame: pd.DataFrame, *, scenario: str) -> pd.DataFrame:
    """Convert one matrix block into the canonical flat long format."""
    data = frame.copy()
    data.index = _flat_axis_index(data.index, side="from", matrix_name=matrix_name)
    data.columns = _flat_axis_index(data.columns, side="to", matrix_name=matrix_name)

    stack_levels = list(range(data.columns.nlevels))
    try:
        stacked = data.stack(stack_levels, future_stack=True)
    except TypeError:
        stacked = data.stack(stack_levels, dropna=False)

    flat = stacked.rename(FLAT_DATA_COLUMNS[-1]).reset_index()
    flat.insert(0, FLAT_DATA_COLUMNS[1], matrix_name)
    flat.insert(0, FLAT_DATA_COLUMNS[0], scenario)
    flat.columns = list(FLAT_DATA_COLUMNS)
    return flat


def _prepare_export_matrix(database, matrix_name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize one matrix just before writing it to disk."""
    if database.table_type != "SUT":
        return frame

    prepared = frame.copy()
    if matrix_name in {"Va", "Vc", "va", "vc", _ENUM.VY} and not isinstance(prepared.index, pd.MultiIndex):
        order = [item for item in database.get_index(_MASTER_INDEX["f"]) if item in prepared.index]
        if order:
            prepared = prepared.loc[order, :]
    elif matrix_name in {"Ea", "Ec", "ea", "ec", _ENUM.EY} and not isinstance(prepared.index, pd.MultiIndex):
        order = [item for item in database.get_index(_MASTER_INDEX["k"]) if item in prepared.index]
        if order:
            prepared = prepared.loc[order, :]

    return prepared


def _trim_flat_frame_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop flat axis columns that are empty for the whole export payload."""
    keep_columns = ["Scenario", "Matrix"]
    for side in ("from", "to"):
        for set_name in FLAT_AXIS_SETS:
            column = f"{set_name}_{side}"
            if column in frame.columns and frame[column].replace("", pd.NA).dropna().any():
                keep_columns.append(column)
    keep_columns.append("Value")
    return frame.loc[:, keep_columns]


def _write_text_frame(frame: pd.DataFrame, path: Path, *, sep: str) -> None:
    """Write one flat text payload."""
    frame.to_csv(path, index=False, sep=sep)


def _coerce_sparse_columns_to_dense(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a parquet-safe dataframe by densifying pandas sparse columns."""
    payload = frame.copy()
    for column in payload.columns:
        if isinstance(payload[column].dtype, pd.SparseDtype):
            payload[column] = payload[column].sparse.to_dense()
    return payload


def _write_parquet_frame(frame: pd.DataFrame, path: Path) -> None:
    """Write one dataframe payload as parquet."""
    _coerce_sparse_columns_to_dense(frame).to_parquet(path, index=False)


def _write_metadata_file(database, root: Path) -> None:
    """Write database metadata to one export directory."""
    root.mkdir(parents=True, exist_ok=True)
    database.save_meta(str(root / "metadata"), format="json")


def _export_flat_directory(
    database,
    *,
    root: Path,
    scenario: str,
    mode: str,
    writer,
    suffix: str,
    sep: str | None = None,
    separate_files: bool = False,
) -> None:
    """Export one scenario as a single flat data file plus units."""
    root.mkdir(parents=True, exist_ok=True)
    export_matrices = _flat_export_names(database, mode)
    matrices = database.query(
        matrices=export_matrices,
        scenarios=[scenario],
    )
    matrices = {
        matrix_name: _prepare_export_matrix(database, matrix_name, frame)
        for matrix_name, frame in matrices.items()
    }
    flat_data = pd.concat(
        [
            _matrix_to_flat_frame(matrix_name, matrices[matrix_name], scenario=scenario)
            for matrix_name in export_matrices
        ],
        ignore_index=True,
    )
    flat_data = _trim_flat_frame_columns(flat_data)
    units = _flat_units_frame(database)

    data_path = root / f"data.{suffix}"
    units_path = root / f"units.{suffix}"
    if sep is None:
        writer(flat_data, data_path)
        writer(units, units_path)
    else:
        writer(flat_data, data_path, sep=sep)
        writer(units, units_path, sep=sep)

    if not separate_files:
        return

    for matrix_name in export_matrices:
        flat_matrix = _matrix_to_flat_frame(
            matrix_name,
            matrices[matrix_name],
            scenario=scenario,
        )
        flat_matrix = _trim_flat_frame_columns(flat_matrix)
        matrix_path = root / f"{matrix_name}.{suffix}"
        if sep is None:
            writer(flat_matrix, matrix_path)
        else:
            writer(flat_matrix, matrix_path, sep=sep)


def _export_matrix_directory(
    database,
    *,
    root: Path,
    scenario: str,
    mode: str,
    suffix: str,
    sep: str | None = None,
) -> None:
    """Export one scenario as one file per matrix plus a units file."""
    root.mkdir(parents=True, exist_ok=True)
    matrices = database.query(
        matrices=_matrix_export_names(database, mode),
        scenarios=[scenario],
    )
    matrices = {
        matrix_name: _prepare_export_matrix(database, matrix_name, frame)
        for matrix_name, frame in matrices.items()
    }

    for key, value in matrices.items():
        target = root / f"{key}.{suffix}"
        if suffix == "parquet":
            _coerce_sparse_columns_to_dense(value).to_parquet(target)
        else:
            value.to_csv(target, header=True, index=True, sep=sep)

    units = _matrix_units_frame(database)
    units_path = root / f"units.{suffix}"
    if suffix == "parquet":
        _coerce_sparse_columns_to_dense(units).to_parquet(units_path)
    else:
        units.to_csv(units_path, header=True, index=True, sep=sep)


_FLOW_MATRIX_NAMES = {
    "Z", "Y", "V", "E", "EY", "VY", "X",
    "U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec",
}

_NUMERATOR_SET_PRIORITY = (
    _MASTER_INDEX["k"],
    _MASTER_INDEX["f"],
    _MASTER_INDEX["s"],
    _MASTER_INDEX["a"],
    _MASTER_INDEX["c"],
)

_DENOMINATOR_SET_PRIORITY = (
    _MASTER_INDEX["s"],
    _MASTER_INDEX["a"],
    _MASTER_INDEX["c"],
    _MASTER_INDEX["f"],
    _MASTER_INDEX["k"],
)

_META_HEADER_FIELDS = (
    "name",
    "year",
    "license",
    "version",
    "release_date",
    "tech_assumption",
    "table",
)

_FILENAME_META_FIELDS = ("name", "year", "table", "version", "tech_assumption")


def _unit_lookup(database) -> dict[str, dict[str, str]]:
    """Build one ``set -> {item: unit}`` lookup for unit-bearing levels."""
    lookups: dict[str, dict[str, str]] = {}
    for set_name in (
        _MASTER_INDEX["s"],
        _MASTER_INDEX["a"],
        _MASTER_INDEX["c"],
        _MASTER_INDEX["f"],
        _MASTER_INDEX["k"],
    ):
        try:
            frame = database.units[set_name]
        except KeyError:
            continue
        if frame is None or frame.shape[0] == 0:
            continue
        series = frame.iloc[:, 0]
        lookups[set_name] = {
            str(item): ("" if pd.isna(unit) else str(unit))
            for item, unit in series.items()
        }
    return lookups


def _resolve_side_units(
    flat: pd.DataFrame,
    lookups: dict[str, dict[str, str]],
    *,
    side: str,
    priority: tuple[str, ...],
) -> pd.Series:
    """Resolve one per-row unit token by walking one axis-set priority order."""
    resolved = pd.Series("", index=flat.index, dtype=object)
    filled = pd.Series(False, index=flat.index)
    for set_name in priority:
        column = f"{set_name}_{side}"
        if column not in flat.columns or set_name not in lookups:
            continue
        values = flat[column].astype(object)
        mask = (~filled) & values.ne("") & values.notna()
        if mask.any():
            resolved.loc[mask] = values.loc[mask].map(lookups[set_name]).fillna("")
            filled.loc[mask] = True
    return resolved


def _flat_units_column(
    flat: pd.DataFrame,
    lookups: dict[str, dict[str, str]],
    *,
    is_coefficient: bool,
) -> pd.Series:
    """Build the per-row Unit column for one flat matrix payload."""
    numerator = _resolve_side_units(
        flat, lookups, side="from", priority=_NUMERATOR_SET_PRIORITY
    )
    if not is_coefficient:
        return numerator

    denominator = _resolve_side_units(
        flat, lookups, side="to", priority=_DENOMINATOR_SET_PRIORITY
    )
    unit = numerator.copy()
    ratio_mask = numerator.ne("") & denominator.ne("")
    unit.loc[ratio_mask] = numerator.loc[ratio_mask] + "/" + denominator.loc[ratio_mask]
    return unit


def _get_export_matrix_frame(database, matrix_name: str, scenario: str) -> pd.DataFrame:
    """Return one matrix frame, supporting exploded ``*_ex`` accessors."""
    if matrix_name.endswith("_ex"):
        accessor = getattr(database, matrix_name, None)
        if accessor is None or not callable(accessor):
            raise WrongInput(f"Unknown exploded matrix accessor: {matrix_name!r}.")
        return accessor(scenario=scenario)

    return database.query(matrix_name, scenarios=[scenario])


def _normalize_export_filters(filters) -> dict[tuple[str, str | None], set[str]]:
    """Normalize the ``filters`` mapping to ``(set, side) -> allowed labels``.

    Keys may be a bare axis set (applied to both sides where it appears) or a
    side-specific ``"<set>_from"`` / ``"<set>_to"`` column name.
    """
    if filters is None:
        return {}
    if not isinstance(filters, MutableMapping):
        raise WrongInput(
            "filters must be one mapping of axis set (optionally suffixed with "
            "'_from'/'_to') to allowed labels."
        )

    normalized: dict[tuple[str, str | None], set[str]] = {}
    for key, values in filters.items():
        key_str = str(key)
        set_name: str = key_str
        side: str | None = None
        for suffix in ("_from", "_to"):
            candidate = key_str[: -len(suffix)]
            if key_str.endswith(suffix) and candidate in FLAT_AXIS_SETS:
                set_name, side = candidate, suffix[1:]
                break

        if set_name not in FLAT_AXIS_SETS:
            raise WrongInput(
                f"Unknown filter set {key_str!r}. Valid sets are {list(FLAT_AXIS_SETS)}, "
                "optionally suffixed with '_from' or '_to'."
            )

        allowed = [values] if isinstance(values, str) else list(values)
        if not allowed:
            raise WrongInput(f"filters[{key_str!r}] must list at least one label.")
        normalized.setdefault((set_name, side), set()).update(str(value) for value in allowed)

    return normalized


def _apply_export_filters(
    flat: pd.DataFrame, filters: dict[tuple[str, str | None], set[str]]
) -> pd.DataFrame:
    """Keep only rows matching every requested axis-label filter.

    A filter constrains a row only on the sides where its set is populated, so
    filtering by e.g. ``Satellite account`` leaves matrices without that axis
    untouched. Bare set keys apply to both the ``_from`` and ``_to`` columns.
    """
    if not filters:
        return flat

    mask = pd.Series(True, index=flat.index)
    for (set_name, side), allowed in filters.items():
        sides = [side] if side is not None else ["from", "to"]
        for current_side in sides:
            column = f"{set_name}_{current_side}"
            if column not in flat.columns:
                continue
            values = flat[column].astype(object)
            present = values.ne("") & values.notna()
            mask &= (~present) | values.isin(allowed)

    return flat.loc[mask]


def _matrix_flat_with_units(
    database,
    matrix_name: str,
    scenario: str,
    lookups: dict[str, dict[str, str]],
    filters: dict[tuple[str, str | None], set[str]],
) -> pd.DataFrame:
    """Build one untrimmed flat frame including the Unit column."""
    frame = _get_export_matrix_frame(database, matrix_name, scenario)
    if not isinstance(frame, pd.DataFrame):
        frame = frame.to_frame()
    frame = _prepare_export_matrix(database, matrix_name, frame)
    flat = _matrix_to_flat_frame(matrix_name, frame, scenario=scenario)
    is_coefficient = matrix_name not in _FLOW_MATRIX_NAMES
    unit = _flat_units_column(flat, lookups, is_coefficient=is_coefficient)
    flat.insert(len(flat.columns) - 1, "Unit", unit)
    return _apply_export_filters(flat, filters)


def _trim_flat_with_units(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop empty axis columns while keeping Scenario, Matrix, Unit and Value."""
    keep_columns = ["Scenario", "Matrix"]
    for side in ("from", "to"):
        for set_name in FLAT_AXIS_SETS:
            column = f"{set_name}_{side}"
            if column in frame.columns and frame[column].replace("", pd.NA).dropna().any():
                keep_columns.append(column)
    keep_columns.extend(["Unit", "Value"])
    return frame.loc[:, keep_columns]


def _meta_value(meta, field: str, scenario: str | None):
    """Resolve one metadata header value, combining name with the scenario."""
    if field == "name":
        base = getattr(meta, "name", None)
        base = "" if base is None else str(base)
        if scenario is None:
            return base
        return f"{base}_{scenario}" if base else str(scenario)

    value = getattr(meta, field, None)
    return "" if value is None else value


def _meta_header_frame(database, scenarios: list[str]) -> pd.DataFrame:
    """Build the one-row-per-scenario metadata header table."""
    rows = [
        {field: _meta_value(database.meta, field, scenario) for field in _META_HEADER_FIELDS}
        for scenario in scenarios
    ]
    return pd.DataFrame(rows, columns=list(_META_HEADER_FIELDS))


def _sanitize_filename_token(value) -> str:
    """Normalize one filename token to a filesystem-friendly slug."""
    text = str(value).strip()
    for character in (" ", "/", "\\", ":"):
        text = text.replace(character, "-")
    return text


def _export_filename(
    database,
    *,
    variable_token: str,
    suffix: str,
) -> str:
    """Compose one export filename from metadata and the split-specific token."""
    tokens: list[str] = []
    for field in _FILENAME_META_FIELDS:
        if field == "name":
            value = getattr(database.meta, "name", None)
            if value:
                tokens.append(_sanitize_filename_token(value))
            tokens.append(_sanitize_filename_token(variable_token))
        else:
            value = getattr(database.meta, field, None)
            if value not in (None, ""):
                tokens.append(_sanitize_filename_token(value))

    if not tokens:
        tokens.append(_sanitize_filename_token(variable_token))

    return f"{'_'.join(tokens)}.{suffix}"


def _disambiguate_variable_tokens(
    variable_field: str, variable_values: list[str]
) -> dict[str, str]:
    """Return collision-free filename tokens for one split axis.

    Matrix names that differ only in case (e.g. ``Z``/``z``) collide on
    case-insensitive filesystems, so the flow keeps its name while the
    coefficient is doubled (``z`` -> ``zz``); any residual collision gets a
    numeric suffix.
    """
    counts: dict[str, int] = {}
    for value in variable_values:
        counts[value.casefold()] = counts.get(value.casefold(), 0) + 1

    tokens: dict[str, str] = {}
    seen: dict[str, int] = {}
    for value in variable_values:
        token = value
        if (
            variable_field == "matrix"
            and counts[value.casefold()] > 1
            and value not in _FLOW_MATRIX_NAMES
        ):
            token = value * 2
        folded = token.casefold()
        seen[folded] = seen.get(folded, 0) + 1
        if seen[folded] > 1:
            token = f"{token}-{seen[folded]}"
        tokens[value] = token
    return tokens


def _write_flat_text_with_meta(
    data: pd.DataFrame,
    meta_frame: pd.DataFrame | None,
    path: Path,
    *,
    sep: str,
) -> None:
    """Write one flat text file, optionally prefixed by a metadata header block."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        if meta_frame is not None:
            meta_frame.to_csv(handle, index=False, sep=sep)
            handle.write("\n")
        data.to_csv(handle, index=False, sep=sep)


def _write_flat_parquet_with_meta(
    data: pd.DataFrame,
    meta_frame: pd.DataFrame | None,
    path: Path,
) -> None:
    """Write one flat parquet file, storing metadata in the schema key/value store."""
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(_coerce_sparse_columns_to_dense(data), preserve_index=False)
    if meta_frame is not None:
        existing = dict(table.schema.metadata or {})
        existing[b"mario_metadata"] = json.dumps(
            meta_frame.astype(object).where(meta_frame.notna(), None).to_dict(orient="records")
        ).encode("utf-8")
        table = table.replace_schema_metadata(existing)
    pq.write_table(table, path)


def export_database_matrices(
    database,
    *,
    matrices,
    scenarios="baseline",
    format: str = "csv",
    path=None,
    split: str = "scenario",
    include_meta: bool = False,
    sep: str = ",",
    filters=None,
    **meta_overrides,
) -> None:
    """Export selected matrices as flat, matrix-specific files.

    Parameters
    ----------
    matrices:
        One matrix name or an iterable of names. Standard MARIO matrices as
        well as exploded accessors (``f_ex``, ``m_ex``, ``p_ex`` and the SUT
        variants) are supported.
    scenarios:
        One scenario name or an iterable of scenario names to export.
    format:
        Output format, one of ``"csv"``, ``"txt"`` or ``"parquet"``.
    path:
        Output directory. Defaults to the database export directory.
    split:
        ``"scenario"`` writes one file per scenario (all matrices inside);
        ``"matrix"`` writes one file per matrix (all scenarios inside).
    include_meta:
        When ``True``, prepend one metadata row per scenario to each file
        (schema key/value metadata for parquet).
    sep:
        Column separator used for the ``csv``/``txt`` formats.
    filters:
        Optional mapping restricting which axis labels are exported, e.g.
        ``{"Satellite account": ["CO2"]}`` to export only the CO2 rows of the
        footprint matrices. Keys are axis sets, optionally suffixed with
        ``"_from"``/``"_to"`` to target a single side; a bare set name applies
        wherever that set appears. A filter constrains a matrix only on the
        sides where its set is populated, so matrices without that axis are
        left untouched.
    **meta_overrides:
        Metadata fields to set or override before exporting, e.g. ``license``,
        ``version`` or ``release_date``.
    """
    if isinstance(matrices, str):
        requested_matrices = [matrices]
    else:
        requested_matrices = list(dict.fromkeys(matrices))
    if not requested_matrices:
        raise WrongInput("matrices must be one non-empty matrix name or iterable of names.")

    if isinstance(scenarios, str):
        requested_scenarios = [scenarios]
    else:
        requested_scenarios = list(dict.fromkeys(scenarios))
    if not requested_scenarios:
        raise WrongInput("scenarios must be one non-empty scenario name or iterable of names.")

    available_scenarios = set(database.scenarios)
    unknown_scenarios = [s for s in requested_scenarios if s not in available_scenarios]
    if unknown_scenarios:
        raise WrongInput(
            f"Unknown scenarios: {unknown_scenarios}. Existing scenarios are {database.scenarios}."
        )

    format = str(format).strip().lower()
    if format not in {"csv", "txt", "parquet"}:
        raise WrongInput("format must be one of 'csv', 'txt' or 'parquet'.")

    if split not in {"scenario", "matrix"}:
        raise WrongInput("split must be either 'scenario' or 'matrix'.")

    normalized_filters = _normalize_export_filters(filters)

    for field, value in meta_overrides.items():
        setattr(database.meta, field, value)
        database.meta._add_history(f"Export: metadata field {field!r} set to {value!r}.")

    if format == "parquet":
        require_pyarrow(feature="Parquet matrix export")

    export_root = Path(database._getdir(path, "Database", ""))
    export_root.mkdir(parents=True, exist_ok=True)
    suffix = format
    lookups = _unit_lookup(database)

    log_time(
        logger,
        f"Export: writing {len(requested_matrices)} matrix/matrices for "
        f"{len(requested_scenarios)} scenario(s) as {format}, split by {split}.",
        "info",
    )

    # Build every (scenario, matrix) flat payload once.
    flat_frames: dict[tuple[str, str], pd.DataFrame] = {}
    for scenario in requested_scenarios:
        for matrix_name in requested_matrices:
            flat_frames[(scenario, matrix_name)] = _matrix_flat_with_units(
                database, matrix_name, scenario, lookups, normalized_filters
            )

    if split == "scenario":
        groups = [
            (
                "scenario",
                scenario,
                [scenario],
                [flat_frames[(scenario, m)] for m in requested_matrices],
            )
            for scenario in requested_scenarios
        ]
    else:
        groups = [
            (
                "matrix",
                matrix_name,
                requested_scenarios,
                [flat_frames[(s, matrix_name)] for s in requested_scenarios],
            )
            for matrix_name in requested_matrices
        ]

    variable_tokens = _disambiguate_variable_tokens(
        groups[0][0], [group[1] for group in groups]
    )

    for variable_field, variable_value, group_scenarios, frames in groups:
        data = _trim_flat_with_units(pd.concat(frames, ignore_index=True))
        meta_frame = _meta_header_frame(database, group_scenarios) if include_meta else None
        filename = _export_filename(
            database,
            variable_token=variable_tokens[variable_value],
            suffix=suffix,
        )
        target = export_root / filename
        if format == "parquet":
            _write_flat_parquet_with_meta(data, meta_frame, target)
        else:
            _write_flat_text_with_meta(data, meta_frame, target, sep=sep)

    log_time(logger, f"Export: matrix-specific {format} export written to {export_root}.", "info")


def export_database_to_excel(
    database,
    *,
    path=None,
    flows: bool = True,
    coefficients: bool = False,
    scenario: str = "baseline",
    include_meta: bool = False,
):
    """Export a database to the historical MARIO Excel format."""

    if scenario not in database.scenarios:
        raise WrongInput(
            "{} is not a valid scenario. Existing scenarios are {}".format(
                scenario, [*database.matrices]
            )
        )

    if flows is False and coefficients is False:
        raise WrongInput("At least one of the flows or coefficients should be True")

    output_path = Path(database._getdir(path, "Database", "New_Database.xlsx"))
    log_time(logger, f"Export: writing Excel database for {scenario}.", "info")
    database_excel(
        database,
        flows,
        coefficients,
        str(output_path),
        scenario,
    )

    if include_meta:
        _write_metadata_file(database, output_path.parent)
    log_time(logger, "Export: Excel database written.", "info")


def export_database_to_txt(
    database,
    *,
    path=None,
    flows: bool = True,
    coefficients: bool = False,
    scenario: str = "baseline",
    _format: str = "txt",
    include_meta: bool = False,
    sep: str = ",",
    flat: bool = False,
    separate_files: bool = False,
):
    """Export a database as multiple txt/csv files.

    When ``flat=False`` the historical matrix-per-file layout is used.
    When ``flat=True`` each mode is exported as one long-format ``data`` file
    plus a ``units`` file. When ``separate_files=True``, the same flat payload
    is also written as one trimmed long-format file per matrix.
    """

    if scenario not in database.scenarios:
        raise WrongInput(
            "{} is not a valid scenario. Existing scenarios are {}".format(
                scenario, [*database.matrices]
            )
        )

    if flows is False and coefficients is False:
        raise WrongInput("At least one of the flows or coefficients should be True")

    export_root = Path(database._getdir(path, "Database", ""))
    log_time(
        logger,
        f"Export: writing {_format} database for {scenario} in {'flat' if flat else 'matrix'} mode.",
        "info",
    )
    if flat:
        if flows:
            _export_flat_directory(
                database,
                root=export_root / "flows",
                scenario=scenario,
                mode="flows",
                writer=_write_text_frame,
                suffix=_format,
                sep=sep,
                separate_files=separate_files,
            )
        if coefficients:
            _export_flat_directory(
                database,
                root=export_root / "coefficients",
                scenario=scenario,
                mode="coefficients",
                writer=_write_text_frame,
                suffix=_format,
                sep=sep,
                separate_files=separate_files,
            )
    else:
        if flows:
            _export_matrix_directory(
                database,
                root=export_root / "flows",
                scenario=scenario,
                mode="flows",
                suffix=_format,
                sep=sep,
            )
        if coefficients:
            _export_matrix_directory(
                database,
                root=export_root / "coefficients",
                scenario=scenario,
                mode="coefficients",
                suffix=_format,
                sep=sep,
            )

    if include_meta:
        _write_metadata_file(database, export_root)
    log_time(logger, f"Export: {_format} database written.", "info")


def export_database_to_parquet(
    database,
    *,
    path=None,
    flows: bool = True,
    coefficients: bool = False,
    scenario: str = "baseline",
    include_meta: bool = False,
    flat: bool = False,
    separate_files: bool = False,
):
    """Export a database as parquet files.

    When ``flat=False`` each matrix is written to its own parquet file.
    When ``flat=True`` each mode is written as one long-format ``data.parquet``
    file plus a ``units.parquet`` companion. When ``separate_files=True``, the
    same flat payload is also written as one trimmed parquet file per matrix.
    """

    if scenario not in database.scenarios:
        raise WrongInput(
            "{} is not a valid scenario. Existing scenarios are {}".format(
                scenario, [*database.matrices]
            )
        )

    if flows is False and coefficients is False:
        raise WrongInput("At least one of the flows or coefficients should be True")

    require_pyarrow(feature="Parquet export")

    export_root = Path(database._getdir(path, "Database", ""))
    log_time(
        logger,
        f"Export: writing parquet database for {scenario} in {'flat' if flat else 'matrix'} mode.",
        "info",
    )

    if flat:
        if flows:
            _export_flat_directory(
                database,
                root=export_root / "flows",
                scenario=scenario,
                mode="flows",
                writer=_write_parquet_frame,
                suffix="parquet",
                separate_files=separate_files,
            )
        if coefficients:
            _export_flat_directory(
                database,
                root=export_root / "coefficients",
                scenario=scenario,
                mode="coefficients",
                writer=_write_parquet_frame,
                suffix="parquet",
                separate_files=separate_files,
            )
    else:
        if flows:
            _export_matrix_directory(
                database,
                root=export_root / "flows",
                scenario=scenario,
                mode="flows",
                suffix="parquet",
            )
        if coefficients:
            _export_matrix_directory(
                database,
                root=export_root / "coefficients",
                scenario=scenario,
                mode="coefficients",
                suffix="parquet",
            )

    if include_meta:
        _write_metadata_file(database, export_root)
    log_time(logger, "Export: parquet database written.", "info")


def export_database_to_pymrio(
    database,
    *,
    satellite_account: str = "satellite_account",
    factor_of_production: str = "factor_of_production",
    include_meta: bool = True,
    scenario: str = "baseline",
    **kwargs,
):
    """Convert an IOT database into a pymrio.IOSystem."""

    if database.table_type != "IOT":
        raise NotImplementable("pymrio supports only IO tables.")

    if any([" " in item for item in [satellite_account, factor_of_production]]):
        raise WrongInput(
            "satellte_account and factor_of_production does not accept values containing space."
        )

    _install_pymrio_pandas3_compat()

    log_time(logger, f"Export: building pymrio IOSystem for {scenario}.", "info")
    matrices = database.query(
        matrices=[_ENUM.V, _ENUM.Z, _ENUM.Y, _ENUM.E, _ENUM.EY],
        scenarios=[scenario],
    )

    factor_input = pymrio.Extension(
        name=factor_of_production,
        F=pymrio_styling(df=matrices[_ENUM.V], **PYMRIO_EXPORT_LAYOUTS["V"]),
        unit=database.units[_MASTER_INDEX["f"]],
    )

    satellite = pymrio.Extension(
        name=satellite_account,
        F=pymrio_styling(df=matrices[_ENUM.E], **PYMRIO_EXPORT_LAYOUTS["E"]),
        F_Y=pymrio_styling(df=matrices[_ENUM.EY], **PYMRIO_EXPORT_LAYOUTS["EY"]),
        unit=database.units[_MASTER_INDEX["k"]],
    )

    units = pd.DataFrame(
        data=np.tile(
            database.units[_MASTER_INDEX["s"]].values,
            (len(database.get_index(_MASTER_INDEX["r"])), 1),
        ),
        index=matrices[_ENUM.Z].index,
        columns=["unit"],
    )

    io = pymrio.IOSystem(
        Z=pymrio_styling(df=matrices[_ENUM.Z], **PYMRIO_EXPORT_LAYOUTS["Z"]),
        Y=pymrio_styling(df=matrices[_ENUM.Y], **PYMRIO_EXPORT_LAYOUTS["Y"]),
        unit=units,
        **kwargs,
    )

    setattr(io, satellite_account, satellite)
    setattr(io, factor_of_production, factor_input)

    io.meta.note("IOSystem and Extension initliazied by mario")

    if include_meta:
        for note in database.meta._history:
            io.meta.note(f"mario HISTORY - {note}")

    log_time(logger, "Export: pymrio IOSystem ready.", "info")
    return io
