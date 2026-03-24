"""Direct Statistics Canada parsers backed by the official WDS full-table API."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile

import numpy as np
import pandas as pd
import requests

from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    STATCAN_ACTIVITY_CODE_PREFIXES,
    STATCAN_FINAL_DEMAND_CODE_PREFIXES,
    STATCAN_IMPORT_CODE_PREFIXES,
    STATCAN_SATELLITE_PLACEHOLDER,
    STATCAN_SATELLITE_UNIT,
    STATCAN_SOURCE,
    STATCAN_TABLES,
    STATCAN_VALUATIONS,
    STATCAN_WDS_BASE_URL,
)

logger = logging.getLogger(__name__)

_CODE_PATTERN = re.compile(r"\[([^\]]+)\]\s*$")


@dataclass(frozen=True)
class StatCanLayout:
    """Resolved metadata for one Statistics Canada table pull."""

    table: str
    level: str
    year: int
    geo: str
    valuation: str
    pid: str
    title: str
    csv_url: str
    catalogue_url: str

    @property
    def dataset_name(self) -> str:
        """Return a compact default dataset name."""
        label = f"StatCan {self.table} {self.level} {self.geo} {self.year}"
        if self.table == "IOT":
            return f"{label} {self.valuation}".strip()
        return label

    @property
    def price(self) -> str:
        """Return the price system label stored in MARIO metadata."""
        if self.table == "SUT":
            return "Basic prices"
        return self.valuation

    @property
    def source(self) -> str:
        """Return the canonical StatCan source string."""
        return f"{STATCAN_SOURCE}; table {self.pid}: {self.catalogue_url}"


def _three_level_index(region: str, level_label: str, items: list[str]) -> pd.MultiIndex:
    """Build one canonical MARIO three-level axis for a single-region dataset."""
    return pd.MultiIndex.from_arrays(
        [
            [region] * len(items),
            [level_label] * len(items),
            items,
        ]
    )


def _zero_frame(index, columns) -> pd.DataFrame:
    """Return a float zero-filled dataframe for parser block construction."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def _extract_code(label: str) -> str | None:
    """Extract the trailing StatCan classification code from one label."""
    if not isinstance(label, str):
        return None
    match = _CODE_PATTERN.search(label)
    if match is None:
        return None
    return match.group(1)


def _looks_like_activity(label: str) -> bool:
    """Return True when one StatCan label behaves like an activity/sector."""
    code = _extract_code(label)
    return code is not None and code.startswith(STATCAN_ACTIVITY_CODE_PREFIXES)


def _looks_like_factor(label: str) -> bool:
    """Return True when one StatCan label behaves like a factor/value-added row."""
    if label == "Gross value-added at basic prices":
        return True
    code = _extract_code(label)
    return code is not None and code.startswith("P")


def _looks_like_final_demand(label: str) -> bool:
    """Return True when one StatCan label behaves like final demand or exports."""
    code = _extract_code(label)
    return code is not None and code.startswith(STATCAN_FINAL_DEMAND_CODE_PREFIXES)


def _looks_like_import(label: str) -> bool:
    """Return True when one StatCan label behaves like an import row/column."""
    if not isinstance(label, str):
        return False
    if "import" in label.casefold():
        return True
    code = _extract_code(label)
    return code is not None and code.startswith(STATCAN_IMPORT_CODE_PREFIXES)


def _looks_like_commodity(label: str) -> bool:
    """Return True when one StatCan product label should map to a commodity row."""
    return isinstance(label, str) and label != "Total products" and not _looks_like_factor(label)


def _compose_unit(frame: pd.DataFrame) -> str:
    """Build a compact unit label from one StatCan slice."""
    if frame.empty:
        return "value"
    first = frame.iloc[0]
    uom = str(first.get("UOM", "")).strip()
    scalar = str(first.get("SCALAR_FACTOR", "")).strip()
    if not scalar or scalar.lower() in {"nan", "units"}:
        return uom or "value"
    return f"{scalar} {uom}".strip()


def _build_sut_units(
    *,
    activity_labels: list[str],
    commodity_labels: list[str],
    factor_labels: list[str],
    unit: str,
) -> dict[str, pd.DataFrame]:
    """Build MARIO unit tables for one StatCan SUT payload."""
    return {
        _MASTER_INDEX["a"]: pd.DataFrame({"unit": [unit] * len(activity_labels)}, index=activity_labels),
        _MASTER_INDEX["c"]: pd.DataFrame({"unit": [unit] * len(commodity_labels)}, index=commodity_labels),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": [unit] * len(factor_labels)}, index=factor_labels),
        _MASTER_INDEX["k"]: pd.DataFrame({"unit": [STATCAN_SATELLITE_UNIT]}, index=[STATCAN_SATELLITE_PLACEHOLDER]),
    }


def _build_iot_units(
    *,
    sector_labels: list[str],
    factor_labels: list[str],
    unit: str,
) -> dict[str, pd.DataFrame]:
    """Build MARIO unit tables for one StatCan IOT payload."""
    return {
        _MASTER_INDEX["s"]: pd.DataFrame({"unit": [unit] * len(sector_labels)}, index=sector_labels),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": [unit] * len(factor_labels)}, index=factor_labels),
        _MASTER_INDEX["k"]: pd.DataFrame({"unit": [STATCAN_SATELLITE_UNIT]}, index=[STATCAN_SATELLITE_PLACEHOLDER]),
    }


def _resolve_spec(table: str, level: str) -> dict:
    """Resolve the official StatCan table specification for one parser request."""
    table_key = str(table).upper()
    try:
        levels = STATCAN_TABLES[table_key]
    except KeyError as exc:
        raise WrongInput(f"StatCan table should be one of {list(STATCAN_TABLES)}.") from exc
    try:
        return levels[level]
    except KeyError as exc:
        raise WrongInput(
            f"StatCan level for {table_key} should be one of {list(levels)}."
        ) from exc


def _download_statcan_csv_table(
    pid: str,
    *,
    timeout: int = 60,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, str]:
    """Download one StatCan full-table CSV payload and return it as a dataframe."""
    meta_url = f"{STATCAN_WDS_BASE_URL}/getFullTableDownloadCSV/{pid}/en"
    http = session or requests.Session()

    log_time(logger, f"Parser: requesting StatCan WDS metadata for table {pid}.", "info")
    response = http.get(meta_url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "SUCCESS" or "object" not in payload:
        raise WrongInput(f"Statistics Canada did not return a downloadable CSV for table {pid}.")

    csv_url = str(payload["object"])
    log_time(logger, f"Parser: downloading StatCan table {pid} from {csv_url}.", "info")
    with tempfile.NamedTemporaryFile(suffix=".zip") as archive_path:
        with http.get(csv_url, timeout=timeout, stream=True) as zip_response:
            zip_response.raise_for_status()
            for chunk in zip_response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    archive_path.write(chunk)
        archive_path.flush()

        with ZipFile(archive_path.name) as archive:
            csv_members = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".csv") and "metadata" not in name.casefold()
            ]
            if not csv_members:
                raise WrongInput(f"Statistics Canada ZIP payload for table {pid} contains no CSV table.")
            csv_name = csv_members[0]
            log_time(logger, f"Parser: reading StatCan CSV member {Path(csv_name).name}.", "debug")
            with archive.open(csv_name) as csv_stream:
                frame = pd.read_csv(csv_stream, low_memory=False)

    if frame.empty:
        raise WrongInput(f"Statistics Canada returned an empty CSV payload for table {pid}.")

    frame["VALUE"] = pd.to_numeric(frame["VALUE"], errors="coerce").fillna(0.0)
    return frame, csv_url


def _read_statcan_csv_table(path: str | Path) -> pd.DataFrame:
    """Read one previously downloaded StatCan CSV file."""
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    log_time(logger, f"Parser: reading local StatCan CSV {csv_path.name}.", "info")
    frame = pd.read_csv(csv_path, low_memory=False)
    if frame.empty:
        raise WrongInput(f"Statistics Canada local CSV payload is empty: {csv_path}.")
    frame["VALUE"] = pd.to_numeric(frame["VALUE"], errors="coerce").fillna(0.0)
    return frame


def _filter_statcan_slice(frame: pd.DataFrame, *, year: int, geo: str) -> pd.DataFrame:
    """Return one StatCan year/geo slice with clear validation errors."""
    available_years = sorted(pd.Series(frame["REF_DATE"]).dropna().astype(int).unique().tolist())
    if int(year) not in available_years:
        raise WrongInput(
            f"Statistics Canada year {year} is not available. Available years are {available_years}."
        )

    geos = pd.Series(frame["GEO"]).dropna().astype(str)
    geo_lookup = {value.casefold(): value for value in geos.drop_duplicates().tolist()}
    try:
        geo_value = geo_lookup[str(geo).casefold()]
    except KeyError as exc:
        available_geos = sorted(geo_lookup.values())
        raise WrongInput(
            f"Statistics Canada geography {geo!r} is not available. Available geographies are {available_geos}."
        ) from exc

    subset = frame[(frame["REF_DATE"].astype(int) == int(year)) & (frame["GEO"] == geo_value)].copy()
    if subset.empty:
        raise WrongInput(f"Statistics Canada returned no rows for {geo_value} {year}.")
    return subset


def build_statcan_sut_from_frame(
    frame: pd.DataFrame,
    *,
    year: int,
    geo: str = "Canada",
    level: str = "summary",
    csv_url: str = "",
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    StatCanLayout,
]:
    """Transform one StatCan SUT full-table frame into split-native MARIO blocks."""
    spec = _resolve_spec("SUT", level)
    subset = _filter_statcan_slice(frame, year=year, geo=geo)

    supply = subset[
        (subset["Supply and use"] == "Supply")
        & (subset["Valuation"] == STATCAN_VALUATIONS["basic"])
    ].copy()
    use_basic = subset[
        (subset["Supply and use"] == "Use")
        & (subset["Valuation"] == STATCAN_VALUATIONS["basic"])
    ].copy()
    use_purchaser = subset[
        (subset["Supply and use"] == "Use")
        & (subset["Valuation"] == STATCAN_VALUATIONS["purchaser"])
    ].copy()

    if supply.empty:
        raise WrongInput("Statistics Canada SUT payload contains no supply rows at basic prices.")
    if use_basic.empty:
        raise WrongInput("Statistics Canada SUT payload contains no use rows at basic prices.")

    activity_labels = [value for value in supply["Industry"].drop_duplicates().tolist() if _looks_like_activity(value)]
    commodity_labels = [value for value in supply["Product"].drop_duplicates().tolist() if _looks_like_commodity(value)]
    final_demand_labels = [value for value in use_basic["Industry"].drop_duplicates().tolist() if _looks_like_final_demand(value)]
    import_labels = [value for value in use_purchaser["Industry"].drop_duplicates().tolist() if _looks_like_import(value)]
    value_added_labels = [value for value in use_basic["Product"].drop_duplicates().tolist() if _looks_like_factor(value)]
    factor_labels = import_labels + [value for value in value_added_labels if value not in import_labels]

    if not activity_labels:
        raise WrongInput("Statistics Canada SUT parser could not detect any activity rows.")
    if not commodity_labels:
        raise WrongInput("Statistics Canada SUT parser could not detect any commodity rows.")
    if not final_demand_labels:
        raise WrongInput("Statistics Canada SUT parser could not detect any final-demand columns.")
    if not factor_labels:
        raise WrongInput("Statistics Canada SUT parser could not detect any factor/value-added rows.")

    supply_matrix = supply.pivot_table(
        index="Industry",
        columns="Product",
        values="VALUE",
        aggfunc="sum",
        fill_value=0.0,
    )
    use_basic_matrix = use_basic.pivot_table(
        index="Product",
        columns="Industry",
        values="VALUE",
        aggfunc="sum",
        fill_value=0.0,
    )
    use_purchaser_matrix = use_purchaser.pivot_table(
        index="Product",
        columns="Industry",
        values="VALUE",
        aggfunc="sum",
        fill_value=0.0,
    )

    activity_axis = _three_level_index(str(geo), _MASTER_INDEX["a"], activity_labels)
    commodity_axis = _three_level_index(str(geo), _MASTER_INDEX["c"], commodity_labels)
    final_demand_axis = _three_level_index(str(geo), _MASTER_INDEX["n"], final_demand_labels)
    factor_axis = pd.Index(factor_labels, name=None)
    satellite_axis = pd.Index([STATCAN_SATELLITE_PLACEHOLDER], name=None)

    S = supply_matrix.reindex(index=activity_labels, columns=commodity_labels, fill_value=0.0).astype(float)
    S.index = activity_axis
    S.columns = commodity_axis

    U = use_basic_matrix.reindex(index=commodity_labels, columns=activity_labels, fill_value=0.0).astype(float)
    U.index = commodity_axis
    U.columns = activity_axis

    Yc = use_basic_matrix.reindex(index=commodity_labels, columns=final_demand_labels, fill_value=0.0).astype(float)
    Yc.index = commodity_axis
    Yc.columns = final_demand_axis

    Ya = _zero_frame(activity_axis, final_demand_axis)

    Va = _zero_frame(factor_axis, activity_axis)
    if value_added_labels:
        va_raw = use_basic_matrix.reindex(index=value_added_labels, columns=activity_labels, fill_value=0.0).astype(float)
        va_raw.columns = activity_axis
        for label in value_added_labels:
            Va.loc[label, :] = va_raw.loc[label, :]

    Vc = _zero_frame(factor_axis, commodity_axis)
    if import_labels:
        for label in import_labels:
            import_values = use_purchaser_matrix.reindex(index=commodity_labels, columns=[label], fill_value=0.0).astype(float)
            Vc.loc[label, :] = import_values.iloc[:, 0].to_numpy()

    Ea = _zero_frame(satellite_axis, activity_axis)
    Ec = _zero_frame(satellite_axis, commodity_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

    layout = StatCanLayout(
        table="SUT",
        level=level,
        year=int(year),
        geo=str(geo),
        valuation=STATCAN_VALUATIONS["basic"],
        pid=spec["pid"],
        title=spec["title"],
        csv_url=csv_url,
        catalogue_url=spec["catalogue_url"],
    )
    unit = _compose_unit(supply)

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
    indexes = {
        "r": {"main": [str(geo)]},
        "a": {"main": activity_labels},
        "c": {"main": commodity_labels},
        "f": {"main": factor_labels},
        "k": {"main": [STATCAN_SATELLITE_PLACEHOLDER]},
        "n": {"main": final_demand_labels},
        "s": {"main": activity_labels + commodity_labels},
    }
    units = _build_sut_units(
        activity_labels=activity_labels,
        commodity_labels=commodity_labels,
        factor_labels=factor_labels,
        unit=unit,
    )

    log_time(
        logger,
        (
            "Parser: StatCan SUT payload ready with shapes "
            f"S={S.shape}, U={U.shape}, Yc={Yc.shape}, Va={Va.shape}, Vc={Vc.shape}."
        ),
        "info",
    )
    return matrices, indexes, units, layout


def build_statcan_iot_from_frame(
    frame: pd.DataFrame,
    *,
    year: int,
    valuation: str = "basic",
    geo: str = "Canada",
    level: str = "summary",
    csv_url: str = "",
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    StatCanLayout,
]:
    """Transform one StatCan symmetric input-output frame into MARIO IOT blocks."""
    if valuation not in STATCAN_VALUATIONS:
        raise WrongInput(f"StatCan valuation should be one of {list(STATCAN_VALUATIONS)}.")

    spec = _resolve_spec("IOT", level)
    subset = _filter_statcan_slice(frame, year=year, geo=geo)
    value_label = STATCAN_VALUATIONS[valuation]
    subset = subset[subset["Valuation"] == value_label].copy()
    if subset.empty:
        raise WrongInput(
            f"Statistics Canada IOT payload contains no rows for valuation {value_label!r}."
        )

    sector_labels = [value for value in subset["Supply"].drop_duplicates().tolist() if _looks_like_activity(value)]
    factor_labels = [value for value in subset["Supply"].drop_duplicates().tolist() if _looks_like_factor(value)]
    final_demand_labels = [
        value
        for value in subset["Use"].drop_duplicates().tolist()
        if value != "Total use" and not _looks_like_activity(value)
    ]

    if not sector_labels:
        raise WrongInput("Statistics Canada IOT parser could not detect any sector rows.")
    if not factor_labels:
        raise WrongInput("Statistics Canada IOT parser could not detect any factor rows.")
    if not final_demand_labels:
        raise WrongInput("Statistics Canada IOT parser could not detect any final-demand columns.")

    matrix = subset.pivot_table(
        index="Supply",
        columns="Use",
        values="VALUE",
        aggfunc="sum",
        fill_value=0.0,
    )

    sector_axis = _three_level_index(str(geo), _MASTER_INDEX["s"], sector_labels)
    final_demand_axis = _three_level_index(str(geo), _MASTER_INDEX["n"], final_demand_labels)
    factor_axis = pd.Index(factor_labels, name=None)
    satellite_axis = pd.Index([STATCAN_SATELLITE_PLACEHOLDER], name=None)

    Z = matrix.reindex(index=sector_labels, columns=sector_labels, fill_value=0.0).astype(float)
    Z.index = sector_axis
    Z.columns = sector_axis

    Y = matrix.reindex(index=sector_labels, columns=final_demand_labels, fill_value=0.0).astype(float)
    Y.index = sector_axis
    Y.columns = final_demand_axis

    V = matrix.reindex(index=factor_labels, columns=sector_labels, fill_value=0.0).astype(float)
    V.index = factor_axis
    V.columns = sector_axis

    E = _zero_frame(satellite_axis, sector_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

    layout = StatCanLayout(
        table="IOT",
        level=level,
        year=int(year),
        geo=str(geo),
        valuation=value_label,
        pid=spec["pid"],
        title=spec["title"],
        csv_url=csv_url,
        catalogue_url=spec["catalogue_url"],
    )
    unit = _compose_unit(subset)

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
    indexes = {
        "r": {"main": [str(geo)]},
        "s": {"main": sector_labels},
        "f": {"main": factor_labels},
        "k": {"main": [STATCAN_SATELLITE_PLACEHOLDER]},
        "n": {"main": final_demand_labels},
    }
    units = _build_iot_units(
        sector_labels=sector_labels,
        factor_labels=factor_labels,
        unit=unit,
    )

    log_time(
        logger,
        (
            "Parser: StatCan IOT payload ready with shapes "
            f"Z={Z.shape}, Y={Y.shape}, V={V.shape}."
        ),
        "info",
    )
    return matrices, indexes, units, layout


def parse_statcan_sut_wds(
    *,
    year: int,
    level: str = "summary",
    geo: str = "Canada",
    csv_path: str | Path | None = None,
    timeout: int = 60,
    session: requests.Session | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    StatCanLayout,
]:
    """Download one StatCan SUT table via WDS and convert it to MARIO blocks."""
    if level not in STATCAN_TABLES["SUT"]:
        raise WrongInput(f"StatCan SUT level should be one of {list(STATCAN_TABLES['SUT'])}.")
    if csv_path is not None:
        frame = _read_statcan_csv_table(csv_path)
        csv_url = str(csv_path)
    else:
        frame, csv_url = _download_statcan_csv_table(
            STATCAN_TABLES["SUT"][level]["pid"],
            timeout=timeout,
            session=session,
        )
    return build_statcan_sut_from_frame(
        frame,
        year=year,
        geo=geo,
        level=level,
        csv_url=csv_url,
    )


def parse_statcan_iot_wds(
    *,
    year: int,
    level: str = "summary",
    geo: str = "Canada",
    valuation: str = "basic",
    csv_path: str | Path | None = None,
    timeout: int = 60,
    session: requests.Session | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    StatCanLayout,
]:
    """Download one StatCan IOT table via WDS and convert it to MARIO blocks."""
    if level not in STATCAN_TABLES["IOT"]:
        raise WrongInput(f"StatCan IOT level should be one of {list(STATCAN_TABLES['IOT'])}.")
    if valuation not in STATCAN_VALUATIONS:
        raise WrongInput(f"StatCan valuation should be one of {list(STATCAN_VALUATIONS)}.")
    if csv_path is not None:
        frame = _read_statcan_csv_table(csv_path)
        csv_url = str(csv_path)
    else:
        frame, csv_url = _download_statcan_csv_table(
            STATCAN_TABLES["IOT"][level]["pid"],
            timeout=timeout,
            session=session,
        )
    return build_statcan_iot_from_frame(
        frame,
        year=year,
        geo=geo,
        level=level,
        valuation=valuation,
        csv_url=csv_url,
    )
