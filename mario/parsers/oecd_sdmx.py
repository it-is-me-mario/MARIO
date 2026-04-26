"""Direct OECD SUT parser backed by the official SDMX API."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
import logging
import re

import numpy as np
import pandas as pd
import requests

from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    OECD_ICIO_SATELLITE_PLACEHOLDER,
    OECD_SDMX_BASE_URL,
    OECD_SUT_FINAL_DEMAND,
    OECD_SUT_SOURCE,
    OECD_SUT_VA_ROWS,
    OECD_SUT_VC_ROWS,
)

logger = logging.getLogger(__name__)

_SUPPLY_DATAFLOW = "OECD.SDD.NAD,DSD_NASU@DF_SUPPLY_T1500,2.0"
_USEPP_DATAFLOW = "OECD.SDD.NAD,DSD_NASU@DF_USEPP_T1600,2.0"
_USEVA_DATAFLOW = "OECD.SDD.NAD,DSD_NASU@DF_USEVA_T1600,2.0"
_OECD_SDMX_USER_AGENT = "MARIO parser (https://github.com/it-is-me-mario/MARIO)"


@dataclass(frozen=True)
class OECDSUTLayout:
    """Resolved metadata for one OECD SUT SDMX pull."""

    country: str
    year: int
    currency: str
    notes: tuple[str, ...] = ()

    @property
    def dataset_name(self) -> str:
        """Return a compact default name for one OECD SUT dataset."""
        return f"OECD SUT {self.country} {self.year}"

    @property
    def price(self) -> str:
        """Return the price-system metadata recorded in MARIO."""
        return "Current prices"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        return OECD_SUT_SOURCE


def _sdmx_key(country: str) -> str:
    """Return the OECD SDMX wildcard key for one country slice."""
    return f"A.{str(country).upper()}......."


def _read_sdmx_csv(
    dataflow: str,
    *,
    country: str,
    year: int,
    timeout: int = 60,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Download one OECD SDMX-CSV slice and return it as a dataframe."""
    country_code = str(country).upper()
    url = f"{OECD_SDMX_BASE_URL}/{dataflow}/{_sdmx_key(country_code)}"
    params = {
        "startPeriod": int(year),
        "endPeriod": int(year),
        "format": "csvfile",
    }
    log_time(logger, f"Parser: requesting OECD SDMX {dataflow} for {country_code} {year}.", "info")
    response = (session or requests).get(
        url,
        params=params,
        timeout=timeout,
        headers={"User-Agent": _OECD_SDMX_USER_AGENT},
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = getattr(response, "status_code", "unknown")
        detail = getattr(response, "text", "")[:500].strip()
        requested_url = getattr(response, "url", url)
        if status_code in {403, 429}:
            raise WrongInput(
                "OECD SDMX temporarily refused the request "
                f"({status_code}) for {dataflow} ({country_code}, {year}). "
                "OECD may throttle or temporarily block repeated API/CSV "
                "downloads; wait and retry, or reduce repeated notebook runs. "
                f"URL: {requested_url}. Response detail: {detail}"
            ) from exc
        raise WrongInput(
            "OECD SDMX request failed "
            f"({status_code}) for {dataflow} ({country_code}, {year}). "
            f"URL: {requested_url}. Response detail: {detail}"
        ) from exc
    frame = pd.read_csv(StringIO(response.text))
    if frame.empty:
        raise WrongInput(
            f"OECD returned no observations for {dataflow} ({country_code}, {year})."
        )
    return frame


def _leaf_codes(codes: list[str], *, prefix: str = "") -> list[str]:
    """Select one mutually exclusive OECD leaf axis from observed codes."""
    observed = set(codes)
    selected: list[str] = []
    for code in sorted(codes):
        raw = code[len(prefix):] if prefix and code.startswith(prefix) else code
        if raw in {"_T", "_Z"}:
            continue
        if len(raw) == 1:
            if any(
                other != code
                and (
                    (other[len(prefix):] if prefix and other.startswith(prefix) else other)
                ).startswith(raw)
                for other in observed
            ):
                continue
            selected.append(code)
            continue
        aggregate_match = re.match(r"^([A-Z]+\d+)(?:T|_)(\d+)$", raw)
        if aggregate_match is not None:
            base = aggregate_match.group(1)
            if any(
                other != code
                and (
                    (other[len(prefix):] if prefix and other.startswith(prefix) else other)
                ).startswith(base)
                for other in observed
            ):
                continue
        selected.append(code)
    return selected


def _three_level_index(country: str, level_label: str, items: list[str]) -> pd.MultiIndex:
    """Build one canonical MARIO three-level axis for a single-region dataset."""
    return pd.MultiIndex.from_arrays(
        [
            [country] * len(items),
            [level_label] * len(items),
            items,
        ]
    )


def _zero_frame(index, columns) -> pd.DataFrame:
    """Allocate one zero-filled dataframe for parser block construction."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def build_oecd_sut_from_frames(
    supply_frame: pd.DataFrame,
    use_frame: pd.DataFrame,
    useva_frame: pd.DataFrame,
    *,
    country: str,
    year: int,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    OECDSUTLayout,
]:
    """Transform OECD SDMX supply/use frames into split-native MARIO blocks."""
    geo = str(country).upper()
    activity_codes = _leaf_codes(sorted(use_frame["ACTIVITY"].dropna().unique().tolist()))
    product_codes = _leaf_codes(
        sorted(use_frame["PRODUCT"].dropna().unique().tolist()),
        prefix="CPA08_",
    )
    if not activity_codes or not product_codes:
        raise WrongInput("Could not detect the OECD SUT activity/product leaf axes.")

    activity_labels = list(activity_codes)
    commodity_labels = [code.removeprefix("CPA08_") for code in product_codes]
    final_demand_codes = [code for code, _label in OECD_SUT_FINAL_DEMAND]
    final_demand_labels = [label for _code, label in OECD_SUT_FINAL_DEMAND]
    va_codes = [code for code, _label in OECD_SUT_VA_ROWS]
    va_labels = [label for _code, label in OECD_SUT_VA_ROWS]
    vc_codes = [code for code, _label in OECD_SUT_VC_ROWS]
    vc_labels = [label for _code, label in OECD_SUT_VC_ROWS]
    factor_labels = vc_labels + [label for label in va_labels if label not in vc_labels]

    currency_values = sorted(
        set(supply_frame["CURRENCY"].dropna().astype(str))
        | set(use_frame["CURRENCY"].dropna().astype(str))
        | set(useva_frame["CURRENCY"].dropna().astype(str))
    )
    currency = currency_values[0] if currency_values else "-"
    layout = OECDSUTLayout(country=geo, year=int(year), currency=currency)

    activity_axis = _three_level_index(geo, _MASTER_INDEX["a"], activity_labels)
    commodity_axis = _three_level_index(geo, _MASTER_INDEX["c"], commodity_labels)
    final_demand_axis = _three_level_index(geo, _MASTER_INDEX["n"], final_demand_labels)
    factor_axis = pd.Index(factor_labels, name=None)
    satellite_axis = pd.Index([OECD_ICIO_SATELLITE_PLACEHOLDER], name=None)

    supply_subset = supply_frame[
        (supply_frame["TRANSACTION"] == "P1")
        & (supply_frame["VALUATION"] == "B")
        & (supply_frame["PRICE_BASE"] == "V")
        & (supply_frame["ACTIVITY"].isin(activity_codes))
        & (supply_frame["PRODUCT"].isin(product_codes))
    ]
    supply_matrix = supply_subset.pivot_table(
        index="ACTIVITY",
        columns="PRODUCT",
        values="OBS_VALUE",
        aggfunc="sum",
        fill_value=0.0,
    ).reindex(index=activity_codes, columns=product_codes, fill_value=0.0)

    use_subset = use_frame[
        (use_frame["TRANSACTION"] == "P2")
        & (use_frame["PRICE_BASE"] == "V")
        & (use_frame["ACTIVITY"].isin(activity_codes))
        & (use_frame["PRODUCT"].isin(product_codes))
    ]
    use_matrix = use_subset.pivot_table(
        index="PRODUCT",
        columns="ACTIVITY",
        values="OBS_VALUE",
        aggfunc="sum",
        fill_value=0.0,
    ).reindex(index=product_codes, columns=activity_codes, fill_value=0.0)

    final_demand_subset = use_frame[
        (use_frame["TRANSACTION"].isin(final_demand_codes))
        & (use_frame["PRICE_BASE"] == "V")
        & (use_frame["PRODUCT"].isin(product_codes))
    ]
    final_demand_matrix = final_demand_subset.pivot_table(
        index="PRODUCT",
        columns="TRANSACTION",
        values="OBS_VALUE",
        aggfunc="sum",
        fill_value=0.0,
    ).reindex(index=product_codes, columns=final_demand_codes, fill_value=0.0)

    va_subset = useva_frame[
        (useva_frame["TRANSACTION"].isin(va_codes))
        & (useva_frame["PRICE_BASE"] == "V")
        & (useva_frame["ACTIVITY"].isin(activity_codes))
    ]
    va_matrix = va_subset.pivot_table(
        index="TRANSACTION",
        columns="ACTIVITY",
        values="OBS_VALUE",
        aggfunc="sum",
        fill_value=0.0,
    ).reindex(index=va_codes, columns=activity_codes, fill_value=0.0)

    vc_subset = supply_frame[
        (supply_frame["TRANSACTION"].isin(vc_codes))
        & (supply_frame["PRICE_BASE"] == "V")
        & (supply_frame["PRODUCT"].isin(product_codes))
    ]
    vc_matrix = vc_subset.pivot_table(
        index="TRANSACTION",
        columns="PRODUCT",
        values="OBS_VALUE",
        aggfunc="sum",
        fill_value=0.0,
    ).reindex(index=vc_codes, columns=product_codes, fill_value=0.0)

    if not use_frame[
        (use_frame["TRANSACTION"] == "P6A")
        & (use_frame["PRICE_BASE"] == "V")
        & (use_frame["PRODUCT"].isin(product_codes))
        & (use_frame["OBS_VALUE"] != 0)
    ].empty:
        log_time(
            logger,
            "Parser: OECD SUT reports non-zero P6A re-exports. They are not stored as a separate Y column because P6 already contains total exports.",
            "debug",
        )

    S = supply_matrix.copy()
    S.index = activity_axis
    S.columns = commodity_axis
    S = S.astype(float)

    U = use_matrix.copy()
    U.index = commodity_axis
    U.columns = activity_axis
    U = U.astype(float)

    Yc = final_demand_matrix.rename(columns=dict(OECD_SUT_FINAL_DEMAND))
    Yc.index = commodity_axis
    Yc.columns = final_demand_axis
    Yc = Yc.astype(float)

    Ya = _zero_frame(activity_axis, final_demand_axis)

    Va = _zero_frame(factor_axis, activity_axis)
    for code, label in OECD_SUT_VA_ROWS:
        Va.loc[label, :] = va_matrix.loc[code].to_numpy()
    Va = Va.astype(float)

    Vc = _zero_frame(factor_axis, commodity_axis)
    for code, label in OECD_SUT_VC_ROWS:
        Vc.loc[label, :] = vc_matrix.loc[code].to_numpy()
    Vc = Vc.astype(float)

    Ea = _zero_frame(satellite_axis, activity_axis)
    Ec = _zero_frame(satellite_axis, commodity_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

    indexes = {
        "r": {"main": [geo]},
        "a": {"main": activity_labels},
        "c": {"main": commodity_labels},
        "f": {"main": factor_labels},
        "k": {"main": list(satellite_axis)},
        "n": {"main": final_demand_labels},
        "s": {"main": activity_labels + commodity_labels},
    }
    units = {
        _MASTER_INDEX["a"]: pd.DataFrame({"unit": [currency] * len(activity_labels)}, index=activity_labels),
        _MASTER_INDEX["c"]: pd.DataFrame({"unit": [currency] * len(commodity_labels)}, index=commodity_labels),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": [currency] * len(factor_labels)}, index=factor_labels),
        _MASTER_INDEX["k"]: pd.DataFrame({"unit": ["-"]}, index=[OECD_ICIO_SATELLITE_PLACEHOLDER]),
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

    commodity_balance = (S.sum(axis=0) + Vc.sum(axis=0) - U.sum(axis=1) - Yc.sum(axis=1)).abs().max()
    activity_balance = (U.sum(axis=0) + Va.sum(axis=0) - S.sum(axis=1)).abs().max()
    log_time(
        logger,
        (
            "Parser: OECD SUT payload ready with shapes "
            f"S={S.shape}, U={U.shape}, Yc={Yc.shape}, Va={Va.shape}, Vc={Vc.shape}; "
            f"commodity_diff={commodity_balance}, activity_diff={activity_balance}."
        ),
        "info",
    )
    return matrices, indexes, units, layout


def parse_oecd_sut_sdmx(
    *,
    country: str,
    year: int,
    timeout: int = 60,
    session: requests.Session | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    OECDSUTLayout,
]:
    """Download and parse one OECD SUT payload through the official SDMX API."""
    supply_frame = _read_sdmx_csv(
        _SUPPLY_DATAFLOW,
        country=country,
        year=year,
        timeout=timeout,
        session=session,
    )
    use_frame = _read_sdmx_csv(
        _USEPP_DATAFLOW,
        country=country,
        year=year,
        timeout=timeout,
        session=session,
    )
    useva_frame = _read_sdmx_csv(
        _USEVA_DATAFLOW,
        country=country,
        year=year,
        timeout=timeout,
        session=session,
    )
    return build_oecd_sut_from_frames(
        supply_frame,
        use_frame,
        useva_frame,
        country=country,
        year=year,
    )
