"""Direct Eurostat SUT parser backed by the official SDMX API."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
import logging

import numpy as np
import pandas as pd
import requests

from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    EUROSTAT_SATELLITE_PLACEHOLDER,
    EUROSTAT_SDMX_BASE_URL,
    EUROSTAT_SOURCE,
    EUROSTAT_SUT_ACTIVITY_CODES,
    EUROSTAT_SUT_ACTIVITY_LABELS,
    EUROSTAT_SUT_COMMODITY_CODES,
    EUROSTAT_SUT_COMMODITY_LABELS,
    EUROSTAT_SUT_DATAFLOWS,
    EUROSTAT_SUT_FACTOR_ROWS,
    EUROSTAT_SUT_FINAL_DEMAND,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EurostatSUTLayout:
    """Resolved metadata for one Eurostat SUT SDMX pull."""

    country: str
    year: int
    unit: str

    @property
    def dataset_name(self) -> str:
        """Return a compact default name for one Eurostat SUT dataset."""
        return f"Eurostat SUT {self.country} {self.year}"

    @property
    def price(self) -> str:
        """Return the price system label recorded in MARIO metadata."""
        return "Current prices"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in metadata."""
        return EUROSTAT_SOURCE


def _sdmx_key(country: str, unit: str) -> str:
    """Return the Eurostat SDMX wildcard key for one country/unit slice."""
    return f"A.{unit}.TOTAL...{country}"


def _read_sdmx_csv(
    dataflow: str,
    *,
    country: str,
    year: int,
    unit: str,
    timeout: int = 60,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Download one Eurostat SDMX-CSV slice and return it as a dataframe."""
    url = f"{EUROSTAT_SDMX_BASE_URL}/{dataflow}/{_sdmx_key(country, unit)}"
    params = {
        "startPeriod": year,
        "endPeriod": year,
        "format": "SDMX-CSV",
    }
    log_time(logger, f"Parser: requesting Eurostat {dataflow} for {country} {year} {unit}.", "info")
    log_time(logger, f"Parser: SDMX request {url} with params {params}.", "debug")

    response = (session or requests).get(url, params=params, timeout=timeout)
    response.raise_for_status()

    frame = pd.read_csv(StringIO(response.text))
    if frame.empty:
        raise WrongInput(
            f"Eurostat returned no observations for {dataflow} ({country}, {year}, {unit})."
        )

    frame["OBS_VALUE"] = pd.to_numeric(frame["OBS_VALUE"], errors="coerce").fillna(0.0)
    flagged = 0
    for column in ("OBS_FLAG", "CONF_STATUS"):
        if column in frame:
            flagged += int(frame[column].notna().sum())
    if flagged:
        log_time(
            logger,
            f"Parser: Eurostat {dataflow} contains {flagged} flagged/confidential observations.",
            "debug",
        )

    log_time(
        logger,
        f"Parser: downloaded {len(frame)} rows from Eurostat {dataflow}.",
        "debug",
    )
    return frame


def _pivot_observations(
    frame: pd.DataFrame,
    *,
    index: str,
    columns: str,
    row_codes: list[str],
    column_codes: list[str],
    label: str,
) -> pd.DataFrame:
    """Pivot one SDMX slice into a dense matrix ordered by canonical codes."""
    subset = frame[[index, columns, "OBS_VALUE"]].copy()
    pivot = subset.pivot_table(
        index=index,
        columns=columns,
        values="OBS_VALUE",
        aggfunc="sum",
        fill_value=0.0,
    )

    missing_rows = [code for code in row_codes if code not in pivot.index]
    missing_columns = [code for code in column_codes if code not in pivot.columns]
    if missing_rows:
        log_time(
            logger,
            f"Parser: {label} is missing {len(missing_rows)} expected rows; padding zeros.",
            "debug",
        )
    if missing_columns:
        log_time(
            logger,
            f"Parser: {label} is missing {len(missing_columns)} expected columns; padding zeros.",
            "debug",
        )

    return pivot.reindex(index=row_codes, columns=column_codes, fill_value=0.0)


def _aggregate_final_demand(use_block: pd.DataFrame) -> pd.DataFrame:
    """Aggregate detailed Eurostat final-demand columns to MARIO's compact triad."""
    aggregated: dict[str, pd.Series] = {}
    for spec in EUROSTAT_SUT_FINAL_DEMAND:
        preferred = spec["preferred"]
        fallback = [code for code in spec["fallback"] if code in use_block.columns]
        label = spec["label"]
        if preferred in use_block.columns:
            aggregated[label] = use_block[preferred]
        elif fallback:
            aggregated[label] = use_block.loc[:, fallback].sum(axis=1)
        else:
            log_time(
                logger,
                f"Parser: missing final-demand code {preferred}; filling {label} with zeros.",
                "debug",
            )
            aggregated[label] = pd.Series(0.0, index=use_block.index)
    return pd.DataFrame(aggregated, index=use_block.index)


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
    """Return a float zero-filled dataframe for parser block construction."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def _build_units(
    *,
    activity_labels: list[str],
    commodity_labels: list[str],
    factor_labels: list[str],
    unit: str,
) -> dict[str, pd.DataFrame]:
    """Build MARIO unit tables for the compact Eurostat SUT payload."""
    return {
        _MASTER_INDEX["a"]: pd.DataFrame({"unit": [unit] * len(activity_labels)}, index=activity_labels),
        _MASTER_INDEX["c"]: pd.DataFrame({"unit": [unit] * len(commodity_labels)}, index=commodity_labels),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": [unit] * len(factor_labels)}, index=factor_labels),
        _MASTER_INDEX["k"]: pd.DataFrame({"unit": ["-"]}, index=[EUROSTAT_SATELLITE_PLACEHOLDER]),
    }


def build_eurostat_sut_from_frames(
    supply_frame: pd.DataFrame,
    use_frame: pd.DataFrame,
    *,
    country: str,
    year: int,
    unit: str,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    EurostatSUTLayout,
]:
    """Transform Eurostat SDMX supply/use frames into split-native MARIO blocks."""
    geo = str(country).upper()
    layout = EurostatSUTLayout(country=geo, year=int(year), unit=str(unit))

    activity_labels = [EUROSTAT_SUT_ACTIVITY_LABELS[code] for code in EUROSTAT_SUT_ACTIVITY_CODES]
    commodity_labels = [EUROSTAT_SUT_COMMODITY_LABELS[code] for code in EUROSTAT_SUT_COMMODITY_CODES]
    factor_codes = [code for code, _label in EUROSTAT_SUT_FACTOR_ROWS]
    factor_labels = [label for _code, label in EUROSTAT_SUT_FACTOR_ROWS]
    final_demand_labels = [spec["label"] for spec in EUROSTAT_SUT_FINAL_DEMAND]

    supply_matrix = _pivot_observations(
        supply_frame,
        index="ind_impv",
        columns="prd_amo",
        row_codes=EUROSTAT_SUT_ACTIVITY_CODES + ["P7"],
        column_codes=EUROSTAT_SUT_COMMODITY_CODES,
        label="Eurostat supply",
    )
    use_matrix = _pivot_observations(
        use_frame,
        index="prd_ava",
        columns="ind_use",
        row_codes=EUROSTAT_SUT_COMMODITY_CODES + [code for code in factor_codes if code != "P7"],
        column_codes=EUROSTAT_SUT_ACTIVITY_CODES
        + [spec["preferred"] for spec in EUROSTAT_SUT_FINAL_DEMAND]
        + [
            code
            for spec in EUROSTAT_SUT_FINAL_DEMAND
            for code in spec["fallback"]
        ],
        label="Eurostat use",
    )

    activity_axis = _three_level_index(geo, _MASTER_INDEX["a"], activity_labels)
    commodity_axis = _three_level_index(geo, _MASTER_INDEX["c"], commodity_labels)
    final_demand_axis = _three_level_index(geo, _MASTER_INDEX["n"], final_demand_labels)
    factor_axis = pd.Index(factor_labels, name=None)
    satellite_axis = pd.Index([EUROSTAT_SATELLITE_PLACEHOLDER], name=None)

    S = supply_matrix.loc[EUROSTAT_SUT_ACTIVITY_CODES, EUROSTAT_SUT_COMMODITY_CODES].copy()
    S.index = activity_axis
    S.columns = commodity_axis
    S = S.astype(float)

    U = use_matrix.loc[EUROSTAT_SUT_COMMODITY_CODES, EUROSTAT_SUT_ACTIVITY_CODES].copy()
    U.index = commodity_axis
    U.columns = activity_axis
    U = U.astype(float)

    Yc_raw = use_matrix.loc[
        EUROSTAT_SUT_COMMODITY_CODES,
        [code for code in use_matrix.columns if code not in EUROSTAT_SUT_ACTIVITY_CODES],
    ]
    Yc = _aggregate_final_demand(Yc_raw)
    Yc.index = commodity_axis
    Yc.columns = final_demand_axis
    Yc = Yc.astype(float)

    Ya = _zero_frame(activity_axis, final_demand_axis)

    Va_raw = use_matrix.loc[
        [code for code in factor_codes if code != "P7"],
        EUROSTAT_SUT_ACTIVITY_CODES,
    ]
    Va = Va_raw.rename(index=dict(EUROSTAT_SUT_FACTOR_ROWS))
    Va = Va.reindex(index=factor_labels, fill_value=0.0)
    Va.columns = activity_axis
    Va.index = factor_axis
    Va = Va.astype(float)

    imports_by_commodity = supply_matrix.loc[["P7"], EUROSTAT_SUT_COMMODITY_CODES].copy()
    imports_by_commodity.index = [dict(EUROSTAT_SUT_FACTOR_ROWS)["P7"]]
    Vc = _zero_frame(factor_axis, commodity_axis)
    if not imports_by_commodity.empty:
        imports_by_commodity.columns = commodity_axis
        imports_by_commodity.index = pd.Index(imports_by_commodity.index.tolist(), name=None)
        Vc.loc[dict(EUROSTAT_SUT_FACTOR_ROWS)["P7"], :] = imports_by_commodity.iloc[0]
    Vc = Vc.astype(float)

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
    indexes = {
        "r": {"main": [geo]},
        "a": {"main": activity_labels},
        "c": {"main": commodity_labels},
        "f": {"main": factor_labels},
        "k": {"main": satellite_axis.tolist()},
        "n": {"main": final_demand_labels},
        "s": {"main": activity_labels + commodity_labels},
    }
    units = _build_units(
        activity_labels=activity_labels,
        commodity_labels=commodity_labels,
        factor_labels=factor_labels,
        unit=layout.unit,
    )

    log_time(
        logger,
        (
            "Parser: Eurostat SUT payload ready with shapes "
            f"S={S.shape}, U={U.shape}, Yc={Yc.shape}, Va={Va.shape}, Vc={Vc.shape}."
        ),
        "info",
    )
    return matrices, indexes, units, layout


def parse_eurostat_sut_sdmx(
    *,
    country: str,
    year: int,
    unit: str = "MIO_EUR",
    timeout: int = 60,
    session: requests.Session | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    EurostatSUTLayout,
]:
    """Download one Eurostat SUT via SDMX and convert it to MARIO blocks."""
    geo = str(country).upper()
    supply = _read_sdmx_csv(
        EUROSTAT_SUT_DATAFLOWS["supply"],
        country=geo,
        year=year,
        unit=unit,
        timeout=timeout,
        session=session,
    )
    use = _read_sdmx_csv(
        EUROSTAT_SUT_DATAFLOWS["use"],
        country=geo,
        year=year,
        unit=unit,
        timeout=timeout,
        session=session,
    )
    return build_eurostat_sut_from_frames(
        supply,
        use,
        country=geo,
        year=year,
        unit=unit,
    )
