"""Parser helpers for GTAP-style MRIO bundles.

The current implementation targets the GTAP Power MRIO layout that was used in
the historical MARIO branch. The parser surface is structured so new GTAP
branches can be added later without changing the public entry point shape.

Internally the parser uses a dense-block assembly engine: every record is
mapped onto integer axis positions and accumulated directly into preallocated
dense matrices (``np.add.at``). This keeps the build cost proportional to the
number of records instead of the size of the cartesian label space, and it
gives duplicated record keys well-defined sum semantics -- recent GTAP csv
exports flatten several GDX symbols (for example combustion and non-combustion
emissions) into one file, so the same key can legitimately appear more than
once.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.matrix_layouts import (
    iot_block_specs_for_matrix_layouts,
    iot_row_layout,
    normalize_matrix_layouts,
)
from mario.parsers.specs import (
    GTAP_INPUT_FORMATS,
    GTAP_LAYOUTS,
    GTAP_MONETARY_UNIT,
    GTAP_POWER_MRIO_CSV_FILES,
    GTAP_POWER_MRIO_GDX_FILES,
    GTAP_POWER_MRIO_SOURCE,
    GTAP_VARIANTS,
)
from mario.utils import delete_duplicates, rename_index, sort_frames

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GTAPLayout:
    """Filesystem layout and metadata for one GTAP parse request."""

    root: Path
    variant: str
    layout: str
    input_format: str
    region_workbook: Path | None = None

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        variant_label = self.variant.upper() if self.variant != "power" else "Power"
        return f"GTAP {variant_label} {self.layout}"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        return GTAP_POWER_MRIO_SOURCE


def _normalize_gtap_variant(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in {item.lower() for item in GTAP_VARIANTS}:
        raise WrongInput(f"GTAP variant should be one of {list(GTAP_VARIANTS)}.")
    return normalized


def _normalize_gtap_layout(value: str) -> str:
    normalized = str(value).strip().upper()
    if normalized not in {item.upper() for item in GTAP_LAYOUTS}:
        raise WrongInput(f"GTAP layout should be one of {list(GTAP_LAYOUTS)}.")
    return normalized


def _normalize_gtap_input_format(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in {item.lower() for item in GTAP_INPUT_FORMATS}:
        raise WrongInput(f"GTAP input_format should be one of {list(GTAP_INPUT_FORMATS)}.")
    return normalized


def _expected_gtap_files(*, variant: str, layout: str, input_format: str) -> dict[str, str]:
    if variant != "power" or layout != "MRIO":
        raise NotImplementedError("Only GTAP Power MRIO is currently implemented.")
    if input_format == "csv":
        return dict(GTAP_POWER_MRIO_CSV_FILES)
    if input_format == "gdx":
        return dict(GTAP_POWER_MRIO_GDX_FILES)
    raise ValueError(input_format)


def detect_gtap_layout(
    path: str | Path,
    *,
    variant: str = "power",
    layout: str = "MRIO",
    input_format: str = "auto",
) -> GTAPLayout:
    """Resolve one GTAP bundle root and its input format.

    Parameters
    ----------
    path:
        Directory containing the GTAP bundle or one file inside that directory.
    variant:
        GTAP family. Only ``power`` is currently implemented.
    layout:
        GTAP bundle layout. Only ``MRIO`` is currently implemented.
    input_format:
        One of ``auto``, ``csv`` or ``gdx``.
    """

    normalized_variant = _normalize_gtap_variant(variant)
    normalized_layout = _normalize_gtap_layout(layout)
    normalized_format = _normalize_gtap_input_format(input_format)

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    root = source if source.is_dir() else source.parent
    region_workbook = root / "162regions.xlsx"

    def _available(fmt: str) -> tuple[bool, list[str]]:
        expected = _expected_gtap_files(
            variant=normalized_variant,
            layout=normalized_layout,
            input_format=fmt,
        )
        missing = [filename for filename in expected.values() if not (root / filename).exists()]
        return len(missing) == 0, missing

    if normalized_format == "auto":
        csv_ok, csv_missing = _available("csv")
        gdx_ok, gdx_missing = _available("gdx")
        if csv_ok:
            normalized_format = "csv"
        elif gdx_ok:
            normalized_format = "gdx"
        else:
            raise WrongInput(
                "The selected directory does not contain a complete GTAP Power MRIO bundle. "
                f"Missing CSV files: {csv_missing}; missing GDX files: {gdx_missing}"
            )
    else:
        available, missing = _available(normalized_format)
        if not available:
            raise WrongInput(
                f"The selected directory does not contain a complete GTAP Power MRIO {normalized_format.upper()} bundle. "
                f"Missing files: {missing}"
            )

    return GTAPLayout(
        root=root,
        variant=normalized_variant,
        layout=normalized_layout,
        input_format=normalized_format,
        region_workbook=region_workbook if region_workbook.exists() else None,
    )


def _gtap_row_unit(row_name: str) -> str:
    if row_name.startswith("EMI") or row_name.startswith("E_P"):
        return "M ton"
    if row_name.startswith("ENE"):
        return "M toe"
    return GTAP_MONETARY_UNIT


def _gtap_units(indexes: dict[str, list[str]]) -> dict[str, pd.DataFrame]:
    return {
        _MASTER_INDEX["s"]: pd.DataFrame(
            {"unit": [GTAP_MONETARY_UNIT] * len(indexes["s"])},
            index=pd.Index(indexes["s"], name=None),
        ),
        _MASTER_INDEX["n"]: pd.DataFrame(
            {"unit": [GTAP_MONETARY_UNIT] * len(indexes["n"])},
            index=pd.Index(indexes["n"], name=None),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [GTAP_MONETARY_UNIT] * len(indexes["f"])},
            index=pd.Index(indexes["f"], name=None),
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": [_gtap_row_unit(row) for row in indexes["k"]]},
            index=pd.Index(indexes["k"], name=None),
        ),
    }


# ---------------------------------------------------------------------------
# Optional structured row layouts
#
# By default GTAP factor and satellite rows keep the historical flat string
# names ("MTAX_AUS_GRO", "EMI_CO2_AUS_COA", ...). When one of the supported
# ``matrix_layouts`` is requested, the same rows are exposed instead as a
# semantic ``(Region, Sector, item)`` MultiIndex, with the sentinel label
# below on levels that do not apply to a row family (e.g. PTAX has neither a
# region nor a sector of its own). MARIO's aggregation maps labels with
# ``mapping.get(value, value)``, so sentinel labels pass through untouched.
# ---------------------------------------------------------------------------

_GTAP_LAYOUT_SENTINEL = "TOTAL"
_GTAP_SUPPORTED_ROW_LAYOUT = ("Region", "Sector")
_GTAP_V_ROW_AXIS_NAMES = (_MASTER_INDEX["r"], _MASTER_INDEX["s"], _MASTER_INDEX["f"])
_GTAP_E_ROW_AXIS_NAMES = (_MASTER_INDEX["r"], _MASTER_INDEX["s"], _MASTER_INDEX["k"])


def _normalize_gtap_matrix_layouts(matrix_layouts) -> dict[str, tuple[str, ...]]:
    """Validate the requested GTAP matrix layouts.

    The GTAP parser currently supports only the standard flat rows or the
    full ``("Region", "Sector")`` row layout, and requires VY/EY to resolve to
    the same layout as V/E because their rows are built family by family.
    """
    normalized = normalize_matrix_layouts(matrix_layouts, table="IOT")
    unsupported = {
        name: layout
        for name, layout in normalized.items()
        if layout not in ((), _GTAP_SUPPORTED_ROW_LAYOUT)
    }
    if unsupported:
        raise WrongInput(
            "The GTAP parser currently supports only the ('Region', 'Sector') matrix "
            f"layout (or the standard flat rows). Unsupported entries: {unsupported}."
        )
    for paired in (("V", "VY"), ("E", "EY")):
        resolved = {name: iot_row_layout(name, normalized) for name in paired}
        if resolved[paired[0]] != resolved[paired[1]]:
            raise WrongInput(
                f"The GTAP parser requires {paired[0]} and {paired[1]} to share the same "
                f"row layout, got {resolved}."
            )
    return normalized


def _gtap_structured_rows(matrix_layouts: dict[str, tuple[str, ...]] | None) -> tuple[bool, bool]:
    """Return whether V/VY and E/EY rows are region-sector structured."""
    normalized = matrix_layouts or {}
    return (
        iot_row_layout("V", normalized) == _GTAP_SUPPORTED_ROW_LAYOUT,
        iot_row_layout("E", normalized) == _GTAP_SUPPORTED_ROW_LAYOUT,
    )


def gtap_block_specs(matrix_layouts: dict[str, object] | None) -> list:
    """Return the semantic block specs implied by validated GTAP matrix layouts."""
    normalized = _normalize_gtap_matrix_layouts(matrix_layouts)
    if not normalized:
        return []
    return iot_block_specs_for_matrix_layouts(normalized)


def _gtap_finalize_iot(
    *,
    Z: pd.DataFrame,
    Y: pd.DataFrame,
    V: pd.DataFrame,
    VY: pd.DataFrame,
    E: pd.DataFrame,
    EY: pd.DataFrame,
    regions: list[str],
    sectors: list[str],
    final_demand: list[str],
    matrix_layouts: dict[str, tuple[str, ...]] | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame]]:
    raw_sector_columns = Z.columns
    raw_final_demand_columns = Y.columns
    sector_axis = pd.MultiIndex.from_arrays(
        [
            Z.index.get_level_values(0),
            [_MASTER_INDEX["s"]] * len(Z.index),
            Z.index.get_level_values(-1),
        ]
    )
    final_demand_axis = pd.MultiIndex.from_arrays(
        [
            Y.columns.get_level_values(0),
            [_MASTER_INDEX["n"]] * len(Y.columns),
            Y.columns.get_level_values(-1),
        ]
    )

    Z = Z.copy()
    Y = Y.copy()
    V = V.copy()
    VY = VY.copy()
    E = E.copy()
    EY = EY.copy()

    Z.index = sector_axis
    Z.columns = sector_axis

    Y.index = sector_axis
    Y.columns = final_demand_axis

    V = V.reindex(columns=raw_sector_columns, fill_value=0.0)
    E = E.reindex(columns=raw_sector_columns, fill_value=0.0)
    VY = VY.reindex(columns=raw_final_demand_columns, fill_value=0.0)
    EY = EY.reindex(columns=raw_final_demand_columns, fill_value=0.0)

    V.columns = sector_axis
    E.columns = sector_axis
    VY.columns = final_demand_axis
    EY.columns = final_demand_axis

    matrices = {
        "baseline": {
            "Z": Z,
            "Y": Y,
            "V": V,
            "VY": VY,
            "E": E,
            "EY": EY,
        }
    }
    v_structured, e_structured = _gtap_structured_rows(matrix_layouts)
    factor_rows = (
        delete_duplicates(V.index.get_level_values(-1).tolist()) if v_structured else V.index.tolist()
    )
    satellite_rows = (
        delete_duplicates(E.index.get_level_values(-1).tolist()) if e_structured else E.index.tolist()
    )
    indexes = {
        "r": {"main": list(regions)},
        "s": {"main": list(sectors)},
        "n": {"main": list(final_demand)},
        "f": {"main": factor_rows},
        "k": {"main": satellite_rows},
    }
    units = _gtap_units(
        {
            "s": indexes["s"]["main"],
            "n": indexes["n"]["main"],
            "f": indexes["f"]["main"],
            "k": indexes["k"]["main"],
        }
    )
    rename_index(matrices["baseline"])
    # rename_index applies the generic Region/Level/Item names everywhere;
    # structured factor/satellite rows keep their semantic axis names instead.
    if v_structured:
        for name in ("V", "VY"):
            matrices["baseline"][name].index.names = list(_GTAP_V_ROW_AXIS_NAMES)
    if e_structured:
        for name in ("E", "EY"):
            matrices["baseline"][name].index.names = list(_GTAP_E_ROW_AXIS_NAMES)
    sort_frames(matrices["baseline"])
    return matrices, indexes, units


# ---------------------------------------------------------------------------
# Dense-block assembly engine
#
# Records never get reindexed onto cartesian products. Each label column is
# categorized once, category codes are translated to positions on the sorted
# dense axes, and values are accumulated straight into ``np.zeros`` blocks.
# Missing combinations therefore stay zero for free, and duplicated keys sum.
# ---------------------------------------------------------------------------


def _appearance_unique(series: pd.Series) -> list[str]:
    """Return unique values in order of first appearance, as plain strings."""
    values = series.unique()
    if isinstance(values, pd.Categorical):
        values = np.asarray(values.astype(str))
    return [str(value) for value in values]


def _categorize_keys(frame: pd.DataFrame, key_columns: list[str]) -> pd.DataFrame:
    """Return a copy of ``frame`` with stripped column names and categorical keys."""
    prepared = frame.copy()
    prepared.columns = [str(column).strip() for column in prepared.columns]
    for column in key_columns:
        if not isinstance(prepared[column].dtype, pd.CategoricalDtype):
            prepared[column] = prepared[column].astype("category")
    return prepared


def _position_codes(series: pd.Series, positions: dict[str, int]) -> np.ndarray:
    """Translate one categorical column onto axis positions (-1 = unmapped)."""
    categories = series.cat.categories
    table = np.full(len(categories) + 1, -1, dtype=np.int64)
    for category_index, category in enumerate(categories):
        table[category_index] = positions.get(str(category), -1)
    codes = series.cat.codes.to_numpy()
    # missing values carry code -1, which safely hits the sentinel slot
    return table[codes]


def _values_array(series: pd.Series) -> np.ndarray:
    values = series.to_numpy(dtype=np.float64)
    if np.isnan(values).any():
        values = np.nan_to_num(values, nan=0.0)
    return values


def _combined_positions(region_positions: np.ndarray, item_positions: np.ndarray, n_items: int) -> np.ndarray:
    valid = (region_positions >= 0) & (item_positions >= 0)
    return np.where(valid, region_positions * n_items + item_positions, -1)


def _accumulate(
    matrix: np.ndarray,
    row_positions: np.ndarray,
    column_positions: np.ndarray,
    values: np.ndarray,
    mask: np.ndarray | None = None,
) -> None:
    valid = (row_positions >= 0) & (column_positions >= 0)
    if mask is not None:
        valid &= mask
    if not valid.any():
        return
    if valid.all():
        np.add.at(matrix, (row_positions, column_positions), values)
    else:
        np.add.at(matrix, (row_positions[valid], column_positions[valid]), values[valid])


def _scatter_matrix(
    n_rows: int,
    n_columns: int,
    row_positions: np.ndarray,
    column_positions: np.ndarray,
    values: np.ndarray,
    mask: np.ndarray | None = None,
) -> np.ndarray:
    matrix = np.zeros((n_rows, n_columns), dtype=np.float64)
    _accumulate(matrix, row_positions, column_positions, values, mask)
    return matrix


class _GTAPAxes:
    """Dense sorted axes plus appearance-order public index lists."""

    def __init__(self, regions: list[str], sectors: list[str], final_demand: list[str]):
        self.regions = [str(region) for region in regions]
        self.sectors = [str(sector) for sector in sectors]
        self.final_demand = [str(item) for item in final_demand]

        self.sorted_regions = sorted(self.regions)
        self.sorted_sectors = sorted(self.sectors)
        self.sorted_final_demand = sorted(self.final_demand)

        self.region_positions = {label: position for position, label in enumerate(self.sorted_regions)}
        self.sector_positions = {label: position for position, label in enumerate(self.sorted_sectors)}
        self.final_demand_positions = {
            label: position for position, label in enumerate(self.sorted_final_demand)
        }

        self.n_regions = len(self.sorted_regions)
        self.n_sectors = len(self.sorted_sectors)
        self.n_final_demand = len(self.sorted_final_demand)
        self.n_sector_columns = self.n_regions * self.n_sectors
        self.n_final_columns = self.n_regions * self.n_final_demand

        self.sector_axis = pd.MultiIndex.from_product(
            [self.sorted_regions, self.sorted_sectors], names=["DST", "AGENT"]
        )
        self.final_demand_axis = pd.MultiIndex.from_product(
            [self.sorted_regions, self.sorted_final_demand], names=["DST", "AGENT"]
        )


def _sector_space_frame(matrix: np.ndarray, axes: _GTAPAxes, columns: pd.MultiIndex) -> pd.DataFrame:
    index = pd.MultiIndex.from_product(
        [axes.sorted_regions, axes.sorted_sectors], names=["SRC", "COMM"]
    )
    return pd.DataFrame(matrix, index=index, columns=columns)


def _sorted_row_frame(
    row_names: list[str],
    matrix: np.ndarray,
    columns: pd.MultiIndex,
    *,
    row_tuples: list[tuple[str, str, str]] | None = None,
    tuple_names: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Build one row block sorted by flat row name.

    Rows are always ordered by the flat name so the structured (layout) and
    flat variants of the same block stay value-identical row by row; only the
    index representation changes.
    """
    order = sorted(range(len(row_names)), key=row_names.__getitem__)
    if row_tuples is None:
        index = pd.Index([row_names[position] for position in order], name="row_name")
    elif row_names:
        index = pd.MultiIndex.from_tuples(
            [row_tuples[position] for position in order], names=list(tuple_names)
        )
    else:
        index = pd.MultiIndex.from_arrays([[] for _ in tuple_names], names=list(tuple_names))
    if order != list(range(len(row_names))):
        matrix = matrix[order]
    return pd.DataFrame(matrix, index=index, columns=columns)


def _observed_labels(codes: np.ndarray, categories: pd.Index, mask: np.ndarray) -> tuple[list[str], np.ndarray]:
    """Appearance-ordered observed category labels plus a code -> row lookup table."""
    valid = mask & (codes >= 0)
    observed = pd.unique(codes[valid])
    lookup = np.full(len(categories) + 1, -1, dtype=np.int64)
    lookup[observed] = np.arange(len(observed))
    labels = [str(categories[code]) for code in observed]
    return labels, lookup


def _observed_pairs(
    primary_codes: np.ndarray,
    secondary_codes: np.ndarray,
    n_secondary: int,
    mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Appearance-ordered observed (primary, secondary) pairs plus a lookup table."""
    valid = mask & (primary_codes >= 0) & (secondary_codes >= 0)
    combined = primary_codes * n_secondary + secondary_codes
    sentinel = combined.max(initial=0) + 1 if valid.any() else 1
    safe = np.where(valid | ((primary_codes >= 0) & (secondary_codes >= 0)), combined, sentinel)
    observed = pd.unique(combined[valid])
    lookup = np.full(int(max(sentinel, combined.max(initial=0))) + 2, -1, dtype=np.int64)
    lookup[observed] = np.arange(len(observed))
    row_codes = np.where((primary_codes >= 0) & (secondary_codes >= 0), lookup[safe], -1)
    return observed, lookup, row_codes


def _region_sector_row_names(categ: str, axes: _GTAPAxes) -> list[str]:
    return [
        f"{categ}_{region}_{sector}"
        for region in axes.sorted_regions
        for sector in axes.sorted_sectors
    ]


# ---------------------------------------------------------------------------
# Coded record views
# ---------------------------------------------------------------------------


class _FlowCodes:
    """Integer-coded view of one record table with region/agent key columns."""

    def __init__(
        self,
        frame: pd.DataFrame,
        axes: _GTAPAxes,
        *,
        sector_column: str | None = None,
        agent_column: str | None = None,
        source_column: str | None = None,
        destination_column: str | None = None,
        value_column: str = "VALUE",
    ):
        self.frame = frame
        self.values = _values_array(frame[value_column])
        self.sector = (
            _position_codes(frame[sector_column], axes.sector_positions)
            if sector_column is not None
            else None
        )
        self.agent_sector = (
            _position_codes(frame[agent_column], axes.sector_positions)
            if agent_column is not None
            else None
        )
        self.agent_final = (
            _position_codes(frame[agent_column], axes.final_demand_positions)
            if agent_column is not None
            else None
        )
        self.source = (
            _position_codes(frame[source_column], axes.region_positions)
            if source_column is not None
            else None
        )
        self.destination = (
            _position_codes(frame[destination_column], axes.region_positions)
            if destination_column is not None
            else None
        )


def _var_mask(frame: pd.DataFrame, value: str, column: str = "VAR") -> np.ndarray:
    return (frame[column] == value).to_numpy()


def _warn_uncaptured_satellite_mass(label: str, raw_total: float, blocks) -> None:
    """Emit a warning when satellite records did not fully land in E/EY.

    The assembly is record-exact by construction, so any residual means the
    source file contains keys the parser does not recognize (for example
    domestic records pointing at two different real regions). Losing that
    mass silently would be worse than the warning noise.
    """
    captured = float(sum(block.to_numpy().sum() for block in blocks))
    difference = raw_total - captured
    if abs(difference) > max(1e-6, 1e-9 * abs(raw_total)):
        log_time(
            logger,
            f"Parser: {difference:,.6f} of the {label} record mass was not captured in E/EY "
            "(records with unrecognized regions/agents or non-diagonal domestic keys).",
            "warning",
        )


# ---------------------------------------------------------------------------
# Shared block builders
# ---------------------------------------------------------------------------


def _flow_blocks(
    axes: _GTAPAxes,
    contributions: list[tuple[_FlowCodes, np.ndarray | None, np.ndarray]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assemble Z and Y from (codes, mask, column-region positions) contributions."""
    z_matrix = np.zeros((axes.n_sector_columns, axes.n_sector_columns), dtype=np.float64)
    y_matrix = np.zeros((axes.n_sector_columns, axes.n_final_columns), dtype=np.float64)
    for codes, mask, column_regions in contributions:
        rows = _combined_positions(codes.source, codes.sector, axes.n_sectors)
        _accumulate(
            z_matrix,
            rows,
            _combined_positions(column_regions, codes.agent_sector, axes.n_sectors),
            codes.values,
            mask,
        )
        _accumulate(
            y_matrix,
            rows,
            _combined_positions(column_regions, codes.agent_final, axes.n_final_demand),
            codes.values,
            mask,
        )
    Z = _sector_space_frame(z_matrix, axes, axes.sector_axis)
    Y = _sector_space_frame(y_matrix, axes, axes.final_demand_axis)
    return Z, Y


def _region_sector_rowname_blocks(
    categ: str,
    axes: _GTAPAxes,
    codes: _FlowCodes,
    mask: np.ndarray | None,
    *,
    structured: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Blocks with one dense row per (source region, sector), e.g. MTAX/ITTM."""
    row_names = _region_sector_row_names(categ, axes)
    row_tuples = (
        [
            (region, sector, categ)
            for region in axes.sorted_regions
            for sector in axes.sorted_sectors
        ]
        if structured
        else None
    )
    rows = _combined_positions(codes.source, codes.sector, axes.n_sectors)
    block = _scatter_matrix(
        len(row_names),
        axes.n_sector_columns,
        rows,
        _combined_positions(codes.destination, codes.agent_sector, axes.n_sectors),
        codes.values,
        mask,
    )
    block_y = _scatter_matrix(
        len(row_names),
        axes.n_final_columns,
        rows,
        _combined_positions(codes.destination, codes.agent_final, axes.n_final_demand),
        codes.values,
        mask,
    )
    return (
        _sorted_row_frame(
            row_names, block, axes.sector_axis,
            row_tuples=row_tuples, tuple_names=_GTAP_V_ROW_AXIS_NAMES,
        ),
        _sorted_row_frame(
            row_names, block_y, axes.final_demand_axis,
            row_tuples=row_tuples, tuple_names=_GTAP_V_ROW_AXIS_NAMES,
        ),
    )


def _region_rowname_block(
    categ: str,
    axes: _GTAPAxes,
    *,
    row_regions: np.ndarray,
    column_regions: np.ndarray,
    column_sectors: np.ndarray,
    values: np.ndarray,
    mask: np.ndarray | None,
    structured: bool = False,
) -> pd.DataFrame:
    """Block with one row per region, e.g. ETAX."""
    row_names = [f"{categ}_{region}" for region in axes.sorted_regions]
    row_tuples = (
        [(region, _GTAP_LAYOUT_SENTINEL, categ) for region in axes.sorted_regions]
        if structured
        else None
    )
    block = _scatter_matrix(
        len(row_names),
        axes.n_sector_columns,
        row_regions,
        _combined_positions(column_regions, column_sectors, axes.n_sectors),
        values,
        mask,
    )
    return _sorted_row_frame(
        row_names, block, axes.sector_axis,
        row_tuples=row_tuples, tuple_names=_GTAP_V_ROW_AXIS_NAMES,
    )


def _single_rowname_block(
    row_name: str,
    axes: _GTAPAxes,
    *,
    column_regions: np.ndarray,
    column_sectors: np.ndarray,
    values: np.ndarray,
    mask: np.ndarray | None,
    structured: bool = False,
    item_label: str | None = None,
) -> pd.DataFrame:
    """Block with one aggregate row, e.g. PTAX."""
    rows = np.zeros(len(values), dtype=np.int64)
    block = _scatter_matrix(
        1,
        axes.n_sector_columns,
        rows,
        _combined_positions(column_regions, column_sectors, axes.n_sectors),
        values,
        mask,
    )
    row_tuples = (
        [(_GTAP_LAYOUT_SENTINEL, _GTAP_LAYOUT_SENTINEL, item_label or row_name)]
        if structured
        else None
    )
    return _sorted_row_frame(
        [row_name], block, axes.sector_axis,
        row_tuples=row_tuples, tuple_names=_GTAP_V_ROW_AXIS_NAMES,
    )


def _observed_item_rowname_block(
    categ_prefix: str,
    axes: _GTAPAxes,
    *,
    item_series: pd.Series,
    column_regions: np.ndarray,
    column_sectors: np.ndarray,
    values: np.ndarray,
    mask: np.ndarray,
    structured: bool = False,
    item_prefix: str | None = None,
) -> pd.DataFrame:
    """Block with one row per observed row-item, e.g. VAAD/VTAX endowments."""
    item_codes = item_series.cat.codes.to_numpy().astype(np.int64)
    labels, lookup = _observed_labels(item_codes, item_series.cat.categories, mask)
    row_names = [f"{categ_prefix}{label}" for label in labels]
    row_tuples = (
        [
            (_GTAP_LAYOUT_SENTINEL, _GTAP_LAYOUT_SENTINEL, f"{item_prefix or categ_prefix}{label}")
            for label in labels
        ]
        if structured
        else None
    )
    rows = lookup[item_codes]
    block = _scatter_matrix(
        len(row_names),
        axes.n_sector_columns,
        rows,
        _combined_positions(column_regions, column_sectors, axes.n_sectors),
        values,
        mask,
    )
    return _sorted_row_frame(
        row_names, block, axes.sector_axis,
        row_tuples=row_tuples, tuple_names=_GTAP_V_ROW_AXIS_NAMES,
    )


def _dense_sector_rowname_blocks(
    categ: str,
    axes: _GTAPAxes,
    codes: _FlowCodes,
    mask: np.ndarray | None,
    *,
    column_regions: np.ndarray,
    structured: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Blocks with one dense row per sector, e.g. DTAX/ITAX."""
    row_names = [f"{categ}_REG_{sector}" for sector in axes.sorted_sectors]
    row_tuples = (
        [(_GTAP_LAYOUT_SENTINEL, sector, categ) for sector in axes.sorted_sectors]
        if structured
        else None
    )
    block = _scatter_matrix(
        len(row_names),
        axes.n_sector_columns,
        codes.sector,
        _combined_positions(column_regions, codes.agent_sector, axes.n_sectors),
        codes.values,
        mask,
    )
    block_y = _scatter_matrix(
        len(row_names),
        axes.n_final_columns,
        codes.sector,
        _combined_positions(column_regions, codes.agent_final, axes.n_final_demand),
        codes.values,
        mask,
    )
    return (
        _sorted_row_frame(
            row_names, block, axes.sector_axis,
            row_tuples=row_tuples, tuple_names=_GTAP_V_ROW_AXIS_NAMES,
        ),
        _sorted_row_frame(
            row_names, block_y, axes.final_demand_axis,
            row_tuples=row_tuples, tuple_names=_GTAP_V_ROW_AXIS_NAMES,
        ),
    )


def _satellite_domestic_blocks(
    axes: _GTAPAxes,
    codes: _FlowCodes,
    *,
    domestic_mask: np.ndarray,
    gas_series: pd.Series | None,
    item_series: pd.Series,
    name_builder,
    tuple_builder=None,
    pseudo_diagonal: np.ndarray | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Domestic satellite rows: one row per observed (gas, item), values on SRC==DST.

    ``pseudo_diagonal`` marks records whose source is a placeholder token
    rather than a region (GTAP csv exports write ``SRC="TOT"`` for output- and
    value-added-based emission accounts): they belong to the destination
    region and are accumulated on the diagonal like any domestic record.
    """
    item_codes = item_series.cat.codes.to_numpy().astype(np.int64)
    item_categories = item_series.cat.categories
    if gas_series is None:
        labels, lookup = _observed_labels(item_codes, item_categories, domestic_mask)
        pair_labels = [(None, label) for label in labels]
        rows = lookup[item_codes]
    else:
        gas_codes = gas_series.cat.codes.to_numpy().astype(np.int64)
        gas_categories = gas_series.cat.categories
        observed, _, rows = _observed_pairs(
            gas_codes, item_codes, len(item_categories), domestic_mask
        )
        pair_labels = [
            (str(gas_categories[pair // len(item_categories)]),
             str(item_categories[pair % len(item_categories)]))
            for pair in observed
        ]
    row_names = [name_builder(gas_label, item_label) for gas_label, item_label in pair_labels]
    row_tuples = (
        [tuple_builder(gas_label, item_label) for gas_label, item_label in pair_labels]
        if tuple_builder is not None
        else None
    )
    diagonal = domestic_mask & (codes.source >= 0) & (codes.source == codes.destination)
    if pseudo_diagonal is not None:
        diagonal |= domestic_mask & pseudo_diagonal & (codes.destination >= 0)
    block = _scatter_matrix(
        len(row_names),
        axes.n_sector_columns,
        rows,
        _combined_positions(codes.destination, codes.agent_sector, axes.n_sectors),
        codes.values,
        diagonal,
    )
    block_y = _scatter_matrix(
        len(row_names),
        axes.n_final_columns,
        rows,
        _combined_positions(codes.destination, codes.agent_final, axes.n_final_demand),
        codes.values,
        diagonal,
    )
    return (
        _sorted_row_frame(
            row_names, block, axes.sector_axis,
            row_tuples=row_tuples, tuple_names=_GTAP_E_ROW_AXIS_NAMES,
        ),
        _sorted_row_frame(
            row_names, block_y, axes.final_demand_axis,
            row_tuples=row_tuples, tuple_names=_GTAP_E_ROW_AXIS_NAMES,
        ),
    )


def _satellite_import_blocks(
    axes: _GTAPAxes,
    codes: _FlowCodes,
    *,
    import_mask: np.ndarray,
    gas_series: pd.Series | None,
    item_series: pd.Series,
    name_builder,
    tuple_builder=None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Import satellite rows: observed (gas, item) pairs expanded over all source regions."""
    item_codes = item_series.cat.codes.to_numpy().astype(np.int64)
    item_categories = item_series.cat.categories
    if gas_series is None:
        labels, lookup = _observed_labels(item_codes, item_categories, import_mask)
        pair_rows = lookup[item_codes]
        pair_labels = [(None, label) for label in labels]
    else:
        gas_codes = gas_series.cat.codes.to_numpy().astype(np.int64)
        gas_categories = gas_series.cat.categories
        observed, _, pair_rows = _observed_pairs(
            gas_codes, item_codes, len(item_categories), import_mask
        )
        pair_labels = [
            (str(gas_categories[pair // len(item_categories)]),
             str(item_categories[pair % len(item_categories)]))
            for pair in observed
        ]
    row_names = [
        name_builder(gas_label, region, item_label)
        for gas_label, item_label in pair_labels
        for region in axes.sorted_regions
    ]
    row_tuples = (
        [
            tuple_builder(gas_label, region, item_label)
            for gas_label, item_label in pair_labels
            for region in axes.sorted_regions
        ]
        if tuple_builder is not None
        else None
    )
    rows = np.where(
        (pair_rows >= 0) & (codes.source >= 0),
        pair_rows * axes.n_regions + codes.source,
        -1,
    )
    block = _scatter_matrix(
        len(row_names),
        axes.n_sector_columns,
        rows,
        _combined_positions(codes.destination, codes.agent_sector, axes.n_sectors),
        codes.values,
        import_mask,
    )
    block_y = _scatter_matrix(
        len(row_names),
        axes.n_final_columns,
        rows,
        _combined_positions(codes.destination, codes.agent_final, axes.n_final_demand),
        codes.values,
        import_mask,
    )
    return (
        _sorted_row_frame(
            row_names, block, axes.sector_axis,
            row_tuples=row_tuples, tuple_names=_GTAP_E_ROW_AXIS_NAMES,
        ),
        _sorted_row_frame(
            row_names, block_y, axes.final_demand_axis,
            row_tuples=row_tuples, tuple_names=_GTAP_E_ROW_AXIS_NAMES,
        ),
    )


# ---------------------------------------------------------------------------
# CSV backend
# ---------------------------------------------------------------------------


_GTAP_CSV_KEY_COLUMNS = {
    "SRCxDST": ["VAR", "COMM", "AGENT", "SRC", "DST"],
    "V": ["VAR", "COMM", "AGENT", "REG"],
    "V - Tax": ["VAR", "COMM", "SRC", "DST"],
    "E+EY - Emissions": ["VAR", "EM", "COMM", "AGT", "SRC", "DST"],
    "E+EY - Energy": ["VAR", "COMM", "AGT", "SRC", "DST"],
}


def build_gtap_mrio_from_csv_frames(
    frames: dict[str, pd.DataFrame],
    matrix_layouts: dict[str, object] | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame]]:
    """Build canonical MARIO IOT blocks from GTAP Power MRIO csv frames."""
    normalized_layouts = _normalize_gtap_matrix_layouts(matrix_layouts)
    v_structured, e_structured = _gtap_structured_rows(normalized_layouts)
    srcxdst = _categorize_keys(frames["SRCxDST"], _GTAP_CSV_KEY_COLUMNS["SRCxDST"])
    value_added = _categorize_keys(frames["V"], _GTAP_CSV_KEY_COLUMNS["V"])
    value_taxes = _categorize_keys(frames["V - Tax"], _GTAP_CSV_KEY_COLUMNS["V - Tax"])
    emissions = _categorize_keys(frames["E+EY - Emissions"], _GTAP_CSV_KEY_COLUMNS["E+EY - Emissions"])
    energy = _categorize_keys(frames["E+EY - Energy"], _GTAP_CSV_KEY_COLUMNS["E+EY - Energy"])

    sectors = _appearance_unique(srcxdst["COMM"])
    sector_set = set(sectors)
    final_demand = [item for item in _appearance_unique(srcxdst["AGENT"]) if item not in sector_set]
    regions = delete_duplicates(
        _appearance_unique(srcxdst["SRC"]) + _appearance_unique(srcxdst["DST"])
    )
    axes = _GTAPAxes(regions=regions, sectors=sectors, final_demand=final_demand)

    log_time(logger, "Parser: building GTAP Power MRIO matrices from CSV frames.", "info")

    flow = _FlowCodes(
        srcxdst,
        axes,
        sector_column="COMM",
        agent_column="AGENT",
        source_column="SRC",
        destination_column="DST",
    )

    log_time(logger, "Parser: assembling intermediate and final demand flows (Z, Y).", "info")
    Z, Y = _flow_blocks(
        axes,
        [
            # domestic flows: the destination region is the source region itself
            (flow, _var_mask(srcxdst, "DOM"), flow.source),
            (flow, _var_mask(srcxdst, "VFOB"), flow.destination),
        ],
    )

    log_time(logger, "Parser: assembling factor of production blocks (V, VY).", "info")
    V_mtax, VY_mtax = _region_sector_rowname_blocks(
        "MTAX", axes, flow, _var_mask(srcxdst, "MTAX"), structured=v_structured
    )
    V_ittm, VY_ittm = _region_sector_rowname_blocks(
        "ITTM", axes, flow, _var_mask(srcxdst, "ITTM"), structured=v_structured
    )

    taxes = _FlowCodes(
        value_taxes,
        axes,
        sector_column="COMM",
        source_column="SRC",
        destination_column="DST",
    )
    V_etax = _region_rowname_block(
        "ETAX",
        axes,
        row_regions=taxes.destination,
        column_regions=taxes.source,
        column_sectors=taxes.sector,
        values=taxes.values,
        mask=_var_mask(value_taxes, "ETAX"),
        structured=v_structured,
    )
    V_ptax = _single_rowname_block(
        "PTAX_REG",
        axes,
        column_regions=taxes.destination,
        column_sectors=taxes.sector,
        values=taxes.values,
        mask=_var_mask(value_taxes, "PTAX"),
        structured=v_structured,
        item_label="PTAX",
    )

    added = _FlowCodes(
        value_added,
        axes,
        sector_column="COMM",
        agent_column="AGENT",
        destination_column="REG",
    )
    V_va = _observed_item_rowname_block(
        "VAAD_REG_",
        axes,
        item_series=value_added["COMM"],
        column_regions=added.destination,
        column_sectors=added.agent_sector,
        values=added.values,
        mask=_var_mask(value_added, "VA"),
        structured=v_structured,
        item_prefix="VAAD_",
    )
    V_vtax = _observed_item_rowname_block(
        "VTAX_REG_",
        axes,
        item_series=value_added["COMM"],
        column_regions=added.destination,
        column_sectors=added.agent_sector,
        values=added.values,
        mask=_var_mask(value_added, "VTAX"),
        structured=v_structured,
        item_prefix="VTAX_",
    )
    V_idtax, VY_idtax = _dense_sector_rowname_blocks(
        "DTAX",
        axes,
        added,
        _var_mask(value_added, "IDTAX"),
        column_regions=added.destination,
        structured=v_structured,
    )
    V_imtax, VY_imtax = _dense_sector_rowname_blocks(
        "ITAX",
        axes,
        added,
        _var_mask(value_added, "IMTAX"),
        column_regions=added.destination,
        structured=v_structured,
    )

    V = pd.concat([V_mtax, V_ittm, V_etax, V_ptax, V_va, V_vtax, V_idtax, V_imtax], axis=0)
    VY = pd.concat([VY_mtax, VY_ittm, VY_idtax, VY_imtax], axis=0)

    log_time(logger, "Parser: assembling satellite blocks (E, EY) from emissions.", "info")
    emission_codes = _FlowCodes(
        emissions,
        axes,
        agent_column="AGT",
        source_column="SRC",
        destination_column="DST",
    )
    # output/value-added based emission accounts are exported with SRC="TOT":
    # they belong to the destination region like any domestic record
    emission_pseudo_diagonal = (emissions["SRC"] == "TOT").to_numpy()
    E_dom, EY_dom = _satellite_domestic_blocks(
        axes,
        emission_codes,
        domestic_mask=_var_mask(emissions, "DOM"),
        gas_series=emissions["EM"],
        item_series=emissions["COMM"],
        name_builder=lambda gas, item: f"EMI_{gas}_dms_{item}",
        tuple_builder=(
            (lambda gas, item: (_GTAP_LAYOUT_SENTINEL, item, f"EMI_{gas}_dms"))
            if e_structured
            else None
        ),
        pseudo_diagonal=emission_pseudo_diagonal,
    )
    E_imp, EY_imp = _satellite_import_blocks(
        axes,
        emission_codes,
        import_mask=_var_mask(emissions, "IMP"),
        gas_series=emissions["EM"],
        item_series=emissions["COMM"],
        name_builder=lambda gas, region, item: f"EMI_{gas}_{region}_{item}",
        tuple_builder=(
            (lambda gas, region, item: (region, item, f"EMI_{gas}"))
            if e_structured
            else None
        ),
    )

    _warn_uncaptured_satellite_mass(
        "emissions", float(emission_codes.values.sum()), (E_dom, EY_dom, E_imp, EY_imp)
    )

    log_time(logger, "Parser: assembling satellite blocks (E, EY) from energy volumes.", "info")
    energy_codes = _FlowCodes(
        energy,
        axes,
        agent_column="AGT",
        source_column="SRC",
        destination_column="DST",
    )
    E_ene_dom, EY_ene_dom = _satellite_domestic_blocks(
        axes,
        energy_codes,
        domestic_mask=_var_mask(energy, "DOM"),
        gas_series=None,
        item_series=energy["COMM"],
        name_builder=lambda gas, item: f"ENE_dms_{item}",
        tuple_builder=(
            (lambda gas, item: (_GTAP_LAYOUT_SENTINEL, item, "ENE_dms"))
            if e_structured
            else None
        ),
        pseudo_diagonal=(energy["SRC"] == "TOT").to_numpy(),
    )
    E_ene_imp, EY_ene_imp = _satellite_import_blocks(
        axes,
        energy_codes,
        import_mask=_var_mask(energy, "IMP"),
        gas_series=None,
        item_series=energy["COMM"],
        name_builder=lambda gas, region, item: f"ENE_{region}_{item}",
        tuple_builder=(
            (lambda gas, region, item: (region, item, "ENE"))
            if e_structured
            else None
        ),
    )

    _warn_uncaptured_satellite_mass(
        "energy volume", float(energy_codes.values.sum()), (E_ene_dom, EY_ene_dom, E_ene_imp, EY_ene_imp)
    )

    E = pd.concat([E_dom, E_imp, E_ene_dom, E_ene_imp], axis=0)
    EY = pd.concat([EY_dom, EY_imp, EY_ene_dom, EY_ene_imp], axis=0)

    log_time(logger, "Parser: finalizing GTAP Power MRIO blocks.", "info")
    return _gtap_finalize_iot(
        Z=Z,
        Y=Y,
        V=V,
        VY=VY,
        E=E,
        EY=EY,
        regions=regions,
        sectors=sectors,
        final_demand=final_demand,
        matrix_layouts=normalized_layouts,
    )


# ---------------------------------------------------------------------------
# GDX backend
# ---------------------------------------------------------------------------


def _require_gdx_symbol(container: Any, symbol: str, *, file_label: str) -> Any:
    """Return one mandatory symbol from a GDX container or raise a parser error."""
    if symbol not in container.data:
        raise WrongFormat(
            f"The GTAP Power MRIO {file_label} GDX file is missing the required symbol {symbol!r}."
        )
    return container.data[symbol]


def _gdx_records(container: Any, symbol: str, key_columns: list[str]) -> pd.DataFrame:
    try:
        records = container.data[symbol].records
    except KeyError as exc:
        raise WrongFormat(f"GTAP GDX bundle is missing symbol {symbol!r}.") from exc
    return _categorize_keys(records, key_columns)


def build_gtap_mrio_from_gdx_containers(
    containers: dict[str, Any],
    matrix_layouts: dict[str, object] | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame]]:
    """Build canonical MARIO IOT blocks from GTAP Power MRIO GDX containers."""
    normalized_layouts = _normalize_gtap_matrix_layouts(matrix_layouts)
    v_structured, e_structured = _gtap_structured_rows(normalized_layouts)
    srcxdst = containers["SRCxDST"]
    sectors = _require_gdx_symbol(srcxdst, "comm", file_label="GSDFSRCxDST").records["uni"].astype(str).tolist()
    regions = _require_gdx_symbol(srcxdst, "REG", file_label="GSDFSRCxDST").records["uni"].astype(str).tolist()
    agents = _require_gdx_symbol(srcxdst, "agt", file_label="GSDFSRCxDST").records["uni"].astype(str).tolist()
    sector_set = set(sectors)
    final_demand = [item for item in agents if item not in sector_set]
    axes = _GTAPAxes(regions=regions, sectors=sectors, final_demand=final_demand)

    log_time(logger, "Parser: building GTAP Power MRIO matrices from GDX containers.", "info")

    vdba = _FlowCodes(
        _gdx_records(srcxdst, "VDBA", ["COMM", "agt", "REG"]),
        axes,
        sector_column="COMM",
        agent_column="agt",
        source_column="REG",
        destination_column="REG",
        value_column="value",
    )
    vfob = _FlowCodes(
        _gdx_records(srcxdst, "VFOB", ["COMM", "agt", "SRC", "DST"]),
        axes,
        sector_column="COMM",
        agent_column="agt",
        source_column="SRC",
        destination_column="DST",
        value_column="value",
    )
    Z, Y = _flow_blocks(
        axes,
        [
            (vdba, None, vdba.destination),
            (vfob, None, vfob.destination),
        ],
    )

    V_blocks: list[pd.DataFrame] = []
    VY_blocks: list[pd.DataFrame] = []
    for categ, symbol in (("MTAX", "MTAX"), ("ITTM", "ITTM")):
        codes = _FlowCodes(
            _gdx_records(srcxdst, symbol, ["COMM", "agt", "SRC", "DST"]),
            axes,
            sector_column="COMM",
            agent_column="agt",
            source_column="SRC",
            destination_column="DST",
            value_column="value",
        )
        block, block_y = _region_sector_rowname_blocks(
            categ, axes, codes, None, structured=v_structured
        )
        V_blocks.append(block)
        VY_blocks.append(block_y)

    taxes_container = containers["V-Tax"]
    etax = _FlowCodes(
        _gdx_records(taxes_container, "ETAX", ["COMM", "SRC", "DST"]),
        axes,
        sector_column="COMM",
        source_column="SRC",
        destination_column="DST",
        value_column="value",
    )
    V_blocks.append(
        _region_rowname_block(
            "ETAX",
            axes,
            row_regions=etax.destination,
            column_regions=etax.source,
            column_sectors=etax.sector,
            values=etax.values,
            mask=None,
            structured=v_structured,
        )
    )
    ptax = _FlowCodes(
        _gdx_records(taxes_container, "PTAX", ["COMM", "REG"]),
        axes,
        sector_column="COMM",
        destination_column="REG",
        value_column="value",
    )
    V_blocks.append(
        _single_rowname_block(
            "PTAX_REG",
            axes,
            column_regions=ptax.destination,
            column_sectors=ptax.sector,
            values=ptax.values,
            mask=None,
            structured=v_structured,
            item_label="PTAX",
        )
    )

    added_container = containers["V"]
    for prefix, item_prefix, symbol in (
        ("VAAD_REG_", "VAAD_", "VA"),
        ("VTAX_REG_", "VTAX_", "VTAX"),
    ):
        records = _gdx_records(added_container, symbol, ["ENDW", "acts", "DST"])
        codes = _FlowCodes(
            records,
            axes,
            agent_column="acts",
            destination_column="DST",
            value_column="value",
        )
        V_blocks.append(
            _observed_item_rowname_block(
                prefix,
                axes,
                item_series=records["ENDW"],
                column_regions=codes.destination,
                column_sectors=codes.agent_sector,
                values=codes.values,
                mask=np.ones(len(records), dtype=bool),
                structured=v_structured,
                item_prefix=item_prefix,
            )
        )

    for categ, symbol in (("DTAX", "IDTAX"), ("ITAX", "IMTAX")):
        codes = _FlowCodes(
            _gdx_records(added_container, symbol, ["COMM", "agt", "DST"]),
            axes,
            sector_column="COMM",
            agent_column="agt",
            destination_column="DST",
            value_column="value",
        )
        block, block_y = _dense_sector_rowname_blocks(
            categ,
            axes,
            codes,
            None,
            column_regions=codes.destination,
            structured=v_structured,
        )
        V_blocks.append(block)
        VY_blocks.append(block_y)

    V = pd.concat(V_blocks, axis=0)
    VY = pd.concat(VY_blocks, axis=0)

    emission_blocks: list[pd.DataFrame] = []
    emission_y_blocks: list[pd.DataFrame] = []
    emissions_container = containers["Emissions"]
    emission_raw_totals: dict[str, float] = {}

    for symbol, source_value in (
        ("Emi_COMB", "DOM"),
        ("Emi_COMB", "IMP"),
        ("Emi", "DOM"),
        ("Emi", "IMP"),
    ):
        if symbol not in emissions_container.data:
            continue
        records = _gdx_records(
            emissions_container, symbol, ["em", "inputs", "agt", "SRC", "DST"]
        )
        codes = _FlowCodes(
            records,
            axes,
            agent_column="agt",
            source_column="SRC",
            destination_column="DST",
            value_column="value",
        )
        emission_raw_totals.setdefault(symbol, float(codes.values.sum()))
        source_mask = (records["source"] == source_value).to_numpy()
        if source_value == "DOM":
            block, block_y = _satellite_domestic_blocks(
                axes,
                codes,
                domestic_mask=source_mask,
                gas_series=records["em"],
                item_series=records["inputs"],
                name_builder=lambda gas, item: f"EMI_{gas}_dms_{item}",
                tuple_builder=(
                    (lambda gas, item: (_GTAP_LAYOUT_SENTINEL, item, f"EMI_{gas}_dms"))
                    if e_structured
                    else None
                ),
                pseudo_diagonal=(records["SRC"] == "TOT").to_numpy(),
            )
        else:
            block, block_y = _satellite_import_blocks(
                axes,
                codes,
                import_mask=source_mask,
                gas_series=records["em"],
                item_series=records["inputs"],
                name_builder=lambda gas, region, item: f"EMI_{gas}_{region}_{item}",
                tuple_builder=(
                    (lambda gas, region, item: (region, item, f"EMI_{gas}"))
                    if e_structured
                    else None
                ),
            )
        emission_blocks.append(block)
        emission_y_blocks.append(block_y)

    if "Emi_Proc" in emissions_container.data:
        records = _gdx_records(emissions_container, "Emi_Proc", ["em", "comm", "acts", "REG"])
        codes = _FlowCodes(
            records,
            axes,
            agent_column="acts",
            destination_column="REG",
            value_column="value",
        )
        emission_raw_totals["Emi_Proc"] = float(codes.values.sum())
        gas_codes = records["em"].cat.codes.to_numpy().astype(np.int64)
        item_codes = records["comm"].cat.codes.to_numpy().astype(np.int64)
        item_categories = records["comm"].cat.categories
        gas_categories = records["em"].cat.categories
        observed, _, rows = _observed_pairs(
            gas_codes, item_codes, len(item_categories), np.ones(len(records), dtype=bool)
        )
        pair_labels = [
            (str(gas_categories[pair // len(item_categories)]),
             str(item_categories[pair % len(item_categories)]))
            for pair in observed
        ]
        row_names = [f"E_P_{gas}_REG_{item}" for gas, item in pair_labels]
        row_tuples = (
            [(_GTAP_LAYOUT_SENTINEL, item, f"E_P_{gas}") for gas, item in pair_labels]
            if e_structured
            else None
        )
        block = _scatter_matrix(
            len(row_names),
            axes.n_sector_columns,
            rows,
            _combined_positions(codes.destination, codes.agent_sector, axes.n_sectors),
            codes.values,
            None,
        )
        block_y = _scatter_matrix(
            len(row_names),
            axes.n_final_columns,
            rows,
            _combined_positions(codes.destination, codes.agent_final, axes.n_final_demand),
            codes.values,
            None,
        )
        emission_blocks.append(
            _sorted_row_frame(
                row_names, block, axes.sector_axis,
                row_tuples=row_tuples, tuple_names=_GTAP_E_ROW_AXIS_NAMES,
            )
        )
        emission_y_blocks.append(
            _sorted_row_frame(
                row_names, block_y, axes.final_demand_axis,
                row_tuples=row_tuples, tuple_names=_GTAP_E_ROW_AXIS_NAMES,
            )
        )

    _warn_uncaptured_satellite_mass(
        "emissions",
        float(sum(emission_raw_totals.values())),
        (*emission_blocks, *emission_y_blocks),
    )

    energy_records = _gdx_records(containers["Energy"], "NRG", ["ERG", "agt", "SRC", "DST"])
    energy_codes = _FlowCodes(
        energy_records,
        axes,
        agent_column="agt",
        source_column="SRC",
        destination_column="DST",
        value_column="value",
    )
    energy_dom, energy_y_dom = _satellite_domestic_blocks(
        axes,
        energy_codes,
        domestic_mask=(energy_records["SOURCE"] == "DOM").to_numpy(),
        gas_series=None,
        item_series=energy_records["ERG"],
        name_builder=lambda gas, item: f"ENE_dms_{item}",
        tuple_builder=(
            (lambda gas, item: (_GTAP_LAYOUT_SENTINEL, item, "ENE_dms"))
            if e_structured
            else None
        ),
        pseudo_diagonal=(energy_records["SRC"] == "TOT").to_numpy(),
    )
    energy_imp, energy_y_imp = _satellite_import_blocks(
        axes,
        energy_codes,
        import_mask=(energy_records["SOURCE"] == "IMP").to_numpy(),
        gas_series=None,
        item_series=energy_records["ERG"],
        name_builder=lambda gas, region, item: f"ENE_{region}_{item}",
        tuple_builder=(
            (lambda gas, region, item: (region, item, "ENE"))
            if e_structured
            else None
        ),
    )

    _warn_uncaptured_satellite_mass(
        "energy volume",
        float(energy_codes.values.sum()),
        (energy_dom, energy_y_dom, energy_imp, energy_y_imp),
    )

    E = pd.concat([*emission_blocks, energy_dom, energy_imp], axis=0)
    EY = pd.concat([*emission_y_blocks, energy_y_dom, energy_y_imp], axis=0)

    return _gtap_finalize_iot(
        Z=Z,
        Y=Y,
        V=V,
        VY=VY,
        E=E,
        EY=EY,
        regions=regions,
        sectors=sectors,
        final_demand=final_demand,
        matrix_layouts=normalized_layouts,
    )


def _import_gams_transfer():
    try:
        from gams import transfer as gt
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "GTAP GDX parsing requires the GAMS Python API (`gams.transfer`) in the current environment."
        ) from exc
    return gt


def _read_gtap_csv_frame(path: Path) -> pd.DataFrame:
    """Read one GTAP csv table with categorical key columns.

    Key columns are read as categories so the assembly engine can reuse the
    category codes directly; the pyarrow engine is preferred for its
    multithreaded parsing and silently falls back to the default engine.
    """
    size_mb = path.stat().st_size / 1e6
    log_time(logger, f"Parser: reading {path.name} ({size_mb:,.0f} MB).", "info")
    started = time.perf_counter()
    header = pd.read_csv(path, nrows=0)
    dtypes = {
        column: "category"
        for column in header.columns
        if str(column).strip().upper() != "VALUE"
    }
    try:
        frame = pd.read_csv(path, dtype=dtypes, engine="pyarrow")
    except (ImportError, ValueError, TypeError):
        frame = pd.read_csv(path, dtype=dtypes)
    log_time(
        logger,
        f"Parser: finished reading {path.name} in {time.perf_counter() - started:,.1f} seconds.",
        "debug",
    )
    return frame


def parse_gtap_mrio_csv(
    path: str | Path,
    *,
    layout: GTAPLayout | None = None,
    matrix_layouts: dict[str, object] | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    GTAPLayout,
]:
    """Parse GTAP Power MRIO csv files from one local bundle."""
    resolved = layout or detect_gtap_layout(path, variant="power", layout="MRIO", input_format="csv")
    files = _expected_gtap_files(variant=resolved.variant, layout=resolved.layout, input_format="csv")
    frames = {
        key: _read_gtap_csv_frame(resolved.root / filename)
        for key, filename in files.items()
    }
    matrices, indexes, units = build_gtap_mrio_from_csv_frames(frames, matrix_layouts=matrix_layouts)
    return matrices, indexes, units, resolved


def parse_gtap_mrio_gdx(
    path: str | Path,
    *,
    layout: GTAPLayout | None = None,
    matrix_layouts: dict[str, object] | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    GTAPLayout,
]:
    """Parse GTAP Power MRIO GDX files from one local bundle."""
    resolved = layout or detect_gtap_layout(path, variant="power", layout="MRIO", input_format="gdx")
    gt = _import_gams_transfer()
    files = _expected_gtap_files(variant=resolved.variant, layout=resolved.layout, input_format="gdx")
    containers = {
        key: gt.Container(str(resolved.root / filename))
        for key, filename in files.items()
    }
    matrices, indexes, units = build_gtap_mrio_from_gdx_containers(containers, matrix_layouts=matrix_layouts)
    return matrices, indexes, units, resolved
