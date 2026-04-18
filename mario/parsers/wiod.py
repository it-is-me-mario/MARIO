"""Direct file-based parsers for WIOD 2016 multiregional Excel workbooks."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from pathlib import Path
import re
from zipfile import BadZipFile

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    WIOD_FACTOR_LABELS,
    WIOD_FACTOR_ROWS,
    WIOD_FINAL_DEMAND_CODES,
    WIOD_MONETARY_UNIT,
    WIOD_NATIONAL_IOT_FINAL_DEMAND_CODES,
    WIOD_NATIONAL_SUT_FINAL_DEMAND_CODES,
    WIOD_NATIONAL_SUT_FINAL_DEMAND_LABELS,
    WIOD_NATIONAL_SUT_SUPPLY_TOTAL_COLUMNS,
    WIOD_NATIONAL_SUT_USE_TOTAL_COLUMNS,
    WIOD_SATELLITE_PLACEHOLDER,
    WIOD_SATELLITE_UNIT,
    WIOD_SOURCE,
    WIOD_SUT_FINAL_DEMAND_CODES,
    WIOD_SUT_FINAL_DEMAND_LABELS,
    WIOD_SUT_SUPPLY_TOTAL_COLUMNS,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_WIOD_IOT_FILE_RE = re.compile(
    r"^WIOT(?P<year>\d{4})(?P<variant>_PYP)?_Nov16_ROW\.xlsb$",
    flags=re.IGNORECASE,
)
_WIOD_SUT_FILE_RE = re.compile(r"^intsut(?P<year>\d{2})_nov16\.xlsb$", flags=re.IGNORECASE)
_WIOD_NATIONAL_IOT_FILE_RE = re.compile(
    r"^(?P<country>[A-Z]{3})_NIOT_nov16\.xlsx$",
    flags=re.IGNORECASE,
)
_WIOD_NATIONAL_SUT_FILE_RE = re.compile(
    r"^(?P<country>[A-Z]{3})_SUT_nov16\.xlsx$",
    flags=re.IGNORECASE,
)
_WIOD_SUT_SUPPLY_SHEET = "SUP"
_WIOD_SUT_USE_SHEET = "USE"
_WIOD_SUT_TOTAL_PARTNER = "ZZZ"


@dataclass(frozen=True)
class WIODLayout:
    """Filesystem layout and metadata for one WIOD 2016 workbook."""

    root: Path
    data_path: Path
    year: int
    table: str
    sheet_names: tuple[str, ...]
    scope: str = "MRIO"
    country: str | None = None
    price_label: str = "Current prices"
    notes: tuple[str, ...] = ()

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        return self.data_path.stem

    @property
    def price(self) -> str:
        """Return the price metadata stored in MARIO."""
        return self.price_label

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        return WIOD_SOURCE


def _expand_wiod_year(token: str) -> int:
    """Convert a WIOD filename year token to a four-digit year."""
    if len(token) == 2:
        return 2000 + int(token)
    return int(token)


def detect_wiod_layout(
    path: str | Path,
    *,
    table: str = "IOT",
    year: int | None = None,
    country: str | None = None,
) -> WIODLayout:
    """Resolve the WIOD 2016 multiregional workbook selected for one parse request."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    normalized_table = str(table).upper()
    normalized_country = str(country).upper() if country is not None else None
    if normalized_table not in {"IOT", "SUT"}:
        raise WrongInput("WIOD parsing supports only table='IOT' or table='SUT'.")

    def _parse_candidate(candidate: Path) -> WIODLayout:
        name = candidate.name

        if normalized_table == "IOT":
            match = _WIOD_IOT_FILE_RE.match(name)
            if match is not None:
                parsed_year = _expand_wiod_year(match.group("year"))
                if year is not None and parsed_year != int(year):
                    raise WrongInput(
                        f"The selected WIOD workbook contains year {parsed_year}, not {year}."
                    )
                return WIODLayout(
                    root=candidate.parent,
                    data_path=candidate,
                    year=parsed_year,
                    table=normalized_table,
                    sheet_names=(str(parsed_year),),
                    scope="MRIO",
                    price_label="Previous year prices" if match.group("variant") else "Current prices",
                )

            match = _WIOD_NATIONAL_IOT_FILE_RE.match(name)
            if match is not None:
                parsed_country = match.group("country").upper()
                if normalized_country is not None and parsed_country != normalized_country:
                    raise WrongInput(
                        f"The selected WIOD national IOT workbook contains country {parsed_country}, not {normalized_country}."
                    )
                if year is None:
                    raise WrongInput(
                        "WIOD national IOT workbooks contain multiple years in one sheet. "
                        "Please specify year."
                    )
                return WIODLayout(
                    root=candidate.parent,
                    data_path=candidate,
                    year=int(year),
                    table=normalized_table,
                    sheet_names=("National IO-tables",),
                    scope="National",
                    country=parsed_country,
                    price_label="Current prices",
                )

        if normalized_table == "SUT":
            match = _WIOD_SUT_FILE_RE.match(name)
            if match is not None:
                parsed_year = _expand_wiod_year(match.group("year"))
                if year is not None and parsed_year != int(year):
                    raise WrongInput(
                        f"The selected WIOD workbook contains year {parsed_year}, not {year}."
                    )
                return WIODLayout(
                    root=candidate.parent,
                    data_path=candidate,
                    year=parsed_year,
                    table=normalized_table,
                    sheet_names=(_WIOD_SUT_SUPPLY_SHEET, _WIOD_SUT_USE_SHEET),
                    scope="MRIO",
                    price_label="Current prices",
                )

            match = _WIOD_NATIONAL_SUT_FILE_RE.match(name)
            if match is not None:
                parsed_country = match.group("country").upper()
                if normalized_country is not None and parsed_country != normalized_country:
                    raise WrongInput(
                        f"The selected WIOD national SUT workbook contains country {parsed_country}, not {normalized_country}."
                    )
                if year is None:
                    raise WrongInput(
                        "WIOD national SUT workbooks contain multiple years in one workbook. "
                        "Please specify year."
                    )
                return WIODLayout(
                    root=candidate.parent,
                    data_path=candidate,
                    year=int(year),
                    table=normalized_table,
                    sheet_names=(_WIOD_SUT_SUPPLY_SHEET, _WIOD_SUT_USE_SHEET),
                    scope="National",
                    country=parsed_country,
                    price_label="Current prices",
                )

        if normalized_table == "IOT":
            description = "WIOT<year>[_PYP]_Nov16_ROW.xlsb or <country>_NIOT_nov16.xlsx"
        else:
            description = "intsut<yy>_nov16.xlsb or <country>_SUT_nov16.xlsx"
        raise WrongInput(
            "WIOD parsing currently supports only the WIOD 2016 workbook patterns "
            f"{description}."
        )

    if source.is_file():
        return _parse_candidate(source)

    if normalized_table == "IOT":
        candidate_patterns = ("*.xlsb", "*.xlsx")
    else:
        candidate_patterns = ("*.xlsb", "*.xlsx")

    candidates: list[Path] = []
    for pattern in candidate_patterns:
        for child in source.rglob(pattern):
            if not child.is_file():
                continue
            try:
                layout = _parse_candidate(child)
            except WrongInput:
                continue
            if year is not None and layout.scope == "MRIO" and layout.year != int(year):
                continue
            if normalized_country is not None and layout.country is not None and layout.country != normalized_country:
                continue
            candidates.append(child)

    if not candidates:
        raise WrongInput(
            "No WIOD 2016 workbook matching the selected path and filters was found."
        )
    if len(candidates) > 1:
        raise WrongInput(
            "More than one WIOD workbook matches the selected directory. "
            "Please point to one file explicitly or refine year/country."
        )
    return _parse_candidate(candidates[0])


def _require_pyxlsb() -> None:
    """Ensure the optional ``pyxlsb`` dependency is available."""
    try:
        import pyxlsb  # noqa: F401
    except ImportError as exc:
        raise WrongInput(
            "WIOD Excel parsing requires the optional dependency 'pyxlsb' "
            "to read the WIOD 2016 .xlsb workbook."
        ) from exc


def _wiod_read_error_message(path: Path) -> str:
    """Return a user-facing error for unreadable or incomplete WIOD workbooks."""
    return (
        "The selected WIOD workbook could not be opened as a local readable "
        f"'.xlsb' file: {path}. This usually means the file is incomplete, "
        "still managed as a cloud placeholder (for example OneDrive/iCloud), "
        "or is not a valid WIOD 2016 multiregional workbook. Make sure the "
        "file is fully available offline and try again."
    )


def _assert_wiod_file_readable(path: Path) -> None:
    """Fail early when the workbook cannot be read from the local filesystem."""
    try:
        with path.open("rb") as stream:
            sample = stream.read(8)
    except (OSError, TimeoutError) as exc:
        raise WrongInput(_wiod_read_error_message(path)) from exc
    if not sample:
        raise WrongInput(_wiod_read_error_message(path))


def _read_wiod_workbook(path: Path, *, sheet_name: str) -> pd.DataFrame:
    """Read one raw WIOD IOT sheet into a dataframe without headers."""
    _require_pyxlsb()
    _assert_wiod_file_readable(path)
    log_time(logger, f"Parser: reading WIOD workbook {path.name} sheet {sheet_name}.", "info")
    try:
        frame = pd.read_excel(path, sheet_name=sheet_name, engine="pyxlsb", header=None)
    except (BadZipFile, OSError, TimeoutError) as exc:
        raise WrongInput(_wiod_read_error_message(path)) from exc
    if frame.empty:
        raise WrongFormat("The selected WIOD workbook sheet is empty.")
    return frame


def _read_wiod_table_sheet(path: Path, *, sheet_name: str) -> pd.DataFrame:
    """Read one WIOD SUT table sheet that already stores a header row."""
    _require_pyxlsb()
    _assert_wiod_file_readable(path)
    log_time(logger, f"Parser: reading WIOD workbook {path.name} sheet {sheet_name}.", "info")
    try:
        frame = pd.read_excel(path, sheet_name=sheet_name, engine="pyxlsb", header=0)
    except (BadZipFile, OSError, TimeoutError) as exc:
        raise WrongInput(_wiod_read_error_message(path)) from exc
    if frame.empty:
        raise WrongFormat("The selected WIOD workbook sheet is empty.")
    return frame


def _read_wiod_xlsx_sheet(path: Path, *, sheet_name: str, header=None) -> pd.DataFrame:
    """Read one WIOD xlsx sheet."""
    _assert_wiod_file_readable(path)
    log_time(logger, f"Parser: reading WIOD workbook {path.name} sheet {sheet_name}.", "info")
    try:
        frame = pd.read_excel(path, sheet_name=sheet_name, header=header)
    except (OSError, TimeoutError) as exc:
        raise WrongInput(_wiod_read_error_message(path)) from exc
    if frame.empty:
        raise WrongFormat("The selected WIOD workbook sheet is empty.")
    return frame


def _normalize_wiod_text(value) -> str:
    """Normalize WIOD labels for matching across workbook variants."""
    return " ".join(str(value).strip().split())


def _wiod_sea_metadata(path: Path) -> dict[str, dict[str, str]]:
    """Read WIOD socio-economic variable descriptions and units."""
    notes = pd.read_excel(path, sheet_name="Notes", header=None)
    metadata: dict[str, dict[str, str]] = {}
    for _, row in notes.iloc[7:, 3:5].dropna(subset=[3]).iterrows():
        variable = str(row.iloc[0]).strip()
        description = _normalize_wiod_text(row.iloc[1])
        unit = ""
        if "(" in description and description.endswith(")"):
            base, unit_text = description.rsplit("(", 1)
            description = _normalize_wiod_text(base)
            unit = unit_text[:-1].strip()
            if unit.lower().startswith("in "):
                unit = unit[3:]
        elif "2010=100" in description:
            unit = "index (2010=100)"
        metadata[variable] = {"description": description, "unit": unit or "None"}
    return metadata


def _load_wiod_socioeconomic_accounts(path: str | Path) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    """Load the WIOD socio-economic accounts workbook."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    _assert_wiod_file_readable(source)
    data = pd.read_excel(source, sheet_name="DATA")
    metadata = _wiod_sea_metadata(source)
    return data, metadata


def _zero_frame(index, columns) -> pd.DataFrame:
    """Allocate a zero-filled dataframe with the requested index and columns."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def _three_level_axis(
    regions: list[str],
    level_label: str,
    items: list[str],
) -> pd.MultiIndex:
    """Build one canonical MARIO axis by repeating ``items`` for each region."""
    region_values: list[str] = []
    level_values: list[str] = []
    item_values: list[str] = []
    for region in regions:
        region_values.extend([region] * len(items))
        level_values.extend([level_label] * len(items))
        item_values.extend(items)
    return pd.MultiIndex.from_arrays([region_values, level_values, item_values])


def _strip_cpa_prefix(code: str) -> str:
    """Normalize WIOD SUT ``CPA_*`` codes to MARIO item labels."""
    value = str(code)
    if value.startswith("CPA_"):
        return value[4:]
    return value


def _wiod_external_import_label(region: str, commodity_code: str) -> str:
    """Build one factor-style label for commodity imports from an external WIOD origin."""
    return f"Import from {region} | {commodity_code}"


def _build_iot_units(*, sector_labels: list[str], factor_labels: list[str]) -> dict[str, pd.DataFrame]:
    """Build MARIO unit tables for WIOD 2016 IOT payloads."""
    return {
        _MASTER_INDEX["s"]: pd.DataFrame(
            {"unit": [WIOD_MONETARY_UNIT] * len(sector_labels)},
            index=pd.Index(sector_labels, name=None),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [WIOD_MONETARY_UNIT] * len(factor_labels)},
            index=pd.Index(factor_labels, name=None),
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": [WIOD_SATELLITE_UNIT]},
            index=pd.Index([WIOD_SATELLITE_PLACEHOLDER], name=None),
        ),
    }


def _build_sut_units(
    *,
    activity_labels: list[str],
    commodity_labels: list[str],
    factor_labels: list[str],
) -> dict[str, pd.DataFrame]:
    """Build MARIO unit tables for WIOD 2016 SUT payloads."""
    return {
        _MASTER_INDEX["a"]: pd.DataFrame(
            {"unit": [WIOD_MONETARY_UNIT] * len(activity_labels)},
            index=pd.Index(activity_labels, name=None),
        ),
        _MASTER_INDEX["c"]: pd.DataFrame(
            {"unit": [WIOD_MONETARY_UNIT] * len(commodity_labels)},
            index=pd.Index(commodity_labels, name=None),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [WIOD_MONETARY_UNIT] * len(factor_labels)},
            index=pd.Index(factor_labels, name=None),
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": [WIOD_SATELLITE_UNIT]},
            index=pd.Index([WIOD_SATELLITE_PLACEHOLDER], name=None),
        ),
    }


def build_wiod_national_iot_from_frame(
    frame: pd.DataFrame,
    *,
    year: int,
    country: str,
    source_path: str | Path | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    WIODLayout,
]:
    """Transform one WIOD national IOT workbook sheet into canonical MARIO IOT blocks."""
    if frame.shape[0] < 4 or frame.shape[1] < 10:
        raise WrongFormat("The selected WIOD national IOT sheet is smaller than expected.")

    source = Path(source_path or f"{country}_NIOT_nov16.xlsx")
    layout = WIODLayout(
        root=source.parent,
        data_path=source,
        year=int(year),
        table="IOT",
        sheet_names=("National IO-tables",),
        scope="National",
        country=str(country).upper(),
        price_label="Current prices",
        notes=(
            "WIOD national IOT rows tagged as Domestic and Imports are aggregated "
            "by industry code before building the single-region IOT matrices.",
        ),
    )

    column_codes = frame.iloc[0, 4:].tolist()
    column_labels = frame.iloc[1, 4:].tolist()
    data = frame.iloc[2:].copy()
    data_years = pd.to_numeric(data.iloc[:, 0], errors="coerce")
    data = data.loc[data_years.eq(int(year))].copy()
    if data.empty:
        raise WrongInput(f"The selected WIOD national IOT workbook does not contain year {year}.")

    data.columns = list(range(data.shape[1]))
    data["Code"] = data.iloc[:, 1].astype(str)
    data["Description"] = data.iloc[:, 2].astype(str)
    data["Origin"] = data.iloc[:, 3].astype(str)
    numeric = data.iloc[:, 4 : 4 + len(column_codes)].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    numeric.columns = column_codes

    sector_codes = [
        code for code in column_codes if code not in WIOD_NATIONAL_IOT_FINAL_DEMAND_CODES and code != "GO"
    ]
    final_codes = [code for code in WIOD_NATIONAL_IOT_FINAL_DEMAND_CODES if code in column_codes]
    if not sector_codes:
        raise WrongFormat("Could not detect WIOD national IOT sector columns.")
    if not final_codes:
        raise WrongFormat("Could not detect WIOD national IOT final-demand columns.")

    sector_labels_lookup = {
        str(code): str(label)
        for code, label in zip(column_codes, column_labels)
        if code in sector_codes
    }
    final_labels_lookup = {
        str(code): WIOD_SUT_FINAL_DEMAND_LABELS.get(str(code), str(code))
        for code in final_codes
    }

    domestic_rows = data.loc[(data["Origin"] == "Domestic") & data["Code"].isin(sector_codes)].copy()
    imports_rows = data.loc[(data["Origin"] == "Imports") & data["Code"].isin(sector_codes)].copy()
    factor_rows = data.loc[(data["Origin"] == "TOT") & data["Code"].isin(WIOD_FACTOR_ROWS)].copy()
    if domestic_rows.empty:
        raise WrongFormat("Could not detect domestic industry rows in the WIOD national IOT workbook.")
    if factor_rows.empty:
        raise WrongFormat("Could not detect factor rows in the WIOD national IOT workbook.")

    domestic_numeric = (
        pd.concat([domestic_rows[["Code"]], numeric.loc[domestic_rows.index]], axis=1)
        .groupby("Code", sort=False)
        .sum()
        .reindex(sector_codes)
        .fillna(0.0)
    )
    imports_numeric = (
        pd.concat([imports_rows[["Code"]], numeric.loc[imports_rows.index]], axis=1)
        .groupby("Code", sort=False)
        .sum()
        .reindex(sector_codes)
        .fillna(0.0)
    )
    total_numeric = domestic_numeric.add(imports_numeric, fill_value=0.0)

    factor_numeric = (
        pd.concat([factor_rows[["Code"]], numeric.loc[factor_rows.index]], axis=1)
        .groupby("Code", sort=False)
        .sum()
        .reindex(WIOD_FACTOR_ROWS)
    )
    missing_factors = [code for code in WIOD_FACTOR_ROWS if code not in factor_numeric.dropna(how="all").index]
    if missing_factors:
        factor_numeric = factor_numeric.fillna(0.0)

    sector_labels = [sector_labels_lookup[code] for code in sector_codes]
    final_labels = [final_labels_lookup[code] for code in final_codes]
    factor_labels = [WIOD_FACTOR_LABELS[code] for code in WIOD_FACTOR_ROWS]
    region = layout.country or str(country).upper()

    sector_axis = pd.MultiIndex.from_arrays(
        [
            [region] * len(sector_labels),
            [_MASTER_INDEX["s"]] * len(sector_labels),
            sector_labels,
        ]
    )
    final_axis = pd.MultiIndex.from_arrays(
        [
            [region] * len(final_labels),
            [_MASTER_INDEX["n"]] * len(final_labels),
            final_labels,
        ]
    )
    factor_axis = pd.Index(factor_labels, name=None)
    satellite_axis = pd.Index([WIOD_SATELLITE_PLACEHOLDER], name=None)

    Z = pd.DataFrame(total_numeric[sector_codes].to_numpy(dtype=float), index=sector_axis, columns=sector_axis)
    Y = pd.DataFrame(total_numeric[final_codes].to_numpy(dtype=float), index=sector_axis, columns=final_axis)
    V = pd.DataFrame(factor_numeric[sector_codes].to_numpy(dtype=float), index=factor_axis, columns=sector_axis)
    E = _zero_frame(satellite_axis, sector_axis)
    EY = _zero_frame(satellite_axis, final_axis)

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
    units = _build_iot_units(sector_labels=sector_labels, factor_labels=factor_labels)
    indeces = {
        "r": {"main": [region]},
        "s": {"main": sector_labels},
        "f": {"main": factor_labels},
        "k": {"main": list(satellite_axis)},
        "n": {"main": final_labels},
    }
    rename_index(matrices["baseline"])
    return matrices, indeces, units, layout


def build_wiod_national_sut_from_frames(
    supply_frame: pd.DataFrame,
    use_frame: pd.DataFrame,
    *,
    year: int,
    country: str,
    source_path: str | Path | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    WIODLayout,
]:
    """Transform one WIOD national SUT workbook into split-native MARIO blocks."""
    source = Path(source_path or f"{country}_SUT_nov16.xlsx")
    layout = WIODLayout(
        root=source.parent,
        data_path=source,
        year=int(year),
        table="SUT",
        sheet_names=(_WIOD_SUT_SUPPLY_SHEET, _WIOD_SUT_USE_SHEET),
        scope="National",
        country=str(country).upper(),
        price_label="Current prices",
    )

    supply_codes = supply_frame.iloc[0, 3:].tolist()
    supply_labels = supply_frame.iloc[1, 3:].tolist()
    supply_data = supply_frame.iloc[2:].copy()
    supply_years = pd.to_numeric(supply_data.iloc[:, 0], errors="coerce")
    supply_data = supply_data.loc[supply_years.eq(int(year))].copy()
    if supply_data.empty:
        raise WrongInput(f"The selected WIOD national SUT workbook does not contain year {year}.")
    supply_data.columns = list(range(supply_data.shape[1]))
    supply_data["Code"] = supply_data.iloc[:, 1].astype(str)
    supply_data["Description"] = supply_data.iloc[:, 2].astype(str)
    supply_numeric = supply_data.iloc[:, 3 : 3 + len(supply_codes)].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    supply_numeric.columns = supply_codes

    use_codes = use_frame.iloc[0, 3:].tolist()
    use_labels = use_frame.iloc[1, 3:].tolist()
    use_data = use_frame.iloc[2:].copy()
    use_years = pd.to_numeric(use_data.iloc[:, 0], errors="coerce")
    use_data = use_data.loc[use_years.eq(int(year))].copy()
    if use_data.empty:
        raise WrongInput(f"The selected WIOD national SUT workbook does not contain year {year}.")
    use_data.columns = list(range(use_data.shape[1]))
    use_data["Code"] = use_data.iloc[:, 1].astype(str)
    use_data["Description"] = use_data.iloc[:, 2].astype(str)
    use_numeric = use_data.iloc[:, 3 : 3 + len(use_codes)].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    use_numeric.columns = use_codes

    activity_codes = [code for code in supply_codes if code not in WIOD_NATIONAL_SUT_SUPPLY_TOTAL_COLUMNS]
    final_demand_codes = [code for code in WIOD_NATIONAL_SUT_FINAL_DEMAND_CODES if code in use_codes]
    factor_codes = [code for code in WIOD_FACTOR_ROWS if code in use_data["Code"].tolist()]
    if not activity_codes:
        raise WrongFormat("Could not detect activity columns in the WIOD national SUT workbook.")
    if not final_demand_codes:
        raise WrongFormat("Could not detect final-demand columns in the WIOD national SUT workbook.")
    if not factor_codes:
        raise WrongFormat("Could not detect factor rows in the WIOD national SUT workbook.")

    activity_labels = activity_codes
    commodity_rows_supply = supply_data.loc[supply_data["Code"].astype(str).str.startswith("CPA_")].copy()
    commodity_rows_use = use_data.loc[use_data["Code"].astype(str).str.startswith("CPA_")].copy()
    commodity_codes = commodity_rows_supply["Code"].astype(str).map(_strip_cpa_prefix).tolist()
    if commodity_codes != commodity_rows_use["Code"].astype(str).map(_strip_cpa_prefix).tolist():
        raise WrongFormat("The WIOD national SUT SUP and USE sheets do not expose the same commodity order.")
    commodity_labels = commodity_codes
    factor_labels = [WIOD_FACTOR_LABELS[code] for code in factor_codes]
    final_labels = [WIOD_NATIONAL_SUT_FINAL_DEMAND_LABELS[code] for code in final_demand_codes]

    region = layout.country or str(country).upper()
    activity_axis = pd.MultiIndex.from_arrays(
        [
            [region] * len(activity_codes),
            [_MASTER_INDEX["a"]] * len(activity_codes),
            activity_labels,
        ]
    )
    commodity_axis = pd.MultiIndex.from_arrays(
        [
            [region] * len(commodity_codes),
            [_MASTER_INDEX["c"]] * len(commodity_codes),
            commodity_labels,
        ]
    )
    final_demand_axis = pd.MultiIndex.from_arrays(
        [
            [region] * len(final_labels),
            [_MASTER_INDEX["n"]] * len(final_labels),
            final_labels,
        ]
    )
    factor_axis = pd.Index(factor_labels, name=None)
    satellite_axis = pd.Index([WIOD_SATELLITE_PLACEHOLDER], name=None)

    S = pd.DataFrame(
        supply_numeric.loc[commodity_rows_supply.index, activity_codes].to_numpy(dtype=float).T,
        index=activity_axis,
        columns=commodity_axis,
    )
    U = pd.DataFrame(
        use_numeric.loc[commodity_rows_use.index, activity_codes].to_numpy(dtype=float),
        index=commodity_axis,
        columns=activity_axis,
    )
    Yc = pd.DataFrame(
        use_numeric.loc[commodity_rows_use.index, final_demand_codes].to_numpy(dtype=float),
        index=commodity_axis,
        columns=final_demand_axis,
    )
    factor_rows = use_data.loc[use_data["Code"].isin(factor_codes)].copy()
    factor_rows["factor_order"] = factor_rows["Code"].map({code: i for i, code in enumerate(factor_codes)})
    factor_rows = factor_rows.sort_values("factor_order")
    Va = pd.DataFrame(
        use_numeric.loc[factor_rows.index, activity_codes].to_numpy(dtype=float),
        index=factor_axis,
        columns=activity_axis,
    )
    Ya = _zero_frame(activity_axis, final_demand_axis)
    Vc = _zero_frame(factor_axis, commodity_axis)
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
    units = _build_sut_units(
        activity_labels=activity_labels,
        commodity_labels=commodity_labels,
        factor_labels=factor_labels,
    )
    indeces = {
        "r": {"main": [region]},
        "n": {"main": final_labels},
        "k": {"main": list(satellite_axis)},
        "f": {"main": factor_labels},
        "a": {"main": activity_labels},
        "c": {"main": commodity_labels},
        "s": {"main": activity_labels + [label for label in commodity_labels if label not in activity_labels]},
    }
    rename_index(matrices["baseline"])
    return matrices, indeces, units, layout


def _attach_wiod_socioeconomic_extensions(
    *,
    matrices: dict[str, dict[str, pd.DataFrame]],
    indeces: dict[str, dict[str, list[str]]],
    units: dict[str, pd.DataFrame],
    layout: WIODLayout,
    extensions_path: str | Path,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    WIODLayout,
]:
    """Attach WIOD socio-economic accounts as satellite extensions."""
    data, metadata = _load_wiod_socioeconomic_accounts(extensions_path)
    year_column = int(layout.year)
    if year_column not in data.columns:
        raise WrongInput(
            f"The WIOD socio-economic accounts workbook does not contain year {layout.year}."
        )

    variables = [variable for variable in metadata if variable in set(data["variable"].dropna().astype(str))]
    satellite_labels = [
        f"{variable} | {metadata[variable]['description']}" for variable in variables
    ]
    satellite_units = pd.DataFrame(
        {"unit": [metadata[variable]["unit"] for variable in variables]},
        index=pd.Index(satellite_labels, name=None),
    )
    notes = list(layout.notes)

    if layout.table == "IOT":
        sector_axis = matrices["baseline"]["Z"].columns
        E = _zero_frame(pd.Index(satellite_labels, name=None), sector_axis)
        regions = sector_axis.get_level_values(0)
        items = sector_axis.get_level_values(2)
        normalized_items = [_normalize_wiod_text(item) for item in items]
        for region in pd.Index(regions).unique():
            region_mask = regions == region
            region_data = data.loc[data["country"].astype(str) == str(region)].copy()
            if region_data.empty:
                notes.append(
                    f"WIOD socio-economic extensions do not cover region {region}; related columns were left at zero."
                )
                continue
            region_data["normalized_description"] = region_data["description"].map(_normalize_wiod_text)
            target_items = [normalized_items[idx] for idx, flag in enumerate(region_mask) if flag]
            for row_idx, variable in enumerate(variables):
                variable_data = region_data.loc[region_data["variable"].astype(str) == variable]
                series = (
                    variable_data.drop_duplicates("normalized_description")
                    .set_index("normalized_description")[year_column]
                )
                aligned = pd.to_numeric(series.reindex(target_items), errors="coerce").fillna(0.0)
                E.iloc[row_idx, np.flatnonzero(region_mask)] = aligned.to_numpy(dtype=float)

        matrices["baseline"]["E"] = E
        matrices["baseline"]["EY"] = _zero_frame(E.index, matrices["baseline"]["Y"].columns)

    else:
        activity_axis = matrices["baseline"]["S"].index
        Ea = _zero_frame(pd.Index(satellite_labels, name=None), activity_axis)
        regions = activity_axis.get_level_values(0)
        items = activity_axis.get_level_values(2).astype(str)
        for region in pd.Index(regions).unique():
            region_mask = regions == region
            region_data = data.loc[data["country"].astype(str) == str(region)].copy()
            if region_data.empty:
                notes.append(
                    f"WIOD socio-economic extensions do not cover region {region}; related activity columns were left at zero."
                )
                continue
            target_items = [items[idx] for idx, flag in enumerate(region_mask) if flag]
            for row_idx, variable in enumerate(variables):
                variable_data = region_data.loc[region_data["variable"].astype(str) == variable].copy()
                variable_data["code"] = variable_data["code"].astype(str)
                series = variable_data.drop_duplicates("code").set_index("code")[year_column]
                aligned = pd.to_numeric(series.reindex(target_items), errors="coerce").fillna(0.0)
                Ea.iloc[row_idx, np.flatnonzero(region_mask)] = aligned.to_numpy(dtype=float)

        matrices["baseline"]["Ea"] = Ea
        matrices["baseline"]["Ec"] = _zero_frame(Ea.index, matrices["baseline"]["Ec"].columns)
        matrices["baseline"]["EY"] = _zero_frame(Ea.index, matrices["baseline"]["EY"].columns)

    units[_MASTER_INDEX["k"]] = satellite_units
    indeces["k"]["main"] = satellite_labels
    return matrices, indeces, units, replace(layout, notes=tuple(notes))


def build_wiod_iot_from_frame(
    frame: pd.DataFrame,
    *,
    year: int,
    source_path: str | Path | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    WIODLayout,
]:
    """Transform one raw WIOD 2016 IOT sheet into canonical MARIO IOT blocks."""
    if frame.shape[0] < 8 or frame.shape[1] < 10:
        raise WrongFormat("The selected WIOD sheet is smaller than the expected WIOD 2016 layout.")

    source = Path(source_path or f"WIOT{year}_Nov16_ROW.xlsb")
    price_text = _normalize_wiod_text(frame.iloc[1, 0]) if frame.shape[0] > 1 else ""
    layout = WIODLayout(
        root=source.parent,
        data_path=source,
        year=int(year),
        table="IOT",
        sheet_names=(str(year),),
        scope="MRIO",
        price_label="Previous year prices" if "previous" in price_text.lower() else "Current prices",
    )

    column_codes = frame.iloc[2, 4:].tolist()
    column_labels = frame.iloc[3, 4:].tolist()
    column_regions = frame.iloc[4, 4:].tolist()
    row_codes = frame.iloc[6:, 0].tolist()
    row_labels = frame.iloc[6:, 1].tolist()
    row_regions = frame.iloc[6:, 2].tolist()

    numeric = frame.iloc[6:, 4:].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    column_meta = pd.DataFrame(
        {
            "pos": np.arange(len(column_codes)),
            "code": column_codes,
            "label": column_labels,
            "region": column_regions,
        }
    )
    row_meta = pd.DataFrame(
        {
            "pos": np.arange(len(row_codes)),
            "code": row_codes,
            "label": row_labels,
            "region": row_regions,
        }
    )

    sector_col_mask = column_meta["region"].ne("TOT") & ~column_meta["code"].isin(WIOD_FINAL_DEMAND_CODES)
    final_col_mask = column_meta["region"].ne("TOT") & column_meta["code"].isin(WIOD_FINAL_DEMAND_CODES)
    output_col_mask = column_meta["code"].eq("GO")

    sector_row_mask = row_meta["region"].ne("TOT") & row_meta["region"].notna() & row_meta["code"].notna()
    factor_row_mask = row_meta["code"].isin(WIOD_FACTOR_ROWS)
    skip_row_mask = row_meta["code"].isin({"II_fob", "GO"})

    if not sector_col_mask.any():
        raise WrongFormat("Could not detect the WIOD inter-industry columns.")
    if not final_col_mask.any():
        raise WrongFormat("Could not detect the WIOD final-demand columns.")
    if not factor_row_mask.any():
        raise WrongFormat("Could not detect the WIOD factor rows.")

    sector_cols = column_meta.loc[sector_col_mask].copy()
    final_cols = column_meta.loc[final_col_mask].copy()
    output_cols = column_meta.loc[output_col_mask].copy()
    sector_rows = row_meta.loc[sector_row_mask].copy()
    factor_rows = row_meta.loc[factor_row_mask].copy()

    if len(sector_rows) != len(sector_cols):
        raise WrongFormat(
            "WIOD sector rows and sector columns do not describe the same multiregional axis."
        )
    if (
        sector_rows["code"].tolist() != sector_cols["code"].tolist()
        or sector_rows["region"].tolist() != sector_cols["region"].tolist()
    ):
        raise WrongFormat(
            "WIOD sector rows and sector columns are not aligned in the expected order."
        )
    expected_factors = list(WIOD_FACTOR_ROWS)
    parsed_factors = factor_rows["code"].tolist()
    missing_factors = [code for code in expected_factors if code not in parsed_factors]
    if missing_factors:
        raise WrongFormat(f"The WIOD workbook is missing required factor rows: {missing_factors}.")
    if output_cols.shape[0] != 1:
        raise WrongFormat("The WIOD workbook should contain one trailing GO output column.")
    if skip_row_mask.sum() != 2:
        raise WrongFormat("The WIOD workbook should contain II_fob and GO total rows.")

    sector_axis = pd.MultiIndex.from_arrays(
        [
            sector_cols["region"].tolist(),
            [_MASTER_INDEX["s"]] * len(sector_cols),
            sector_cols["label"].tolist(),
        ]
    )
    final_axis = pd.MultiIndex.from_arrays(
        [
            final_cols["region"].tolist(),
            [_MASTER_INDEX["n"]] * len(final_cols),
            final_cols["label"].tolist(),
        ]
    )
    factor_axis = pd.Index(
        factor_rows.set_index("code").loc[list(WIOD_FACTOR_ROWS), "label"].tolist(),
        name=None,
    )
    satellite_axis = pd.Index([WIOD_SATELLITE_PLACEHOLDER], name=None)

    sector_row_idx = sector_rows["pos"].to_numpy()
    sector_col_idx = sector_cols["pos"].to_numpy()
    final_col_idx = final_cols["pos"].to_numpy()

    Z = pd.DataFrame(
        numeric.iloc[sector_row_idx, sector_col_idx].to_numpy(dtype=float, copy=True),
        index=sector_axis,
        columns=sector_axis,
    )
    Y = pd.DataFrame(
        numeric.iloc[sector_row_idx, final_col_idx].to_numpy(dtype=float, copy=True),
        index=sector_axis,
        columns=final_axis,
    )
    factor_row_lookup = factor_rows.set_index("code")["pos"]
    ordered_factor_row_idx = factor_row_lookup.loc[list(WIOD_FACTOR_ROWS)].to_numpy()
    V = pd.DataFrame(
        numeric.iloc[ordered_factor_row_idx, sector_col_idx].to_numpy(dtype=float, copy=True),
        index=factor_axis,
        columns=sector_axis,
    )

    E = _zero_frame(satellite_axis, sector_axis)
    EY = _zero_frame(satellite_axis, final_axis)

    sector_labels = list(dict.fromkeys(sector_cols["label"].tolist()))
    final_labels = list(dict.fromkeys(final_cols["label"].tolist()))
    factor_labels = factor_axis.tolist()
    region_codes = list(dict.fromkeys(sector_cols["region"].tolist()))

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
    units = _build_iot_units(sector_labels=sector_labels, factor_labels=factor_labels)
    indeces = {
        "r": {"main": region_codes},
        "s": {"main": sector_labels},
        "f": {"main": factor_labels},
        "k": {"main": list(satellite_axis)},
        "n": {"main": final_labels},
    }

    rename_index(matrices["baseline"])
    log_time(
        logger,
        f"Parser: WIOD IOT payload ready with shapes Z={Z.shape}, Y={Y.shape}, V={V.shape}.",
        "info",
    )
    return matrices, indeces, units, layout


def build_wiod_sut_from_frames(
    supply_frame: pd.DataFrame,
    use_frame: pd.DataFrame,
    *,
    year: int,
    row_mode: str = "external_account",
    source_path: str | Path | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    WIODLayout,
]:
    """Transform WIOD 2016 multiregional supply/use sheets into MARIO SUT blocks."""
    source = Path(source_path or f"intsut{str(year)[-2:]}_nov16.xlsb")
    normalized_row_mode = str(row_mode).strip().lower()
    if normalized_row_mode not in {"external_account", "legacy_region"}:
        raise WrongInput(
            "WIOD SUT row_mode should be either 'external_account' or 'legacy_region'."
        )

    notes: list[str] = []
    layout = WIODLayout(
        root=source.parent,
        data_path=source,
        year=int(year),
        table="SUT",
        sheet_names=(_WIOD_SUT_SUPPLY_SHEET, _WIOD_SUT_USE_SHEET),
        scope="MRIO",
        price_label="Current prices",
    )

    required_supply_cols = {"REP", "PAR", "CPA"}
    required_use_cols = {"REP", "PAR", "CPA"}
    if not required_supply_cols.issubset(set(supply_frame.columns)):
        raise WrongFormat("The selected WIOD SUP sheet does not expose REP/PAR/CPA columns.")
    if not required_use_cols.issubset(set(use_frame.columns)):
        raise WrongFormat("The selected WIOD USE sheet does not expose REP/PAR/CPA columns.")

    supply = supply_frame.copy()
    use = use_frame.copy()
    supply["REP"] = supply["REP"].astype(str)
    supply["PAR"] = supply["PAR"].astype(str)
    supply["CPA"] = supply["CPA"].astype(str)
    use["REP"] = use["REP"].astype(str)
    use["PAR"] = use["PAR"].astype(str)
    use["CPA"] = use["CPA"].astype(str)

    activity_codes = [
        str(column)
        for column in supply.columns[3:]
        if str(column) not in WIOD_SUT_SUPPLY_TOTAL_COLUMNS
    ]
    if not activity_codes:
        raise WrongFormat("Could not detect activity columns in the WIOD SUP sheet.")

    final_demand_codes = [code for code in WIOD_SUT_FINAL_DEMAND_CODES if code in use.columns]
    missing_final = [code for code in WIOD_SUT_FINAL_DEMAND_CODES if code not in final_demand_codes]
    if missing_final:
        raise WrongFormat(f"The WIOD USE sheet is missing final-demand columns: {missing_final}.")

    supply_commodity_rows = supply.loc[supply["CPA"].str.startswith("CPA_")].copy()
    if supply_commodity_rows.empty:
        raise WrongFormat("Could not detect commodity rows in the WIOD SUP sheet.")
    if not supply_commodity_rows["REP"].equals(supply_commodity_rows["PAR"]):
        raise WrongFormat(
            "The WIOD SUP sheet is expected to contain only domestic supply rows with REP == PAR."
        )

    use_commodity_rows = use.loc[
        use["CPA"].str.startswith("CPA_") & use["PAR"].ne(_WIOD_SUT_TOTAL_PARTNER)
    ].copy()
    if use_commodity_rows.empty:
        raise WrongFormat("Could not detect commodity rows in the WIOD USE sheet.")

    factor_rows = use.loc[
        use["PAR"].eq(_WIOD_SUT_TOTAL_PARTNER) & use["CPA"].isin(WIOD_FACTOR_ROWS)
    ].copy()
    if factor_rows.empty:
        raise WrongFormat("Could not detect factor rows in the WIOD USE sheet.")

    activity_regions = list(dict.fromkeys(supply_commodity_rows["REP"].tolist()))
    if normalized_row_mode == "legacy_region":
        commodity_regions = list(dict.fromkeys(use_commodity_rows["PAR"].tolist()))
        external_regions: list[str] = []
    else:
        commodity_regions = activity_regions.copy()
        external_regions = [
            region
            for region in dict.fromkeys(use_commodity_rows["PAR"].tolist())
            if region not in set(activity_regions)
        ]
    commodity_codes = list(
        dict.fromkeys(supply_commodity_rows["CPA"].map(_strip_cpa_prefix).tolist())
    )
    use_commodity_codes = list(
        dict.fromkeys(use_commodity_rows["CPA"].map(_strip_cpa_prefix).tolist())
    )
    if commodity_codes != use_commodity_codes:
        raise WrongFormat(
            "The WIOD SUP and USE sheets do not expose the same commodity code order."
        )

    factor_codes = list(WIOD_FACTOR_ROWS)
    base_factor_labels = [WIOD_FACTOR_LABELS[code] for code in factor_codes]
    import_labels = [
        _wiod_external_import_label(region, commodity_code)
        for region in external_regions
        for commodity_code in commodity_codes
    ]
    factor_labels = base_factor_labels + import_labels
    final_demand_labels = [WIOD_SUT_FINAL_DEMAND_LABELS[code] for code in final_demand_codes]
    satellite_axis = pd.Index([WIOD_SATELLITE_PLACEHOLDER], name=None)
    factor_axis = pd.Index(factor_labels, name=None)
    import_row_labels = {
        (region, commodity_code): _wiod_external_import_label(region, commodity_code)
        for region in external_regions
        for commodity_code in commodity_codes
    }
    if external_regions:
        notes.append(
            "External WIOD commodity origins "
            f"{', '.join(external_regions)} were removed from the endogenous region set. "
            "Their intermediate uses were reclassified into Va and their final-demand uses into VY."
        )

    activity_axis = _three_level_axis(activity_regions, _MASTER_INDEX["a"], activity_codes)
    commodity_axis = _three_level_axis(commodity_regions, _MASTER_INDEX["c"], commodity_codes)
    final_demand_axis = _three_level_axis(activity_regions, _MASTER_INDEX["n"], final_demand_labels)

    activity_slices = {
        region: slice(index * len(activity_codes), (index + 1) * len(activity_codes))
        for index, region in enumerate(activity_regions)
    }
    commodity_slices = {
        region: slice(index * len(commodity_codes), (index + 1) * len(commodity_codes))
        for index, region in enumerate(commodity_regions)
    }
    final_demand_slices = {
        region: slice(index * len(final_demand_codes), (index + 1) * len(final_demand_codes))
        for index, region in enumerate(activity_regions)
    }

    S_data = np.zeros((len(activity_axis), len(commodity_axis)), dtype=float)
    U_data = np.zeros((len(commodity_axis), len(activity_axis)), dtype=float)
    Yc_data = np.zeros((len(commodity_axis), len(final_demand_axis)), dtype=float)
    Va_data = np.zeros((len(factor_axis), len(activity_axis)), dtype=float)
    VY_data = np.zeros((len(factor_axis), len(final_demand_axis)), dtype=float)

    supply_commodity_rows["commodity_code"] = supply_commodity_rows["CPA"].map(_strip_cpa_prefix)
    for region in activity_regions:
        block = supply_commodity_rows.loc[
            (supply_commodity_rows["REP"] == region) & (supply_commodity_rows["PAR"] == region)
        ].copy()
        if block.duplicated("commodity_code").any():
            raise WrongFormat(f"The WIOD SUP sheet contains duplicate commodity rows for {region}.")
        block = block.set_index("commodity_code").reindex(commodity_codes)
        if block[activity_codes].isna().any().any():
            raise WrongFormat(f"The WIOD SUP sheet is missing commodity rows for region {region}.")
        S_data[
            activity_slices[region],
            commodity_slices[region],
        ] = block[activity_codes].to_numpy(dtype=float, copy=True).T

    use_commodity_rows["commodity_code"] = use_commodity_rows["CPA"].map(_strip_cpa_prefix)
    par_dtype = pd.CategoricalDtype(categories=commodity_regions, ordered=True)
    commodity_dtype = pd.CategoricalDtype(categories=commodity_codes, ordered=True)
    for region in activity_regions:
        region_rows = use_commodity_rows.loc[use_commodity_rows["REP"] == region].copy()

        if normalized_row_mode == "legacy_region":
            block = region_rows.copy()
            block["PAR"] = block["PAR"].astype(par_dtype)
            block["commodity_code"] = block["commodity_code"].astype(commodity_dtype)
            if block.duplicated(["PAR", "commodity_code"]).any():
                raise WrongFormat(f"The WIOD USE sheet contains duplicate commodity rows for {region}.")
            block = block.sort_values(["PAR", "commodity_code"])
            expected_rows = len(commodity_regions) * len(commodity_codes)
            if len(block) != expected_rows:
                raise WrongFormat(
                    f"The WIOD USE sheet exposes {len(block)} commodity rows for {region}, expected {expected_rows}."
                )
            U_data[:, activity_slices[region]] = block[activity_codes].to_numpy(dtype=float, copy=True)
            Yc_data[:, final_demand_slices[region]] = block[final_demand_codes].to_numpy(dtype=float, copy=True)
            continue

        endogenous_block = region_rows.loc[region_rows["PAR"].isin(commodity_regions)].copy()
        endogenous_block["PAR"] = endogenous_block["PAR"].astype(par_dtype)
        endogenous_block["commodity_code"] = endogenous_block["commodity_code"].astype(commodity_dtype)
        if endogenous_block.duplicated(["PAR", "commodity_code"]).any():
            raise WrongFormat(f"The WIOD USE sheet contains duplicate commodity rows for {region}.")
        endogenous_block = endogenous_block.sort_values(["PAR", "commodity_code"])
        expected_rows = len(commodity_regions) * len(commodity_codes)
        if len(endogenous_block) != expected_rows:
            raise WrongFormat(
                f"The WIOD USE sheet exposes {len(endogenous_block)} endogenous commodity rows for {region}, expected {expected_rows}."
            )
        U_data[:, activity_slices[region]] = endogenous_block[activity_codes].to_numpy(dtype=float, copy=True)
        Yc_data[:, final_demand_slices[region]] = endogenous_block[final_demand_codes].to_numpy(dtype=float, copy=True)

        external_block = region_rows.loc[~region_rows["PAR"].isin(commodity_regions)].copy()
        if external_block.empty:
            continue
        if external_block.duplicated(["PAR", "commodity_code"]).any():
            raise WrongFormat(f"The WIOD USE sheet contains duplicate external commodity rows for {region}.")
        external_lookup = external_block.set_index(["PAR", "commodity_code"])
        for external_region in external_regions:
            missing_external = [
                commodity_code
                for commodity_code in commodity_codes
                if (external_region, commodity_code) not in external_lookup.index
            ]
            if missing_external:
                raise WrongFormat(
                    f"The WIOD USE sheet is missing external commodity rows for reporter {region}, origin {external_region}: {missing_external}."
                )
            for commodity_code in commodity_codes:
                row = external_lookup.loc[(external_region, commodity_code)]
                factor_pos = factor_axis.get_loc(import_row_labels[(external_region, commodity_code)])
                Va_data[factor_pos, activity_slices[region]] = row[activity_codes].to_numpy(
                    dtype=float,
                    copy=True,
                )
                VY_data[factor_pos, final_demand_slices[region]] = row[final_demand_codes].to_numpy(
                    dtype=float,
                    copy=True,
                )

    for region in activity_regions:
        block = factor_rows.loc[factor_rows["REP"] == region].copy()
        if block.duplicated("CPA").any():
            raise WrongFormat(f"The WIOD USE sheet contains duplicate factor rows for {region}.")
        block = block.set_index("CPA")
        missing_factors = [code for code in factor_codes if code not in block.index]
        if missing_factors:
            raise WrongFormat(
                f"The WIOD USE sheet is missing factor rows for {region}: {missing_factors}."
            )
        Va_data[: len(base_factor_labels), activity_slices[region]] = block.loc[factor_codes, activity_codes].to_numpy(
            dtype=float,
            copy=True,
        )

    S = pd.DataFrame(S_data, index=activity_axis, columns=commodity_axis)
    U = pd.DataFrame(U_data, index=commodity_axis, columns=activity_axis)
    Yc = pd.DataFrame(Yc_data, index=commodity_axis, columns=final_demand_axis)
    Ya = _zero_frame(activity_axis, final_demand_axis)
    Va = pd.DataFrame(Va_data, index=factor_axis, columns=activity_axis)
    Vc = _zero_frame(factor_axis, commodity_axis)
    Ea = _zero_frame(satellite_axis, activity_axis)
    Ec = _zero_frame(satellite_axis, commodity_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

    activity_labels = activity_codes
    commodity_labels = commodity_codes
    units = _build_sut_units(
        activity_labels=activity_labels,
        commodity_labels=commodity_labels,
        factor_labels=factor_labels,
    )
    indeces = {
        "r": {"main": commodity_regions},
        "n": {"main": final_demand_labels},
        "k": {"main": list(satellite_axis)},
        "f": {"main": factor_labels},
        "a": {"main": activity_labels},
        "c": {"main": commodity_labels},
        "s": {"main": activity_labels + [label for label in commodity_labels if label not in activity_labels]},
    }

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
    if normalized_row_mode == "external_account":
        VY = pd.DataFrame(VY_data, index=factor_axis, columns=final_demand_axis)
        matrices["baseline"]["VY"] = VY
    layout = replace(layout, notes=tuple(notes))
    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: WIOD SUT payload ready with shapes "
            f"S={S.shape}, U={U.shape}, Yc={Yc.shape}, Va={Va.shape}"
            + (
                f", VY={matrices['baseline']['VY'].shape}."
                if normalized_row_mode == "external_account"
                else "."
            )
        ),
        "info",
    )
    return matrices, indeces, units, layout


def parse_wiod_iot(
    path: str | Path,
    *,
    year: int | None = None,
    country: str | None = None,
    add_extensions: str | Path | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    WIODLayout,
]:
    """Parse one WIOD 2016 IOT workbook into MARIO blocks."""
    layout = detect_wiod_layout(path, table="IOT", year=year, country=country)
    if layout.scope == "MRIO":
        frame = _read_wiod_workbook(layout.data_path, sheet_name=layout.sheet_names[0])
        matrices, indeces, units, layout = build_wiod_iot_from_frame(
            frame,
            year=layout.year,
            source_path=layout.data_path,
        )
    else:
        frame = _read_wiod_xlsx_sheet(layout.data_path, sheet_name=layout.sheet_names[0], header=None)
        matrices, indeces, units, layout = build_wiod_national_iot_from_frame(
            frame,
            year=layout.year,
            country=layout.country or country or "UNK",
            source_path=layout.data_path,
        )

    if add_extensions is not None:
        matrices, indeces, units, layout = _attach_wiod_socioeconomic_extensions(
            matrices=matrices,
            indeces=indeces,
            units=units,
            layout=layout,
            extensions_path=add_extensions,
        )
    return matrices, indeces, units, layout


def parse_wiod_sut(
    path: str | Path,
    *,
    year: int | None = None,
    country: str | None = None,
    add_extensions: str | Path | None = None,
    row_mode: str = "external_account",
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    WIODLayout,
]:
    """Parse one WIOD 2016 SUT workbook into split-native MARIO blocks."""
    layout = detect_wiod_layout(path, table="SUT", year=year, country=country)
    if layout.scope == "MRIO":
        supply = _read_wiod_table_sheet(layout.data_path, sheet_name=_WIOD_SUT_SUPPLY_SHEET)
        use = _read_wiod_table_sheet(layout.data_path, sheet_name=_WIOD_SUT_USE_SHEET)
        matrices, indeces, units, layout = build_wiod_sut_from_frames(
            supply,
            use,
            year=layout.year,
            row_mode=row_mode,
            source_path=layout.data_path,
        )
    else:
        supply = _read_wiod_xlsx_sheet(layout.data_path, sheet_name=_WIOD_SUT_SUPPLY_SHEET, header=None)
        use = _read_wiod_xlsx_sheet(layout.data_path, sheet_name=_WIOD_SUT_USE_SHEET, header=None)
        matrices, indeces, units, layout = build_wiod_national_sut_from_frames(
            supply,
            use,
            year=layout.year,
            country=layout.country or country or "UNK",
            source_path=layout.data_path,
        )

    if add_extensions is not None:
        matrices, indeces, units, layout = _attach_wiod_socioeconomic_extensions(
            matrices=matrices,
            indeces=indeces,
            units=units,
            layout=layout,
            extensions_path=add_extensions,
        )
    return matrices, indeces, units, layout
