"""Direct parser for USEEIO model workbooks."""

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
    USEEIO_FORMATS,
    USEEIO_MONETARY_UNIT,
    USEEIO_PRICE_LABEL,
    USEEIO_SOURCE,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_USEEIO_FILENAME_RE = re.compile(
    r"USEEIOv(?P<version>\d+(?:\.\d+)*)-(?P<alias>.+)-(?P<release>\d{2,4})$",
    flags=re.IGNORECASE,
)
_USEEIO_DEMAND_RE = re.compile(
    r"(?P<year>\d{4})_[A-Z]{2}_(Production|Consumption)_(Complete|Domestic)$"
)
_USEEIO_REQUIRED_SHEETS = {
    "V",
    "U",
    "B",
    "q",
    "flows",
    "commodities_meta",
    "final_demand_meta",
    "value_added_meta",
}


@dataclass(frozen=True)
class USEEIOLayout:
    """Workbook layout metadata for one USEEIO parser run."""

    path: Path
    workbook_format: str
    workbook_version: str | None
    model_alias: str | None
    release_year: int | None
    io_year: int
    region_code: str
    notes: tuple[str, ...] = ()

    @property
    def dataset_name(self) -> str:
        """Return the default dataset label stored in MARIO metadata."""
        alias = self.model_alias or self.path.stem
        version = f"v{self.workbook_version}" if self.workbook_version else "workbook"
        if self.release_year is not None:
            return f"USEEIO {version} {alias} {self.release_year}"
        return f"USEEIO {version} {alias}"

    @property
    def price(self) -> str:
        """Return the price label stored in MARIO metadata."""
        return USEEIO_PRICE_LABEL

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        return USEEIO_SOURCE


def _resolve_useeio_workbook(
    path: str | Path,
    *,
    model_alias: str | None = None,
    release_year: int | None = None,
) -> Path:
    """Resolve one local USEEIO workbook from a file or directory path."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    if source.is_file():
        if source.suffix.lower() != ".xlsx":
            raise WrongInput("USEEIO parsing currently supports local .xlsx workbooks only.")
        return source

    candidates = sorted(
        candidate
        for candidate in source.iterdir()
        if candidate.is_file()
        and candidate.suffix.lower() == ".xlsx"
        and not candidate.name.startswith("~$")
    )
    if not candidates:
        raise WrongInput("Could not find any USEEIO .xlsx workbook in the selected directory.")

    requested_alias = str(model_alias).strip().lower() if model_alias is not None else None
    requested_release_year = (
        _parse_release_year(str(release_year)) if release_year is not None else None
    )
    if requested_alias is not None or requested_release_year is not None:
        filtered = []
        for candidate in candidates:
            match = _USEEIO_FILENAME_RE.fullmatch(candidate.stem)
            candidate_alias = match.group("alias").lower() if match is not None else None
            candidate_release_year = _parse_release_year(
                match.group("release") if match is not None else None
            )
            if requested_alias is not None and candidate_alias != requested_alias:
                continue
            if (
                requested_release_year is not None
                and candidate_release_year != requested_release_year
            ):
                continue
            filtered.append(candidate)
        candidates = filtered

    if not candidates:
        selector = []
        if requested_alias is not None:
            selector.append(f"model_alias={requested_alias!r}")
        if requested_release_year is not None:
            selector.append(f"release_year={requested_release_year!r}")
        raise WrongInput(
            "Could not find a USEEIO workbook matching "
            f"{', '.join(selector) or 'the requested selectors'}."
        )
    if len(candidates) > 1:
        names = ", ".join(candidate.name for candidate in candidates[:10])
        raise WrongInput(
            "More than one USEEIO workbook was found. "
            "Please point the parser to one specific .xlsx file, or select a "
            f"directory workbook with model_alias= and release_year=. Found: {names}"
        )
    return candidates[0]


def _normalize_format(value: str) -> str:
    """Validate the requested USEEIO workbook format selector."""
    normalized = str(value).strip().lower()
    if normalized not in USEEIO_FORMATS:
        raise WrongInput(f"USEEIO format should be one of {list(USEEIO_FORMATS)}.")
    return normalized


def _parse_release_year(token: str | None) -> int | None:
    """Normalize one year token found in the workbook filename."""
    if token is None:
        return None
    if len(token) == 4:
        return int(token)
    if len(token) == 2:
        return 2000 + int(token)
    return None


def _read_numeric_sheet(workbook: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    """Read one numeric workbook sheet using the first column as row labels."""
    frame = workbook.parse(sheet_name, index_col=0)
    frame.index = frame.index.map(str)
    frame.columns = frame.columns.map(str)
    return frame.apply(pd.to_numeric, errors="coerce").fillna(0.0)


def _read_vector_sheet(workbook: pd.ExcelFile, sheet_name: str) -> pd.Series:
    """Read one one-column vector sheet keyed by the first column."""
    frame = workbook.parse(sheet_name, index_col=0)
    if frame.empty:
        raise WrongFormat(f"USEEIO sheet '{sheet_name}' is empty.")
    series = pd.to_numeric(frame.iloc[:, 0], errors="coerce").fillna(0.0)
    series.index = series.index.map(str)
    series.name = sheet_name
    return series


def _read_meta_sheet(
    workbook: pd.ExcelFile,
    sheet_name: str,
    *,
    required_columns: tuple[str, ...],
) -> pd.DataFrame:
    """Read one metadata sheet and validate the required fields."""
    frame = workbook.parse(sheet_name)
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise WrongFormat(
            f"USEEIO sheet '{sheet_name}' is missing the required columns {missing}."
        )
    return frame.copy()


def _infer_io_year(workbook: pd.ExcelFile) -> int:
    """Infer the model IO year from the workbook demand metadata."""
    if "demands" in workbook.sheet_names:
        demands = workbook.parse("demands")
        if "Year" in demands.columns:
            years = {
                int(year)
                for year in pd.to_numeric(demands["Year"], errors="coerce").dropna().astype(int).tolist()
            }
            if len(years) == 1:
                return next(iter(years))

    years = {
        int(match.group("year"))
        for sheet_name in workbook.sheet_names
        for match in [_USEEIO_DEMAND_RE.fullmatch(str(sheet_name).strip())]
        if match is not None
    }
    if len(years) == 1:
        return next(iter(years))

    raise WrongFormat("Could not infer one unique IO year from the USEEIO workbook.")


def _infer_region_code(
    commodities_meta: pd.DataFrame,
    final_demand_meta: pd.DataFrame,
    value_added_meta: pd.DataFrame,
) -> str:
    """Infer the one region code represented by the USEEIO workbook."""
    locations: set[str] = set()
    for frame in (commodities_meta, final_demand_meta, value_added_meta):
        if "Location" in frame.columns:
            locations.update(
                str(value).strip()
                for value in frame["Location"].dropna().tolist()
                if str(value).strip()
            )
    if len(locations) != 1:
        raise WrongFormat(
            f"USEEIO workbooks should represent one region only. Found locations: {sorted(locations)}"
        )
    return next(iter(locations))


def _dedupe_labels(labels: list[str], ids: list[str]) -> list[str]:
    """Keep labels human-readable while preserving uniqueness."""
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1

    deduped: list[str] = []
    for label, identifier in zip(labels, ids):
        if counts[label] == 1:
            deduped.append(label)
        else:
            deduped.append(f"{label} [{identifier}]")
    return deduped


def _label_map(meta: pd.DataFrame) -> dict[str, str]:
    """Build one ID -> human label mapping from a USEEIO metadata table."""
    ids = meta["ID"].astype(str).tolist()
    names = meta["Name"].fillna(meta["ID"]).astype(str).tolist()
    labels = _dedupe_labels(names, ids)
    return dict(zip(ids, labels))


def _single_region_axis(region_code: str, labels: list[str], *, level_code: str) -> pd.MultiIndex:
    """Build one canonical MARIO three-level axis for one single-region table."""
    return pd.MultiIndex.from_arrays(
        [
            [region_code] * len(labels),
            [_MASTER_INDEX[level_code]] * len(labels),
            labels,
        ]
    )


def _zero_frame(index, columns) -> pd.DataFrame:
    """Allocate one zero-filled dataframe with the requested axes."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def detect_useeio_layout(
    path: str | Path,
    *,
    format: str = "auto",
    model_alias: str | None = None,
    release_year: int | None = None,
) -> USEEIOLayout:
    """Detect the supported USEEIO workbook layout."""
    workbook_path = _resolve_useeio_workbook(
        path,
        model_alias=model_alias,
        release_year=release_year,
    )
    requested = _normalize_format(format)
    workbook = pd.ExcelFile(workbook_path)

    missing_sheets = sorted(_USEEIO_REQUIRED_SHEETS.difference(workbook.sheet_names))
    if missing_sheets:
        raise WrongFormat(
            f"The selected USEEIO workbook is missing the required sheets {missing_sheets}."
        )

    detected = "v2.5_workbook"
    if requested != "auto" and requested != detected:
        raise WrongInput(
            f"USEEIO format '{requested}' is not compatible with this workbook. "
            f"Detected format: '{detected}'."
        )

    io_year = _infer_io_year(workbook)
    commodities_meta = _read_meta_sheet(
        workbook,
        "commodities_meta",
        required_columns=("ID", "Name", "Location"),
    )
    final_demand_meta = _read_meta_sheet(
        workbook,
        "final_demand_meta",
        required_columns=("ID", "Name", "Location"),
    )
    value_added_meta = _read_meta_sheet(
        workbook,
        "value_added_meta",
        required_columns=("ID", "Name", "Location"),
    )
    region_code = _infer_region_code(commodities_meta, final_demand_meta, value_added_meta)

    match = _USEEIO_FILENAME_RE.fullmatch(workbook_path.stem)
    workbook_version = match.group("version") if match is not None else None
    model_alias = match.group("alias") if match is not None else None
    release_year = _parse_release_year(match.group("release") if match is not None else None)

    notes = [
        "Parsed from one USEEIO workbook export.",
        (
            "For the supported v2.5 workbook format, direct environmental flows are "
            "loaded on the commodity side as Ec = B * q."
        ),
    ]
    if release_year is not None and release_year != io_year:
        notes.append(
            f"The workbook release year is {release_year}, while the internal IO year is {io_year}."
        )

    return USEEIOLayout(
        path=workbook_path,
        workbook_format=detected,
        workbook_version=workbook_version,
        model_alias=model_alias,
        release_year=release_year,
        io_year=io_year,
        region_code=region_code,
        notes=tuple(notes),
    )


def parse_useeio_sut(
    path: str | Path,
    *,
    format: str = "auto",
    model_alias: str | None = None,
    release_year: int | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], USEEIOLayout]:
    """Parse one supported USEEIO workbook into canonical MARIO SUT blocks."""
    layout = detect_useeio_layout(
        path,
        format=format,
        model_alias=model_alias,
        release_year=release_year,
    )
    workbook = pd.ExcelFile(layout.path)

    V = _read_numeric_sheet(workbook, "V")
    U_sheet = _read_numeric_sheet(workbook, "U")
    B = _read_numeric_sheet(workbook, "B")
    q = _read_vector_sheet(workbook, "q")

    commodities_meta = _read_meta_sheet(
        workbook,
        "commodities_meta",
        required_columns=("ID", "Name", "Location", "Unit"),
    )
    final_demand_meta = _read_meta_sheet(
        workbook,
        "final_demand_meta",
        required_columns=("ID", "Name", "Location"),
    )
    value_added_meta = _read_meta_sheet(
        workbook,
        "value_added_meta",
        required_columns=("ID", "Name", "Location"),
    )
    flows_meta = _read_meta_sheet(
        workbook,
        "flows",
        required_columns=("ID", "Unit"),
    )

    commodity_ids = commodities_meta["ID"].astype(str).tolist()
    activity_ids = V.index.astype(str).tolist()
    factor_ids = value_added_meta["ID"].astype(str).tolist()
    final_demand_ids = final_demand_meta["ID"].astype(str).tolist()

    expected_u_rows = set(commodity_ids).union(factor_ids)
    expected_u_columns = set(activity_ids).union(final_demand_ids)
    actual_u_rows = set(U_sheet.index.astype(str))
    actual_u_columns = set(U_sheet.columns.astype(str))

    if actual_u_rows != expected_u_rows:
        missing = sorted(expected_u_rows.difference(actual_u_rows))
        extra = sorted(actual_u_rows.difference(expected_u_rows))
        raise WrongFormat(
            "Unexpected USEEIO U-row structure. "
            f"Missing rows: {missing}; unexpected rows: {extra}"
        )
    if actual_u_columns != expected_u_columns:
        missing = sorted(expected_u_columns.difference(actual_u_columns))
        extra = sorted(actual_u_columns.difference(expected_u_columns))
        raise WrongFormat(
            "Unexpected USEEIO U-column structure. "
            f"Missing columns: {missing}; unexpected columns: {extra}"
        )

    if set(B.columns.astype(str)) != set(commodity_ids):
        missing = sorted(set(commodity_ids).difference(B.columns.astype(str)))
        extra = sorted(set(B.columns.astype(str)).difference(commodity_ids))
        raise WrongFormat(
            "The USEEIO B matrix does not align with the expected commodity axis. "
            f"Missing commodities: {missing}; unexpected columns: {extra}"
        )
    if set(q.index.astype(str)) != set(commodity_ids):
        missing = sorted(set(commodity_ids).difference(q.index.astype(str)))
        extra = sorted(set(q.index.astype(str)).difference(commodity_ids))
        raise WrongFormat(
            "The USEEIO q vector does not align with the expected commodity axis. "
            f"Missing commodities: {missing}; unexpected rows: {extra}"
        )

    commodity_labels_by_id = _label_map(commodities_meta)
    final_demand_labels_by_id = _label_map(final_demand_meta)
    factor_labels_by_id = _label_map(value_added_meta)

    commodity_names = [commodity_labels_by_id[code] for code in commodity_ids]
    activity_names = _dedupe_labels(
        [commodity_labels_by_id.get(code, code) for code in activity_ids],
        activity_ids,
    )
    final_demand_names = [final_demand_labels_by_id[code] for code in final_demand_ids]
    factor_names = [factor_labels_by_id[code] for code in factor_ids]

    flow_unit_by_id = dict(
        zip(
            flows_meta["ID"].astype(str).tolist(),
            flows_meta["Unit"].fillna("").astype(str).tolist(),
        )
    )
    satellite_ids = B.index.astype(str).tolist()
    satellite_names = satellite_ids

    activity_axis = _single_region_axis(layout.region_code, activity_names, level_code="a")
    commodity_axis = _single_region_axis(layout.region_code, commodity_names, level_code="c")
    final_demand_axis = _single_region_axis(layout.region_code, final_demand_names, level_code="n")
    factor_axis = pd.Index(factor_names, name=None)
    satellite_axis = pd.Index(satellite_names, name=None)

    S = pd.DataFrame(
        V.reindex(index=activity_ids, columns=commodity_ids, fill_value=0.0).to_numpy(dtype=float),
        index=activity_axis,
        columns=commodity_axis,
    )
    U = pd.DataFrame(
        U_sheet.reindex(index=commodity_ids, columns=activity_ids, fill_value=0.0).to_numpy(dtype=float),
        index=commodity_axis,
        columns=activity_axis,
    )
    Yc = pd.DataFrame(
        U_sheet.reindex(index=commodity_ids, columns=final_demand_ids, fill_value=0.0).to_numpy(dtype=float),
        index=commodity_axis,
        columns=final_demand_axis,
    )
    Va = pd.DataFrame(
        U_sheet.reindex(index=factor_ids, columns=activity_ids, fill_value=0.0).to_numpy(dtype=float),
        index=factor_axis,
        columns=activity_axis,
    )

    q_aligned = q.reindex(commodity_ids).astype(float)
    Ec_raw = B.reindex(index=satellite_ids, columns=commodity_ids, fill_value=0.0).mul(q_aligned, axis=1)
    Ec = pd.DataFrame(
        Ec_raw.to_numpy(dtype=float),
        index=satellite_axis,
        columns=commodity_axis,
    )

    Ya = _zero_frame(activity_axis, final_demand_axis)
    Vc = _zero_frame(factor_axis, commodity_axis)
    Ea = _zero_frame(satellite_axis, activity_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

    factor_to_fd = U_sheet.reindex(index=factor_ids, columns=final_demand_ids, fill_value=0.0)
    notes = list(layout.notes)
    if float(np.abs(factor_to_fd.to_numpy(dtype=float)).sum()) != 0.0:
        notes.append(
            "The USEEIO U sheet contains non-zero value-added entries in final-demand columns. "
            "MARIO currently ignores that block and keeps EY zero-filled."
        )
        layout = USEEIOLayout(
            path=layout.path,
            workbook_format=layout.workbook_format,
            workbook_version=layout.workbook_version,
            model_alias=layout.model_alias,
            release_year=layout.release_year,
            io_year=layout.io_year,
            region_code=layout.region_code,
            notes=tuple(notes),
        )

    matrices = {
        "baseline": {
            "U": U,
            "S": S,
            "Ya": Ya,
            "Yc": Yc,
            "Va": Va,
            "Vc": Vc,
            "Ea": Ea,
            "Ec": Ec,
            "EY": EY,
        }
    }

    units = {
        _MASTER_INDEX["a"]: pd.DataFrame(
            {"unit": [USEEIO_MONETARY_UNIT] * len(activity_names)},
            index=activity_names,
        ),
        _MASTER_INDEX["c"]: pd.DataFrame(
            {"unit": [USEEIO_MONETARY_UNIT] * len(commodity_names)},
            index=commodity_names,
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [USEEIO_MONETARY_UNIT] * len(factor_names)},
            index=factor_names,
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": [flow_unit_by_id.get(code, "") for code in satellite_ids]},
            index=satellite_names,
        ),
    }

    sector_index = activity_names + [name for name in commodity_names if name not in activity_names]
    indeces = {
        "r": {"main": [layout.region_code]},
        "a": {"main": activity_names},
        "c": {"main": commodity_names},
        "s": {"main": sector_index},
        "f": {"main": factor_names},
        "k": {"main": satellite_names},
        "n": {"main": final_demand_names},
    }

    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: USEEIO workbook parsed with "
            f"{len(activity_names)} activities, {len(commodity_names)} commodities, "
            f"{len(factor_names)} value-added rows and {len(satellite_names)} satellite rows."
        ),
        "info",
    )
    return matrices, indeces, units, layout
