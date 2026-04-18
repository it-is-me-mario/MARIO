"""Parsers for OECD national Input-Output total-table CSV files."""

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
    OECD_ICIO_SATELLITE_PLACEHOLDER,
    OECD_ICIO_SATELLITE_UNIT,
    OECD_IOT_SOURCE,
    OECD_IOT_TOTAL_FACTOR_ROWS,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_OECD_IOT_TOTAL_RE = re.compile(
    r"^(?P<country>[A-Z]{3})(?P<year>\d{4})ttl\.csv$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class OECDIOTTotalLayout:
    """Filesystem layout and metadata for one OECD national IOT total table."""

    root: Path
    data_path: Path
    country: str
    year: int
    notes: tuple[str, ...] = ()

    @property
    def dataset_name(self) -> str:
        """Return a compact default dataset label for MARIO metadata."""
        return f"OECD IOT {self.country} {self.year}"

    @property
    def price(self) -> str:
        """Return the price metadata recorded in MARIO."""
        return "Current prices"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in metadata."""
        return OECD_IOT_SOURCE


def detect_oecd_iot_total_layout(
    path: str | Path,
    *,
    year: int | None = None,
    country: str | None = None,
) -> OECDIOTTotalLayout:
    """Resolve one OECD national total-table csv file from a file or directory."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    selected_country = None if country is None else str(country).upper()

    if source.is_file():
        match = _OECD_IOT_TOTAL_RE.match(source.name)
        if match is None:
            raise WrongInput(
                "OECD national total tables should be named like CZE2014ttl.csv."
            )
        parsed_country = str(match.group("country")).upper()
        parsed_year = int(match.group("year"))
        if selected_country is not None and parsed_country != selected_country:
            raise WrongInput(
                f"The selected OECD IOT file contains country {parsed_country}, not {selected_country}."
            )
        if year is not None and parsed_year != int(year):
            raise WrongInput(
                f"The selected OECD IOT file contains year {parsed_year}, not {year}."
            )
        return OECDIOTTotalLayout(
            root=source.parent,
            data_path=source,
            country=parsed_country,
            year=parsed_year,
        )

    candidates = []
    for child in source.rglob("*.csv"):
        if not child.is_file():
            continue
        match = _OECD_IOT_TOTAL_RE.match(child.name)
        if match is None:
            continue
        parsed_country = str(match.group("country")).upper()
        parsed_year = int(match.group("year"))
        if selected_country is not None and parsed_country != selected_country:
            continue
        if year is not None and parsed_year != int(year):
            continue
        candidates.append(child)

    if not candidates:
        raise WrongInput(
            "No OECD national total-table csv file was found in the selected directory."
        )

    if len(candidates) > 1:
        available = sorted(child.name for child in candidates)
        raise WrongInput(
            "More than one OECD national total-table csv matches the selected directory. "
            f"Please specify country/year or point to one file. Available files: {available}"
        )

    return detect_oecd_iot_total_layout(candidates[0], year=year, country=selected_country)


def _read_oecd_iot_total_frame(path: Path) -> pd.DataFrame:
    """Read one OECD national total-table csv into a numeric dataframe."""
    log_time(logger, f"Parser: reading OECD IOT file {path.name}.", "info")
    frame = pd.read_csv(path, index_col=0, low_memory=False)
    frame.index = frame.index.astype(str)
    frame.columns = frame.columns.astype(str)
    missing = int(frame.isna().sum().sum())
    if missing:
        log_time(
            logger,
            f"Parser: OECD IOT file contains {missing} missing values; filling them with zero.",
            "debug",
        )
    return frame.fillna(0.0).astype(float)


def parse_oecd_iot_total(
    path: str | Path,
    *,
    year: int | None = None,
    country: str | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    OECDIOTTotalLayout,
]:
    """Parse one OECD national input-output total table into MARIO IOT blocks."""
    layout = detect_oecd_iot_total_layout(path, year=year, country=country)
    frame = _read_oecd_iot_total_frame(layout.data_path)

    sector_rows = [label for label in frame.index if label.startswith("TTL_") and label != "TTL_INT_FNL"]
    if not sector_rows:
        raise WrongFormat("Could not detect sector rows in the OECD national IOT total table.")
    sector_codes = [label.removeprefix("TTL_") for label in sector_rows]
    sector_columns = [code for code in sector_codes if code in frame.columns]
    if set(sector_columns) != set(sector_codes):
        raise WrongFormat(
            "The OECD national IOT total table does not expose the same sector axis on rows and columns."
        )
    sector_rows = [f"TTL_{code}" for code in sector_columns]

    final_demand_columns = [
        column for column in frame.columns if column not in set(sector_columns) | {"TOTAL"}
    ]
    if not final_demand_columns:
        raise WrongFormat("Could not detect final-demand columns in the OECD national IOT total table.")

    missing_factor_rows = [label for label in OECD_IOT_TOTAL_FACTOR_ROWS if label not in frame.index]
    if missing_factor_rows:
        raise WrongFormat(
            f"The OECD national IOT total table is missing required rows: {missing_factor_rows}."
        )

    sector_axis = pd.MultiIndex.from_arrays(
        [
            [layout.country] * len(sector_columns),
            [_MASTER_INDEX["s"]] * len(sector_columns),
            sector_columns,
        ]
    )
    final_demand_axis = pd.MultiIndex.from_arrays(
        [
            [layout.country] * len(final_demand_columns),
            [_MASTER_INDEX["n"]] * len(final_demand_columns),
            final_demand_columns,
        ]
    )
    factor_axis = pd.Index(list(OECD_IOT_TOTAL_FACTOR_ROWS), name=None)
    satellite_axis = pd.Index([OECD_ICIO_SATELLITE_PLACEHOLDER], name=None)

    Z = frame.loc[sector_rows, sector_columns].copy()
    Z.index = sector_axis
    Z.columns = sector_axis

    Y = frame.loc[sector_rows, final_demand_columns].copy()
    Y.index = sector_axis
    Y.columns = final_demand_axis

    V = frame.loc[list(OECD_IOT_TOTAL_FACTOR_ROWS), sector_columns].copy()
    V.index = factor_axis
    V.columns = sector_axis

    E = pd.DataFrame(
        np.zeros((len(satellite_axis), len(sector_axis))),
        index=satellite_axis,
        columns=sector_axis,
    )
    EY = pd.DataFrame(
        np.zeros((len(satellite_axis), len(final_demand_axis))),
        index=satellite_axis,
        columns=final_demand_axis,
    )

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
    units = {
        _MASTER_INDEX["s"]: pd.DataFrame(
            {"unit": ["current million USD"] * len(sector_columns)},
            index=pd.Index(sector_columns, name=None),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": ["current million USD"] * len(factor_axis)},
            index=factor_axis,
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": [OECD_ICIO_SATELLITE_UNIT]},
            index=satellite_axis,
        ),
    }
    indexes = {
        "r": {"main": [layout.country]},
        "s": {"main": list(sector_columns)},
        "f": {"main": list(factor_axis)},
        "k": {"main": list(satellite_axis)},
        "n": {"main": list(final_demand_columns)},
    }

    rename_index(matrices["baseline"])

    row_total_diff = None
    if "TOTAL" in frame.columns:
        row_total_diff = (
            frame.loc[sector_rows, sector_columns + final_demand_columns].sum(axis=1)
            - frame.loc[sector_rows, "TOTAL"]
        ).abs().max()
    column_total_diff = None
    if "OUTPUT" in frame.index:
        column_total_diff = (
            frame.loc[sector_rows + list(OECD_IOT_TOTAL_FACTOR_ROWS), sector_columns].sum(axis=0)
            - frame.loc["OUTPUT", sector_columns]
        ).abs().max()
    if row_total_diff is not None or column_total_diff is not None:
        log_time(
            logger,
            (
                "Parser: OECD IOT total-table consistency checks "
                f"row_diff={row_total_diff}, col_diff={column_total_diff}."
            ),
            "debug",
        )

    log_time(
        logger,
        (
            "Parser: OECD national IOT parsed with "
            f"{len(sector_columns)} sectors, {len(final_demand_columns)} final-demand columns "
            f"and {len(factor_axis)} factor rows."
        ),
        "info",
    )

    return matrices, indexes, units, layout
