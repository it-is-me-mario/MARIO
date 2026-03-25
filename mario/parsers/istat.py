"""Direct file-based parsers for official ISTAT input-output workbooks."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
from pathlib import Path
import re
import tempfile
import zipfile

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    ISTAT_FINAL_DEMAND_TOTAL_PREFIX,
    ISTAT_IMPORT_FACTOR_LABEL,
    ISTAT_IO_SOURCE,
    ISTAT_IOT_FACTOR_EXCLUDE,
    ISTAT_IOT_FINAL_DEMAND_EXCLUDE,
    ISTAT_IOT_MODES,
    ISTAT_MONETARY_UNIT,
    ISTAT_SATELLITE_PLACEHOLDER,
    ISTAT_SATELLITE_UNIT,
    ISTAT_SUT_FACTOR_EXCLUDE,
    ISTAT_SUT_FINAL_DEMAND_EXCLUDE,
    ISTAT_SUT_LEVELS,
    ISTAT_SUT_PRICES,
    ISTAT_SUT_VALUATIONS,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_ISTAT_IOT_FILE_PATTERNS = {
    "product": re.compile(r"^SIMM_TOT_63PXP(?:_V\d+)?\.xlsx$", re.IGNORECASE),
    "industry": re.compile(r"^SIMM_TOT_63BXB(?:_V\d+)?\.xlsx$", re.IGNORECASE),
}
_ISTAT_IOT_SHEET_PREFIX = {"product": "STOTPP_", "industry": "STOTBB_"}
_ISTAT_SUT_USE_FILES = {"basic": "USEPB", "purchaser": "USEPA"}


@dataclass(frozen=True)
class IstatLayout:
    """Filesystem layout and metadata for one ISTAT workbook selection."""

    root: Path
    year: int
    table: str
    level: str | None = None
    price: str = "current"
    valuation: str | None = None
    iot_mode: str | None = None
    iot_path: Path | None = None
    supply_path: Path | None = None
    use_path: Path | None = None
    import_path: Path | None = None
    sheet_name: str | None = None

    @property
    def dataset_name(self) -> str:
        """Return a compact default dataset name."""
        if self.table == "IOT":
            return f"ISTAT IOT {self.year} {self.iot_mode}"
        return f"ISTAT SUT {self.year} {self.level} {self.price} {self.valuation}"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in metadata."""
        return ISTAT_IO_SOURCE

    @property
    def price_label(self) -> str:
        """Return the price metadata stored in MARIO."""
        if self.table == "IOT":
            return "Current prices"
        return "Previous-year prices" if self.price == "pyp" else "Current prices"


def _normalize_text(value) -> str | None:
    """Normalize one cell value to a compact string."""
    if pd.isna(value):
        return None
    text = " ".join(str(value).replace("\n", " ").split())
    if not text or text.lower() == "nan":
        return None
    return text


def _code_like(value: str | None, *, prefix: str, total_code: str) -> bool:
    """Return True when one workbook code belongs to a contiguous code block."""
    if value is None:
        return False
    return value.startswith(prefix) and value != total_code


def _three_level_axis(region: str, level_label: str, items: list[str]) -> pd.MultiIndex:
    """Build one canonical MARIO single-region axis."""
    return pd.MultiIndex.from_arrays(
        [[region] * len(items), [level_label] * len(items), items]
    )


def _zero_frame(index, columns) -> pd.DataFrame:
    """Allocate a zero-filled dataframe with the requested index and columns."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def _numeric_block(frame: pd.DataFrame, row_positions: list[int], col_positions: list[int]) -> np.ndarray:
    """Return one numeric block from raw workbook cells."""
    block = frame.iloc[row_positions, col_positions].apply(pd.to_numeric, errors="coerce")
    return block.fillna(0.0).to_numpy(dtype=float, copy=True)


def _activity_columns(frame: pd.DataFrame) -> tuple[list[str], list[str], list[int], int]:
    """Extract activity columns from one ISTAT SUT workbook."""
    codes: list[str] = []
    labels: list[str] = []
    positions: list[int] = []
    col = 2
    while col < frame.shape[1]:
        code = _normalize_text(frame.iat[5, col])
        if not _code_like(code, prefix="V", total_code="V"):
            break
        codes.append(code)
        labels.append(_normalize_text(frame.iat[4, col]) or code)
        positions.append(col)
        col += 1
    if not codes:
        raise WrongFormat("Could not detect activity columns in the selected ISTAT SUT workbook.")
    return codes, labels, positions, col


def _sector_columns(frame: pd.DataFrame) -> tuple[list[str], list[str], list[int], int]:
    """Extract sector columns from one ISTAT symmetric table workbook."""
    codes: list[str] = []
    labels: list[str] = []
    positions: list[int] = []
    col = 2
    while col < frame.shape[1]:
        code = _normalize_text(frame.iat[5, col])
        if not _code_like(code, prefix="R", total_code="R"):
            break
        codes.append(code)
        labels.append(_normalize_text(frame.iat[4, col]) or code)
        positions.append(col)
        col += 1
    if not codes:
        raise WrongFormat("Could not detect sector columns in the selected ISTAT symmetric table.")
    return codes, labels, positions, col


def _code_row_positions(frame: pd.DataFrame, *, prefix: str, total_code: str) -> tuple[list[str], list[str], list[int]]:
    """Extract contiguous code rows from the left side of one raw workbook."""
    codes: list[str] = []
    labels: list[str] = []
    positions: list[int] = []
    row = 6
    while row < frame.shape[0]:
        code = _normalize_text(frame.iat[row, 0])
        if not _code_like(code, prefix=prefix, total_code=total_code):
            break
        codes.append(code)
        labels.append(_normalize_text(frame.iat[row, 1]) or code)
        positions.append(row)
        row += 1
    if not codes:
        raise WrongFormat("Could not detect coded rows in the selected ISTAT workbook.")
    return codes, labels, positions


def _final_demand_columns(
    frame: pd.DataFrame,
    *,
    start_col: int,
    excluded_labels: tuple[str, ...],
) -> tuple[list[str], list[int]]:
    """Extract detailed final-demand columns while skipping aggregate totals."""
    labels: list[str] = []
    positions: list[int] = []
    for col in range(start_col, frame.shape[1]):
        label = _normalize_text(frame.iat[4, col])
        if label is None:
            continue
        if label.startswith(ISTAT_FINAL_DEMAND_TOTAL_PREFIX):
            continue
        if label in excluded_labels:
            continue
        labels.append(label)
        positions.append(col)
    if not labels:
        raise WrongFormat("Could not detect final-demand columns in the selected ISTAT workbook.")
    return labels, positions


def _factor_rows(
    frame: pd.DataFrame,
    *,
    start_row: int,
    excluded_labels: tuple[str, ...],
) -> tuple[list[str], list[int]]:
    """Extract named factor/value-added rows while skipping totals and notes."""
    labels: list[str] = []
    positions: list[int] = []
    for row in range(start_row, frame.shape[0]):
        label = _normalize_text(frame.iat[row, 1])
        if label is None:
            continue
        if label.startswith("("):
            continue
        if label in excluded_labels:
            continue
        labels.append(label)
        positions.append(row)
    if not labels:
        raise WrongFormat("Could not detect factor/value-added rows in the selected ISTAT workbook.")
    return labels, positions


def _find_row_by_label(frame: pd.DataFrame, label: str) -> int:
    """Locate one row by its normalized label."""
    for row in range(frame.shape[0]):
        if _normalize_text(frame.iat[row, 1]) == label:
            return row
    raise WrongFormat(f"Could not find row '{label}' in the selected ISTAT workbook.")


def _find_last_total_use_column(frame: pd.DataFrame) -> int:
    """Locate the rightmost total-use column in one ISTAT use/import workbook."""
    matches: list[int] = []
    for col in range(frame.shape[1]):
        label = _normalize_text(frame.iat[4, col])
        if label and label.startswith(ISTAT_FINAL_DEMAND_TOTAL_PREFIX):
            matches.append(col)
    if not matches:
        raise WrongFormat("Could not detect the total-use column in the selected ISTAT workbook.")
    return matches[-1]


def _read_excel_sheet(path: Path, *, sheet_name: str) -> pd.DataFrame:
    """Read one raw ISTAT Excel sheet without applying headers."""
    log_time(logger, f"Parser: reading ISTAT workbook {path.name} sheet {sheet_name}.", "info")
    frame = pd.read_excel(path, sheet_name=sheet_name, header=None)
    if frame.empty:
        raise WrongFormat("The selected ISTAT workbook sheet is empty.")
    return frame


@contextmanager
def _materialized_istat_source(path: str | Path):
    """Yield one parser-ready filesystem source, extracting zip archives on the fly."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    if source.is_file() and source.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            with zipfile.ZipFile(source, "r") as archive:
                archive.extractall(temp_root)
            children = list(temp_root.iterdir())
            if len(children) == 1 and children[0].is_dir():
                yield children[0]
            else:
                yield temp_root
        return

    yield source


def _sheet_name_for_year(path: Path, year: int, *, table: str, price: str = "current", mode: str = "product") -> str:
    """Resolve the ISTAT workbook sheet name that matches one year."""
    workbook = pd.ExcelFile(path)
    if table == "IOT":
        expected = f"{_ISTAT_IOT_SHEET_PREFIX[mode]}{int(year)}"
    else:
        upper_name = path.name.upper()
        if upper_name.startswith("SUPPLY"):
            prefix = "sup"
        elif upper_name.startswith("IMPORT"):
            prefix = "imprt"
        elif "USEPA" in upper_name:
            prefix = "use"
        else:
            prefix = "uspb"
        suffix = str(year)[-2:]
        expected = f"{prefix}{suffix}"

    if expected not in workbook.sheet_names:
        raise WrongInput(
            f"The selected ISTAT workbook does not contain sheet {expected!r}. "
            f"Available sheets are: {workbook.sheet_names}"
        )
    return expected


def detect_istat_iot_layout(
    path: str | Path,
    *,
    year: int,
    mode: str = "product",
) -> IstatLayout:
    """Resolve the ISTAT symmetric table workbook selected for one parse request."""
    if mode not in ISTAT_IOT_MODES:
        raise WrongInput(f"ISTAT iot_mode should be one of {list(ISTAT_IOT_MODES)}.")

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    pattern = _ISTAT_IOT_FILE_PATTERNS[mode]

    def _select_file(root: Path) -> Path:
        if root.is_file():
            if root.suffix.lower() != ".xlsx" or pattern.match(root.name) is None:
                raise WrongInput(
                    "ISTAT IOT parsing currently supports only the official "
                    "SIMM_TOT_63PxP.xlsx / SIMM_TOT_63BxB.xlsx workbooks."
                )
            return root

        candidates = sorted(
            child for child in root.rglob("*.xlsx") if child.is_file() and pattern.match(child.name)
        )
        if not candidates:
            raise WrongInput("No supported ISTAT symmetric table workbook was found in the selected path.")
        if len(candidates) > 1:
            raise WrongInput(
                "More than one ISTAT symmetric table workbook matches the selected path. "
                "Point to one workbook or one extracted release directory."
            )
        return candidates[0]

    data_path = _select_file(source)
    sheet_name = _sheet_name_for_year(data_path, int(year), table="IOT", mode=mode)
    return IstatLayout(
        root=data_path.parent,
        year=int(year),
        table="IOT",
        iot_mode=mode,
        iot_path=data_path,
        sheet_name=sheet_name,
    )


def detect_istat_sut_layout(
    path: str | Path,
    *,
    year: int,
    level: str = "63",
    price: str = "current",
    valuation: str = "basic",
) -> IstatLayout:
    """Resolve the ISTAT SUT workbook triplet selected for one parse request."""
    normalized_level = str(level)
    if normalized_level not in ISTAT_SUT_LEVELS:
        raise WrongInput(f"ISTAT SUT level should be one of {list(ISTAT_SUT_LEVELS)}.")
    if price not in ISTAT_SUT_PRICES:
        raise WrongInput(f"ISTAT SUT price should be one of {list(ISTAT_SUT_PRICES)}.")
    if valuation not in ISTAT_SUT_VALUATIONS:
        raise WrongInput(f"ISTAT SUT valuation should be one of {list(ISTAT_SUT_VALUATIONS)}.")

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    token = f"{normalized_level}B.xlsx"
    suffix = "_PYP_" if price == "pyp" else "_"
    expected = {
        "supply": f"SUPPLY{suffix}{token}",
        "use": f"{_ISTAT_SUT_USE_FILES[valuation]}{suffix}{token}",
        "import": f"IMPORT{suffix}{token}",
    }

    def _resolve_from_root(root: Path) -> dict[str, Path]:
        if root.is_file():
            if root.suffix.lower() != ".xlsx":
                raise WrongInput("ISTAT SUT parsing expects a directory, zip archive, or one workbook within the release.")
            root = root.parent

        resolved: dict[str, Path] = {}
        for key, filename in expected.items():
            matches = sorted(child for child in root.rglob(filename) if child.is_file())
            if not matches:
                raise WrongInput(f"Could not find the ISTAT SUT workbook {filename} in the selected path.")
            if len(matches) > 1:
                raise WrongInput(
                    f"More than one ISTAT SUT workbook matches {filename}. "
                    "Point to one extracted release directory."
                )
            resolved[key] = matches[0]
        return resolved

    resolved = _resolve_from_root(source)
    sheet_name = _sheet_name_for_year(
        resolved["supply"], int(year), table="SUT", price=price
    )
    _sheet_name_for_year(resolved["use"], int(year), table="SUT", price=price)
    _sheet_name_for_year(resolved["import"], int(year), table="SUT", price=price)
    return IstatLayout(
        root=resolved["supply"].parent,
        year=int(year),
        table="SUT",
        level=normalized_level,
        price=price,
        valuation=valuation,
        supply_path=resolved["supply"],
        use_path=resolved["use"],
        import_path=resolved["import"],
        sheet_name=sheet_name,
    )


def build_istat_iot_from_frame(
    frame: pd.DataFrame,
    *,
    year: int,
    mode: str = "product",
    source_path: str | Path | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    IstatLayout,
]:
    """Transform one ISTAT symmetric table sheet into canonical MARIO IOT blocks."""
    layout = IstatLayout(
        root=Path(source_path or ".").parent,
        year=int(year),
        table="IOT",
        iot_mode=mode,
        iot_path=Path(source_path or f"SIMM_TOT_63{'PxP' if mode == 'product' else 'BxB'}.xlsx"),
        sheet_name=f"{_ISTAT_IOT_SHEET_PREFIX[mode]}{int(year)}",
    )

    sector_codes, sector_labels, sector_col_positions, first_non_sector_col = _sector_columns(frame)
    row_sector_codes, row_sector_labels, sector_row_positions = _code_row_positions(
        frame,
        prefix="R",
        total_code="R",
    )
    if row_sector_codes != sector_codes:
        raise WrongFormat("The ISTAT symmetric table row and column sector codes do not match.")
    if len(row_sector_labels) != len(sector_labels):
        raise WrongFormat("The ISTAT symmetric table row and column sector labels do not match.")

    fd_labels, fd_positions = _final_demand_columns(
        frame,
        start_col=first_non_sector_col + 1,
        excluded_labels=ISTAT_IOT_FINAL_DEMAND_EXCLUDE,
    )
    factor_start = _find_row_by_label(frame, "Consumi intermedi ai prezzi base") + 1
    factor_labels, factor_positions = _factor_rows(
        frame,
        start_row=factor_start,
        excluded_labels=ISTAT_IOT_FACTOR_EXCLUDE,
    )

    sector_axis = _three_level_axis("ITA", _MASTER_INDEX["s"], sector_labels)
    final_demand_axis = _three_level_axis("ITA", _MASTER_INDEX["n"], fd_labels)
    factor_axis = pd.Index(factor_labels, name=None)
    satellite_axis = pd.Index([ISTAT_SATELLITE_PLACEHOLDER], name=None)

    Z = pd.DataFrame(
        _numeric_block(frame, sector_row_positions, sector_col_positions),
        index=sector_axis,
        columns=sector_axis,
    )
    Y = pd.DataFrame(
        _numeric_block(frame, sector_row_positions, fd_positions),
        index=sector_axis,
        columns=final_demand_axis,
    )
    V = pd.DataFrame(
        _numeric_block(frame, factor_positions, sector_col_positions),
        index=factor_axis,
        columns=sector_axis,
    )
    E = _zero_frame(satellite_axis, sector_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
    rename_index(matrices["baseline"])
    indeces = {
        "r": {"main": ["ITA"]},
        "s": {"main": sector_labels},
        "n": {"main": fd_labels},
        "f": {"main": factor_labels},
        "k": {"main": satellite_axis.tolist()},
    }
    units = {
        _MASTER_INDEX["s"]: pd.DataFrame({"unit": [ISTAT_MONETARY_UNIT] * len(sector_labels)}, index=sector_labels),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": [ISTAT_MONETARY_UNIT] * len(factor_labels)}, index=factor_labels),
        _MASTER_INDEX["k"]: pd.DataFrame({"unit": [ISTAT_SATELLITE_UNIT]}, index=satellite_axis),
    }
    log_time(
        logger,
        f"Parser: ISTAT IOT payload ready with shapes Z={Z.shape}, Y={Y.shape}, V={V.shape}.",
        "info",
    )
    return matrices, indeces, units, layout


def build_istat_sut_from_frames(
    supply_frame: pd.DataFrame,
    use_frame: pd.DataFrame,
    import_frame: pd.DataFrame,
    *,
    year: int,
    level: str = "63",
    price: str = "current",
    valuation: str = "basic",
    source_path: str | Path | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    IstatLayout,
]:
    """Transform one ISTAT SUT workbook triplet into split-native MARIO blocks."""
    layout = IstatLayout(
        root=Path(source_path or ".").parent,
        year=int(year),
        table="SUT",
        level=str(level),
        price=price,
        valuation=valuation,
        supply_path=Path(source_path or f"SUPPLY_{level}B.xlsx"),
        use_path=Path(source_path or f"{_ISTAT_SUT_USE_FILES[valuation]}_{level}B.xlsx"),
        import_path=Path(source_path or f"IMPORT_{level}B.xlsx"),
    )

    activity_codes, activity_labels, activity_col_positions, first_non_activity_col = _activity_columns(supply_frame)
    commodity_codes, commodity_labels, commodity_row_positions = _code_row_positions(
        supply_frame,
        prefix="R",
        total_code="R",
    )

    use_activity_codes, use_activity_labels, use_activity_positions, use_first_non_activity_col = _activity_columns(use_frame)
    use_commodity_codes, use_commodity_labels, use_commodity_row_positions = _code_row_positions(
        use_frame,
        prefix="R",
        total_code="R",
    )
    if use_activity_codes != activity_codes:
        raise WrongFormat("The ISTAT SUPPLY and USE workbooks do not expose the same activity code order.")
    if use_commodity_codes != commodity_codes:
        raise WrongFormat("The ISTAT SUPPLY and USE workbooks do not expose the same commodity code order.")

    import_activity_codes, _import_activity_labels, _import_activity_positions, _import_first_non_activity_col = _activity_columns(import_frame)
    import_commodity_codes, _import_commodity_labels, import_commodity_positions = _code_row_positions(
        import_frame,
        prefix="R",
        total_code="R",
    )
    if import_activity_codes != activity_codes or import_commodity_codes != commodity_codes:
        raise WrongFormat("The ISTAT IMPORT workbook does not align with the selected SUT supply/use workbooks.")

    fd_labels, fd_positions = _final_demand_columns(
        use_frame,
        start_col=use_first_non_activity_col + 1,
        excluded_labels=ISTAT_SUT_FINAL_DEMAND_EXCLUDE,
    )
    factor_start = _find_row_by_label(use_frame, "Consumi intermedi ai prezzi base") + 1
    va_labels, va_positions = _factor_rows(
        use_frame,
        start_row=factor_start,
        excluded_labels=ISTAT_SUT_FACTOR_EXCLUDE,
    )
    total_import_col = _find_last_total_use_column(import_frame)

    activity_axis = _three_level_axis("ITA", _MASTER_INDEX["a"], activity_labels)
    commodity_axis = _three_level_axis("ITA", _MASTER_INDEX["c"], commodity_labels)
    final_demand_axis = _three_level_axis("ITA", _MASTER_INDEX["n"], fd_labels)
    factor_labels = va_labels if ISTAT_IMPORT_FACTOR_LABEL in va_labels else [ISTAT_IMPORT_FACTOR_LABEL, *va_labels]
    factor_axis = pd.Index(factor_labels, name=None)
    satellite_axis = pd.Index([ISTAT_SATELLITE_PLACEHOLDER], name=None)

    S = pd.DataFrame(
        _numeric_block(supply_frame, commodity_row_positions, activity_col_positions).T,
        index=activity_axis,
        columns=commodity_axis,
    )
    U = pd.DataFrame(
        _numeric_block(use_frame, use_commodity_row_positions, use_activity_positions),
        index=commodity_axis,
        columns=activity_axis,
    )
    Yc = pd.DataFrame(
        _numeric_block(use_frame, use_commodity_row_positions, fd_positions),
        index=commodity_axis,
        columns=final_demand_axis,
    )
    Ya = _zero_frame(activity_axis, final_demand_axis)

    Va = pd.DataFrame(
        _numeric_block(use_frame, va_positions, use_activity_positions),
        index=pd.Index(va_labels, name=None),
        columns=activity_axis,
    )
    Vc = _zero_frame(factor_axis, commodity_axis)
    import_values = pd.to_numeric(import_frame.iloc[import_commodity_positions, total_import_col], errors="coerce").fillna(0.0).to_numpy(dtype=float, copy=True)
    if ISTAT_IMPORT_FACTOR_LABEL in Vc.index:
        Vc.loc[ISTAT_IMPORT_FACTOR_LABEL, :] = import_values
    Ea = _zero_frame(satellite_axis, activity_axis)
    Ec = _zero_frame(satellite_axis, commodity_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

    matrices = {
        "baseline": {
            "S": S,
            "U": U,
            "Ya": Ya,
            "Yc": Yc,
            "Va": Va,
            "Vc": Vc,
            "Ea": Ea,
            "Ec": Ec,
            "EY": EY,
        }
    }
    rename_index(matrices["baseline"])
    indeces = {
        "r": {"main": ["ITA"]},
        "a": {"main": activity_labels},
        "c": {"main": commodity_labels},
        "s": {"main": activity_labels + [label for label in commodity_labels if label not in activity_labels]},
        "n": {"main": fd_labels},
        "f": {"main": factor_labels},
        "k": {"main": satellite_axis.tolist()},
    }
    units = {
        _MASTER_INDEX["a"]: pd.DataFrame({"unit": [ISTAT_MONETARY_UNIT] * len(activity_labels)}, index=activity_labels),
        _MASTER_INDEX["c"]: pd.DataFrame({"unit": [ISTAT_MONETARY_UNIT] * len(commodity_labels)}, index=commodity_labels),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": [ISTAT_MONETARY_UNIT] * len(factor_labels)}, index=factor_labels),
        _MASTER_INDEX["k"]: pd.DataFrame({"unit": [ISTAT_SATELLITE_UNIT]}, index=satellite_axis),
    }
    log_time(
        logger,
        f"Parser: ISTAT SUT payload ready with shapes S={S.shape}, U={U.shape}, Yc={Yc.shape}, Va={Va.shape}, Vc={Vc.shape}.",
        "info",
    )
    return matrices, indeces, units, layout


def parse_istat_iot(
    path: str | Path,
    *,
    year: int,
    mode: str = "product",
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    IstatLayout,
]:
    """Parse one ISTAT symmetric table workbook into canonical MARIO IOT blocks."""
    with _materialized_istat_source(path) as source:
        layout = detect_istat_iot_layout(source, year=year, mode=mode)
        frame = _read_excel_sheet(layout.iot_path, sheet_name=layout.sheet_name)
        return build_istat_iot_from_frame(
            frame,
            year=layout.year,
            mode=mode,
            source_path=layout.iot_path,
        )


def parse_istat_sut(
    path: str | Path,
    *,
    year: int,
    level: str = "63",
    price: str = "current",
    valuation: str = "basic",
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    IstatLayout,
]:
    """Parse one ISTAT supply/use release bundle into split-native MARIO blocks."""
    with _materialized_istat_source(path) as source:
        layout = detect_istat_sut_layout(
            source,
            year=year,
            level=level,
            price=price,
            valuation=valuation,
        )
        supply_sheet = _sheet_name_for_year(layout.supply_path, layout.year, table="SUT", price=price)
        use_sheet = _sheet_name_for_year(layout.use_path, layout.year, table="SUT", price=price)
        import_sheet = _sheet_name_for_year(layout.import_path, layout.year, table="SUT", price=price)
        supply = _read_excel_sheet(layout.supply_path, sheet_name=supply_sheet)
        use = _read_excel_sheet(layout.use_path, sheet_name=use_sheet)
        imports = _read_excel_sheet(layout.import_path, sheet_name=import_sheet)
        return build_istat_sut_from_frames(
            supply,
            use,
            imports,
            year=layout.year,
            level=layout.level,
            price=layout.price,
            valuation=layout.valuation,
            source_path=layout.supply_path,
        )
