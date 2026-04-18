"""Local-file parsers for selected CEADS China MRIO workbooks."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    CEADS_FORMATS,
    CEADS_MONETARY_UNIT,
    CEADS_PRICE_LABEL,
    CEADS_SATELLITE_PLACEHOLDER,
    CEADS_SATELLITE_UNIT,
    CEADS_SOURCE,
)

logger = logging.getLogger(__name__)

_WORKBOOK_YEAR_RE = re.compile(r"MRIO\s*(?P<year>\d{4})", flags=re.IGNORECASE)
_TABLE_SHEET_RE = re.compile(r"Table_(?P<year>\d{4})_English Version", flags=re.IGNORECASE)
_FINAL_DEMAND_CODE_LABELS = {
    "FU101": "Rural household consumption",
    "FU102": "Urban household consumption",
    "FU103": "Government consumption",
    "FU201": "Fixed capital formation",
    "FU202": "Changes in inventories",
    "EX": "Exports",
}
_FACTOR_CODE_LABELS = {
    "IM": "Imports",
    "VA001": "Compensation of employees",
    "VA002": "Net taxes on production",
    "VA003": "Depreciation of fixed capital",
    "VA004": "Operating surplus",
}


@dataclass(frozen=True)
class CEADSLayout:
    """Workbook layout metadata for one CEADS parser run."""

    path: Path
    workbook_format: str
    year: int
    table_sheet: str
    notes: tuple[str, ...] = ()

    @property
    def dataset_name(self) -> str:
        """Return the default dataset label stored in MARIO metadata."""
        return f"CEADS China Provincial MRIO {self.year}"

    @property
    def price(self) -> str:
        """Return the price label stored in MARIO metadata."""
        return CEADS_PRICE_LABEL

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        return CEADS_SOURCE


def _text(value) -> str:
    """Normalize one cell to stripped text."""
    if pd.isna(value):
        return ""
    return str(value).replace("\n", " ").strip()


def _code(value) -> str:
    """Normalize one code-like cell to a compact string."""
    text = _text(value)
    if not text:
        return ""
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        return str(int(float(text))).zfill(2)
    return text


def _ffill_labels(values) -> list[str]:
    """Forward-fill one sequence of workbook headers as plain strings."""
    normalized = [_text(value) for value in values]
    filled: list[str] = []
    current = ""
    for value in normalized:
        if value:
            current = value
        filled.append(current)
    return filled


def _resolve_workbook(path: str | Path, *, year: int | None = None) -> Path:
    """Resolve one local workbook from a file or directory path."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    if source.is_file():
        match = _WORKBOOK_YEAR_RE.search(source.stem)
        if year is not None and match is not None and int(match.group("year")) != int(year):
            raise WrongInput(
                f"The selected CEADS workbook contains year {match.group('year')}, not {year}."
            )
        return source

    candidates = []
    for child in source.iterdir():
        if not child.is_file() or child.suffix.lower() != ".xlsx" or child.name.startswith("~$"):
            continue
        match = _WORKBOOK_YEAR_RE.search(child.stem)
        if match is None:
            continue
        if year is not None and int(match.group("year")) != int(year):
            continue
        candidates.append(child)

    if not candidates:
        raise WrongInput("Could not find any supported CEADS workbook in the selected directory.")
    if len(candidates) > 1:
        raise WrongInput(
            "More than one CEADS workbook was found. Please point to one file or specify year=."
        )
    return candidates[0]


def _normalize_format(value: str) -> str:
    """Validate the requested CEADS workbook format selector."""
    normalized = str(value).strip().lower()
    if normalized not in CEADS_FORMATS:
        raise WrongInput(f"CEADS format should be one of {list(CEADS_FORMATS)}.")
    return normalized


def _find_metadata_column(frame: pd.DataFrame, preferred: str) -> str:
    """Return the workbook column matching one expected metadata label."""
    for column in frame.columns:
        if _text(column).lower() == preferred.lower():
            return column
    for column in frame.columns:
        if _text(column).lower().startswith(preferred.lower()):
            return column
    raise WrongFormat(f"Could not find the '{preferred}' column in the CEADS workbook.")


def _read_provinces(workbook: pd.ExcelFile) -> list[str]:
    """Read the province list from the workbook metadata sheet."""
    if "Province" not in workbook.sheet_names:
        raise WrongFormat("The CEADS workbook is missing the 'Province' sheet.")
    frame = workbook.parse("Province")
    column = _find_metadata_column(frame, "Province")
    provinces = [_text(value) for value in frame[column].tolist() if _text(value)]
    if not provinces:
        raise WrongFormat("The CEADS workbook contains an empty 'Province' sheet.")
    return provinces


def _read_sectors(workbook: pd.ExcelFile) -> tuple[list[str], list[str]]:
    """Read sector codes and English labels from the workbook metadata sheet."""
    sector_sheet = next((name for name in workbook.sheet_names if _text(name).lower().startswith("sector")), None)
    if sector_sheet is None:
        raise WrongFormat("The CEADS workbook is missing the 'Sector' sheet.")

    frame = workbook.parse(sector_sheet)
    code_column = _find_metadata_column(frame, "No.")
    label_column = _find_metadata_column(frame, "Sector")

    codes = [_code(value) for value in frame[code_column].tolist() if _code(value)]
    labels = [_text(value) for value in frame[label_column].tolist() if _text(value)]
    if not codes or not labels or len(codes) != len(labels):
        raise WrongFormat("The CEADS sector metadata sheet is malformed.")
    return codes, labels


def detect_ceads_layout(path: str | Path, *, format: str = "auto", year: int | None = None) -> CEADSLayout:
    """Detect the supported CEADS workbook layout."""
    workbook_path = _resolve_workbook(path, year=year)
    requested = _normalize_format(format)
    workbook = pd.ExcelFile(workbook_path)

    table_sheets = []
    for sheet_name in workbook.sheet_names:
        match = _TABLE_SHEET_RE.fullmatch(_text(sheet_name))
        if match is not None:
            table_sheets.append((int(match.group("year")), sheet_name))
    if not table_sheets:
        raise WrongFormat(
            "Could not find any supported English table sheet like 'Table_2018_English Version'."
        )
    if len(table_sheets) > 1:
        raise WrongFormat("The selected CEADS workbook exposes more than one English table sheet.")

    detected_year, table_sheet = table_sheets[0]
    filename_match = _WORKBOOK_YEAR_RE.search(workbook_path.stem)
    if filename_match is not None and int(filename_match.group("year")) != detected_year:
        raise WrongFormat(
            f"Workbook filename year {filename_match.group('year')} does not match table sheet year {detected_year}."
        )
    if year is not None and int(year) != detected_year:
        raise WrongInput(f"The selected CEADS workbook contains year {detected_year}, not {year}.")

    detected = "ceads_provincial_workbook"
    if requested != "auto" and requested != detected:
        raise WrongInput(
            f"CEADS format '{requested}' is not compatible with this workbook. "
            f"Detected format: '{detected}'."
        )

    notes = (
        "Exports are stored as one exogenous final-demand category attached to the originating province.",
        "The imports row is stored inside V as an exogenous input row labelled 'Imports'.",
        "The optional CO2 row, when present, is loaded as a direct extension in E.",
    )
    return CEADSLayout(
        path=workbook_path,
        workbook_format=detected,
        year=detected_year,
        table_sheet=table_sheet,
        notes=notes,
    )


def _find_first_data_row(
    table: pd.DataFrame,
    *,
    first_province: str,
    first_sector_label: str,
    first_sector_code: str,
) -> int:
    """Locate the first transaction row in the English table sheet."""
    for row in range(min(50, table.shape[0])):
        if (
            _text(table.iat[row, 0]) == first_province
            and _text(table.iat[row, 1]) == first_sector_label
            and _code(table.iat[row, 2]) == first_sector_code
        ):
            return row
    raise WrongFormat("Could not locate the first transaction row in the CEADS workbook.")


def _find_first_sector_column(
    table: pd.DataFrame,
    *,
    sector_header_row: int,
    code_header_row: int,
    first_sector_label: str,
    first_sector_code: str,
) -> int:
    """Locate the first sector column in the English table sheet."""
    for column in range(table.shape[1]):
        if (
            _text(table.iat[sector_header_row, column]) == first_sector_label
            and _code(table.iat[code_header_row, column]) == first_sector_code
        ):
            return column
    raise WrongFormat("Could not locate the first sector column in the CEADS workbook.")


def _numeric_block(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert one workbook slice to numeric values."""
    return frame.apply(pd.to_numeric, errors="coerce").fillna(0.0).astype(float)


def _extract_block_axis(
    regions: list[str],
    sectors: list[str],
    sector_codes: list[str],
    *,
    expected_region_count: int,
    expected_sector_count: int,
    axis_name: str,
) -> tuple[list[str], list[str], list[str]]:
    """Validate one repeated region-sector axis and return its canonical labels."""
    if len(regions) != expected_region_count * expected_sector_count:
        raise WrongFormat(f"The {axis_name} axis in the CEADS workbook has an unexpected length.")

    canonical_regions = regions[::expected_sector_count]
    canonical_sectors = sectors[:expected_sector_count]
    canonical_codes = sector_codes[:expected_sector_count]

    if len(canonical_regions) != expected_region_count:
        raise WrongFormat(f"The {axis_name} axis in the CEADS workbook has an unexpected region count.")

    for position, region in enumerate(canonical_regions):
        start = position * expected_sector_count
        stop = start + expected_sector_count
        if any(value != region for value in regions[start:stop]):
            raise WrongFormat(
                f"The {axis_name} axis in the CEADS workbook does not keep sector blocks within one region."
            )
        if sectors[start:stop] != canonical_sectors:
            raise WrongFormat(
                f"The {axis_name} axis in the CEADS workbook exposes inconsistent sector labels across regions."
            )
        if sector_codes[start:stop] != canonical_codes:
            raise WrongFormat(
                f"The {axis_name} axis in the CEADS workbook exposes inconsistent sector codes across regions."
            )

    return canonical_regions, canonical_sectors, canonical_codes


def parse_ceads_iot(
    path: str | Path,
    *,
    format: str = "auto",
    year: int | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    CEADSLayout,
]:
    """Parse one local CEADS provincial MRIO workbook into MARIO IOT blocks."""
    layout = detect_ceads_layout(path, format=format, year=year)
    workbook = pd.ExcelFile(layout.path)
    provinces = _read_provinces(workbook)
    sector_codes, sector_labels = _read_sectors(workbook)
    table = workbook.parse(layout.table_sheet, header=None)

    first_data_row = _find_first_data_row(
        table,
        first_province=provinces[0],
        first_sector_label=sector_labels[0],
        first_sector_code=sector_codes[0],
    )
    province_header_row = first_data_row - 3
    sector_header_row = first_data_row - 2
    code_header_row = first_data_row - 1

    row_count = len(provinces) * len(sector_labels)
    first_sector_column = _find_first_sector_column(
        table,
        sector_header_row=sector_header_row,
        code_header_row=code_header_row,
        first_sector_label=sector_labels[0],
        first_sector_code=sector_codes[0],
    )
    z_start = first_sector_column
    z_end = z_start + row_count - 1
    ti_col = z_end + 1

    export_col = None
    tail_codes = {}
    for column in range(ti_col + 1, table.shape[1]):
        code = _code(table.iat[code_header_row, column])
        if not code:
            continue
        tail_codes[code] = column
    export_col = tail_codes.get("EX")
    if export_col is None:
        raise WrongFormat("Could not detect the export column in the CEADS workbook.")
    fd_start = ti_col + 1
    fd_end = export_col - 1
    if fd_end < fd_start:
        raise WrongFormat("Could not detect the domestic final-demand block in the CEADS workbook.")

    row_slice = slice(first_data_row, first_data_row + row_count)
    z_slice = slice(z_start, z_end + 1)
    fd_slice = slice(fd_start, fd_end + 1)

    row_regions = _ffill_labels(table.iloc[row_slice, 0].tolist())
    row_sector_names = [_text(value) for value in table.iloc[row_slice, 1].tolist()]
    row_sector_codes = [_code(value) for value in table.iloc[row_slice, 2].tolist()]
    col_regions = _ffill_labels(table.iloc[province_header_row, z_slice].tolist())
    col_sector_names = [_text(value) for value in table.iloc[sector_header_row, z_slice].tolist()]
    col_sector_codes = [_code(value) for value in table.iloc[code_header_row, z_slice].tolist()]

    row_provinces, row_sector_block, row_code_block = _extract_block_axis(
        row_regions,
        row_sector_names,
        row_sector_codes,
        expected_region_count=len(provinces),
        expected_sector_count=len(sector_labels),
        axis_name="row",
    )
    col_provinces, col_sector_block, col_code_block = _extract_block_axis(
        col_regions,
        col_sector_names,
        col_sector_codes,
        expected_region_count=len(provinces),
        expected_sector_count=len(sector_labels),
        axis_name="column",
    )

    if row_provinces != col_provinces:
        raise WrongFormat("The CEADS workbook exposes different province orders on rows and columns.")
    if row_sector_block != col_sector_block or row_code_block != col_code_block:
        raise WrongFormat("The CEADS workbook exposes different sector axes on rows and columns.")

    provinces = row_provinces
    sector_labels = row_sector_block
    sector_codes = row_code_block
    expected_pairs = [(province, sector) for province in provinces for sector in sector_labels]

    sector_axis = pd.MultiIndex.from_tuples(
        [(province, _MASTER_INDEX["s"], sector) for province, sector in expected_pairs]
    )

    Z = _numeric_block(table.iloc[row_slice, z_slice])
    Z.index = sector_axis
    Z.columns = sector_axis

    fd_regions = _ffill_labels(table.iloc[province_header_row, fd_slice].tolist())
    fd_codes = [_code(value) for value in table.iloc[code_header_row, fd_slice].tolist()]
    fd_labels = [_FINAL_DEMAND_CODE_LABELS.get(code, _text(label)) for code, label in zip(fd_codes, table.iloc[sector_header_row, fd_slice].tolist())]
    domestic_fd_axis = pd.MultiIndex.from_tuples(
        [(region, _MASTER_INDEX["n"], label) for region, label in zip(fd_regions, fd_labels)]
    )
    Y_domestic = _numeric_block(table.iloc[row_slice, fd_slice])
    Y_domestic.index = sector_axis
    Y_domestic.columns = domestic_fd_axis

    export_values = pd.to_numeric(table.iloc[row_slice, export_col], errors="coerce").fillna(0.0).to_numpy()
    export_matrix = np.zeros((row_count, len(provinces)))
    region_index = {region: idx for idx, region in enumerate(provinces)}
    for row_pos, region in enumerate(row_regions):
        export_matrix[row_pos, region_index[region]] = export_values[row_pos]
    export_axis = pd.MultiIndex.from_tuples(
        [(region, _MASTER_INDEX["n"], "Exports") for region in provinces]
    )
    Y_export = pd.DataFrame(export_matrix, index=sector_axis, columns=export_axis)
    Y = pd.concat([Y_domestic, Y_export], axis=1)

    factor_rows = []
    for code in ["IM", "VA001", "VA002", "VA003", "VA004"]:
        matches = [row for row in range(first_data_row + row_count, table.shape[0]) if _code(table.iat[row, 2]) == code]
        if not matches:
            raise WrongFormat(f"The CEADS workbook is missing the required row {code}.")
        factor_rows.append(matches[0])
    factor_labels = [_FACTOR_CODE_LABELS[_code(table.iat[row, 2])] for row in factor_rows]
    V = _numeric_block(table.iloc[factor_rows, z_slice])
    V.index = pd.Index(factor_labels, name=None)
    V.columns = sector_axis

    satellite_matches = [
        row for row in range(first_data_row + row_count, table.shape[0]) if _text(table.iat[row, 1]).startswith("CO2")
    ]
    if satellite_matches:
        E = _numeric_block(table.iloc[[satellite_matches[0]], z_slice])
        E.index = pd.Index(["CO2"], name=None)
        satellite_unit = "Mt"
    else:
        E = pd.DataFrame(
            np.zeros((1, len(sector_axis))),
            index=pd.Index([CEADS_SATELLITE_PLACEHOLDER], name=None),
            columns=sector_axis,
        )
        satellite_unit = CEADS_SATELLITE_UNIT
    E.columns = sector_axis

    EY = pd.DataFrame(
        np.zeros((len(E.index), len(Y.columns))),
        index=E.index,
        columns=Y.columns,
    )

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
    units = {
        _MASTER_INDEX["s"]: pd.DataFrame(
            {"unit": [CEADS_MONETARY_UNIT] * len(sector_labels)},
            index=pd.Index(sector_labels, name=None),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [CEADS_MONETARY_UNIT] * len(factor_labels)},
            index=pd.Index(factor_labels, name=None),
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": [satellite_unit] * len(E.index)},
            index=E.index,
        ),
    }
    indexes = {
        "r": {"main": list(provinces)},
        "s": {"main": list(sector_labels)},
        "n": {
            "main": [
                "Rural household consumption",
                "Urban household consumption",
                "Government consumption",
                "Fixed capital formation",
                "Changes in inventories",
                "Exports",
            ]
        },
        "f": {"main": list(factor_labels)},
        "k": {"main": E.index.tolist()},
    }
    return matrices, indexes, units, layout
