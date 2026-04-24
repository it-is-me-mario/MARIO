"""API-based parser for Eurostat FIGARO supply-use and input-output tables."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
import requests

from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    FIGARO_API_BASE_URL,
    FIGARO_EXTENSION_PLACEHOLDER,
    FIGARO_FACTOR_UNIT,
    FIGARO_IOT_MODES,
    FIGARO_SATELLITE_UNIT,
    FIGARO_SOURCE,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

FIGARO_UNIT_OPTIONS = ("MIO_EUR",)
FIGARO_DEFAULT_TIMEOUT = 60
FIGARO_GROUPS = (
    (2010, 2013, "1"),
    (2014, 2017, "2"),
    (2018, 2021, "3"),
    (2022, None, "4"),
)
FIGARO_SUT_DATAFLOWS = {"supply": "naio_10_fcp_s{suffix}", "use": "naio_10_fcp_u{suffix}"}
FIGARO_IOT_DATAFLOWS = {"product": "naio_10_fcp_ip{suffix}", "industry": "naio_10_fcp_ii{suffix}"}

_REPEATED_HYPHEN_RANGE_RE = re.compile(
    r"(?P<prefix>[A-Z_]*)(?P<letter>[A-Z])(?P<start>\d{2})-(?P=letter)(?P<end>\d{2})"
)
_SIMPLE_HYPHEN_RANGE_RE = re.compile(r"(?P<prefix>[A-Z_]*[A-Z])(?P<start>\d{2})-(?P<end>\d{2})")
_REPEATED_UNDERSCORE_RANGE_RE = re.compile(
    r"(?P<prefix>[A-Z_]*)(?P<letter>[A-Z])(?P<start>\d{2})_(?P=letter)(?P<end>\d{2})"
)


@dataclass(frozen=True)
class FigaroSUTLayout:
    """API metadata for one FIGARO SUT parse request."""

    year: int
    unit: str
    supply_dataflow: str
    use_dataflow: str

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        return f"FIGARO SUT {self.year}"

    @property
    def price(self) -> str:
        """Return the price system label recorded in MARIO metadata."""
        return "Current prices"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        return FIGARO_SOURCE


@dataclass(frozen=True)
class FigaroIOTLayout:
    """API metadata for one FIGARO IOT parse request."""

    year: int
    unit: str
    dataflow: str
    mode: str

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        return f"FIGARO IOT {self.year} {self.mode}"

    @property
    def price(self) -> str:
        """Return the price system label recorded in MARIO metadata."""
        return "Current prices"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        detail = "product-by-product" if self.mode == "product" else "industry-by-industry"
        return f"{FIGARO_SOURCE} ({detail})"


@lru_cache(maxsize=1)
def load_figaro_metadata() -> pd.DataFrame:
    """Load the packaged FIGARO label metadata used to map codes to names."""
    return pd.read_csv(Path(__file__).with_name("figaro_metadata.csv"))


def _figaro_suffix(year: int) -> str:
    """Return the Eurostat FIGARO dataflow suffix for ``year``."""
    if year is None:
        raise WrongInput("FIGARO API parsing requires an explicit year.")
    for start, end, suffix in FIGARO_GROUPS:
        if year >= start and (end is None or year <= end):
            return suffix
    raise WrongInput("FIGARO API dataflows are available from 2010 onwards.")


def _validate_unit(unit: str) -> None:
    """Validate the requested FIGARO unit."""
    if unit not in FIGARO_UNIT_OPTIONS:
        raise WrongInput(f"FIGARO unit should be one of {list(FIGARO_UNIT_OPTIONS)}.")


def detect_figaro_sut_layout(year: int, *, unit: str = "MIO_EUR") -> FigaroSUTLayout:
    """Resolve the Eurostat FIGARO dataflows used for one SUT parse request."""
    _validate_unit(unit)
    suffix = _figaro_suffix(year)
    layout = FigaroSUTLayout(
        year=year,
        unit=unit,
        supply_dataflow=FIGARO_SUT_DATAFLOWS["supply"].format(suffix=suffix),
        use_dataflow=FIGARO_SUT_DATAFLOWS["use"].format(suffix=suffix),
    )
    log_time(
        logger,
        (
            "Parser: detected FIGARO SUT API dataflows "
            f"year={layout.year} supply={layout.supply_dataflow} use={layout.use_dataflow}."
        ),
        "debug",
    )
    return layout


def detect_figaro_iot_layout(
    year: int,
    *,
    mode: str = "auto",
    unit: str = "MIO_EUR",
) -> FigaroIOTLayout:
    """Resolve the Eurostat FIGARO dataflow used for one IOT parse request."""
    _validate_unit(unit)
    if mode not in FIGARO_IOT_MODES:
        raise WrongInput(f"FIGARO iot_mode should be one of {list(FIGARO_IOT_MODES)}.")
    if mode == "auto":
        mode = "product"
    suffix = _figaro_suffix(year)
    layout = FigaroIOTLayout(
        year=year,
        unit=unit,
        dataflow=FIGARO_IOT_DATAFLOWS[mode].format(suffix=suffix),
        mode=mode,
    )
    log_time(
        logger,
        (
            "Parser: detected FIGARO IOT API dataflow "
            f"year={layout.year} mode={layout.mode} dataflow={layout.dataflow}."
        ),
        "debug",
    )
    return layout


def _jsonstat_category_codes(payload: dict[str, Any], dimension: str) -> list[str]:
    """Return JSON-stat category codes ordered by their category position."""
    category = payload["dimension"][dimension]["category"]
    index = category.get("index", {})
    ordered = [None] * len(index)
    for code, position in index.items():
        ordered[int(position)] = code
    return [code for code in ordered if code is not None]


def _jsonstat_to_frame(payload: dict[str, Any]) -> pd.DataFrame:
    """Convert one Eurostat JSON-stat payload into a tidy dataframe."""
    dimensions = payload.get("id", [])
    sizes = payload.get("size", [])
    values = payload.get("value", {})
    if not dimensions or not sizes or not values:
        return pd.DataFrame(columns=[*dimensions, "obsValue"])

    categories = [_jsonstat_category_codes(payload, dimension) for dimension in dimensions]
    if isinstance(values, list):
        items = ((index, value) for index, value in enumerate(values) if value is not None)
    else:
        items = ((int(index), value) for index, value in values.items())

    rows = []
    for flat_index, value in items:
        remainder = int(flat_index)
        positions = []
        for size in reversed(sizes):
            positions.append(remainder % size)
            remainder //= size
        positions.reverse()
        row = {
            dimension: categories[position_index][position]
            for position_index, (dimension, position) in enumerate(zip(dimensions, positions))
        }
        row["obsValue"] = value
        rows.append(row)

    return pd.DataFrame(rows)


def _request_figaro_json(
    dataflow: str,
    *,
    params: dict[str, str | int],
    timeout: int = FIGARO_DEFAULT_TIMEOUT,
    session: Any | None = None,
) -> dict[str, Any]:
    """Request one JSON-stat payload from the Eurostat FIGARO API."""
    url = f"{FIGARO_API_BASE_URL.rstrip('/')}/{dataflow}"
    client = session or requests
    response = client.get(url, params=params, timeout=timeout)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text[:500].strip()
        raise WrongInput(
            f"Eurostat FIGARO API request failed for {dataflow} with params {params}: {detail}"
        ) from exc
    return response.json()


@lru_cache(maxsize=16)
def _load_figaro_dimensions_cached(dataflow: str, unit: str) -> dict[str, list[str]]:
    """Load dimension categories for a FIGARO dataflow using a no-data year."""
    payload = _request_figaro_json(
        dataflow,
        params={"time": "9999", "unit": unit},
        timeout=FIGARO_DEFAULT_TIMEOUT,
    )
    return {dimension: _jsonstat_category_codes(payload, dimension) for dimension in payload["id"]}


def _load_figaro_dimensions(
    dataflow: str,
    *,
    unit: str,
    session: Any | None,
    timeout: int,
) -> dict[str, list[str]]:
    """Load dimension categories for one FIGARO dataflow."""
    if session is None and timeout == FIGARO_DEFAULT_TIMEOUT:
        return _load_figaro_dimensions_cached(dataflow, unit)
    payload = _request_figaro_json(
        dataflow,
        params={"time": "9999", "unit": unit},
        timeout=timeout,
        session=session,
    )
    return {dimension: _jsonstat_category_codes(payload, dimension) for dimension in payload["id"]}


def _to_api_region_code(code: str) -> str:
    """Map packaged FIGARO region codes to Eurostat API codes."""
    if code == "FIGW1":
        return "WRL_REST"
    if code == "W2":
        return "DOM"
    return code


def _from_api_region_code(code: str) -> str:
    """Map Eurostat API region codes to packaged FIGARO region codes."""
    if code == "WRL_REST":
        return "FIGW1"
    if code == "DOM":
        return "W2"
    return code


def _normalize_figaro_code(code: str) -> str:
    """Normalize Eurostat FIGARO activity/product range codes to MARIO metadata codes."""
    if not isinstance(code, str):
        return code
    code = _from_api_region_code(code)
    code = _REPEATED_HYPHEN_RANGE_RE.sub(
        lambda match: f"{match.group('prefix')}{match.group('letter')}{match.group('start')}T{match.group('end')}",
        code,
    )
    code = _SIMPLE_HYPHEN_RANGE_RE.sub(
        lambda match: f"{match.group('prefix')}{match.group('start')}T{match.group('end')}",
        code,
    )
    return _REPEATED_UNDERSCORE_RANGE_RE.sub(
        lambda match: f"{match.group('prefix')}{match.group('letter')}{match.group('start')}_{match.group('end')}",
        code,
    )


def _resolve_api_countries(
    dimensions: dict[str, list[str]],
    *,
    countries: str | list[str] | tuple[str, ...] | None,
) -> tuple[list[str], list[str]]:
    """Return API origin and destination country codes requested by the user."""
    available_origins = dimensions.get("c_orig", [])
    available_destinations = dimensions.get("c_dest", [])
    if countries is None:
        origins = [code for code in available_origins if code != "DOM"]
        destinations = list(available_destinations)
        return origins, destinations

    if isinstance(countries, str):
        requested = [countries]
    else:
        requested = list(countries)
    requested = [_to_api_region_code(str(code).upper()) for code in requested]

    missing_origins = sorted(set(requested).difference(available_origins))
    missing_destinations = sorted(set(requested).difference(available_destinations))
    if missing_origins or missing_destinations:
        raise WrongInput(
            "Requested FIGARO countries are not available in the selected dataflow: "
            f"missing origins={missing_origins}, missing destinations={missing_destinations}."
        )
    return requested, requested


def _download_figaro_api_frame(
    dataflow: str,
    *,
    year: int,
    unit: str,
    row_dim: str,
    col_dim: str,
    countries: str | list[str] | tuple[str, ...] | None = None,
    include_dom: bool = False,
    factor_codes: list[str] | None = None,
    timeout: int = FIGARO_DEFAULT_TIMEOUT,
    session: Any | None = None,
) -> pd.DataFrame:
    """Download one FIGARO dataflow and return canonical row/column columns."""
    dimensions = _load_figaro_dimensions(dataflow, unit=unit, session=session, timeout=timeout)
    origins, destinations = _resolve_api_countries(dimensions, countries=countries)
    if include_dom and "DOM" in dimensions.get("c_orig", []):
        origins = [*origins, "DOM"]

    frames: list[pd.DataFrame] = []
    for origin in origins:
        log_time(
            logger,
            f"Parser: downloading FIGARO {dataflow} year={year} c_orig={origin}.",
            "info",
        )
        payload = _request_figaro_json(
            dataflow,
            params={"time": year, "unit": unit, "c_orig": origin},
            timeout=timeout,
            session=session,
        )
        frame = _jsonstat_to_frame(payload)
        if frame.empty:
            continue
        if "c_dest" in frame.columns:
            frame = frame.loc[frame["c_dest"].isin(destinations)]
        frames.append(frame)

    if frames:
        api_frame = pd.concat(frames, ignore_index=True)
    else:
        api_frame = pd.DataFrame(columns=["c_orig", "c_dest", row_dim, col_dim, "obsValue"])

    factor_codes = set(factor_codes or [])
    ref_area = api_frame["c_orig"].astype(str).map(_from_api_region_code)
    if factor_codes:
        factor_mask = api_frame[row_dim].astype(str).map(_normalize_figaro_code).isin(factor_codes)
        ref_area = ref_area.mask(factor_mask & (api_frame["c_orig"] == "DOM"), "W2")

    normalized = pd.DataFrame(
        {
            "refArea": ref_area,
            "rowCode": api_frame[row_dim].astype(str).map(_normalize_figaro_code),
            "counterpartArea": api_frame["c_dest"].astype(str).map(_from_api_region_code),
            "colCode": api_frame[col_dim].astype(str).map(_normalize_figaro_code),
            "obsValue": pd.to_numeric(api_frame["obsValue"], errors="coerce").fillna(0.0),
        }
    )
    return normalized


def _ordered_present_codes(actual: set[str], ordered: list[str]) -> list[str]:
    """Return actual codes ordered first by metadata order, then by sorted extras."""
    ordered_present = [code for code in ordered if code in actual]
    extras = sorted(actual.difference(set(ordered)))
    return ordered_present + extras


def _label_map(metadata: pd.DataFrame, *, level: str) -> tuple[list[str], dict[str, str]]:
    """Return the ordered codes and label map for one FIGARO metadata level."""
    subset = metadata.loc[metadata["Level"] == level, ["Code", "Name"]]
    return subset["Code"].tolist(), dict(zip(subset["Code"], subset["Name"]))


def _safe_label(code: str, labels: dict[str, str], *, label: str) -> str:
    """Return one human-readable label, falling back to the raw code if needed."""
    if code not in labels:
        log_time(
            logger,
            f"Parser: missing FIGARO {label} metadata for code {code}; keeping the raw code.",
            "debug",
        )
    return labels.get(code, code)


def _regional_axis(
    region_codes: list[str],
    item_codes: list[str],
    *,
    level_code: str,
    region_labels: dict[str, str],
    item_labels: dict[str, str],
    item_label: str,
) -> tuple[pd.MultiIndex, pd.MultiIndex]:
    """Build one raw code axis and the corresponding canonical labeled axis."""
    raw_axis = pd.MultiIndex.from_product([region_codes, item_codes])
    labeled_axis = pd.MultiIndex.from_arrays(
        [
            [_safe_label(region, region_labels, label="region") for region, _ in raw_axis],
            [_MASTER_INDEX[level_code]] * len(raw_axis),
            [_safe_label(item, item_labels, label=item_label) for _, item in raw_axis],
        ]
    )
    return raw_axis, labeled_axis


def _factor_axis(factor_codes: list[str], factor_labels: dict[str, str]) -> pd.Index:
    """Build the canonical factor index used for FIGARO value-added rows."""
    return pd.Index(
        [_safe_label(code, factor_labels, label="factor") for code in factor_codes],
        name=None,
    )


def _zero_frame(index, columns) -> pd.DataFrame:
    """Allocate a zero-filled dataframe with the given index and columns."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def _pivot(
    frame: pd.DataFrame,
    *,
    index_columns: list[str],
    column_columns: list[str],
    index_axis,
    column_axis,
) -> pd.DataFrame:
    """Pivot a tidy FIGARO slice into a dense matrix on canonical raw axes."""
    block = frame.pivot_table(
        index=index_columns,
        columns=column_columns,
        values="obsValue",
        aggfunc="sum",
        fill_value=0.0,
    )
    return block.reindex(index=index_axis, columns=column_axis, fill_value=0.0)


def parse_figaro_sut(
    *,
    year: int,
    unit: str = "MIO_EUR",
    countries: str | list[str] | tuple[str, ...] | None = None,
    timeout: int = FIGARO_DEFAULT_TIMEOUT,
    session: Any | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], FigaroSUTLayout]:
    """Parse FIGARO SUT dataflows from the Eurostat API into MARIO SUT blocks."""
    layout = detect_figaro_sut_layout(year, unit=unit)
    metadata = load_figaro_metadata()

    region_codes_meta, region_labels = _label_map(metadata, level="r")
    commodity_codes_meta, commodity_labels = _label_map(metadata, level="c")
    activity_codes_meta, activity_labels = _label_map(metadata, level="a")
    factor_codes_meta, factor_labels = _label_map(metadata, level="f")
    final_demand_codes_meta, final_demand_labels = _label_map(metadata, level="n")

    supply = _download_figaro_api_frame(
        layout.supply_dataflow,
        year=layout.year,
        unit=layout.unit,
        row_dim="cpa2_1",
        col_dim="nace_r2",
        countries=countries,
        timeout=timeout,
        session=session,
    )
    use = _download_figaro_api_frame(
        layout.use_dataflow,
        year=layout.year,
        unit=layout.unit,
        row_dim="prd_ava",
        col_dim="ind_use",
        countries=countries,
        include_dom=True,
        factor_codes=factor_codes_meta,
        timeout=timeout,
        session=session,
    )

    region_codes = _ordered_present_codes(
        set(supply["refArea"].astype(str)).union(
            set(supply["counterpartArea"].astype(str)),
            set(use.loc[use["refArea"] != "W2", "refArea"].astype(str)),
            set(use["counterpartArea"].astype(str)),
        ),
        region_codes_meta,
    )
    region_codes = [code for code in region_codes if code != "W2"]
    commodity_codes = _ordered_present_codes(
        set(supply["rowCode"].astype(str)).union(
            set(use.loc[use["refArea"] != "W2", "rowCode"].astype(str))
        ),
        commodity_codes_meta,
    )
    activity_codes = _ordered_present_codes(
        set(supply["colCode"].astype(str)).union(
            set(use.loc[~use["colCode"].isin(final_demand_codes_meta), "colCode"].astype(str))
        ),
        activity_codes_meta,
    )
    factor_codes = _ordered_present_codes(
        set(use.loc[use["refArea"] == "W2", "rowCode"].astype(str)),
        factor_codes_meta,
    )
    final_demand_codes = _ordered_present_codes(
        set(use.loc[use["colCode"].isin(final_demand_codes_meta), "colCode"].astype(str)),
        final_demand_codes_meta,
    )

    raw_activity_axis, activity_axis = _regional_axis(
        region_codes,
        activity_codes,
        level_code="a",
        region_labels=region_labels,
        item_labels=activity_labels,
        item_label="activity",
    )
    raw_commodity_axis, commodity_axis = _regional_axis(
        region_codes,
        commodity_codes,
        level_code="c",
        region_labels=region_labels,
        item_labels=commodity_labels,
        item_label="commodity",
    )
    raw_final_demand_axis, final_demand_axis = _regional_axis(
        region_codes,
        final_demand_codes,
        level_code="n",
        region_labels=region_labels,
        item_labels=final_demand_labels,
        item_label="final demand",
    )
    factor_axis = _factor_axis(factor_codes, factor_labels)
    satellite_axis = pd.Index([FIGARO_EXTENSION_PLACEHOLDER], name=None)

    supply_subset = supply.loc[
        supply["rowCode"].isin(commodity_codes) & supply["colCode"].isin(activity_codes),
        ["counterpartArea", "colCode", "refArea", "rowCode", "obsValue"],
    ]
    use_intermediate = use.loc[
        (use["refArea"] != "W2")
        & use["rowCode"].isin(commodity_codes)
        & use["colCode"].isin(activity_codes),
        ["refArea", "rowCode", "counterpartArea", "colCode", "obsValue"],
    ]
    use_final = use.loc[
        (use["refArea"] != "W2")
        & use["rowCode"].isin(commodity_codes)
        & use["colCode"].isin(final_demand_codes),
        ["refArea", "rowCode", "counterpartArea", "colCode", "obsValue"],
    ]
    use_factors = use.loc[
        (use["refArea"] == "W2")
        & use["rowCode"].isin(factor_codes)
        & use["colCode"].isin(activity_codes),
        ["rowCode", "counterpartArea", "colCode", "obsValue"],
    ]

    S = _pivot(
        supply_subset,
        index_columns=["counterpartArea", "colCode"],
        column_columns=["refArea", "rowCode"],
        index_axis=raw_activity_axis,
        column_axis=raw_commodity_axis,
    )
    S.index = activity_axis
    S.columns = commodity_axis

    U = _pivot(
        use_intermediate,
        index_columns=["refArea", "rowCode"],
        column_columns=["counterpartArea", "colCode"],
        index_axis=raw_commodity_axis,
        column_axis=raw_activity_axis,
    )
    U.index = commodity_axis
    U.columns = activity_axis

    Yc = _pivot(
        use_final,
        index_columns=["refArea", "rowCode"],
        column_columns=["counterpartArea", "colCode"],
        index_axis=raw_commodity_axis,
        column_axis=raw_final_demand_axis,
    )
    Yc.index = commodity_axis
    Yc.columns = final_demand_axis

    Ya = _zero_frame(activity_axis, final_demand_axis)

    Va = _pivot(
        use_factors,
        index_columns=["rowCode"],
        column_columns=["counterpartArea", "colCode"],
        index_axis=factor_codes,
        column_axis=raw_activity_axis,
    )
    Va.index = factor_axis
    Va.columns = activity_axis

    Vc = _zero_frame(factor_axis, commodity_axis)
    Ea = _zero_frame(satellite_axis, activity_axis)
    Ec = _zero_frame(satellite_axis, commodity_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

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
            {"unit": [FIGARO_FACTOR_UNIT] * len(activity_codes)},
            index=activity_axis.unique(2),
        ),
        _MASTER_INDEX["c"]: pd.DataFrame(
            {"unit": [FIGARO_FACTOR_UNIT] * len(commodity_codes)},
            index=commodity_axis.unique(2),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": [FIGARO_FACTOR_UNIT] * len(factor_axis)}, index=factor_axis),
        _MASTER_INDEX["k"]: pd.DataFrame({"unit": [FIGARO_SATELLITE_UNIT]}, index=satellite_axis),
    }

    indeces = {
        "r": {"main": [_safe_label(code, region_labels, label="region") for code in region_codes]},
        "n": {"main": [_safe_label(code, final_demand_labels, label="final demand") for code in final_demand_codes]},
        "k": {"main": list(satellite_axis)},
        "f": {"main": list(factor_axis)},
        "a": {"main": [_safe_label(code, activity_labels, label="activity") for code in activity_codes]},
        "c": {"main": [_safe_label(code, commodity_labels, label="commodity") for code in commodity_codes]},
        "s": {
            "main": [_safe_label(code, activity_labels, label="activity") for code in activity_codes]
            + [_safe_label(code, commodity_labels, label="commodity") for code in commodity_codes]
        },
    }

    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: FIGARO SUT parsed from Eurostat API with "
            f"{len(region_codes)} regions, {len(activity_codes)} activities, "
            f"{len(commodity_codes)} commodities, {len(factor_codes)} factor rows."
        ),
        "info",
    )
    return matrices, indeces, units, layout


def parse_figaro_iot(
    *,
    year: int,
    mode: str = "auto",
    unit: str = "MIO_EUR",
    countries: str | list[str] | tuple[str, ...] | None = None,
    timeout: int = FIGARO_DEFAULT_TIMEOUT,
    session: Any | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], FigaroIOTLayout]:
    """Parse FIGARO IOT dataflows from the Eurostat API into MARIO IOT blocks."""
    layout = detect_figaro_iot_layout(year, mode=mode, unit=unit)
    metadata = load_figaro_metadata()

    region_codes_meta, region_labels = _label_map(metadata, level="r")
    activity_codes_meta, activity_labels = _label_map(metadata, level="a")
    commodity_codes_meta, commodity_labels = _label_map(metadata, level="c")
    factor_codes_meta, factor_labels = _label_map(metadata, level="f")
    final_demand_codes_meta, final_demand_labels = _label_map(metadata, level="n")

    if layout.mode == "industry":
        row_dim = "ind_ava"
        col_dim = "ind_use"
        sector_codes_meta = activity_codes_meta
        sector_labels_meta = activity_labels
        sector_label_name = "activity"
    else:
        row_dim = "prd_ava"
        col_dim = "prd_use"
        sector_codes_meta = commodity_codes_meta
        sector_labels_meta = commodity_labels
        sector_label_name = "commodity"

    iot = _download_figaro_api_frame(
        layout.dataflow,
        year=layout.year,
        unit=layout.unit,
        row_dim=row_dim,
        col_dim=col_dim,
        countries=countries,
        include_dom=True,
        factor_codes=factor_codes_meta,
        timeout=timeout,
        session=session,
    )

    region_codes = _ordered_present_codes(
        set(iot.loc[iot["refArea"] != "W2", "refArea"].astype(str)).union(
            set(iot["counterpartArea"].astype(str))
        ),
        region_codes_meta,
    )
    region_codes = [code for code in region_codes if code != "W2"]
    sector_codes = _ordered_present_codes(
        set(iot.loc[iot["refArea"] != "W2", "rowCode"].astype(str)).union(
            set(iot.loc[~iot["colCode"].isin(final_demand_codes_meta), "colCode"].astype(str))
        ),
        sector_codes_meta,
    )
    factor_codes = _ordered_present_codes(
        set(iot.loc[iot["refArea"] == "W2", "rowCode"].astype(str)),
        factor_codes_meta,
    )
    final_demand_codes = _ordered_present_codes(
        set(iot.loc[iot["colCode"].isin(final_demand_codes_meta), "colCode"].astype(str)),
        final_demand_codes_meta,
    )

    raw_sector_axis, sector_axis = _regional_axis(
        region_codes,
        sector_codes,
        level_code="s",
        region_labels=region_labels,
        item_labels=sector_labels_meta,
        item_label=sector_label_name,
    )
    raw_final_demand_axis, final_demand_axis = _regional_axis(
        region_codes,
        final_demand_codes,
        level_code="n",
        region_labels=region_labels,
        item_labels=final_demand_labels,
        item_label="final demand",
    )
    factor_axis = _factor_axis(factor_codes, factor_labels)
    satellite_axis = pd.Index([FIGARO_EXTENSION_PLACEHOLDER], name=None)

    intermediate = iot.loc[
        (iot["refArea"] != "W2")
        & iot["rowCode"].isin(sector_codes)
        & iot["colCode"].isin(sector_codes),
        ["refArea", "rowCode", "counterpartArea", "colCode", "obsValue"],
    ]
    final = iot.loc[
        (iot["refArea"] != "W2")
        & iot["rowCode"].isin(sector_codes)
        & iot["colCode"].isin(final_demand_codes),
        ["refArea", "rowCode", "counterpartArea", "colCode", "obsValue"],
    ]
    factors = iot.loc[
        (iot["refArea"] == "W2")
        & iot["rowCode"].isin(factor_codes)
        & iot["colCode"].isin(sector_codes),
        ["rowCode", "counterpartArea", "colCode", "obsValue"],
    ]

    Z = _pivot(
        intermediate,
        index_columns=["refArea", "rowCode"],
        column_columns=["counterpartArea", "colCode"],
        index_axis=raw_sector_axis,
        column_axis=raw_sector_axis,
    )
    Z.index = sector_axis
    Z.columns = sector_axis

    Y = _pivot(
        final,
        index_columns=["refArea", "rowCode"],
        column_columns=["counterpartArea", "colCode"],
        index_axis=raw_sector_axis,
        column_axis=raw_final_demand_axis,
    )
    Y.index = sector_axis
    Y.columns = final_demand_axis

    V = _pivot(
        factors,
        index_columns=["rowCode"],
        column_columns=["counterpartArea", "colCode"],
        index_axis=factor_codes,
        column_axis=raw_sector_axis,
    )
    V.index = factor_axis
    V.columns = sector_axis

    E = _zero_frame(satellite_axis, sector_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
    units = {
        _MASTER_INDEX["s"]: pd.DataFrame(
            {"unit": [FIGARO_FACTOR_UNIT] * len(sector_codes)},
            index=sector_axis.unique(2),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [FIGARO_FACTOR_UNIT] * len(factor_axis)},
            index=factor_axis,
        ),
        _MASTER_INDEX["k"]: pd.DataFrame({"unit": [FIGARO_SATELLITE_UNIT]}, index=satellite_axis),
    }
    indeces = {
        "r": {"main": [_safe_label(code, region_labels, label="region") for code in region_codes]},
        "s": {"main": [_safe_label(code, sector_labels_meta, label=sector_label_name) for code in sector_codes]},
        "f": {"main": list(factor_axis)},
        "k": {"main": list(satellite_axis)},
        "n": {"main": [_safe_label(code, final_demand_labels, label="final demand") for code in final_demand_codes]},
    }

    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: FIGARO IOT parsed from Eurostat API with "
            f"{len(region_codes)} regions, {len(sector_codes)} sectors, "
            f"{len(factor_codes)} factor rows, mode={layout.mode}."
        ),
        "info",
    )
    return matrices, indeces, units, layout
