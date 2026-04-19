"""Local-file parser for BEA Supply-Use workbooks."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
from pathlib import Path
import tempfile
import zipfile

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    BEA_LEVELS,
    BEA_MONETARY_UNIT,
    BEA_PRICE_LABEL,
    BEA_SATELLITE_PLACEHOLDER,
    BEA_SATELLITE_UNIT,
    BEA_SOURCE,
    BEA_SUPPLY_COMMODITY_INPUT_CODES,
    BEA_USE_VALUE_ADDED_CODES,
    BEA_WORKBOOK_FILES,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_BEA_HEADER_LAYOUT = {
    "summary": {"label_row": 6, "code_row": 5, "data_start": 7},
    "sector": {"label_row": 6, "code_row": 5, "data_start": 7},
    "detail": {"label_row": 4, "code_row": 5, "data_start": 6},
}
_BEA_REGION = "USA"


@dataclass(frozen=True)
class BEALayout:
    """Filesystem layout and metadata for one BEA supply-use selection."""

    root: Path
    year: int
    level: str
    supply_path: Path
    use_path: Path
    notes: tuple[str, ...] = ()

    @property
    def dataset_name(self) -> str:
        """Return a compact default dataset label."""
        return f"BEA Supply-Use {self.year} {self.level.title()}"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in metadata."""
        return BEA_SOURCE

    @property
    def price(self) -> str:
        """Return the price metadata stored in MARIO."""
        return BEA_PRICE_LABEL


def _normalize_text(value) -> str | None:
    """Normalize one cell to compact plain text."""
    if pd.isna(value):
        return None
    text = " ".join(str(value).replace("\n", " ").split())
    if not text or text.lower() == "nan":
        return None
    return text


def _normalize_code(value) -> str | None:
    """Normalize one code-like cell for structural comparisons."""
    text = _normalize_text(value)
    if text is None:
        return None
    return text.replace(" ", "").upper()


def _three_level_axis(region: str, level_label: str, items: list[str]) -> pd.MultiIndex:
    """Build one canonical MARIO single-region axis."""
    return pd.MultiIndex.from_arrays(
        [[region] * len(items), [level_label] * len(items), items]
    )


def _zero_frame(index, columns) -> pd.DataFrame:
    """Allocate one zero-filled dataframe with the requested axes."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


@contextmanager
def _materialized_bea_source(path: str | Path):
    """Yield one directory-like BEA source from a directory, workbook, or zip."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    if source.is_dir():
        yield source
        return

    if source.suffix.lower() == ".xlsx":
        yield source.parent
        return

    if source.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(source, "r") as archive:
                archive.extractall(root)
            yield root
        return

    raise WrongInput(
        "BEA parsing supports one extracted directory, one workbook path, or the official SUPPLY-USE.zip bundle."
    )


def _normalize_level(level: str) -> str:
    """Validate the requested BEA aggregation level."""
    normalized = str(level).strip().lower()
    if normalized not in BEA_LEVELS:
        raise WrongInput(f"BEA level should be one of {list(BEA_LEVELS)}.")
    return normalized


def _read_excel_sheet(path: Path, *, year: int) -> pd.DataFrame:
    """Read one yearly sheet from one BEA workbook."""
    workbook = pd.ExcelFile(path)
    sheet_name = str(year)
    if sheet_name not in workbook.sheet_names:
        raise WrongInput(
            f"The workbook '{path.name}' does not contain year {year}. "
            f"Available sheets: {workbook.sheet_names}."
        )
    return workbook.parse(sheet_name=sheet_name, header=None)


def detect_bea_sut_layout(
    path: str | Path,
    *,
    year: int,
    level: str = "summary",
) -> BEALayout:
    """Resolve one BEA Supply-Use workbook pair from a local path."""
    normalized_level = _normalize_level(level)
    source = Path(path)
    root = source if source.is_dir() else source.parent

    expected = BEA_WORKBOOK_FILES[normalized_level]
    supply_path = root / expected["supply"]
    use_path = root / expected["use"]
    if not supply_path.exists() or not use_path.exists():
        raise WrongInput(
            "Could not find the expected BEA Supply-Use workbook pair for level "
            f"'{normalized_level}' under '{root}'. Expected files: "
            f"{expected['supply']} and {expected['use']}."
        )

    notes = (
        "S is read from the BEA Supply workbook using domestic industry output columns.",
        "Va is read from the use-workbook value-added footer rows.",
        "Vc stores commodity-side imports, CIF/FOB adjustments, trade and transport margins, and product taxes from the Supply workbook.",
    )
    return BEALayout(
        root=root,
        year=int(year),
        level=normalized_level,
        supply_path=supply_path,
        use_path=use_path,
        notes=notes,
    )


def _extract_activity_columns(
    frame: pd.DataFrame,
    *,
    code_row: int,
    label_row: int,
    total_code: str,
) -> tuple[list[str], list[str], list[int], int]:
    """Extract activity columns up to the total marker column."""
    codes: list[str] = []
    labels: list[str] = []
    positions: list[int] = []
    total_col = -1
    col = 2
    target = _normalize_code(total_code)
    while col < frame.shape[1]:
        code = _normalize_code(frame.iat[code_row, col])
        if code is None:
            col += 1
            continue
        if code == target:
            total_col = col
            break
        codes.append(code)
        labels.append(_normalize_text(frame.iat[label_row, col]) or code)
        positions.append(col)
        col += 1

    if not codes or total_col < 0:
        raise WrongFormat("Could not detect the BEA activity block in the selected workbook.")
    return codes, labels, positions, total_col


def _extract_contiguous_rows(
    frame: pd.DataFrame,
    *,
    data_start: int,
    total_code: str,
    total_label: str | None = None,
) -> tuple[list[str], list[str], list[int], int]:
    """Extract coded rows up to the requested total marker row."""
    codes: list[str] = []
    labels: list[str] = []
    positions: list[int] = []
    total_row = -1
    target = _normalize_code(total_code)
    target_label = _normalize_code(total_label) if total_label is not None else None

    for row in range(data_start, frame.shape[0]):
        code = _normalize_code(frame.iat[row, 0])
        label = _normalize_code(frame.iat[row, 1])
        if code is None:
            if target_label is not None and label == target_label:
                total_row = row
                break
            continue
        if code == target or (target_label is not None and label == target_label):
            total_row = row
            break
        codes.append(code)
        labels.append(_normalize_text(frame.iat[row, 1]) or code)
        positions.append(row)

    if not codes or total_row < 0:
        raise WrongFormat(
            f"Could not detect the BEA commodity block before total marker '{total_code}'."
        )
    return codes, labels, positions, total_row


def _extract_named_columns(
    frame: pd.DataFrame,
    *,
    start_col: int,
    code_row: int,
    label_row: int,
    stop_code: str,
) -> tuple[list[str], list[str], list[int]]:
    """Extract contiguous named columns up to one stop marker."""
    codes: list[str] = []
    labels: list[str] = []
    positions: list[int] = []
    target = _normalize_code(stop_code)

    for col in range(start_col, frame.shape[1]):
        code = _normalize_code(frame.iat[code_row, col])
        if code is None:
            continue
        if code == target:
            break
        codes.append(code)
        labels.append(_normalize_text(frame.iat[label_row, col]) or code)
        positions.append(col)

    if not codes:
        raise WrongFormat("Could not detect the requested BEA column block.")
    return codes, labels, positions


def _numeric_block(frame: pd.DataFrame, row_positions: list[int], col_positions: list[int]) -> np.ndarray:
    """Return one numeric block from raw workbook cells."""
    block = frame.iloc[row_positions, col_positions].apply(pd.to_numeric, errors="coerce")
    return block.fillna(0.0).to_numpy(dtype=float, copy=True)


def _build_value_added(
    use_frame: pd.DataFrame,
    *,
    total_row: int,
    activity_positions: list[int],
    factor_axis: pd.Index,
) -> pd.DataFrame:
    """Build the activity-side exogenous input matrix from BEA use footer rows."""
    row_lookup: dict[str, int] = {}
    for row in range(total_row + 1, use_frame.shape[0]):
        code = _normalize_code(use_frame.iat[row, 0])
        if code is not None and code not in row_lookup:
            row_lookup[code] = row

    Va = _zero_frame(factor_axis, pd.RangeIndex(len(activity_positions)))
    for code, label in BEA_USE_VALUE_ADDED_CODES:
        normalized = _normalize_code(code)
        if normalized in row_lookup and label in Va.index:
            values = (
                pd.to_numeric(use_frame.iloc[row_lookup[normalized], activity_positions], errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=float, copy=True)
            )
            Va.loc[label, :] = values
    return Va


def _build_commodity_inputs(
    supply_frame: pd.DataFrame,
    *,
    commodity_rows: list[int],
    supply_total_col: int,
    factor_axis: pd.Index,
) -> pd.DataFrame:
    """Build the commodity-side exogenous input matrix from BEA supply columns."""
    col_lookup: dict[str, int] = {}
    for col in range(supply_total_col + 1, supply_frame.shape[1]):
        code = _normalize_code(supply_frame.iat[_BEA_HEADER_LAYOUT["summary"]["code_row"], col])
        if code is not None and code not in col_lookup:
            col_lookup[code] = col

    # Detail workbooks use the same code row index as the summary/sector case,
    # but the label row changes. Column-code scanning above therefore remains safe
    # because the code row is fixed at row index 5 for every verified level.
    Vc = _zero_frame(factor_axis, pd.RangeIndex(len(commodity_rows)))
    for code, label in BEA_SUPPLY_COMMODITY_INPUT_CODES:
        normalized = _normalize_code(code)
        if normalized in col_lookup and label in Vc.index:
            values = (
                pd.to_numeric(supply_frame.iloc[commodity_rows, col_lookup[normalized]], errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=float, copy=True)
            )
            Vc.loc[label, :] = values
    return Vc


def build_bea_sut_from_frames(
    supply_frame: pd.DataFrame,
    use_frame: pd.DataFrame,
    *,
    year: int,
    level: str,
    layout: BEALayout,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    BEALayout,
]:
    """Build canonical MARIO SUT blocks from one BEA supply-use workbook pair."""
    header = _BEA_HEADER_LAYOUT[level]

    supply_activity_codes, supply_activity_labels, supply_activity_positions, supply_total_col = _extract_activity_columns(
        supply_frame,
        code_row=header["code_row"],
        label_row=header["label_row"],
        total_code="T007",
    )
    use_activity_codes, use_activity_labels, use_activity_positions, use_total_col = _extract_activity_columns(
        use_frame,
        code_row=header["code_row"],
        label_row=header["label_row"],
        total_code="T001",
    )
    if supply_activity_codes != use_activity_codes:
        raise WrongFormat("The selected BEA Supply and Use workbooks do not expose the same activity code order.")

    supply_commodity_codes, supply_commodity_labels, supply_commodity_rows, _supply_total_row = _extract_contiguous_rows(
        supply_frame,
        data_start=header["data_start"],
        total_code="T017",
        total_label="Total industry supply",
    )
    use_commodity_codes, use_commodity_labels, use_commodity_rows, use_total_row = _extract_contiguous_rows(
        use_frame,
        data_start=header["data_start"],
        total_code="T005",
        total_label="Total Intermediate",
    )
    if supply_commodity_codes != use_commodity_codes:
        raise WrongFormat("The selected BEA Supply and Use workbooks do not expose the same commodity code order.")

    fd_codes, fd_labels, fd_positions = _extract_named_columns(
        use_frame,
        start_col=use_total_col + 1,
        code_row=header["code_row"],
        label_row=header["label_row"],
        stop_code="T019",
    )
    _ = fd_codes

    va_labels: list[str] = []
    for code, label in BEA_USE_VALUE_ADDED_CODES:
        if any(_normalize_code(use_frame.iat[row, 0]) == _normalize_code(code) for row in range(use_total_row + 1, use_frame.shape[0])):
            if label not in va_labels:
                va_labels.append(label)

    vc_labels: list[str] = []
    for code, label in BEA_SUPPLY_COMMODITY_INPUT_CODES:
        if any(_normalize_code(supply_frame.iat[header["code_row"], col]) == _normalize_code(code) for col in range(supply_total_col + 1, supply_frame.shape[1])):
            if label not in vc_labels:
                vc_labels.append(label)

    factor_labels = va_labels + [label for label in vc_labels if label not in va_labels]
    if not factor_labels:
        raise WrongFormat("Could not detect any BEA exogenous input rows or columns.")

    activity_axis = _three_level_axis(_BEA_REGION, _MASTER_INDEX["a"], supply_activity_labels)
    commodity_axis = _three_level_axis(_BEA_REGION, _MASTER_INDEX["c"], supply_commodity_labels)
    final_demand_axis = _three_level_axis(_BEA_REGION, _MASTER_INDEX["n"], fd_labels)
    factor_axis = pd.Index(factor_labels, name=None)
    satellite_axis = pd.Index([BEA_SATELLITE_PLACEHOLDER], name=None)

    S = pd.DataFrame(
        _numeric_block(supply_frame, supply_commodity_rows, supply_activity_positions).T,
        index=activity_axis,
        columns=commodity_axis,
    )
    U = pd.DataFrame(
        _numeric_block(use_frame, use_commodity_rows, use_activity_positions),
        index=commodity_axis,
        columns=activity_axis,
    )
    Yc = pd.DataFrame(
        _numeric_block(use_frame, use_commodity_rows, fd_positions),
        index=commodity_axis,
        columns=final_demand_axis,
    )
    Ya = _zero_frame(activity_axis, final_demand_axis)

    Va = _build_value_added(
        use_frame,
        total_row=use_total_row,
        activity_positions=use_activity_positions,
        factor_axis=factor_axis,
    )
    Va.columns = activity_axis

    supply_code_row = header["code_row"]
    Vc = _zero_frame(factor_axis, commodity_axis)
    col_lookup = {
        _normalize_code(supply_frame.iat[supply_code_row, col]): col
        for col in range(supply_total_col + 1, supply_frame.shape[1])
        if _normalize_code(supply_frame.iat[supply_code_row, col]) is not None
    }
    for code, label in BEA_SUPPLY_COMMODITY_INPUT_CODES:
        normalized = _normalize_code(code)
        if normalized in col_lookup and label in Vc.index:
            values = (
                pd.to_numeric(supply_frame.iloc[supply_commodity_rows, col_lookup[normalized]], errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=float, copy=True)
            )
            Vc.loc[label, :] = values

    Ea = _zero_frame(satellite_axis, activity_axis)
    Ec = _zero_frame(satellite_axis, commodity_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

    matrices = {
        "baseline": {
            "S": S.astype(float),
            "U": U.astype(float),
            "Ya": Ya.astype(float),
            "Yc": Yc.astype(float),
            "Va": Va.astype(float),
            "Vc": Vc.astype(float),
            "Ea": Ea.astype(float),
            "Ec": Ec.astype(float),
            "EY": EY.astype(float),
        }
    }
    rename_index(matrices["baseline"])
    indeces = {
        "r": {"main": [_BEA_REGION]},
        "a": {"main": supply_activity_labels},
        "c": {"main": supply_commodity_labels},
        "s": {
            "main": supply_activity_labels
            + [label for label in supply_commodity_labels if label not in supply_activity_labels]
        },
        "n": {"main": fd_labels},
        "f": {"main": factor_labels},
        "k": {"main": satellite_axis.tolist()},
    }
    units = {
        _MASTER_INDEX["a"]: pd.DataFrame({"unit": [BEA_MONETARY_UNIT] * len(supply_activity_labels)}, index=supply_activity_labels),
        _MASTER_INDEX["c"]: pd.DataFrame({"unit": [BEA_MONETARY_UNIT] * len(supply_commodity_labels)}, index=supply_commodity_labels),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": [BEA_MONETARY_UNIT] * len(factor_labels)}, index=factor_labels),
        _MASTER_INDEX["k"]: pd.DataFrame({"unit": [BEA_SATELLITE_UNIT]}, index=satellite_axis),
    }

    log_time(
        logger,
        (
            "Parser: BEA SUT payload ready with shapes "
            f"S={S.shape}, U={U.shape}, Yc={Yc.shape}, Va={Va.shape}, Vc={Vc.shape}."
        ),
        "info",
    )
    return matrices, indeces, units, layout


def parse_bea_sut(
    path: str | Path,
    *,
    year: int,
    level: str = "summary",
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    BEALayout,
]:
    """Parse one local BEA Supply-Use bundle into split-native MARIO blocks."""
    with _materialized_bea_source(path) as source:
        layout = detect_bea_sut_layout(source, year=year, level=level)
        supply_frame = _read_excel_sheet(layout.supply_path, year=layout.year)
        use_frame = _read_excel_sheet(layout.use_path, year=layout.year)
        return build_bea_sut_from_frames(
            supply_frame,
            use_frame,
            year=layout.year,
            level=layout.level,
            layout=layout,
        )
