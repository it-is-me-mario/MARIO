"""Local-file parsers for selected CEPALSTAT input-output bundles."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path
import re
import unicodedata
from zipfile import BadZipFile, ZipFile

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import NotImplementable, WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    CEPALSTAT_IOT_MODES,
    CEPALSTAT_MONETARY_UNIT,
    CEPALSTAT_SATELLITE_PLACEHOLDER,
    CEPALSTAT_SATELLITE_UNIT,
    CEPALSTAT_SOURCE,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_CEPALSTAT_FILE_RE = re.compile(
    r"^(?:(?P<country>[A-Z]{3})[_\s-]+)?(?P<dataset>COU|MIP)[_\s-]+(?P<start>\d{4})(?:[_\s-]+(?P<end>\d{4}))?(?P<suffix>.*)\.(?P<ext>zip|xlsx|xls|xlsm)$",
    flags=re.IGNORECASE,
)
_DOMESTIC_IOT_TOTAL_LABEL = "TOTAL INSUMOS INTERMEDIOS (a precios de comprador)"
_DOMESTIC_IOT_OUTPUT_LABEL = "PRODUCCION TOTAL"


@dataclass(frozen=True)
class CEPALSTATLayout:
    """Filesystem layout and metadata for one CEPALSTAT table bundle."""

    root: Path
    data_path: Path
    country: str
    year: int
    table: str
    family: str
    workbook_member: str | None = None
    auxiliary_members: tuple[str, ...] = ()
    sheet_names: tuple[str, ...] = ()
    iot_mode: str | None = None
    notes: tuple[str, ...] = ()

    @property
    def dataset_name(self) -> str:
        if self.table == "SUT":
            return f"CEPALSTAT SUT {self.country} {self.year}"
        suffix = f" {self.iot_mode.upper()}" if self.iot_mode else ""
        return f"CEPALSTAT IOT {self.country} {self.year}{suffix}"

    @property
    def price(self) -> str:
        return "Current prices"

    @property
    def source(self) -> str:
        return CEPALSTAT_SOURCE


def _text(value) -> str:
    """Normalize one cell to stripped text."""
    if pd.isna(value):
        return ""
    return str(value).replace("\n", " ").strip()


def _norm(value) -> str:
    """Normalize one code-like cell to a compact string."""
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).replace("\n", " ").strip()


def _plain(text: str) -> str:
    """Return one lowercase ASCII-folded string for robust header matching."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _strip_activity_code(text: str) -> str:
    """Remove one leading activity code from a combined code+label header."""
    match = re.match(r"^(?P<code>[A-Z0-9][A-Z0-9 +\-]{0,30})\s+(?P<label>.+)$", text)
    if match is None:
        return text
    return match.group("label").strip()


def _parse_candidate_metadata(path: Path) -> dict[str, object] | None:
    """Parse CEPALSTAT metadata encoded in one local filename."""
    match = _CEPALSTAT_FILE_RE.match(path.name)
    if match is None:
        return None

    dataset = str(match.group("dataset")).upper()
    suffix = str(match.group("suffix") or "").lower()
    mode = None
    if "pxp" in suffix or re.search(r"(^|[_-])p($|[_-])", suffix):
        mode = "pxp"
    elif "axa" in suffix or re.search(r"(^|[_-])a($|[_-])", suffix):
        mode = "axa"

    start = int(match.group("start"))
    end = int(match.group("end") or match.group("start"))
    return {
        "country": str(match.group("country")).upper() if match.group("country") else None,
        "dataset": dataset,
        "start": start,
        "end": end,
        "mode": mode,
    }


def _list_candidate_files(
    path: str | Path,
    *,
    table: str,
    year: int | None,
    country: str | None,
    iot_mode: str,
) -> list[Path]:
    """Resolve local CEPALSTAT bundle candidates from one file or directory."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    normalized_country = country.upper() if country is not None else None
    dataset = "COU" if table == "SUT" else "MIP"

    if source.is_file():
        candidates = [source]
    else:
        candidates = [
            child
            for child in source.rglob("*")
            if child.is_file() and child.suffix.lower() in {".zip", ".xlsx", ".xls", ".xlsm"}
        ]

    filtered: list[Path] = []
    for candidate in candidates:
        info = _parse_candidate_metadata(candidate)
        if info is None or info["dataset"] != dataset:
            continue
        if normalized_country is not None and info["country"] not in {None, normalized_country}:
            continue
        if not source.is_file() and year is not None and not (int(info["start"]) <= int(year) <= int(info["end"])):
            continue
        if table == "IOT" and iot_mode != "auto" and info["mode"] is not None and info["mode"] != iot_mode:
            continue
        filtered.append(candidate)

    if not filtered:
        raise WrongInput(
            f"No CEPALSTAT {table} bundle was found for the selected path, country, year and mode."
        )

    if table == "IOT" and iot_mode != "auto":
        preferred = [candidate for candidate in filtered if (_parse_candidate_metadata(candidate) or {}).get("mode") == iot_mode]
        if preferred:
            filtered = preferred

    return sorted(filtered)


def _resolve_layout_country(metadata: dict[str, object], country: str | None) -> str:
    """Resolve the layout country from filename metadata or the explicit parser argument."""
    parsed_country = metadata.get("country")
    if isinstance(parsed_country, str) and parsed_country:
        return parsed_country
    if country is not None:
        return country.upper()
    raise WrongInput(
        "The selected CEPALSTAT file name does not encode the country. Please provide the explicit country argument."
    )


def _select_candidate_file(
    path: str | Path,
    *,
    table: str,
    year: int | None,
    country: str | None,
    iot_mode: str,
) -> Path:
    """Select one CEPALSTAT bundle candidate after filename-level filtering."""
    candidates = _list_candidate_files(
        path,
        table=table,
        year=year,
        country=country,
        iot_mode=iot_mode,
    )
    if len(candidates) > 1:
        ranked = sorted(
            candidates,
            key=lambda item: (_member_price_rank(item.name), -_member_dimension_score(item.name), item.name.lower()),
        )
        best = ranked[0]
        best_key = (_member_price_rank(best.name), _member_dimension_score(best.name))
        equally_ranked = [
            candidate
            for candidate in ranked
            if (_member_price_rank(candidate.name), _member_dimension_score(candidate.name)) == best_key
        ]
        if len(equally_ranked) == 1:
            return equally_ranked[0]
        raise WrongInput(
            "More than one CEPALSTAT bundle matches the selected arguments. "
            "Please point to one file or refine country/year/mode. "
            f"Available candidates: {[candidate.name for candidate in candidates]}"
        )
    return candidates[0]


def _zip_excel_members(data_path: Path) -> list[str]:
    """List Excel members inside one CEPALSTAT zip bundle."""
    if data_path.suffix.lower() != ".zip":
        return []

    try:
        with ZipFile(data_path) as zf:
            return [
                name
                for name in zf.namelist()
                if name.lower().endswith((".xlsx", ".xls", ".xlsm")) and not Path(name).name.startswith("~$")
            ]
    except BadZipFile as exc:
        raise WrongInput(
            f"The selected CEPALSTAT bundle {data_path.name} is not a valid zip archive."
        ) from exc


def _open_excel_member(data_path: Path, workbook_member: str | None = None) -> pd.ExcelFile:
    """Open one direct Excel file or one selected member inside a zip bundle."""
    if data_path.suffix.lower() != ".zip":
        return pd.ExcelFile(data_path)

    if workbook_member is None:
        raise WrongInput(
            f"The selected CEPALSTAT bundle {data_path.name} requires one explicit workbook member."
        )

    try:
        with ZipFile(data_path) as zf:
            payload = BytesIO(zf.read(workbook_member))
    except BadZipFile as exc:
        raise WrongInput(
            f"The selected CEPALSTAT bundle {data_path.name} is not a valid zip archive."
        ) from exc
    except KeyError as exc:
        raise WrongInput(
            f"The selected CEPALSTAT bundle {data_path.name} does not contain workbook member {workbook_member}."
        ) from exc

    return pd.ExcelFile(payload)


def _open_excel_payload(
    data_path: Path,
    *,
    table: str,
    iot_mode: str,
    workbook_member: str | None = None,
) -> tuple[pd.ExcelFile, str | None]:
    """Open one CEPALSTAT workbook from a direct file or from inside a zip bundle."""
    if workbook_member is not None:
        return _open_excel_member(data_path, workbook_member), workbook_member

    suffix = data_path.suffix.lower()
    if suffix != ".zip":
        return pd.ExcelFile(data_path), None

    members = _zip_excel_members(data_path)
    with ZipFile(data_path) as zf:
        if not members:
            raise WrongInput(
                f"The selected CEPALSTAT bundle {data_path.name} does not contain any Excel workbook."
            )

        selected_member = None
        if table == "IOT":
            ranked = []
            for member in members:
                meta = _parse_candidate_metadata(Path(member))
                member_mode = None if meta is None else meta["mode"]
                ranked.append((member, member_mode))
            if iot_mode != "auto":
                for member, member_mode in ranked:
                    if member_mode == iot_mode:
                        selected_member = member
                        break
            if selected_member is None:
                for member, member_mode in ranked:
                    if iot_mode == "auto" or member_mode == "pxp":
                        selected_member = member
                        break
            if selected_member is None:
                selected_member = members[0]
        else:
            if len(members) == 1:
                selected_member = members[0]
            else:
                current_members = [member for member in members if "corrient" in member.lower() or "current" in member.lower()]
                if len(current_members) == 1:
                    selected_member = current_members[0]
                else:
                    raise WrongInput(
                        f"The selected CEPALSTAT SUT bundle {data_path.name} contains more than one workbook. "
                        "Please point to one workbook directly."
                    )

        payload = BytesIO(zf.read(selected_member))
        return pd.ExcelFile(payload), selected_member


def _extract_year(header: pd.DataFrame) -> int | None:
    """Extract one four-digit year from a small header frame."""
    matches: list[int] = []
    for value in header.to_numpy().ravel():
        text = _text(value)
        match = re.search(r"\bAño\s+(\d{4})\b", text, flags=re.IGNORECASE)
        if match is not None:
            matches.append(int(match.group(1)))
    return matches[0] if matches else None


def _find_header_row(frame: pd.DataFrame, patterns: tuple[str, ...], *, search_rows: range = range(0, 20)) -> int:
    """Find the first row whose flattened text contains all requested patterns."""
    for row in search_rows:
        if row >= len(frame):
            continue
        row_text = " | ".join(_plain(_text(value)) for value in frame.iloc[row].to_list() if _text(value))
        if all(pattern in row_text for pattern in patterns):
            return row
    joined = ", ".join(patterns)
    raise WrongFormat(f"Could not detect the CEPALSTAT header row containing {joined}.")


def _find_col_by_pattern(frame: pd.DataFrame, row: int, pattern: str, *, start: int = 0) -> int:
    """Find one column by substring match on a given header row."""
    target = _plain(pattern)
    for column in range(start, frame.shape[1]):
        if target in _plain(_text(frame.iat[row, column])):
            return column
    raise WrongFormat(f"Could not find required column matching '{pattern}' in the CEPALSTAT workbook.")


def _find_col_in_rows(
    frame: pd.DataFrame,
    rows: tuple[int, ...],
    labels: str | tuple[str, ...],
    *,
    start: int = 0,
) -> int:
    """Find one exact header label across a small set of rows."""
    if isinstance(labels, str):
        targets = {_plain(labels)}
    else:
        targets = {_plain(label) for label in labels}
    for row in rows:
        if row >= len(frame):
            continue
        for column in range(start, frame.shape[1]):
            if _plain(_text(frame.iat[row, column])) in targets:
                return column
    expected = labels if isinstance(labels, str) else " / ".join(labels)
    raise WrongFormat(f"Could not find required column '{expected}' in the CEPALSTAT workbook.")


def _find_price_column_within_group(
    frame: pd.DataFrame,
    labels: str | tuple[str, ...],
    *,
    header_rows: tuple[int, ...],
    start: int = 0,
    width: int = 8,
) -> int:
    """Find the buyer-price value column within one grouped final-demand header block."""
    anchor = _find_col_in_rows(frame, header_rows, labels, start=start)
    for column in range(anchor, min(anchor + width, frame.shape[1])):
        texts = {_plain(_text(frame.iat[row, column])) for row in header_rows if row < len(frame)}
        if "a precios de comprador" in texts:
            return column
    return anchor


def _find_export_total_column(frame: pd.DataFrame, *, header_rows: tuple[int, ...]) -> int:
    """Find the total exports-at-purchaser-prices column in one CEPALSTAT use sheet."""
    anchor = None
    try:
        anchor = _find_col_in_rows(frame, header_rows, "Exportaciones")
    except WrongFormat:
        anchor = None

    if anchor is not None:
        for column in range(anchor, min(anchor + 8, frame.shape[1])):
            texts = [_plain(_text(frame.iat[row, column])) for row in header_rows if row < len(frame)]
            if "total" in texts and "a precios de comprador" in texts:
                return column

    fallback = [
        column
        for column in range(frame.shape[1])
        if "total" in [_plain(_text(frame.iat[row, column])) for row in header_rows if row < len(frame)]
        and "a precios de comprador" in [_plain(_text(frame.iat[row, column])) for row in header_rows if row < len(frame)]
    ]
    if fallback:
        return fallback[-1]
    raise WrongFormat("Could not detect the export final-demand column in the CEPALSTAT use sheet.")


def _scan_colombia_sut_index_pairs(workbook: pd.ExcelFile, *, digits: str = "dos") -> dict[int, dict[str, str]]:
    """Scan the DANE-style Índice sheet and map years to offer/use Cuadro pairs."""
    if "Índice" not in workbook.sheet_names:
        return {}

    index_frame = pd.read_excel(workbook, sheet_name="Índice", header=None)
    pairs: dict[int, dict[str, str]] = {}
    current_year: int | None = None
    current_digits: str | None = None

    for row in range(len(index_frame)):
        row_values = [_text(value) for value in index_frame.iloc[row].to_list() if _text(value)]
        if not row_values:
            continue
        row_text = " | ".join(_plain(value) for value in row_values)
        title_match = re.search(
            r"cuadro oferta[- ]utilizacion (?P<year>\d{4})(?: [a-z]+)? a (?P<digits>dos|seis) digitos",
            row_text,
        )
        if title_match is not None:
            current_year = int(title_match.group("year"))
            current_digits = title_match.group("digits")
            continue

        if current_year is None or current_digits != digits:
            continue

        sheet_name = next(
            (
                value.strip()
                for value in row_values
                if re.match(r"^Cuadro\s+\d+\s*$", value, flags=re.IGNORECASE)
            ),
            None,
        )
        if sheet_name is None:
            continue
        if "cuadro oferta" in row_text:
            pairs.setdefault(current_year, {})["offer"] = sheet_name
        elif "cuadro utilizacion" in row_text:
            pairs.setdefault(current_year, {})["use"] = sheet_name

    return {year: item for year, item in pairs.items() if {"offer", "use"}.issubset(item)}


def _resolve_colombia_legacy_iot_sheet(
    workbook: pd.ExcelFile,
    *,
    year: int | None,
    iot_mode: str,
) -> str | None:
    """Resolve one year-specific sheet inside the legacy Colombian 2005/2010 IOT workbooks."""
    available_years = sorted({int(name) for sheet in workbook.sheet_names for name in _member_years(sheet)})
    if year is None:
        if len(available_years) != 1:
            raise WrongInput(
                "The selected CEPALSTAT Colombian IOT workbook contains more than one year. "
                f"Available years: {available_years}. Please specify year."
            )
        target_year = available_years[0]
    else:
        target_year = int(year)
        if available_years and target_year not in available_years:
            raise WrongInput(
                f"The selected CEPALSTAT Colombian IOT workbook does not contain year {target_year}. "
                f"Available years: {available_years}."
            )

    if iot_mode == "axa":
        exact = next((sheet for sheet in workbook.sheet_names if sheet.strip() == str(target_year)), None)
        if exact is not None:
            return exact
        return None

    exact = next(
        (
            sheet
            for sheet in workbook.sheet_names
            if _plain(sheet) == _plain(f"Matriz Insumo-Producto {target_year}")
        ),
        None,
    )
    if exact is not None:
        return exact

    for sheet in workbook.sheet_names:
        normalized = _plain(sheet)
        if (
            "matriz insumo-producto" in normalized
            and "dom" not in normalized
            and "multiplicador" not in normalized
            and target_year in _member_years(sheet)
        ):
            return sheet
    return None


def _scan_integrated_sut_sheet_pairs(workbook: pd.ExcelFile) -> dict[int, dict[str, str]]:
    """Scan a workbook for integrated offer/use sheet pairs keyed by year."""
    pairs: dict[int, dict[str, str]] = {}
    for sheet_name in workbook.sheet_names:
        preview = pd.read_excel(workbook, sheet_name=sheet_name, header=None, nrows=8)
        preview_text = " | ".join(_plain(_text(value)) for value in preview.to_numpy().ravel() if _text(value))
        kind = None
        if "cuadro oferta" in preview_text:
            kind = "offer"
        elif "cuadro utilizacion" in preview_text:
            kind = "use"
        if kind is None:
            continue
        year = _extract_year(preview)
        if year is None:
            continue
        pairs.setdefault(year, {})[kind] = sheet_name
    return {year: item for year, item in pairs.items() if {"offer", "use"}.issubset(item)}


def _member_years(name: str) -> list[int]:
    """Extract four-digit years encoded in one workbook or member name."""
    return [int(match) for match in re.findall(r"(?:19|20)\d{2}", name)]


def _member_dimension_score(name: str) -> int:
    """Return one ordering score for layout dimensions encoded in a member name."""
    match = re.search(r"(?P<rows>\d+)x(?P<cols>\d+)", name, flags=re.IGNORECASE)
    if match is None:
        return 0
    return int(match.group("rows")) * int(match.group("cols"))


def _member_dimensions(name: str) -> tuple[int, int] | None:
    """Return the row/column dimensions encoded in one workbook or member name."""
    match = re.search(r"(?P<rows>\d+)x(?P<cols>\d+)", name, flags=re.IGNORECASE)
    if match is None:
        return None
    return int(match.group("rows")), int(match.group("cols"))


def _member_price_rank(name: str) -> int:
    """Rank workbook members so current-price files are preferred over constant-price files."""
    normalized = name.lower()
    if "corrient" in normalized or "current" in normalized:
        return 0
    if "const" in normalized:
        return 2
    return 1


def _sheet_preview_text(workbook: pd.ExcelFile, sheet_name: str, *, nrows: int = 10) -> str:
    """Return a flattened normalized preview string for one sheet."""
    preview = pd.read_excel(workbook, sheet_name=sheet_name, header=None, nrows=nrows)
    return " | ".join(_plain(_text(value)) for value in preview.to_numpy().ravel() if _text(value))


def _find_first_sheet(workbook: pd.ExcelFile, patterns: tuple[str, ...], *, nrows: int = 10) -> str | None:
    """Find the first sheet whose preview contains all requested substrings."""
    for sheet_name in workbook.sheet_names:
        preview_text = _sheet_preview_text(workbook, sheet_name, nrows=nrows)
        if all(pattern in preview_text for pattern in patterns):
            return sheet_name
    return None


def _resolve_member_for_year(members: list[str], year: int | None) -> str:
    """Select one workbook member by year when the bundle contains many yearly files."""
    if len(members) == 1:
        return members[0]

    if year is None:
        raise WrongInput(
            "The selected CEPALSTAT bundle contains more than one yearly workbook. "
            f"Available members: {members}. Please specify year."
        )

    matching = [member for member in members if year in _member_years(Path(member).name)]
    if not matching:
        raise WrongInput(
            f"The selected CEPALSTAT bundle does not contain a workbook for year {year}. "
            f"Available members: {members}"
        )
    if len(matching) > 1:
        raise WrongInput(
            f"The selected CEPALSTAT bundle contains more than one workbook for year {year}: {matching}"
        )
    return matching[0]


def _resolve_bra_pair_members(
    data_path: Path,
    *,
    table: str,
    year: int | None,
) -> tuple[str, str]:
    """Resolve the paired BRA offer/demand workbooks inside one zip bundle or directory."""
    if data_path.suffix.lower() == ".zip":
        members = _zip_excel_members(data_path)
    else:
        members = [
            child.name
            for child in data_path.parent.iterdir()
            if child.is_file() and child.suffix.lower() in {".xls", ".xlsx", ".xlsm"}
        ]

    upper_members = {member.upper(): member for member in members}
    family_token = "COU" if table == "SUT" else "MIP"
    if year is not None:
        year_token = str(year)
        members = [member for member in members if year_token in member]
    if table == "SUT":
        members = [member for member in members if "PRECIOSCORRIENTES" in member.upper()]
        offer_members = [member for member in members if "_OFERTA" in member.upper()]
        demand_members = [member for member in members if "_DEMANDA" in member.upper()]
    else:
        members = [member for member in members if "DEMANDA_BASICO" in member.upper()]
        offer_members = [member for member in members if "_DEMANDA_BASICO" in member.upper()]
        demand_members = offer_members

    if not offer_members:
        raise NotImplementable(
            f"Could not locate the supported BRA {family_token} workbook members inside {data_path.name}."
        )

    if table == "SUT":
        pairs: list[tuple[str, str]] = []
        for offer_member in offer_members:
            offer_key = offer_member.upper().replace("_OFERTA", "")
            for demand_member in demand_members:
                demand_key = demand_member.upper().replace("_DEMANDA", "")
                if offer_key == demand_key:
                    pairs.append((offer_member, demand_member))
        if not pairs:
            raise NotImplementable(
                f"Could not pair BRA {family_token} offer and demand workbooks inside {data_path.name}."
            )
        pairs.sort(key=lambda item: _member_dimension_score(item[0]), reverse=True)
        return pairs[0]

    square_members = []
    for member in offer_members:
        dims = _member_dimensions(member)
        if dims is not None and dims[0] == dims[1]:
            square_members.append(member)
    selected_pool = square_members or offer_members
    selected = sorted(selected_pool, key=_member_dimension_score, reverse=True)[0]
    return selected, selected


def detect_cepalstat_sut_layout(
    path: str | Path,
    *,
    year: int | None = None,
    country: str | None = None,
) -> CEPALSTATLayout:
    """Resolve one supported CEPALSTAT SUT bundle and yearly sheet pair."""
    data_path = _select_candidate_file(path, table="SUT", year=year, country=country, iot_mode="auto")
    metadata = _parse_candidate_metadata(data_path)
    if metadata is None:
        raise WrongInput("The selected CEPALSTAT file name does not match a supported SUT bundle.")
    resolved_country = _resolve_layout_country(metadata, country)

    if data_path.suffix.lower() == ".zip":
        members = _zip_excel_members(data_path)
    else:
        members = [data_path.name]

    has_offer_members = any("_OFERTA" in member.upper() for member in members)
    has_demand_members = any("_DEMANDA" in member.upper() for member in members)
    if has_offer_members and has_demand_members:
        offer_member, demand_member = _resolve_bra_pair_members(data_path, table="SUT", year=year)
        notes = (
            "Parsed from the CEPALSTAT/Brazil split SUT layout with paired offer and demand workbooks.",
            "When the bundle contains more than one current-price aggregation, the largest layout is selected by default.",
        )
        return CEPALSTATLayout(
            root=data_path.parent,
            data_path=data_path,
            country=str(metadata["country"]),
            year=int(year) if year is not None else int(metadata["start"]),
            table="SUT",
            family="bra_split_sut",
            workbook_member=offer_member if data_path.suffix.lower() == ".zip" else Path(offer_member).name,
            auxiliary_members=(demand_member if data_path.suffix.lower() == ".zip" else Path(demand_member).name,),
            sheet_names=("oferta", "producao", "CI", "demanda", "VA", "importacao"),
            notes=notes,
        )

    if data_path.suffix.lower() == ".zip":
        workbook_members = sorted(members, key=lambda member: (_member_price_rank(member), member.lower()))
    else:
        workbook_members = [None]

    integrated_candidate: CEPALSTATLayout | None = None
    colombia_candidate: CEPALSTATLayout | None = None
    arg_candidate: CEPALSTATLayout | None = None
    chi_candidate: CEPALSTATLayout | None = None
    integrated_years: set[int] = set()
    colombia_years: set[int] = set()
    arg_years: set[int] = set()

    for member in workbook_members:
        workbook = _open_excel_member(data_path, member)
        colombia_pairs = _scan_colombia_sut_index_pairs(workbook, digits="dos")
        if colombia_pairs:
            colombia_years.update(int(item) for item in colombia_pairs)
            target_year = year
            if target_year is None:
                if len(colombia_pairs) != 1:
                    raise WrongInput(
                        "The selected CEPALSTAT SUT workbook contains more than one two-digit Colombia year. "
                        f"Available years: {sorted(colombia_pairs)}. Please specify year."
                    )
                target_year = next(iter(sorted(colombia_pairs)))
            if int(target_year) in colombia_pairs:
                candidate = CEPALSTATLayout(
                    root=data_path.parent,
                    data_path=data_path,
                    country=resolved_country,
                    year=int(target_year),
                    table="SUT",
                    family="col_indexed_sut",
                    workbook_member=member,
                    sheet_names=(colombia_pairs[int(target_year)]["offer"], colombia_pairs[int(target_year)]["use"]),
                    notes=(
                        "Parsed from the CEPALSTAT/Colombia indexed two-digit SUT layout.",
                    ),
                )
                if (
                    colombia_candidate is None
                    or _member_price_rank(candidate.workbook_member or data_path.name)
                    < _member_price_rank(colombia_candidate.workbook_member or data_path.name)
                ):
                    colombia_candidate = candidate
                continue

        pairs = _scan_integrated_sut_sheet_pairs(workbook)
        if pairs:
            integrated_years.update(int(item) for item in pairs)
            target_year = year
            if target_year is None:
                if len(pairs) != 1:
                    raise WrongInput(
                        "The selected CEPALSTAT SUT workbook contains more than one year. "
                        f"Available years: {sorted(pairs)}. Please specify year."
                    )
                target_year = next(iter(sorted(pairs)))
            if int(target_year) in pairs:
                candidate = CEPALSTATLayout(
                    root=data_path.parent,
                    data_path=data_path,
                    country=resolved_country,
                    year=int(target_year),
                    table="SUT",
                    family="integrated_sut_cuadros",
                    workbook_member=member,
                    sheet_names=(pairs[int(target_year)]["offer"], pairs[int(target_year)]["use"]),
                    notes=(
                        "Parsed from the CEPALSTAT integrated SUT workbook layout with paired offer/use sheets.",
                    ),
                )
                if (
                    integrated_candidate is None
                    or _member_price_rank(candidate.workbook_member or data_path.name)
                    < _member_price_rank(integrated_candidate.workbook_member or data_path.name)
                ):
                    integrated_candidate = candidate
                continue

        normalized_sheets = {sheet.lower(): sheet for sheet in workbook.sheet_names}
        if any(sheet.lower().startswith("mat_of") for sheet in workbook.sheet_names) and any(
            sheet.lower().startswith("mat_ut") for sheet in workbook.sheet_names
        ):
            if year is None and data_path.suffix.lower() == ".zip" and len(workbook_members) > 1:
                # Keep scanning other members until the requested year is resolved explicitly.
                member_years = _member_years(member or data_path.name)
                if member_years and member_years[0] != int(metadata["start"]):
                    pass
            offer_sheet = next(sheet for sheet in workbook.sheet_names if sheet.lower().startswith("mat_of"))
            use_sheet = next(sheet for sheet in workbook.sheet_names if sheet.lower().startswith("mat_ut"))
            resolved_year = year
            member_years = _member_years((member or data_path.name))
            if member_years:
                arg_years.update(member_years)
            if resolved_year is None:
                resolved_year = member_years[0] if member_years else int(metadata["start"])
            if year is None or resolved_year == year:
                arg_candidate = CEPALSTATLayout(
                    root=data_path.parent,
                    data_path=data_path,
                    country=resolved_country,
                    year=int(resolved_year),
                    table="SUT",
                    family="arg_two_sheet_sut",
                    workbook_member=member,
                    sheet_names=(offer_sheet, use_sheet),
                    notes=(
                        "Parsed from the CEPALSTAT/Argentina two-sheet SUT layout with one offer and one use worksheet.",
                    ),
                )
                continue

        if {"1", "2", "5", "6", "23"}.issubset(set(workbook.sheet_names)):
            title_1 = _sheet_preview_text(workbook, "1", nrows=8)
            title_23 = _sheet_preview_text(workbook, "23", nrows=8)
            if "matriz de produccion" in title_1 and "cuadrante de valor agregado" in title_23:
                chi_candidate = CEPALSTATLayout(
                    root=data_path.parent,
                    data_path=data_path,
                    country=resolved_country,
                    year=int(year) if year is not None else int(metadata["start"]),
                    table="SUT",
                    family="chi_multicuadro_sut",
                    workbook_member=member,
                    sheet_names=("1", "5", "6", "23", "2"),
                    notes=(
                        "Parsed from the CEPALSTAT/Chile multi-cuadro SUT layout.",
                    ),
                )

    if arg_candidate is not None:
        if year is not None and arg_candidate.year != int(year):
            raise WrongInput(
                f"The selected CEPALSTAT SUT bundle does not contain year {year} in the supported Argentina layout."
            )
        return arg_candidate
    if chi_candidate is not None:
        return chi_candidate
    if colombia_candidate is not None:
        return colombia_candidate
    if integrated_candidate is not None:
        return integrated_candidate
    if year is not None and colombia_years:
        raise WrongInput(
            "The selected CEPALSTAT SUT bundle does not contain year "
            f"{year} in the supported indexed Colombia layout. "
            f"Available years: {sorted(colombia_years)}."
        )
    if year is not None and integrated_years:
        raise WrongInput(
            "The selected CEPALSTAT SUT bundle does not contain year "
            f"{year} in the supported integrated offer/use layout. "
            f"Available years: {sorted(integrated_years)}."
        )
    if year is not None and arg_years:
        raise WrongInput(
            f"The selected CEPALSTAT SUT bundle does not contain year {year} in the supported Argentina layout. "
            f"Available years: {sorted(arg_years)}."
        )

    raise NotImplementable(
        "This CEPALSTAT SUT bundle is not in one of the currently supported layouts: "
        "integrated offer/use workbook, Argentina two-sheet workbook, Brazil split workbooks, or Chile multi-cuadro."
    )


def detect_cepalstat_iot_layout(
    path: str | Path,
    *,
    year: int | None = None,
    country: str | None = None,
    iot_mode: str = "pxp",
) -> CEPALSTATLayout:
    """Resolve one supported CEPALSTAT IOT bundle and direct matrix workbook."""
    if iot_mode not in CEPALSTAT_IOT_MODES:
        raise WrongInput(f"CEPALSTAT iot_mode should be one of {list(CEPALSTAT_IOT_MODES)}.")

    data_path = _select_candidate_file(
        path,
        table="IOT",
        year=year,
        country=country,
        iot_mode=iot_mode,
    )
    metadata = _parse_candidate_metadata(data_path)
    if metadata is None:
        raise WrongInput("The selected CEPALSTAT file name does not match a supported IOT bundle.")
    resolved_country = _resolve_layout_country(metadata, country)

    if data_path.suffix.lower() == ".zip":
        members = _zip_excel_members(data_path)
    else:
        members = [data_path.name]

    upper_members = {member.upper(): member for member in members}

    if any("DEMANDA_BASICO" in member.upper() for member in members):
        workbook_member, _ = _resolve_bra_pair_members(data_path, table="IOT", year=year)
        return CEPALSTATLayout(
            root=data_path.parent,
            data_path=data_path,
            country=resolved_country,
            year=int(year) if year is not None else int(metadata["start"]),
            table="IOT",
            family="bra_demand_basic_iot",
            workbook_member=workbook_member if data_path.suffix.lower() == ".zip" else Path(workbook_member).name,
            sheet_names=("3",),
            iot_mode="auto",
            notes=(
                "Parsed from the CEPALSTAT/Brazil demand-at-basic-prices IOT workbook layout.",
                "When the bundle contains more than one aggregation, the largest layout is selected by default.",
            ),
        )

    symmetric_members = [member for member in members if "simetric" in _plain(member)]
    if symmetric_members:
        selected_member = symmetric_members[0]
        return CEPALSTATLayout(
            root=data_path.parent,
            data_path=data_path,
            country=resolved_country,
            year=int(year) if year is not None else int(metadata["start"]),
            table="IOT",
            family="arg_symmetric_iot",
            workbook_member=selected_member if data_path.suffix.lower() == ".zip" else Path(selected_member).name,
            sheet_names=("Cuadro 12",),
            iot_mode="auto",
            notes=("Parsed from the CEPALSTAT/Argentina symmetric IOT workbook layout.",),
        )

    if any((_parse_candidate_metadata(Path(member)) or {}).get("mode") in {"pxp", "axa"} for member in members):
        preferred_mode = "pxp" if iot_mode == "auto" else iot_mode
        ranked_members = []
        for member in members:
            member_meta = _parse_candidate_metadata(Path(member))
            member_mode = None if member_meta is None else member_meta["mode"]
            ranked_members.append((member, member_mode))
        selected_member = None
        for member, member_mode in ranked_members:
            if member_mode == preferred_mode:
                selected_member = member
                break
        if selected_member is None:
            for member, member_mode in ranked_members:
                if member_mode is not None:
                    selected_member = member
                    break
        if selected_member is None:
            selected_member = ranked_members[0][0]

        workbook = _open_excel_member(data_path, selected_member if data_path.suffix.lower() == ".zip" else None)
        if {"Cuadro 3", "Cuadro 7"}.issubset(set(workbook.sheet_names)):
            sheet_name = "Cuadro 7" if preferred_mode == "axa" else "Cuadro 3"
            resolved_mode = "axa" if sheet_name == "Cuadro 7" else "pxp"
            return CEPALSTATLayout(
                root=data_path.parent,
                data_path=data_path,
                country=resolved_country,
                year=int(year) if year is not None else int(metadata["start"]),
                table="IOT",
                family="col_cuadro_iot",
                workbook_member=selected_member if data_path.suffix.lower() == ".zip" else Path(selected_member).name,
                sheet_names=(sheet_name,),
                iot_mode=resolved_mode,
                notes=("Parsed from the CEPALSTAT/Colombia IOT cuadro workbook layout.",),
            )
        legacy_colombia_sheet = None
        if resolved_country == "COL":
            legacy_colombia_sheet = _resolve_colombia_legacy_iot_sheet(
                workbook,
                year=year,
                iot_mode=preferred_mode,
            )
        if legacy_colombia_sheet is not None:
            return CEPALSTATLayout(
                root=data_path.parent,
                data_path=data_path,
                country=resolved_country,
                year=int(year) if year is not None else int(metadata["start"]),
                table="IOT",
                family="col_legacy_iot",
                workbook_member=selected_member if data_path.suffix.lower() == ".zip" else Path(selected_member).name,
                sheet_names=(legacy_colombia_sheet,),
                iot_mode=preferred_mode,
                notes=(
                    "Parsed from the legacy CEPALSTAT/Colombia 2005-2010 multi-year IOT workbook layout.",
                ),
            )
        target_sheet = next((sheet for sheet in workbook.sheet_names if sheet.lower().startswith("mip")), None)
        if target_sheet is None:
            target_sheet = _find_first_sheet(workbook, ("matriz insumo-producto",), nrows=8)
        if target_sheet is None:
            target_sheet = _find_first_sheet(workbook, ("matriz simetrica de insumo-producto",), nrows=8)
        if target_sheet is None:
            target_sheet = next(
                (sheet for sheet in workbook.sheet_names if "matriz u simetrica" in _plain(sheet)),
                None,
            )
        if target_sheet is None:
            target_sheet = _find_first_sheet(workbook, ("matriz u",), nrows=10)
        if target_sheet is None:
            raise NotImplementable(
                f"Could not detect the supported matrix sheet inside CEPALSTAT member {selected_member}."
            )
        family = "gtm_member_iot" if target_sheet.lower().startswith("mip_") else "dom_direct_iot"
        resolved_mode = preferred_mode
        return CEPALSTATLayout(
            root=data_path.parent,
            data_path=data_path,
            country=resolved_country,
            year=int(year) if year is not None else int(metadata["start"]),
            table="IOT",
            family=family,
            workbook_member=selected_member if data_path.suffix.lower() == ".zip" else Path(selected_member).name,
            sheet_names=(target_sheet,),
            iot_mode=resolved_mode,
            notes=("Parsed from a CEPALSTAT direct symmetric IOT workbook member.",),
        )

    workbook_members = members if data_path.suffix.lower() == ".zip" else [None]
    for member in workbook_members:
        workbook = _open_excel_member(data_path, member)
        if {"Cuadro 3", "Cuadro 7"}.issubset(set(workbook.sheet_names)):
            sheet_name = "Cuadro 7" if iot_mode == "axa" else "Cuadro 3"
            resolved_mode = "axa" if sheet_name == "Cuadro 7" else "pxp"
            return CEPALSTATLayout(
                root=data_path.parent,
                data_path=data_path,
                country=resolved_country,
                year=int(year) if year is not None else int(metadata["start"]),
                table="IOT",
                family="col_cuadro_iot",
                workbook_member=member,
                sheet_names=(sheet_name,),
                iot_mode=resolved_mode,
                notes=("Parsed from the CEPALSTAT/Colombia IOT cuadro workbook layout.",),
            )

        if "1" in workbook.sheet_names and "matriz de insumo-producto" in _sheet_preview_text(workbook, "1", nrows=8):
            return CEPALSTATLayout(
                root=data_path.parent,
                data_path=data_path,
                country=resolved_country,
                year=int(year) if year is not None else int(metadata["start"]),
                table="IOT",
                family="chi_matrix_iot",
                workbook_member=member,
                sheet_names=("1",),
                iot_mode="axa",
                notes=(
                    "Parsed from the CEPALSTAT/Chile matrix workbook layout.",
                    "Only the activity-by-activity matrix is distributed in this workbook.",
                ),
            )

    raise NotImplementable(
        "This CEPALSTAT IOT bundle is not in one of the currently supported layouts: "
        "DOM/GTM direct member, Colombia cuadro workbook, Argentina symmetric workbook, Brazil demand-basic workbook, or Chile matrix workbook."
    )


def _read_cepalstat_sheet(layout: CEPALSTATLayout, sheet_name: str) -> pd.DataFrame:
    """Read one selected sheet from a CEPALSTAT workbook."""
    workbook, _ = _open_excel_payload(
        layout.data_path,
        table=layout.table,
        iot_mode=layout.iot_mode or "auto",
        workbook_member=layout.workbook_member,
    )
    return pd.read_excel(workbook, sheet_name=sheet_name, header=None)


def _read_cepalstat_auxiliary_sheet(layout: CEPALSTATLayout, index: int, sheet_name: str) -> pd.DataFrame:
    """Read one selected sheet from an auxiliary CEPALSTAT workbook member."""
    workbook_member = layout.auxiliary_members[index]
    workbook, _ = _open_excel_payload(
        layout.data_path,
        table=layout.table,
        iot_mode=layout.iot_mode or "auto",
        workbook_member=workbook_member,
    )
    return pd.read_excel(workbook, sheet_name=sheet_name, header=None)


def _find_activity_columns_in_offer(frame: pd.DataFrame) -> list[int]:
    """Return the activity columns in one integrated offer sheet."""
    header = frame.iloc[10]
    total_col = None
    for column in range(frame.shape[1]):
        if _text(header.iloc[column]).lower() == "total":
            total_col = column
            break
    if total_col is None:
        raise WrongFormat("Could not detect the activity total column in the CEPALSTAT offer sheet.")
    columns = [column for column in range(10, total_col) if _norm(header.iloc[column])]
    if not columns:
        raise WrongFormat("Could not detect activity columns in the CEPALSTAT offer sheet.")
    return columns


def _find_activity_columns_in_use(frame: pd.DataFrame) -> list[int]:
    """Return the activity columns in one integrated use sheet."""
    header = frame.iloc[10]
    stop_markers = {
        "total",
        "a precios de comprador",
        "a precios basicos",
        "impuestos excepto iva",
    }
    columns: list[int] = []
    for column in range(5, frame.shape[1]):
        label = _plain(_text(header.iloc[column]))
        if label in stop_markers:
            break
        if label:
            columns.append(column)
    if not columns:
        raise WrongFormat("Could not detect activity columns in the CEPALSTAT use sheet.")
    return columns


def _find_product_rows(frame: pd.DataFrame, *, start_row: int) -> list[int]:
    """Return the contiguous product rows in one CEPALSTAT sheet."""
    rows: list[int] = []
    started = False
    for row in range(start_row, len(frame)):
        code = _norm(frame.iat[row, 0] if frame.shape[1] > 0 else np.nan)
        label = _text(frame.iat[row, 1] if frame.shape[1] > 1 else np.nan).lower()
        if not code:
            if started:
                break
            continue
        if label in {"total", "totales"}:
            break
        rows.append(row)
        started = True
    if not rows:
        raise WrongFormat("Could not detect product rows in the CEPALSTAT workbook.")
    return rows


def _find_row_by_label(frame: pd.DataFrame, label: str) -> int:
    """Find one row by the normalized label in the second column."""
    target = label.strip().lower()
    for row in range(len(frame)):
        if _text(frame.iat[row, 1] if frame.shape[1] > 1 else np.nan).strip().lower() == target:
            return row
    raise WrongFormat(f"Could not find required row '{label}' in the CEPALSTAT workbook.")


def _find_row_by_pattern(frame: pd.DataFrame, pattern: str, *, column: int = 1) -> int:
    """Find one row by substring match in the selected column."""
    target = _plain(pattern)
    for row in range(len(frame)):
        value = _plain(_text(frame.iat[row, column] if column < frame.shape[1] else np.nan))
        if target in value:
            return row
    raise WrongFormat(f"Could not find required row matching '{pattern}' in the CEPALSTAT workbook.")


def _find_col(frame: pd.DataFrame, row: int, label: str | tuple[str, ...], *, start: int = 0) -> int:
    """Find one column by one or more normalized header labels on a given row."""
    if isinstance(label, str):
        labels = (label,)
    else:
        labels = label
    targets = {item.strip().lower() for item in labels}
    for column in range(start, frame.shape[1]):
        if _text(frame.iat[row, column]).strip().lower() in targets:
            return column
    expected = " / ".join(labels)
    raise WrongFormat(f"Could not find required column '{expected}' in the CEPALSTAT workbook.")


def _map_iot_factor_label(code: str, label: str) -> str | None:
    """Map one CEPALSTAT direct-IOT row label to the standard factor naming."""
    normalized_code = _plain(code)
    normalized_label = _plain(label)
    if normalized_code == "d.1" or "remuner" in normalized_label or "asalariad" in normalized_label:
        return "Compensation of employees"
    if normalized_code == "d.29" or "otros impuestos sobre la produccion" in normalized_label:
        return "Other taxes on production"
    if normalized_code == "d.39" or ("subvencion" in normalized_label and "producto" not in normalized_label):
        return "Other subsidies on production"
    if normalized_code == "b.2b" or ("excedente" in normalized_label and "valor agregado" not in normalized_label):
        return "Gross operating surplus"
    if normalized_code == "b.3b" or "ingreso mixto" in normalized_label:
        return "Mixed income"
    if (
        "impuestos netos sobre los productos" in normalized_label
        or "impuestos sobre bienes y servicios netos" in normalized_label
        or "impuestos sobre productos" in normalized_label
    ):
        return "Taxes less subsidies on products"
    if (
        "impuestos sobre la produccion y las importaciones" in normalized_label
        or "impuestos menos subvenciones sobre la produccion e importaciones" in normalized_label
    ):
        return "Other taxes on production and imports"
    if "valor agregado bruto" in normalized_label:
        return "Value added at basic prices"
    return None


def _find_total_intermediate_column(
    frame: pd.DataFrame,
    *,
    search_rows: tuple[int, ...] = tuple(range(0, 20)),
) -> int | None:
    """Detect the intermediate-demand total column from multi-row headers."""
    for row in search_rows:
        if row >= len(frame):
            continue
        for column in range(frame.shape[1]):
            label = _plain(_text(frame.iat[row, column]))
            if "demanda intermedia" in label and "total" in label:
                return column
    candidates: list[tuple[int, int]] = []
    for row in search_rows:
        if row >= len(frame):
            continue
        for column in range(frame.shape[1]):
            label = _plain(_text(frame.iat[row, column]))
            if "demanda intermedia" not in label and "consumo intermedio" not in label:
                continue
            numeric_count = sum(
                1 for probe_row in range(row + 1, min(row + 8, len(frame))) if _is_numeric_cell(frame.iat[probe_row, column])
            )
            if numeric_count:
                candidates.append((numeric_count, column))
    if candidates:
        return max(column for _, column in candidates)
    return None


def _is_numeric_cell(value) -> bool:
    """Return ``True`` when one workbook cell contains a numeric value."""
    if pd.isna(value):
        return False
    if isinstance(value, (int, float, np.integer, np.floating)):
        return True
    try:
        float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return False
    return True


def _looks_like_iot_code(text: str) -> bool:
    """Heuristic for short sector codes in direct CEPALSTAT IOT headers."""
    normalized = _norm(text)
    if not normalized:
        return False
    compact = normalized.replace(" ", "")
    if len(compact) > 20:
        return False
    if not any(character.isdigit() for character in compact):
        return False
    return all(character.isalnum() or character in "._-" for character in compact)


def _detect_direct_iot_layout(frame: pd.DataFrame, total_col: int) -> dict[str, object]:
    """Infer one direct-IOT sheet layout from its multi-row headers."""
    header_anchor = next(
        (
            row
            for row in range(min(20, len(frame)))
            if any(
                token in _plain(_text(frame.iat[row, column]))
                for column in range(min(total_col + 1, frame.shape[1]))
                for token in ("demanda intermedia", "consumo intermedio")
            )
        ),
        None,
    )
    if header_anchor is None:
        raise WrongFormat("Could not detect the intermediate-demand header row in the CEPALSTAT direct IOT sheet.")

    sector_row_start = None
    sector_col_start = None
    for row in range(header_anchor + 1, min(header_anchor + 12, len(frame))):
        text_columns = [
            column
            for column in range(total_col)
            if _text(frame.iat[row, column]) and not _is_numeric_cell(frame.iat[row, column])
        ]
        if not text_columns:
            continue
        numeric_columns = [
            column
            for column in range(total_col)
            if _is_numeric_cell(frame.iat[row, column]) and column > max(text_columns)
        ]
        if len(numeric_columns) < 2:
            continue
        sector_row_start = row
        sector_col_start = min(numeric_columns)
        break
    if sector_row_start is None or sector_col_start is None:
        raise WrongFormat("Could not detect sector rows in the CEPALSTAT direct IOT sheet.")

    candidate_header_rows = list(range(header_anchor, sector_row_start))
    code_row = max(
        candidate_header_rows,
        key=lambda row: sum(
            1 for column in range(sector_col_start, total_col) if _looks_like_iot_code(_text(frame.iat[row, column]))
        ),
    )
    left_columns = [column for column in range(sector_col_start) if _text(frame.iat[sector_row_start, column])]
    if not left_columns:
        raise WrongFormat("Could not detect the identifier columns in the CEPALSTAT direct IOT sheet.")

    code_col = next(
        (column for column in left_columns if _looks_like_iot_code(_text(frame.iat[sector_row_start, column]))),
        left_columns[0],
    )
    label_candidates = [column for column in left_columns if column != code_col]
    label_col = label_candidates[-1] if label_candidates else code_col

    output_col = next(
        (
            column
            for column in range(total_col + 1, frame.shape[1])
            if "produccion" in _plain(" | ".join(_text(frame.iat[row, column]) for row in candidate_header_rows))
        ),
        None,
    )
    regime_split = any(
        "regimen" in _plain(_text(frame.iat[max(sector_row_start - 1, 0), column]))
        for column in range(sector_col_start, min(total_col, frame.shape[1]))
    )

    return {
        "sector_col_start": sector_col_start,
        "sector_row_start": sector_row_start,
        "code_col": code_col,
        "label_col": label_col,
        "header_rows": tuple(candidate_header_rows),
        "code_row": code_row,
        "output_col": output_col,
        "regime_split": regime_split,
    }


def _build_direct_iot_row_groups(
    frame: pd.DataFrame,
    *,
    sector_row_start: int,
    sector_col_start: int,
    code_col: int,
    label_col: int,
    total_col: int,
) -> list[list[int]]:
    """Group one direct-IOT row block into sectors, collapsing sub-rows when needed."""
    groups: list[list[int]] = []
    current: list[int] = []
    for row in range(sector_row_start, len(frame)):
        code = _norm(frame.iat[row, code_col] if code_col < frame.shape[1] else np.nan)
        label = _text(frame.iat[row, label_col] if label_col < frame.shape[1] else np.nan)
        left_cells = [
            _text(frame.iat[row, column])
            for column in range(min(sector_col_start, frame.shape[1]))
            if _text(frame.iat[row, column])
        ]
        left_has_text = bool(left_cells)
        numeric_in_sector = any(_is_numeric_cell(frame.iat[row, column]) for column in range(sector_col_start, min(total_col, frame.shape[1])))
        if _map_iot_factor_label(code, f"{code} | {label}") is not None:
            if current:
                groups.append(current)
            break

        if code:
            if current:
                groups.append(current)
            current = [row]
            continue
        if current and numeric_in_sector and any("regimen" in _plain(cell) for cell in left_cells):
            current.append(row)
            continue
        if current:
            groups.append(current)
            current = []
        if not left_has_text and not numeric_in_sector:
            break
    if current:
        groups.append(current)
    return groups


def _build_direct_iot_column_groups(
    frame: pd.DataFrame,
    *,
    code_row: int,
    sector_col_start: int,
    total_col: int,
) -> list[list[int]]:
    """Group one direct-IOT column block into sectors, collapsing sub-columns when needed."""
    code_positions = [
        column
        for column in range(sector_col_start, total_col)
        if _text(frame.iat[code_row, column])
    ]
    if not code_positions:
        return [[column] for column in range(sector_col_start, total_col)]

    groups: list[list[int]] = []
    for index, start in enumerate(code_positions):
        end = code_positions[index + 1] if index + 1 < len(code_positions) else total_col
        groups.append(list(range(start, end)))
    return groups


def _zero_frame(index: pd.Index, columns: pd.Index) -> pd.DataFrame:
    """Build one float zero dataframe."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns, dtype=float)


def _numeric_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert one mixed-type dataframe slice to float, filling missing values with zero."""
    return frame.apply(pd.to_numeric, errors="coerce").fillna(0.0).astype(float)


def _numeric_series(series: pd.Series) -> pd.Series:
    """Convert one mixed-type series slice to float, filling missing values with zero."""
    return pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)


_STANDARD_FINAL_LABELS = (
    "Households",
    "NPISH",
    "Government",
    "Gross fixed capital formation",
    "Changes in inventories",
    "Valuables",
    "Exports",
)


def _make_axis(country: str, key: str, labels: list[str]) -> pd.MultiIndex:
    """Build one standard three-level MARIO axis."""
    return pd.MultiIndex.from_arrays(
        [
            [country] * len(labels),
            [_MASTER_INDEX[key]] * len(labels),
            labels,
        ]
    )


def _standard_final_axis(country: str) -> pd.MultiIndex:
    """Build the standard final-demand axis used by CEPALSTAT parsers."""
    return _make_axis(country, "n", list(_STANDARD_FINAL_LABELS))


def _initialize_standard_yc(commodity_axis: pd.MultiIndex, final_axis: pd.MultiIndex) -> pd.DataFrame:
    """Create one empty final-demand dataframe with the standard CEPALSTAT column order."""
    return _zero_frame(commodity_axis, final_axis)


def _finalize_cepalstat_sut_state(
    layout: CEPALSTATLayout,
    *,
    activity_labels: list[str],
    product_codes: list[str],
    factor_labels: list[str],
    matrices: dict[str, dict[str, pd.DataFrame]],
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    CEPALSTATLayout,
]:
    """Build indexes and units for one already assembled CEPALSTAT SUT state."""
    satellite_axis = pd.Index([CEPALSTAT_SATELLITE_PLACEHOLDER], name=None)
    indexes = {
        "r": {"main": [layout.country]},
        "a": {"main": activity_labels},
        "c": {"main": product_codes},
        "f": {"main": factor_labels},
        "k": {"main": list(satellite_axis)},
        "n": {"main": list(_STANDARD_FINAL_LABELS)},
        "s": {"main": activity_labels + product_codes},
    }
    units = {
        _MASTER_INDEX["a"]: pd.DataFrame(
            {"unit": [CEPALSTAT_MONETARY_UNIT] * len(activity_labels)},
            index=pd.Index(activity_labels, name=None),
        ),
        _MASTER_INDEX["c"]: pd.DataFrame(
            {"unit": [CEPALSTAT_MONETARY_UNIT] * len(product_codes)},
            index=pd.Index(product_codes, name=None),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [CEPALSTAT_MONETARY_UNIT] * len(factor_labels)},
            index=pd.Index(factor_labels, name=None),
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": [CEPALSTAT_SATELLITE_UNIT]},
            index=satellite_axis,
        ),
    }

    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: CEPALSTAT SUT parsed with "
            f"{len(activity_labels)} activities, {len(product_codes)} commodities and "
            f"{len(_STANDARD_FINAL_LABELS)} final-demand categories."
        ),
        "info",
    )
    return matrices, indexes, units, layout


def _parse_integrated_sut_layout(layout: CEPALSTATLayout):
    """Parse the integrated paired offer/use workbook family."""
    offer = _read_cepalstat_sheet(layout, layout.sheet_names[0])
    use = _read_cepalstat_sheet(layout, layout.sheet_names[1])

    try:
        offer_header_row = _find_header_row(
            offer,
            ("total oferta a precios comprador", "margenes de comercio"),
        )
    except WrongFormat:
        offer_header_row = _find_header_row(
            offer,
            ("margenes de comercio", "margenes de transporte"),
        )
    offer_code_row = offer_header_row + 1
    offer_label_row = offer_header_row + 2
    offer_total_col = _find_col(offer, offer_code_row, "Total", start=10)
    offer_activity_cols = [column for column in range(10, offer_total_col) if _norm(offer.iat[offer_code_row, column])]

    try:
        use_header_row = _find_header_row(
            use,
            ("total oferta a precios comprador", "consumo intermedio"),
        )
    except WrongFormat:
        use_header_row = _find_header_row(
            use,
            ("hogares", "gobierno"),
        )
    current_row_activity_labels = sum(1 for column in range(5, min(40, use.shape[1])) if _text(use.iat[use_header_row, column]))
    use_activity_row = use_header_row if current_row_activity_labels > 1 else use_header_row + 1
    use_header_rows = tuple(
        row for row in (use_header_row, use_activity_row, use_activity_row + 1, use_activity_row + 2) if row < len(use)
    )
    stop_markers = {
        "total",
        "a precios de comprador",
        "a precios basicos",
        "impuestos excepto iva",
    }
    total_intermediate_col = None
    for column in range(5, use.shape[1]):
        if _plain(_text(use.iat[use_activity_row, column])) in stop_markers:
            total_intermediate_col = column
            break
    if total_intermediate_col is None:
        raise WrongFormat("Could not detect the end of the activity block in the CEPALSTAT use sheet.")
    if current_row_activity_labels > 1:
        use_activity_cols = [column for column in range(5, total_intermediate_col) if _text(use.iat[use_activity_row, column])]
    else:
        use_activity_cols = list(range(5, total_intermediate_col))

    activity_labels = [
        _text(offer.iat[offer_label_row, column]) or _norm(offer.iat[offer_code_row, column])
        for column in offer_activity_cols
    ]
    use_activity_labels = [_strip_activity_code(_text(use.iat[use_activity_row, column])) for column in use_activity_cols]
    if any(use_activity_labels):
        if activity_labels != use_activity_labels:
            raise WrongFormat("The CEPALSTAT offer/use sheets expose different activity axes.")
    elif len(activity_labels) != len(use_activity_cols):
        raise WrongFormat("The CEPALSTAT offer/use sheets expose different activity-axis lengths.")

    product_rows = _find_product_rows(offer, start_row=offer_label_row + 2)
    use_product_rows = _find_product_rows(use, start_row=use_activity_row + 3)
    offer_product_map = {_norm(offer.iat[row, 0]): row for row in product_rows}
    use_product_map = {_norm(use.iat[row, 0]): row for row in use_product_rows}
    product_codes = list(offer_product_map)
    use_product_codes = list(use_product_map)
    if product_codes != use_product_codes:
        common_products = [code for code in product_codes if code in use_product_map]
        if not common_products or set(common_products) != set(offer_product_map).intersection(use_product_map):
            raise WrongFormat("The CEPALSTAT offer/use sheets expose incompatible product axes.")
        skipped_offer = [code for code in product_codes if code not in use_product_map]
        skipped_use = [code for code in use_product_codes if code not in offer_product_map]
        if skipped_offer or skipped_use:
            log_time(
                logger,
                (
                    "Parser: CEPALSTAT SUT offer/use product axes differ; parsing the common product set only. "
                    f"offer_only={skipped_offer}, use_only={skipped_use}"
                ),
                "warning",
            )
        product_codes = common_products
        product_rows = [offer_product_map[code] for code in product_codes]
        use_product_rows = [use_product_map[code] for code in product_codes]

    activity_axis = _make_axis(layout.country, "a", activity_labels)
    commodity_axis = _make_axis(layout.country, "c", product_codes)
    final_axis = _standard_final_axis(layout.country)

    supply = _numeric_frame(offer.loc[product_rows, offer_activity_cols])
    supply.index = commodity_axis
    supply.columns = activity_axis
    S = supply.T

    U = _numeric_frame(use.loc[use_product_rows, use_activity_cols])
    U.index = commodity_axis
    U.columns = activity_axis

    household_col = _find_price_column_within_group(
        use,
        "Hogares",
        header_rows=use_header_rows,
        start=max(use_activity_cols) + 1,
    )
    npish_col = _find_price_column_within_group(
        use,
        ("Instituciones sin fines de lucro que sirven a los hogares", "ISFLH1"),
        header_rows=use_header_rows,
        start=household_col + 1,
    )
    government_col = _find_price_column_within_group(
        use,
        "Gobierno",
        header_rows=use_header_rows,
        start=npish_col + 1,
    )
    gfcf_col = _find_price_column_within_group(
        use,
        "Formación bruta de capital fijo",
        header_rows=use_header_rows,
        start=government_col + 1,
    )
    inventory_col = _find_price_column_within_group(
        use,
        "Variación de existencias",
        header_rows=use_header_rows,
        start=gfcf_col + 1,
    )
    valuables_col = _find_price_column_within_group(
        use,
        "Adquisición menos disposición de objetos valiosos",
        header_rows=use_header_rows,
        start=inventory_col + 1,
    )
    export_col = _find_export_total_column(use, header_rows=use_header_rows)

    Yc = _initialize_standard_yc(commodity_axis, final_axis)
    mapped_columns = {
        "Households": household_col,
        "NPISH": npish_col,
        "Government": government_col,
        "Gross fixed capital formation": gfcf_col,
        "Changes in inventories": inventory_col,
        "Valuables": valuables_col,
        "Exports": export_col,
    }
    for label, column in mapped_columns.items():
        Yc.loc[:, (layout.country, _MASTER_INDEX["n"], label)] = _numeric_series(use.loc[use_product_rows, column]).to_numpy()

    Ya = _zero_frame(activity_axis, final_axis)

    vc_columns = {
        "Trade margins": _find_col(offer, offer_header_row, "Márgenes de comercio"),
        "Transport margins": _find_col(offer, offer_header_row, "Márgenes de transporte"),
        "Import duties": _find_col(offer, offer_header_row, "Impuestos y derechos a las importaciones"),
        "Non-deductible VAT": _find_col(offer, offer_header_row, "IVA no deducible"),
        "Other product taxes": _find_col(
            offer,
            offer_header_row,
            "Impuestos a los productos (excepto impuestos a importaciones e IVA no deducible)",
        ),
        "Product subsidies": _find_col(offer, offer_header_row, "Subvenciones a los productos"),
        "CIF / FOB adjustment on imports": _find_col(offer, offer_code_row, "Ajustes  CIF/FOB sobre importaciones", start=70),
        "Imports of goods": _find_col(offer, offer_code_row, "Bienes", start=70),
        "Imports of services": _find_col(offer, offer_code_row, "Servicios", start=70),
    }
    va_rows = {
        "Compensation of employees": _find_row_by_pattern(use, "remuneración de los asalariados"),
        "Other taxes on production": _find_row_by_pattern(use, "otros impuestos sobre la producción"),
        "Other subsidies on production": _find_row_by_pattern(use, "otras subvenciones a la producción"),
        "Mixed income": _find_row_by_pattern(use, "ingreso mixto"),
        "Gross operating surplus": _find_row_by_pattern(use, "excedente de explotación bruto"),
    }
    factor_labels = list(dict.fromkeys(list(va_rows) + list(vc_columns)))
    factor_axis = pd.Index(factor_labels, name=None)

    Va = _zero_frame(factor_axis, activity_axis)
    for label, row in va_rows.items():
        Va.loc[label, :] = _numeric_series(use.loc[row, use_activity_cols]).to_numpy()

    Vc = _zero_frame(factor_axis, commodity_axis)
    for label, column in vc_columns.items():
        Vc.loc[label, :] = _numeric_series(offer.loc[product_rows, column]).to_numpy()

    satellite_axis = pd.Index([CEPALSTAT_SATELLITE_PLACEHOLDER], name=None)
    Ea = _zero_frame(satellite_axis, activity_axis)
    Ec = _zero_frame(satellite_axis, commodity_axis)
    EY = _zero_frame(satellite_axis, final_axis)

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
    return _finalize_cepalstat_sut_state(
        layout,
        activity_labels=activity_labels,
        product_codes=product_codes,
        factor_labels=factor_labels,
        matrices=matrices,
    )


def _parse_arg_sut_layout(layout: CEPALSTATLayout):
    """Parse the Argentina two-sheet SUT family."""
    offer = _read_cepalstat_sheet(layout, layout.sheet_names[0])
    use = _read_cepalstat_sheet(layout, layout.sheet_names[1])

    opb_col = _find_col(offer, 4, "OPB", start=2)
    activity_cols = list(range(2, opb_col))
    activity_labels = [_text(offer.iat[3, column]) or _text(offer.iat[4, column]) for column in activity_cols]

    product_rows = []
    for row in range(5, len(offer)):
        code = _norm(offer.iat[row, 1] if offer.shape[1] > 1 else np.nan)
        label = _plain(_text(offer.iat[row, 0] if offer.shape[1] > 0 else np.nan))
        if label in {"total", "totales"}:
            break
        if code:
            product_rows.append(row)
    if not product_rows:
        raise WrongFormat("Could not detect product rows in the CEPALSTAT Argentina SUT offer sheet.")

    use_product_rows = []
    for row in range(5, len(use)):
        code = _norm(use.iat[row, 1] if use.shape[1] > 1 else np.nan)
        label = _plain(_text(use.iat[row, 0] if use.shape[1] > 0 else np.nan))
        if label in {"total", "totales"}:
            break
        if code:
            use_product_rows.append(row)
    if not use_product_rows:
        raise WrongFormat("Could not detect product rows in the CEPALSTAT Argentina SUT use sheet.")

    offer_product_map = {_norm(offer.iat[row, 1]): row for row in product_rows}
    use_product_map = {_norm(use.iat[row, 1]): row for row in use_product_rows}
    product_codes = [code for code in offer_product_map if code in use_product_map]
    if not product_codes:
        raise WrongFormat("The CEPALSTAT Argentina SUT offer/use workbooks do not share a common product axis.")

    activity_axis = _make_axis(layout.country, "a", activity_labels)
    commodity_axis = _make_axis(layout.country, "c", product_codes)
    final_axis = _standard_final_axis(layout.country)

    S = _numeric_frame(offer.loc[[offer_product_map[code] for code in product_codes], activity_cols]).T
    S.index = activity_axis
    S.columns = commodity_axis

    U = _numeric_frame(use.loc[[use_product_map[code] for code in product_codes], activity_cols])
    U.index = commodity_axis
    U.columns = activity_axis

    col_map = { _plain(_text(use.iat[4, column])): column for column in range(use.shape[1]) if _text(use.iat[4, column]) }
    Yc = _initialize_standard_yc(commodity_axis, final_axis)
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Households")] = _numeric_series(
        use.loc[[use_product_map[code] for code in product_codes], col_map["ch"]]
    ).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Government")] = _numeric_series(
        use.loc[[use_product_map[code] for code in product_codes], col_map["cp"]]
    ).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Gross fixed capital formation")] = _numeric_series(
        use.loc[[use_product_map[code] for code in product_codes], col_map["fbc fijo"]]
    ).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Valuables")] = _numeric_series(
        use.loc[[use_product_map[code] for code in product_codes], col_map["ov"]]
    ).to_numpy()
    inventories = (
        _numeric_series(use.loc[[use_product_map[code] for code in product_codes], col_map["productos terminados"]]).to_numpy()
        + _numeric_series(use.loc[[use_product_map[code] for code in product_codes], col_map["trabajos en curso"]]).to_numpy()
    )
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Changes in inventories")] = inventories
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Exports")] = _numeric_series(
        use.loc[[use_product_map[code] for code in product_codes], col_map["ex"]]
    ).to_numpy()
    Ya = _zero_frame(activity_axis, final_axis)

    detailed_factor_rows = {
        "Compensation of employees": "remuneraciones",
        "Other taxes on production": "impuestos netos sobre la producción",
        "Gross operating surplus and mixed income": "excedente bruto de explotación",
    }
    fallback_value_added_row = next(
        (
            idx
            for idx in range(len(use))
            if "valor agregado bruto pb" in _plain(_text(use.iat[idx, 0] if use.shape[1] > 0 else np.nan))
        ),
        None,
    )
    explicit_factor_rows: dict[str, int] = {}
    for label, marker in detailed_factor_rows.items():
        row = next(
            (
                idx
                for idx in range(len(use))
                if marker in _plain(_text(use.iat[idx, 0] if use.shape[1] > 0 else np.nan))
                or marker in _plain(_text(use.iat[idx, 1] if use.shape[1] > 1 else np.nan))
            ),
            None,
        )
        if row is not None:
            explicit_factor_rows[label] = row

    if explicit_factor_rows:
        factor_labels = list(explicit_factor_rows)
    elif fallback_value_added_row is not None:
        log_time(
            logger,
            (
                "Parser: CEPALSTAT Argentina SUT workbook does not expose disaggregated value-added rows. "
                "Using the aggregate 'Valor Agregado Bruto pb' row."
            ),
            "warning",
        )
        factor_labels = ["Value added at basic prices"]
        explicit_factor_rows = {"Value added at basic prices": fallback_value_added_row}
    else:
        raise WrongFormat(
            "Could not find either disaggregated value-added rows or the aggregate "
            "'Valor Agregado Bruto pb' row in the CEPALSTAT Argentina SUT workbook."
        )

    factor_labels = factor_labels + [
        "Imports",
        "CIF / FOB adjustment on imports",
        "Import duties",
        "Other product taxes",
        "Trade margins",
        "Non-deductible VAT",
        "Currency-exchange service commissions",
    ]
    factor_axis = pd.Index(factor_labels, name=None)
    Va = _zero_frame(factor_axis, activity_axis)
    for label, row in explicit_factor_rows.items():
        Va.loc[label, :] = _numeric_series(use.loc[row, activity_cols]).to_numpy()

    offer_tail = { _plain(_text(offer.iat[4, column])): column for column in range(offer.shape[1]) if _text(offer.iat[4, column]) }
    Vc = _zero_frame(factor_axis, commodity_axis)
    vc_map = {
        "Imports": "impo",
        "CIF / FOB adjustment on imports": "ajuste cif/fob",
        "Import duties": "di",
        "Other product taxes": "ip",
        "Trade margins": "mg d",
        "Non-deductible VAT": "iva",
        "Currency-exchange service commissions": "cscd",
    }
    offer_rows = [offer_product_map[code] for code in product_codes]
    for label, marker in vc_map.items():
        column = offer_tail.get(marker)
        if column is None:
            raise WrongFormat(f"Could not find required commodity-side column '{label}' in the CEPALSTAT Argentina SUT workbook.")
        Vc.loc[label, :] = _numeric_series(offer.loc[offer_rows, column]).to_numpy()

    satellite_axis = pd.Index([CEPALSTAT_SATELLITE_PLACEHOLDER], name=None)
    Ea = _zero_frame(satellite_axis, activity_axis)
    Ec = _zero_frame(satellite_axis, commodity_axis)
    EY = _zero_frame(satellite_axis, final_axis)
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
    return _finalize_cepalstat_sut_state(
        layout,
        activity_labels=activity_labels,
        product_codes=product_codes,
        factor_labels=factor_labels,
        matrices=matrices,
    )


def _parse_bra_sut_layout(layout: CEPALSTATLayout):
    """Parse the Brazil split-workbook SUT family."""
    oferta = _read_cepalstat_sheet(layout, layout.sheet_names[0])
    producao = _read_cepalstat_sheet(layout, layout.sheet_names[1])
    ci = _read_cepalstat_auxiliary_sheet(layout, 0, layout.sheet_names[2])
    demanda = _read_cepalstat_auxiliary_sheet(layout, 0, layout.sheet_names[3])
    va = _read_cepalstat_auxiliary_sheet(layout, 0, layout.sheet_names[4])
    importacao = _read_cepalstat_sheet(layout, layout.sheet_names[5])

    activity_cols = list(range(2, producao.shape[1] - 1))
    activity_labels = [_text(producao.iat[3, column]) for column in activity_cols]

    product_rows = [row for row in range(5, len(producao)) if _norm(producao.iat[row, 0]) and _plain(_text(producao.iat[row, 0])) != "total"]
    product_codes = [_norm(producao.iat[row, 0]) for row in product_rows]
    commodity_axis = _make_axis(layout.country, "c", product_codes)
    activity_axis = _make_axis(layout.country, "a", activity_labels)
    final_axis = _standard_final_axis(layout.country)

    S = _numeric_frame(producao.loc[product_rows, activity_cols]).T
    S.index = activity_axis
    S.columns = commodity_axis

    U = _numeric_frame(ci.loc[product_rows, activity_cols])
    U.index = commodity_axis
    U.columns = activity_axis

    Yc = _initialize_standard_yc(commodity_axis, final_axis)
    demand_rows = [row for row in range(5, len(demanda)) if _norm(demanda.iat[row, 0]) and _plain(_text(demanda.iat[row, 0])) != "total"]
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Government")] = _numeric_series(demanda.loc[demand_rows, 4]).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "NPISH")] = _numeric_series(demanda.loc[demand_rows, 5]).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Households")] = _numeric_series(demanda.loc[demand_rows, 6]).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Gross fixed capital formation")] = _numeric_series(demanda.loc[demand_rows, 7]).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Changes in inventories")] = _numeric_series(demanda.loc[demand_rows, 8]).to_numpy()
    exports = _numeric_series(demanda.loc[demand_rows, 2]).to_numpy() + _numeric_series(demanda.loc[demand_rows, 3]).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Exports")] = exports
    Ya = _zero_frame(activity_axis, final_axis)

    factor_labels = [
        "Compensation of employees",
        "Gross operating surplus and mixed income",
        "Other taxes on production",
        "Imports of goods",
        "Imports of services",
        "CIF / FOB adjustment on imports",
        "Trade margins",
        "Transport margins",
        "Import tax",
        "IPI",
        "ICMS",
        "Other taxes less subsidies",
    ]
    factor_axis = pd.Index(factor_labels, name=None)
    Va = _zero_frame(factor_axis, activity_axis)
    Va.loc["Compensation of employees", :] = _numeric_series(va.loc[6, activity_cols]).to_numpy()
    Va.loc["Gross operating surplus and mixed income", :] = _numeric_series(va.loc[12, activity_cols]).to_numpy()
    Va.loc["Other taxes on production", :] = _numeric_series(va.loc[15, activity_cols]).to_numpy()

    Vc = _zero_frame(factor_axis, commodity_axis)
    oferta_rows = [row for row in range(5, len(oferta)) if _norm(oferta.iat[row, 0]) and _plain(_text(oferta.iat[row, 0])) != "total"]
    if importacao.shape[1] == 4:
        import_rows = oferta_rows
        cif_col, goods_col, services_col = 1, 2, 3
    else:
        import_rows = [row for row in range(5, len(importacao)) if _norm(importacao.iat[row, 0]) and _plain(_text(importacao.iat[row, 0])) != "total"]
        cif_col, goods_col, services_col = 2, 3, 4
    Vc.loc["Trade margins", :] = _numeric_series(oferta.loc[oferta_rows, 3]).to_numpy()
    Vc.loc["Transport margins", :] = _numeric_series(oferta.loc[oferta_rows, 4]).to_numpy()
    Vc.loc["Import tax", :] = _numeric_series(oferta.loc[oferta_rows, 5]).to_numpy()
    Vc.loc["IPI", :] = _numeric_series(oferta.loc[oferta_rows, 6]).to_numpy()
    Vc.loc["ICMS", :] = _numeric_series(oferta.loc[oferta_rows, 7]).to_numpy()
    Vc.loc["Other taxes less subsidies", :] = _numeric_series(oferta.loc[oferta_rows, 8]).to_numpy()
    Vc.loc["CIF / FOB adjustment on imports", :] = _numeric_series(importacao.loc[import_rows, cif_col]).to_numpy()
    Vc.loc["Imports of goods", :] = _numeric_series(importacao.loc[import_rows, goods_col]).to_numpy()
    Vc.loc["Imports of services", :] = _numeric_series(importacao.loc[import_rows, services_col]).to_numpy()

    satellite_axis = pd.Index([CEPALSTAT_SATELLITE_PLACEHOLDER], name=None)
    Ea = _zero_frame(satellite_axis, activity_axis)
    Ec = _zero_frame(satellite_axis, commodity_axis)
    EY = _zero_frame(satellite_axis, final_axis)
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
    return _finalize_cepalstat_sut_state(
        layout,
        activity_labels=activity_labels,
        product_codes=product_codes,
        factor_labels=factor_labels,
        matrices=matrices,
    )


def _parse_chi_sut_layout(layout: CEPALSTATLayout):
    """Parse the Chile multi-cuadro SUT family."""
    production = _read_cepalstat_sheet(layout, layout.sheet_names[0])
    intermediate = _read_cepalstat_sheet(layout, layout.sheet_names[1])
    final_use = _read_cepalstat_sheet(layout, layout.sheet_names[2])
    value_added = _read_cepalstat_sheet(layout, layout.sheet_names[3])
    offer_total = _read_cepalstat_sheet(layout, layout.sheet_names[4])

    activity_cols = list(range(2, production.shape[1]))
    activity_labels = [_norm(production.iat[10, column]) for column in activity_cols if _norm(production.iat[10, column])]
    activity_cols = activity_cols[: len(activity_labels)]
    activity_axis = _make_axis(layout.country, "a", activity_labels)

    product_rows = [row for row in range(13, len(production)) if _norm(production.iat[row, 1]) and _plain(_text(production.iat[row, 1])) != "total"]
    product_codes = [_norm(production.iat[row, 1]) for row in product_rows]
    commodity_axis = _make_axis(layout.country, "c", product_codes)
    final_axis = _standard_final_axis(layout.country)

    S = _numeric_frame(production.loc[product_rows, activity_cols]).T
    S.index = activity_axis
    S.columns = commodity_axis

    U = _numeric_frame(intermediate.loc[product_rows, activity_cols])
    U.index = commodity_axis
    U.columns = activity_axis

    Yc = _initialize_standard_yc(commodity_axis, final_axis)
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Households")] = _numeric_series(final_use.loc[product_rows, 4]).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "NPISH")] = _numeric_series(final_use.loc[product_rows, 5]).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Government")] = _numeric_series(final_use.loc[product_rows, 6]).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Gross fixed capital formation")] = _numeric_series(final_use.loc[product_rows, 7]).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Changes in inventories")] = _numeric_series(final_use.loc[product_rows, 8]).to_numpy()
    Yc.loc[:, (layout.country, _MASTER_INDEX["n"], "Exports")] = _numeric_series(final_use.loc[product_rows, 9]).to_numpy()
    Ya = _zero_frame(activity_axis, final_axis)

    factor_labels = [
        "Compensation of employees",
        "Gross operating surplus and mixed income",
        "Other taxes on production",
        "Imports at CIF prices",
        "Indirect taxes on goods and services",
        "Import duties",
        "Trade margins",
        "VAT",
    ]
    factor_axis = pd.Index(factor_labels, name=None)
    Va = _zero_frame(factor_axis, activity_axis)
    va_marker_rows = {
        "Compensation of employees": "remuneraciones",
        "Gross operating surplus and mixed income": "excedente bruto de explotacion",
        "Other taxes on production": "impuestos netos",
    }
    for label, marker in va_marker_rows.items():
        row = next(
            (
                idx
                for idx in range(len(value_added))
                if marker in _plain(_text(value_added.iat[idx, 1] if value_added.shape[1] > 1 else np.nan))
            ),
            None,
        )
        if row is None:
            raise WrongFormat(f"Could not find required value-added row '{label}' in the CEPALSTAT Chile SUT workbook.")
        Va.loc[label, :] = _numeric_series(value_added.loc[row, activity_cols]).to_numpy()

    Vc = _zero_frame(factor_axis, commodity_axis)
    offer_rows = [row for row in range(14, len(offer_total)) if _norm(offer_total.iat[row, 1]) and _plain(_text(offer_total.iat[row, 1])) != "total"]
    Vc.loc["Imports at CIF prices", :] = _numeric_series(offer_total.loc[offer_rows, 3]).to_numpy()
    Vc.loc["Indirect taxes on goods and services", :] = _numeric_series(offer_total.loc[offer_rows, 5]).to_numpy()
    Vc.loc["Import duties", :] = _numeric_series(offer_total.loc[offer_rows, 6]).to_numpy()
    Vc.loc["Trade margins", :] = _numeric_series(offer_total.loc[offer_rows, 8]).to_numpy()
    Vc.loc["VAT", :] = _numeric_series(offer_total.loc[offer_rows, 9]).to_numpy()

    satellite_axis = pd.Index([CEPALSTAT_SATELLITE_PLACEHOLDER], name=None)
    Ea = _zero_frame(satellite_axis, activity_axis)
    Ec = _zero_frame(satellite_axis, commodity_axis)
    EY = _zero_frame(satellite_axis, final_axis)
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
    return _finalize_cepalstat_sut_state(
        layout,
        activity_labels=activity_labels,
        product_codes=product_codes,
        factor_labels=factor_labels,
        matrices=matrices,
    )


def parse_cepalstat_sut(
    path: str | Path,
    *,
    year: int | None = None,
    country: str | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    CEPALSTATLayout,
]:
    """Parse one supported CEPALSTAT SUT bundle."""
    layout = detect_cepalstat_sut_layout(path, year=year, country=country)
    if layout.family in {"integrated_sut_cuadros", "col_indexed_sut"}:
        return _parse_integrated_sut_layout(layout)
    if layout.family == "arg_two_sheet_sut":
        return _parse_arg_sut_layout(layout)
    if layout.family == "bra_split_sut":
        return _parse_bra_sut_layout(layout)
    if layout.family == "chi_multicuadro_sut":
        return _parse_chi_sut_layout(layout)
    raise NotImplementable(f"Unsupported CEPALSTAT SUT family '{layout.family}'.")


def parse_cepalstat_iot(
    path: str | Path,
    *,
    year: int | None = None,
    country: str | None = None,
    iot_mode: str = "pxp",
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    CEPALSTATLayout,
]:
    """Parse one supported CEPALSTAT IOT bundle."""

    def _map_iot_final_label(header_text: str) -> str | None:
        normalized = _plain(header_text)
        if not normalized:
            return None
        if "export" in normalized:
            return "Exports"
        if "instituciones sin fines de lucro" in normalized or "isfl" in normalized or "ipsfl" in normalized or "npish" in normalized:
            return "NPISH"
        if "hogar" in normalized or "famil" in normalized:
            return "Households"
        if "gobierno" in normalized or "government" in normalized:
            return "Government"
        if "capital fijo" in normalized or "formacion bruta de capital" in normalized:
            return "Gross fixed capital formation"
        if "existenc" in normalized or "stock" in normalized:
            return "Changes in inventories"
        if "valios" in normalized:
            return "Valuables"
        return None

    def _map_iot_factor_label(code: str, label: str) -> str | None:
        normalized_code = _plain(code)
        normalized_label = _plain(label)
        if normalized_code == "d.1" or "remuner" in normalized_label or "asalariad" in normalized_label:
            return "Compensation of employees"
        if normalized_code == "d.29" or "otros impuestos sobre la produccion" in normalized_label:
            return "Other taxes on production"
        if normalized_code == "d.39" or ("subvencion" in normalized_label and "producto" not in normalized_label):
            return "Other subsidies on production"
        if normalized_code == "b.2b" or ("excedente" in normalized_label and "valor agregado" not in normalized_label):
            return "Gross operating surplus"
        if normalized_code == "b.3b" or "ingreso mixto" in normalized_label:
            return "Mixed income"
        if (
            "impuestos netos sobre los productos" in normalized_label
            or "impuestos sobre bienes y servicios netos" in normalized_label
            or "impuestos sobre productos" in normalized_label
        ):
            return "Taxes less subsidies on products"
        if (
            "impuestos sobre la produccion y las importaciones" in normalized_label
            or "impuestos menos subvenciones sobre la produccion e importaciones" in normalized_label
        ):
            return "Other taxes on production and imports"
        if "valor agregado bruto" in normalized_label:
            return "Value added at basic prices"
        return None

    def _collect_fd_columns(frame: pd.DataFrame, header_rows: tuple[int, ...], start_col: int) -> dict[str, list[int]]:
        columns: dict[str, list[int]] = {label: [] for label in _STANDARD_FINAL_LABELS}
        for column in range(start_col, frame.shape[1]):
            header_text = " | ".join(_text(frame.iat[row, column]) for row in header_rows if row < len(frame))
            label = _map_iot_final_label(header_text)
            if label is not None:
                columns[label].append(column)
        return {label: cols for label, cols in columns.items() if cols}

    def _finalize_iot_state(
        layout: CEPALSTATLayout,
        *,
        sector_codes: list[str],
        factor_labels: list[str],
        matrices: dict[str, dict[str, pd.DataFrame]],
    ):
        satellite_axis = pd.Index([CEPALSTAT_SATELLITE_PLACEHOLDER], name=None)
        indexes = {
            "r": {"main": [layout.country]},
            "s": {"main": sector_codes},
            "f": {"main": factor_labels},
            "k": {"main": list(satellite_axis)},
            "n": {"main": list(_STANDARD_FINAL_LABELS)},
        }
        units = {
            _MASTER_INDEX["s"]: pd.DataFrame(
                {"unit": [CEPALSTAT_MONETARY_UNIT] * len(sector_codes)},
                index=pd.Index(sector_codes, name=None),
            ),
            _MASTER_INDEX["f"]: pd.DataFrame(
                {"unit": [CEPALSTAT_MONETARY_UNIT] * len(factor_labels)},
                index=pd.Index(factor_labels, name=None),
            ),
            _MASTER_INDEX["k"]: pd.DataFrame(
                {"unit": [CEPALSTAT_SATELLITE_UNIT]},
                index=satellite_axis,
            ),
        }
        rename_index(matrices["baseline"])
        log_time(
            logger,
            (
                "Parser: CEPALSTAT IOT parsed with "
                f"{len(sector_codes)} sectors, {len(_STANDARD_FINAL_LABELS)} final-demand categories "
                f"and {len(factor_labels)} factor rows."
            ),
            "info",
        )
        return matrices, indexes, units, layout

    def _parse_matrix_sheet(
        layout: CEPALSTATLayout,
        frame: pd.DataFrame,
        *,
        sector_col_start: int,
        total_col: int,
        sector_row_start: int,
        code_col: int,
        label_col: int,
        header_rows: tuple[int, ...],
        sector_cols: list[int] | None = None,
        output_col: int | None = None,
        residual_factor_label: str | None = None,
        row_groups: list[list[int]] | None = None,
        column_groups: list[list[int]] | None = None,
    ):
        if column_groups is None:
            if sector_cols is None:
                sector_cols = list(range(sector_col_start, total_col))
            column_groups = [[column] for column in sector_cols]
        if row_groups is None:
            sector_rows: list[int] = []
            sector_codes: list[str] = []
            for row in range(sector_row_start, len(frame)):
                code = _norm(frame.iat[row, code_col] if code_col < frame.shape[1] else np.nan)
                if not code:
                    break
                sector_rows.append(row)
                label = _text(frame.iat[row, label_col] if label_col < frame.shape[1] else np.nan)
                sector_codes.append(label or code)
            row_groups = [[row] for row in sector_rows]
        else:
            sector_codes = []
            for group in row_groups:
                row = group[0]
                code = _norm(frame.iat[row, code_col] if code_col < frame.shape[1] else np.nan)
                label = _text(frame.iat[row, label_col] if label_col < frame.shape[1] else np.nan)
                sector_codes.append(label or code)

        if not row_groups:
            raise WrongFormat(f"Could not detect sector rows in CEPALSTAT IOT family '{layout.family}'.")

        sector_axis = _make_axis(layout.country, "s", sector_codes)
        final_axis = _standard_final_axis(layout.country)
        Z = pd.DataFrame(
            [
                [
                    _numeric_frame(frame.loc[row_group, column_group]).to_numpy().sum()
                    for column_group in column_groups
                ]
                for row_group in row_groups
            ],
            index=sector_axis,
            columns=sector_axis,
            dtype=float,
        )

        Y = _zero_frame(sector_axis, final_axis)
        fd_columns = _collect_fd_columns(frame, header_rows, total_col + 1)
        for label, columns in fd_columns.items():
            values = np.zeros(len(row_groups), dtype=float)
            for column in columns:
                values = values + np.array(
                    [_numeric_series(frame.loc[row_group, column]).to_numpy().sum() for row_group in row_groups],
                    dtype=float,
                )
            Y.loc[:, (layout.country, _MASTER_INDEX["n"], label)] = values

        factor_rows: dict[str, int] = {}
        for row in range(row_groups[-1][-1] + 1, len(frame)):
            left_cells = [
                _text(frame.iat[row, column])
                for column in range(min(sector_col_start, frame.shape[1]))
                if _text(frame.iat[row, column])
            ]
            if not left_cells:
                continue
            code = next((cell for cell in left_cells if _looks_like_iot_code(cell)), left_cells[0])
            label = " | ".join(left_cells)
            factor_label = _map_iot_factor_label(code, label)
            if factor_label is not None and factor_label not in factor_rows:
                factor_rows[factor_label] = row
        if factor_rows:
            factor_labels = list(factor_rows)
            factor_axis = pd.Index(factor_labels, name=None)
            V = pd.DataFrame(
                [
                    [
                        _numeric_series(frame.loc[row_index, column_group]).to_numpy().sum()
                        for column_group in column_groups
                    ]
                    for row_index in factor_rows.values()
                ],
                index=factor_axis,
                columns=sector_axis,
                dtype=float,
            )
        elif residual_factor_label is not None and output_col is not None:
            output = np.array(
                [_numeric_series(frame.loc[row_group, output_col]).to_numpy().sum() for row_group in row_groups],
                dtype=float,
            )
            residual = output - Z.sum(axis=0).to_numpy()
            factor_labels = [residual_factor_label]
            factor_axis = pd.Index(factor_labels, name=None)
            V = pd.DataFrame([residual], index=factor_axis, columns=sector_axis, dtype=float)
            log_time(
                logger,
                (
                    "Parser: CEPALSTAT IOT workbook does not expose explicit factor rows. "
                    f"Building aggregate '{residual_factor_label}' as output minus intermediate inputs."
                ),
                "warning",
            )
        else:
            raise WrongFormat(f"Could not detect factor rows in CEPALSTAT IOT family '{layout.family}'.")

        satellite_axis = pd.Index([CEPALSTAT_SATELLITE_PLACEHOLDER], name=None)
        E = _zero_frame(satellite_axis, sector_axis)
        EY = _zero_frame(satellite_axis, final_axis)
        matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
        return _finalize_iot_state(layout, sector_codes=sector_codes, factor_labels=factor_labels, matrices=matrices)

    layout = detect_cepalstat_iot_layout(path, year=year, country=country, iot_mode=iot_mode)
    frame = _read_cepalstat_sheet(layout, layout.sheet_names[0])

    if layout.family == "dom_direct_iot":
        total_intermediate_col = _find_total_intermediate_column(frame)
        if total_intermediate_col is None:
            raise WrongFormat("Could not detect the intermediate-demand total column in the CEPALSTAT direct IOT sheet.")
        detected = _detect_direct_iot_layout(frame, total_intermediate_col)
        row_groups = _build_direct_iot_row_groups(
            frame,
            sector_row_start=int(detected["sector_row_start"]),
            sector_col_start=int(detected["sector_col_start"]),
            code_col=int(detected["code_col"]),
            label_col=int(detected["label_col"]),
            total_col=total_intermediate_col,
        )
        column_groups = _build_direct_iot_column_groups(
            frame,
            code_row=int(detected["code_row"]),
            sector_col_start=int(detected["sector_col_start"]),
            total_col=total_intermediate_col,
        )
        return _parse_matrix_sheet(
            layout,
            frame,
            sector_col_start=int(detected["sector_col_start"]),
            total_col=total_intermediate_col,
            sector_row_start=int(detected["sector_row_start"]),
            code_col=int(detected["code_col"]),
            label_col=int(detected["label_col"]),
            header_rows=tuple(detected["header_rows"]),
            output_col=detected["output_col"],
            row_groups=row_groups,
            column_groups=column_groups,
        )

    if layout.family == "gtm_member_iot":
        return _parse_matrix_sheet(
            layout,
            frame,
            sector_col_start=3,
            total_col=155,
            sector_row_start=11,
            code_col=1,
            label_col=2,
            header_rows=(7, 8, 9),
        )

    if layout.family == "col_cuadro_iot":
        return _parse_matrix_sheet(
            layout,
            frame,
            sector_col_start=2,
            total_col=70,
            sector_row_start=13,
            code_col=0,
            label_col=1,
            header_rows=(9, 10, 11),
        )

    if layout.family == "col_legacy_iot":
        if layout.iot_mode == "axa":
            total_col = _find_col_by_pattern(frame, 8, "Total ramas de actividad", start=2)
            sector_rows = [
                row
                for row in range(10, len(frame))
                if re.fullmatch(r"\d{1,3}", _norm(frame.iat[row, 0]))
            ]
            result = _parse_matrix_sheet(
                layout,
                frame,
                sector_col_start=2,
                total_col=total_col,
                sector_row_start=sector_rows[0],
                code_col=0,
                label_col=1,
                header_rows=(8, 9),
                row_groups=[[row] for row in sector_rows],
            )
            log_time(
                logger,
                (
                    "Parser: CEPALSTAT legacy Colombia AxA workbook exposes aggregated final consumption and capital columns. "
                    "MARIO maps them to the standard final-demand axis with zeroes for unavailable splits."
                ),
                "warning",
            )
            return result

        total_col = _find_col_by_pattern(frame, 10, "Consumo intermedio total", start=2)
        sector_rows = [
            row
            for row in range(12, len(frame))
            if re.fullmatch(r"\d{1,3}", _norm(frame.iat[row, 0]))
        ]
        return _parse_matrix_sheet(
            layout,
            frame,
            sector_col_start=2,
            total_col=total_col,
            sector_row_start=sector_rows[0],
            code_col=0,
            label_col=1,
            header_rows=(10, 11),
            output_col=next(
                (
                    column
                    for column in range(total_col + 1, frame.shape[1])
                    if "produccion" in _plain(_text(frame.iat[10, column]))
                ),
                None,
            ),
            row_groups=[[row] for row in sector_rows],
        )

    if layout.family == "arg_symmetric_iot":
        total_intermediate_col = next(
            (
                column
                for column in range(frame.shape[1])
                if "demanda intermedia" in " | ".join(_text(frame.iat[row, column]) for row in (5, 6, 7)).lower()
            ),
            None,
        )
        if total_intermediate_col is None:
            raise WrongFormat("Could not detect the intermediate-demand total column in the CEPALSTAT Argentina IOT workbook.")
        return _parse_matrix_sheet(
            layout,
            frame,
            sector_col_start=2,
            total_col=total_intermediate_col,
            sector_row_start=8,
            code_col=0,
            label_col=1,
            header_rows=(5, 6),
        )

    if layout.family == "bra_demand_basic_iot":
        total_col = next(
            (
                column
                for column in range(2, frame.shape[1])
                if "total" in _plain(_text(frame.iat[3, column]))
            ),
            None,
        )
        if total_col is None:
            raise WrongFormat("Could not detect the total-intermediate column in the CEPALSTAT Brazil IOT workbook.")
        sector_cols = [column for column in range(3, total_col) if _norm(frame.iat[3, column])]
        return _parse_matrix_sheet(
            layout,
            frame,
            sector_col_start=3,
            total_col=total_col,
            sector_row_start=5,
            code_col=0,
            label_col=1,
            header_rows=(2, 3),
            sector_cols=sector_cols,
            output_col=2,
            residual_factor_label="Value added at basic prices",
        )

    if layout.family == "chi_matrix_iot":
        total_intermediate_col = next(
            (
                column
                for column in range(frame.shape[1])
                if _plain(_text(frame.iat[8, column])) == "total"
            ),
            None,
        )
        if total_intermediate_col is None:
            raise WrongFormat("Could not detect the intermediate-demand total column in the CEPALSTAT Chile IOT workbook.")
        sector_cols = [column for column in range(2, total_intermediate_col) if _norm(frame.iat[8, column])]
        return _parse_matrix_sheet(
            layout,
            frame,
            sector_col_start=2,
            total_col=total_intermediate_col,
            sector_row_start=11,
            code_col=1,
            label_col=1,
            header_rows=(7,),
            sector_cols=sector_cols,
        )

    raise NotImplementable(f"Unsupported CEPALSTAT IOT family '{layout.family}'.")
