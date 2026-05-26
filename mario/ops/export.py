"""Export operations extracted from the ``Database`` class."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pymrio

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
                    if matrix_name in {_ENUM.V, _ENUM.v, "M", "m", _ENUM.VY} and side == "from":
                        mapping[_MASTER_INDEX["f"]] = value
                    elif matrix_name in {_ENUM.E, _ENUM.e, _ENUM.EY, _ENUM.F, _ENUM.f} and side == "from":
                        mapping[_MASTER_INDEX["k"]] = value
                    elif matrix_name in {_ENUM.Y, _ENUM.EY, _ENUM.VY} and side == "to":
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
    with (root / "metadata.json").open("w") as fp:
        json.dump(database.meta._to_dict(), fp)


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
    matrices = database.query(
        matrices=_FLAT_EXPORT_MATRICES[mode],
        scenarios=[scenario],
    )
    flat_data = pd.concat(
        [
            _matrix_to_flat_frame(matrix_name, matrices[matrix_name], scenario=scenario)
            for matrix_name in _FLAT_EXPORT_MATRICES[mode]
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

    for matrix_name in _FLAT_EXPORT_MATRICES[mode]:
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
        matrices=_MATRIX_EXPORT_MATRICES[mode],
        scenarios=[scenario],
    )

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

    log_time(logger, f"Export: writing Excel database for {scenario}.", "info")
    database_excel(
        database,
        flows,
        coefficients,
        database._getdir(path, "Database", "New_Database.xlsx"),
        scenario,
    )

    if include_meta:
        meta = database.meta._to_dict()
        meta_path = database._getdir(path, "Database", "")
        meta_path = meta_path.split("/")[:-1]
        meta_path = ("/").join(meta_path) + "/metadata.json"

        with open(meta_path, "w") as fp:
            json.dump(meta, fp)
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
        database_txt(
            database,
            flows,
            coefficients,
            str(export_root),
            scenario,
            _format,
            sep,
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
