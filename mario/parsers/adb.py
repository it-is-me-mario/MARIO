"""Direct file-based parser for ADB MRIO Excel workbooks."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    ADB_FACTOR_LABELS,
    ADB_FACTOR_ROWS,
    ADB_FINAL_DEMAND_CODES,
    ADB_FINAL_DEMAND_LABELS,
    ADB_MONETARY_UNIT,
    ADB_SATELLITE_PLACEHOLDER,
    ADB_SATELLITE_UNIT,
    ADB_SOURCE,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_ADB_FILE_RE = re.compile(r"ADB[-_ ]?MRIO", flags=re.IGNORECASE)
_YEAR_RE = re.compile(r"(20\d{2})")
_TITLE_ECONOMIES_RE = re.compile(r"(?P<count>\d+)\s+economies", flags=re.IGNORECASE)
_FOLDER_VARIANT_RE = re.compile(r"(?P<count>\d+)\s+economies", flags=re.IGNORECASE)
_STEM_VARIANT_RE = re.compile(r"MRIO[-_ ]?(?P<count>\d{2})|[-_ ](?P<trailing>\d{2})(?:\D|$)", flags=re.IGNORECASE)
_SECTOR_CODE_RE = re.compile(r"c\d+$", flags=re.IGNORECASE)
_FINAL_CODE_RE = re.compile(r"F\d+$", flags=re.IGNORECASE)
_REGION_CODE_RE = re.compile(r"[A-Z][A-Z0-9]{1,5}$")


@dataclass(frozen=True)
class ADBLayout:
    """Filesystem layout and parsed header metadata for one ADB MRIO workbook."""

    root: Path
    data_path: Path
    year: int
    sheet_name: str
    variant: int | None
    economies: int | None
    label_row: int
    region_row: int
    code_row: int
    sector_start: int
    sector_end: int
    final_demand_start: int
    final_demand_end: int
    row_label_col: int
    row_region_col: int
    row_code_col: int

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        if self.variant is not None:
            return f"ADB MRIO {self.year} ({self.variant} economies)"
        if self.economies is not None:
            return f"ADB MRIO {self.year} ({self.economies} economies)"
        return f"ADB MRIO {self.year}"

    @property
    def price(self) -> str:
        """Return the price metadata stored in MARIO."""
        return "Current prices"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        return ADB_SOURCE


def _clean_string(value) -> str | None:
    """Return one stripped string or ``None`` when the cell is empty."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def _looks_like_region_code(value: str | None) -> bool:
    """Return ``True`` when one cell looks like a compact region code."""
    if value is None:
        return False
    return _REGION_CODE_RE.fullmatch(value) is not None


def _looks_like_label(value: str | None) -> bool:
    """Return ``True`` for descriptive item labels used in ADB headers."""
    if value is None:
        return False
    if _looks_like_region_code(value):
        return False
    if _SECTOR_CODE_RE.fullmatch(value) or _FINAL_CODE_RE.fullmatch(value):
        return False
    if value.isdigit():
        return False
    return True


def _find_adb_sheet(path: Path) -> str:
    """Return the main ADB data sheet, skipping the legend sheet."""
    workbook = pd.ExcelFile(path)
    candidates = [sheet for sheet in workbook.sheet_names if sheet.lower() != "legend"]
    if not candidates:
        raise WrongFormat("The selected ADB workbook does not contain a data sheet.")
    return candidates[0]


def _read_adb_preview(path: Path, *, sheet_name: str) -> pd.DataFrame:
    """Read the first header rows needed to detect an ADB workbook layout."""
    return pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=12)


def _infer_variant(path: Path) -> int | None:
    """Infer the user-facing workbook variant from folder or filename markers."""
    for candidate in [*path.parents, path]:
        match = _FOLDER_VARIANT_RE.search(candidate.name)
        if match is not None:
            return int(match.group("count"))
        match = _STEM_VARIANT_RE.search(candidate.stem if candidate.suffix else candidate.name)
        if match is not None:
            return int(match.group("count") or match.group("trailing"))
    return None


def _infer_year(path: Path, preview: pd.DataFrame | None = None) -> int:
    """Infer the reference year from filename or workbook title."""
    match = _YEAR_RE.search(path.name)
    if match is not None:
        return int(match.group(1))
    if preview is not None:
        title = _clean_string(preview.iat[0, 0])
        if title is not None:
            match = _YEAR_RE.search(title)
            if match is not None:
                return int(match.group(1))
    raise WrongFormat("Could not infer the ADB MRIO year from the workbook name or title.")


def _infer_economies(preview: pd.DataFrame) -> int | None:
    """Infer the economies count printed in the workbook subtitle."""
    if preview.empty:
        return None
    subtitle = _clean_string(preview.iat[1, 0])
    if subtitle is None:
        return None
    match = _TITLE_ECONOMIES_RE.search(subtitle)
    if match is None:
        return None
    return int(match.group("count"))


def _find_header_rows(preview: pd.DataFrame) -> tuple[int, int, int, int, int]:
    """Detect the ADB header rows and the inter-industry/final-demand split."""
    code_row = None
    sector_start = None
    sector_end = None
    final_demand_start = None
    final_demand_end = None

    for row_idx in range(min(12, len(preview))):
        row = [_clean_string(value) for value in preview.iloc[row_idx].tolist()]
        positions = [idx for idx, value in enumerate(row) if value and _SECTOR_CODE_RE.fullmatch(value)]
        if len(positions) < 4:
            continue
        current_start = positions[0]
        current_end = current_start
        while current_end < len(row) and row[current_end] and _SECTOR_CODE_RE.fullmatch(row[current_end]):
            current_end += 1
        current_fd_end = current_end
        while current_fd_end < len(row) and row[current_fd_end] and _FINAL_CODE_RE.fullmatch(row[current_fd_end]):
            current_fd_end += 1
        code_row = row_idx
        sector_start = current_start
        sector_end = current_end
        final_demand_start = current_end
        final_demand_end = current_fd_end
        break

    if code_row is None or sector_start is None or sector_end is None:
        raise WrongFormat("Could not detect the ADB inter-industry code row.")
    if final_demand_start == final_demand_end:
        raise WrongFormat("Could not detect the ADB final-demand columns.")

    region_row = None
    label_row = None
    sample_col = sector_start
    for row_idx in range(code_row - 1, -1, -1):
        cell = _clean_string(preview.iat[row_idx, sample_col])
        if region_row is None and _looks_like_region_code(cell):
            region_row = row_idx
            continue
        if region_row is not None and _looks_like_label(cell):
            label_row = row_idx
            break

    if region_row is None or label_row is None:
        raise WrongFormat("Could not detect the ADB header label rows.")

    return label_row, region_row, code_row, sector_start, sector_end, final_demand_start, final_demand_end


def _candidate_layout(path: Path) -> ADBLayout:
    """Build the lightweight layout metadata for one local ADB workbook."""
    sheet_name = _find_adb_sheet(path)
    preview = _read_adb_preview(path, sheet_name=sheet_name)
    (
        label_row,
        region_row,
        code_row,
        sector_start,
        sector_end,
        final_demand_start,
        final_demand_end,
    ) = _find_header_rows(preview)
    row_code_col = sector_start - 1
    row_region_col = sector_start - 2
    row_label_col = sector_start - 3
    return ADBLayout(
        root=path.parent,
        data_path=path,
        year=_infer_year(path, preview),
        sheet_name=sheet_name,
        variant=_infer_variant(path),
        economies=_infer_economies(preview),
        label_row=label_row,
        region_row=region_row,
        code_row=code_row,
        sector_start=sector_start,
        sector_end=sector_end,
        final_demand_start=final_demand_start,
        final_demand_end=final_demand_end,
        row_label_col=row_label_col,
        row_region_col=row_region_col,
        row_code_col=row_code_col,
    )


def detect_adb_layout(
    path: str | Path,
    *,
    year: int | None = None,
    economies: int | None = None,
) -> ADBLayout:
    """Resolve the ADB MRIO workbook selected for one parse request."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    def _validate(layout: ADBLayout) -> ADBLayout:
        if year is not None and layout.year != int(year):
            raise WrongInput(f"The selected ADB workbook contains year {layout.year}, not {year}.")
        if economies is not None:
            candidates = {value for value in (layout.variant, layout.economies) if value is not None}
            if int(economies) not in candidates:
                raise WrongInput(
                    "The selected ADB workbook does not match economies="
                    f"{economies}. Detected values: {sorted(candidates) or ['unknown']}"
                )
        return layout

    if source.is_file():
        if source.suffix.lower() != ".xlsx" or _ADB_FILE_RE.search(source.name) is None:
            raise WrongInput(
                "ADB MRIO parsing expects one local .xlsx workbook downloaded from "
                "the ADB MRIO release page, or a directory containing those workbooks."
            )
        return _validate(_candidate_layout(source))

    candidates = sorted(
        child
        for child in source.rglob("*.xlsx")
        if child.is_file() and not child.name.startswith("~$") and _ADB_FILE_RE.search(child.name)
    )
    if not candidates:
        raise WrongInput("No ADB MRIO .xlsx workbook was found in the selected directory.")

    layouts = [_candidate_layout(candidate) for candidate in candidates]
    if year is not None:
        layouts = [layout for layout in layouts if layout.year == int(year)]
        if not layouts:
            raise WrongInput(f"No ADB MRIO workbook was found for year {year}.")

    if economies is not None:
        requested = int(economies)
        filtered = []
        for layout in layouts:
            candidates = {value for value in (layout.variant, layout.economies) if value is not None}
            if requested in candidates:
                filtered.append(layout)
        layouts = filtered
        if not layouts:
            raise WrongInput(
                f"No ADB MRIO workbook was found for economies={economies} in the selected directory."
            )

    if len(layouts) > 1:
        options = [
            f"{layout.data_path.name} (year={layout.year}, variant={layout.variant}, title_economies={layout.economies})"
            for layout in layouts
        ]
        raise WrongInput(
            "More than one ADB MRIO workbook matches the selected directory. "
            "Please point to one file or specify year/economies. "
            f"Available workbooks: {options}"
        )

    return layouts[0]


def _read_adb_workbook(path: Path, *, sheet_name: str) -> pd.DataFrame:
    """Read one raw ADB workbook sheet without promoting headers."""
    log_time(logger, f"Parser: reading ADB workbook {path.name} sheet {sheet_name}.", "info")
    frame = pd.read_excel(path, sheet_name=sheet_name, header=None)
    if frame.empty:
        raise WrongFormat("The selected ADB workbook sheet is empty.")
    return frame


def _zero_frame(index, columns) -> pd.DataFrame:
    """Allocate a zero-filled dataframe with the requested index and columns."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def _build_iot_units(*, sector_labels: list[str], factor_labels: list[str]) -> dict[str, pd.DataFrame]:
    """Build MARIO unit tables for ADB MRIO IOT payloads."""
    return {
        _MASTER_INDEX["s"]: pd.DataFrame(
            {"unit": [ADB_MONETARY_UNIT] * len(sector_labels)},
            index=pd.Index(sector_labels, name=None),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [ADB_MONETARY_UNIT] * len(factor_labels)},
            index=pd.Index(factor_labels, name=None),
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": [ADB_SATELLITE_UNIT]},
            index=pd.Index([ADB_SATELLITE_PLACEHOLDER], name=None),
        ),
    }


def _axis_from_pairs(
    regions: list[str],
    level_label: str,
    items: list[str],
) -> pd.MultiIndex:
    """Build one canonical MARIO axis from aligned region/item lists."""
    return pd.MultiIndex.from_arrays(
        [
            regions,
            [level_label] * len(regions),
            items,
        ]
    )


def _preserve_order(values: list[str]) -> list[str]:
    """Return one list with duplicates removed while preserving the first order."""
    return list(dict.fromkeys(values))


def build_adb_iot_from_frame(
    frame: pd.DataFrame,
    *,
    year: int,
    source_path: str | Path | None = None,
    variant: int | None = None,
    economies: int | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    ADBLayout,
]:
    """Transform one raw ADB MRIO sheet into canonical MARIO IOT blocks."""
    source = Path(source_path or f"ADB-MRIO-{year}.xlsx")
    preview = frame.iloc[:12].copy()
    (
        label_row,
        region_row,
        code_row,
        sector_start,
        sector_end,
        final_demand_start,
        final_demand_end,
    ) = _find_header_rows(preview)
    row_code_col = sector_start - 1
    row_region_col = sector_start - 2
    row_label_col = sector_start - 3
    layout = ADBLayout(
        root=source.parent,
        data_path=source,
        year=year,
        sheet_name="ADB MRIO",
        variant=variant,
        economies=economies,
        label_row=label_row,
        region_row=region_row,
        code_row=code_row,
        sector_start=sector_start,
        sector_end=sector_end,
        final_demand_start=final_demand_start,
        final_demand_end=final_demand_end,
        row_label_col=row_label_col,
        row_region_col=row_region_col,
        row_code_col=row_code_col,
    )

    row_codes = [_clean_string(value) for value in frame.iloc[:, row_code_col].tolist()]
    first_data_row = code_row + 1
    sector_rows: list[int] = []
    pointer = first_data_row
    while pointer < len(row_codes) and row_codes[pointer] and _SECTOR_CODE_RE.fullmatch(row_codes[pointer]):
        sector_rows.append(pointer)
        pointer += 1
    if not sector_rows:
        raise WrongFormat("Could not detect the ADB inter-industry row block.")

    factor_rows = [
        row_idx
        for row_idx in range(pointer, len(row_codes))
        if row_codes[row_idx] in set(ADB_FACTOR_ROWS)
    ]
    missing_factor_codes = [code for code in ADB_FACTOR_ROWS if code not in {row_codes[idx] for idx in factor_rows}]
    if missing_factor_codes:
        raise WrongFormat(
            f"The ADB workbook is missing required factor rows: {missing_factor_codes}."
        )

    sector_column_codes = [_clean_string(value) for value in frame.iloc[code_row, sector_start:sector_end].tolist()]
    if not all(code and _SECTOR_CODE_RE.fullmatch(code) for code in sector_column_codes):
        raise WrongFormat("The detected ADB sector columns are not contiguous.")
    final_demand_codes = [
        _clean_string(value)
        for value in frame.iloc[code_row, final_demand_start:final_demand_end].tolist()
    ]
    if not all(code and _FINAL_CODE_RE.fullmatch(code) for code in final_demand_codes):
        raise WrongFormat("The detected ADB final-demand columns are not contiguous.")

    sector_regions = [
        _clean_string(value) for value in frame.iloc[region_row, sector_start:sector_end].tolist()
    ]
    sector_items = [
        _clean_string(value) for value in frame.iloc[label_row, sector_start:sector_end].tolist()
    ]
    row_regions = [_clean_string(value) for value in frame.iloc[sector_rows, row_region_col].tolist()]
    row_items = [_clean_string(value) for value in frame.iloc[sector_rows, row_label_col].tolist()]

    if sector_regions != row_regions or sector_items != row_items:
        raise WrongFormat(
            "ADB inter-industry rows and columns do not describe the same regional-sector axis."
        )

    final_demand_regions = [
        _clean_string(value)
        for value in frame.iloc[region_row, final_demand_start:final_demand_end].tolist()
    ]
    final_demand_items = [
        ADB_FINAL_DEMAND_LABELS.get(code, _clean_string(label) or code)
        for code, label in zip(
            final_demand_codes,
            frame.iloc[label_row, final_demand_start:final_demand_end].tolist(),
        )
    ]

    sector_axis = _axis_from_pairs(sector_regions, _MASTER_INDEX["s"], sector_items)
    final_demand_axis = _axis_from_pairs(final_demand_regions, _MASTER_INDEX["n"], final_demand_items)
    factor_labels = [ADB_FACTOR_LABELS[row_codes[row_idx]] for row_idx in factor_rows]
    factor_axis = pd.Index(factor_labels, name=None)
    satellite_axis = pd.Index([ADB_SATELLITE_PLACEHOLDER], name=None)

    numeric = frame.apply(pd.to_numeric, errors="coerce").fillna(0.0)

    Z = numeric.iloc[sector_rows, sector_start:sector_end].copy()
    Z.index = sector_axis
    Z.columns = sector_axis

    Y = numeric.iloc[sector_rows, final_demand_start:final_demand_end].copy()
    Y.index = sector_axis
    Y.columns = final_demand_axis

    V = numeric.iloc[factor_rows, sector_start:sector_end].copy()
    V.index = factor_axis
    V.columns = sector_axis

    E = _zero_frame(satellite_axis, sector_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

    unique_sector_labels = _preserve_order(sector_items)
    unique_regions = _preserve_order(sector_regions)
    unique_final_demand = [ADB_FINAL_DEMAND_LABELS[code] for code in ADB_FINAL_DEMAND_CODES if code in final_demand_codes]

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
    units = _build_iot_units(
        sector_labels=unique_sector_labels,
        factor_labels=list(factor_axis),
    )
    indeces = {
        "r": {"main": unique_regions},
        "s": {"main": unique_sector_labels},
        "f": {"main": list(factor_axis)},
        "k": {"main": list(satellite_axis)},
        "n": {"main": unique_final_demand},
    }

    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: ADB MRIO parsed with "
            f"{len(unique_regions)} regions, "
            f"{len(unique_sector_labels)} sectors, "
            f"{len(final_demand_axis)} final-demand columns and "
            f"{len(factor_axis)} factor rows."
        ),
        "info",
    )
    return matrices, indeces, units, layout


def parse_adb_iot(
    path: str | Path,
    *,
    year: int | None = None,
    economies: int | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    ADBLayout,
]:
    """Parse one locally downloaded ADB MRIO workbook into MARIO IOT blocks."""
    layout = detect_adb_layout(path, year=year, economies=economies)
    frame = _read_adb_workbook(layout.data_path, sheet_name=layout.sheet_name)
    return build_adb_iot_from_frame(
        frame,
        year=layout.year,
        source_path=layout.data_path,
        variant=layout.variant,
        economies=layout.economies,
    )
