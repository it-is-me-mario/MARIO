"""Direct file-based parser for OECD ICIO CSV bundles."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from pathlib import Path
import re

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    OECD_ICIO_FACTOR_ROWS,
    OECD_ICIO_FACTOR_UNIT,
    OECD_ICIO_FINAL_DEMAND_CODES,
    OECD_ICIO_SATELLITE_PLACEHOLDER,
    OECD_ICIO_SATELLITE_UNIT,
    OECD_ICIO_SOURCE,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_YEAR_FILE_RE = re.compile(r"^(?P<year>\d{4})(?:_SML)?\.csv$", flags=re.IGNORECASE)
_EXTENDED_RE = re.compile(r"(?:^|[_ -])EXT(?:$|[_ -])|extended", flags=re.IGNORECASE)
_REGULAR_RE = re.compile(r"(?:^|[_ -])REG(?:$|[_ -])|regular|_SML(?:$|[_ -])", flags=re.IGNORECASE)
_ICIO_REGION_AGGREGATES = {
    "CN1": "CHN",
    "CN2": "CHN",
    "MX1": "MEX",
    "MX2": "MEX",
}


@dataclass(frozen=True)
class OECDICIOLayout:
    """Filesystem layout and metadata for one OECD ICIO CSV file."""

    root: Path
    data_path: Path
    year: int
    edition: str | None = None
    notes: tuple[str, ...] = ()

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        suffix = f" {self.edition}" if self.edition else ""
        return f"OECD ICIO {self.year}{suffix}"

    @property
    def price(self) -> str | None:
        """Return the price metadata stored in MARIO."""
        return None

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        if self.edition is None:
            return OECD_ICIO_SOURCE
        return f"{OECD_ICIO_SOURCE} ({self.edition} ICIO)"


def _infer_edition(path: Path) -> str | None:
    """Infer whether a local OECD ICIO bundle is regular or extended."""
    for candidate in [path, *path.parents]:
        name = candidate.name
        if _EXTENDED_RE.search(name):
            return "extended"
        if _REGULAR_RE.search(name):
            return "regular"
    return None


def detect_oecd_icio_layout(path: str | Path, *, year: int | None = None) -> OECDICIOLayout:
    """Resolve the OECD ICIO CSV file used for one parse request."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    if source.is_file():
        if source.suffix.lower() != ".csv":
            raise WrongInput("OECD ICIO parsing expects a local .csv file or a directory containing yearly .csv files.")
        match = _YEAR_FILE_RE.match(source.name)
        if match is None:
            raise WrongInput("OECD ICIO files should be named <year>.csv or <year>_SML.csv.")
        parsed_year = int(match.group("year"))
        if year is not None and parsed_year != year:
            raise WrongInput(
                f"The selected OECD ICIO file contains year {parsed_year}, not {year}."
            )
        return OECDICIOLayout(
            root=source.parent,
            data_path=source,
            year=parsed_year,
            edition=_infer_edition(source.parent),
        )

    candidates = sorted(
        child
        for child in source.rglob("*.csv")
        if child.is_file() and _YEAR_FILE_RE.match(child.name)
    )
    if not candidates:
        raise WrongInput("No OECD ICIO yearly csv file was found in the selected directory.")

    if year is not None:
        candidates = [
            child for child in candidates if int(_YEAR_FILE_RE.match(child.name).group("year")) == year
        ]
        if not candidates:
            raise WrongInput(f"No OECD ICIO csv file was found for year {year}.")

    if len(candidates) > 1:
        years = sorted(int(_YEAR_FILE_RE.match(child.name).group("year")) for child in candidates)
        raise WrongInput(
            "More than one OECD ICIO csv file matches the selected directory. "
            f"Please specify year or point to one file. Available years: {years}"
        )

    return detect_oecd_icio_layout(candidates[0], year=year)


def _read_oecd_icio_frame(path: Path) -> pd.DataFrame:
    """Read one OECD ICIO csv file into a dense numeric dataframe."""
    log_time(logger, f"Parser: reading OECD ICIO file {path.name}.", "info")
    frame = pd.read_csv(path, index_col=0, low_memory=False)
    frame.index = frame.index.astype(str)
    frame.columns = frame.columns.astype(str)

    missing = int(frame.isna().sum().sum())
    if missing:
        log_time(
            logger,
            f"Parser: OECD ICIO file contains {missing} missing values; filling them with zero.",
            "debug",
        )
    frame = frame.fillna(0.0).astype(float)
    return frame


def _split_regional_code(code: str) -> tuple[str, str]:
    """Split one OECD code into region prefix and item suffix."""
    if "_" not in code:
        raise WrongFormat(f"Expected a regional OECD code with one underscore, got {code!r}.")
    region, item = code.split("_", 1)
    return region, item


def _remap_oecd_icio_code(code: str) -> str:
    """Collapse OECD split-country labels onto their aggregate region code."""
    if "_" not in code:
        return code
    region, item = _split_regional_code(code)
    return f"{_ICIO_REGION_AGGREGATES.get(region, region)}_{item}"


def _aggregate_oecd_icio_split_regions(
    frame: pd.DataFrame,
    layout: OECDICIOLayout,
) -> tuple[pd.DataFrame, OECDICIOLayout]:
    """Aggregate OECD split-country ICIO labels such as CN1/CN2 and MX1/MX2."""
    remapped_index = [_remap_oecd_icio_code(label) for label in frame.index]
    remapped_columns = [_remap_oecd_icio_code(label) for label in frame.columns]

    changed_regions = sorted(
        {
            original.split("_", 1)[0]
            for original, remapped in zip(frame.index.tolist(), remapped_index)
            if original != remapped and "_" in original
        }
        | {
            original.split("_", 1)[0]
            for original, remapped in zip(frame.columns.tolist(), remapped_columns)
            if original != remapped and "_" in original
        }
    )
    if not changed_regions:
        return frame, layout

    aggregated = frame.copy()
    aggregated.index = pd.Index(remapped_index)
    aggregated.columns = pd.Index(remapped_columns)
    aggregated = aggregated.groupby(level=0, sort=False).sum()
    aggregated = aggregated.T.groupby(level=0, sort=False).sum().T

    notes = list(layout.notes)
    notes.append(
        "OECD ICIO split-country labels CN1/CN2 and MX1/MX2 were aggregated into CHN and MEX."
    )
    log_time(
        logger,
        (
            "Parser: aggregating OECD ICIO split-country regions "
            f"{changed_regions} into their CHN/MEX totals."
        ),
        "info",
    )
    return aggregated, replace(layout, notes=tuple(notes))


def _regional_axis(codes: list[str], *, level_code: str) -> tuple[list[str], list[str], pd.MultiIndex]:
    """Build the canonical MARIO axis for OECD sector or final-demand codes."""
    parsed = [_split_regional_code(code) for code in codes]
    regions = [region for region, _ in parsed]
    items = [item for _, item in parsed]
    axis = pd.MultiIndex.from_arrays(
        [
            regions,
            [_MASTER_INDEX[level_code]] * len(parsed),
            items,
        ]
    )
    return regions, items, axis


def _zero_frame(index, columns) -> pd.DataFrame:
    """Allocate a zero-filled dataframe with the given index and columns."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def parse_oecd_icio(
    path: str | Path,
    *,
    year: int | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], OECDICIOLayout]:
    """Parse one OECD ICIO CSV file into canonical MARIO IOT blocks."""
    layout = detect_oecd_icio_layout(path, year=year)
    frame = _read_oecd_icio_frame(layout.data_path)
    frame, layout = _aggregate_oecd_icio_split_regions(frame, layout)

    all_columns = frame.columns.tolist()
    all_rows = frame.index.tolist()

    sector_columns = [
        code
        for code in all_columns
        if code != "OUT" and _split_regional_code(code)[1] not in set(OECD_ICIO_FINAL_DEMAND_CODES)
    ]
    final_demand_columns = [
        code
        for code in all_columns
        if code != "OUT" and _split_regional_code(code)[1] in set(OECD_ICIO_FINAL_DEMAND_CODES)
    ]
    factor_rows = [label for label in all_rows if label in OECD_ICIO_FACTOR_ROWS]
    sector_rows = [label for label in all_rows if label not in set(factor_rows) | {"OUT"}]

    if not sector_columns:
        raise WrongFormat("Could not detect the OECD ICIO inter-industry columns.")
    if not final_demand_columns:
        raise WrongFormat("Could not detect the OECD ICIO final-demand columns.")
    missing_factors = [label for label in OECD_ICIO_FACTOR_ROWS if label not in factor_rows]
    if missing_factors:
        raise WrongFormat(
            f"The OECD ICIO file is missing required factor rows: {missing_factors}."
        )
    if set(sector_rows) != set(sector_columns):
        raise WrongFormat(
            "OECD ICIO sector rows and sector columns do not describe the same regional-sector axis."
        )

    # Align rows and columns on one shared sector ordering so downstream
    # computations see a square Z block with a deterministic axis order.
    sector_codes = sector_rows
    sector_columns = sector_rows

    _, sector_items, sector_axis = _regional_axis(sector_codes, level_code="s")
    _, final_demand_items, final_demand_axis = _regional_axis(
        final_demand_columns,
        level_code="n",
    )
    factor_axis = pd.Index(factor_rows, name=None)
    satellite_axis = pd.Index([OECD_ICIO_SATELLITE_PLACEHOLDER], name=None)

    Z = frame.loc[sector_codes, sector_columns].copy()
    Z.index = sector_axis
    Z.columns = sector_axis

    Y = frame.loc[sector_codes, final_demand_columns].copy()
    Y.index = sector_axis
    Y.columns = final_demand_axis

    V = frame.loc[factor_rows, sector_columns].copy()
    V.index = factor_axis
    V.columns = sector_axis

    E = _zero_frame(satellite_axis, sector_axis)
    EY = _zero_frame(satellite_axis, final_demand_axis)

    region_codes = list(dict.fromkeys(region for region, _ in map(_split_regional_code, sector_codes)))
    final_demand_codes = list(dict.fromkeys(final_demand_items))

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
    units = {
        _MASTER_INDEX["s"]: pd.DataFrame(
            {"unit": [OECD_ICIO_FACTOR_UNIT] * len(dict.fromkeys(sector_items))},
            index=pd.Index(list(dict.fromkeys(sector_items)), name=None),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [OECD_ICIO_FACTOR_UNIT] * len(factor_axis)},
            index=factor_axis,
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": [OECD_ICIO_SATELLITE_UNIT]},
            index=satellite_axis,
        ),
    }
    indeces = {
        "r": {"main": region_codes},
        "s": {"main": list(dict.fromkeys(sector_items))},
        "f": {"main": list(factor_axis)},
        "k": {"main": list(satellite_axis)},
        "n": {"main": final_demand_codes},
    }

    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: OECD ICIO parsed with "
            f"{len(region_codes)} sector regions, "
            f"{len(indeces['s']['main'])} sectors, "
            f"{len(final_demand_axis)} final-demand columns and "
            f"{len(factor_axis)} factor rows."
        ),
        "info",
    )
    return matrices, indeces, units, layout
