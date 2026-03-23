"""Direct file-based parser for FIGARO supply and use table bundles."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
import logging
from pathlib import Path
import re
from zipfile import ZipFile

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    FIGARO_EXTENSION_PLACEHOLDER,
    FIGARO_FACTOR_UNIT,
    FIGARO_IOT_MODES,
    FIGARO_SATELLITE_UNIT,
    FIGARO_SOURCE,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_YEAR_RE = re.compile(r"_(?P<year>\d{4})(?:\.(?:zip|csv))$", flags=re.IGNORECASE)
_EDITION_RE = re.compile(
    r"(?P<kind>supply|use)_(?P<edition>[^_]+)_(?P<year>\d{4})\.(?:zip|csv)$",
    flags=re.IGNORECASE,
)
_IOT_RE = re.compile(
    r"io_(?P<variant>ind-by-ind|prod-by-prod)_(?P<edition>[^_]+)_(?P<year>\d{4})\.(?:zip|csv)$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class FigaroSUTLayout:
    """Filesystem layout and metadata for one FIGARO SUT bundle."""

    root: Path
    supply_path: Path
    use_path: Path
    year: int
    edition: str | None = None

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        suffix = f" {self.edition}" if self.edition else ""
        return f"FIGARO SUT {self.year}{suffix}"

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
    """Filesystem layout and metadata for one FIGARO IOT bundle."""

    root: Path
    iot_path: Path
    year: int
    mode: str
    edition: str | None = None

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        suffix = f" {self.edition}" if self.edition else ""
        return f"FIGARO IOT {self.year} {self.mode}{suffix}"

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


def _classify_candidate(path: Path) -> tuple[str, int | None, str | None] | None:
    """Classify one directory entry as a FIGARO ``supply`` or ``use`` file."""
    if not path.is_file() or path.suffix.lower() not in {".csv", ".zip"}:
        return None

    lower = path.name.lower()
    if "supply" in lower:
        kind = "supply"
    elif "use" in lower:
        kind = "use"
    else:
        return None

    year_match = _YEAR_RE.search(path.name)
    edition_match = _EDITION_RE.search(path.name)
    year = int(year_match.group("year")) if year_match else None
    edition = edition_match.group("edition") if edition_match else None
    return kind, year, edition


def _classify_iot_candidate(path: Path) -> tuple[str, int | None, str | None] | None:
    """Classify one directory entry as a FIGARO IOT file."""
    if not path.is_file() or path.suffix.lower() not in {".csv", ".zip"}:
        return None

    match = _IOT_RE.search(path.name.lower())
    if match is None:
        return None

    variant = match.group("variant")
    mode = "product" if variant == "prod-by-prod" else "industry"
    year = int(match.group("year"))
    edition = match.group("edition")
    return mode, year, edition


def _pick_one(paths: list[Path], *, label: str) -> Path:
    """Choose one preferred file among csv/zip duplicates for the same role."""
    if not paths:
        raise WrongInput(f"No FIGARO {label} file was found.")
    return sorted(paths, key=lambda item: (0 if item.suffix.lower() == ".csv" else 1, item.name))[0]


def detect_figaro_sut_layout(path: str | Path, *, year: int | None = None) -> FigaroSUTLayout:
    """Resolve the FIGARO supply/use files used for one SUT parse request."""
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise WrongInput("FIGARO parsing expects a directory containing supply and use files.")

    candidates: dict[str, dict[int | None, list[Path]]] = {"supply": {}, "use": {}}
    editions: dict[tuple[str, int | None], str | None] = {}
    for child in root.iterdir():
        parsed = _classify_candidate(child)
        if parsed is None:
            continue
        kind, parsed_year, edition = parsed
        candidates[kind].setdefault(parsed_year, []).append(child)
        editions[(kind, parsed_year)] = edition

    available_years = sorted(
        {parsed_year for mapping in candidates.values() for parsed_year in mapping if parsed_year is not None}
    )
    if year is None:
        if len(available_years) > 1:
            raise WrongInput(
                f"More than one FIGARO year is available in {root}. Please specify year."
            )
        if available_years:
            year = available_years[0]

    supply_candidates = candidates["supply"].get(year, [])
    use_candidates = candidates["use"].get(year, [])
    if not supply_candidates or not use_candidates:
        detail = f" for year {year}" if year is not None else ""
        raise WrongInput(f"Could not find both FIGARO supply and use files{detail}.")

    supply_path = _pick_one(supply_candidates, label="supply")
    use_path = _pick_one(use_candidates, label="use")
    if year is None:
        supply_year = _classify_candidate(supply_path)[1]
        use_year = _classify_candidate(use_path)[1]
        if supply_year != use_year:
            raise WrongInput("FIGARO supply and use files refer to different years.")
        year = supply_year
    if year is None:
        raise WrongInput("Could not infer the FIGARO reference year from the selected files.")

    edition = editions.get(("supply", year)) or editions.get(("use", year))
    layout = FigaroSUTLayout(
        root=root,
        supply_path=supply_path,
        use_path=use_path,
        year=year,
        edition=edition,
    )
    log_time(
        logger,
        (
            "Parser: detected FIGARO SUT layout "
            f"year={layout.year} edition={layout.edition or 'unknown'} "
            f"supply={layout.supply_path.name} use={layout.use_path.name}"
        ),
        "debug",
    )
    return layout


def detect_figaro_iot_layout(
    path: str | Path,
    *,
    year: int | None = None,
    mode: str = "auto",
) -> FigaroIOTLayout:
    """Resolve the FIGARO IOT file used for one parse request."""
    if mode not in FIGARO_IOT_MODES:
        raise WrongInput(f"FIGARO iot_mode should be one of {list(FIGARO_IOT_MODES)}.")

    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise WrongInput("FIGARO parsing expects a directory containing local FIGARO files.")

    candidates: dict[str, dict[int, list[Path]]] = {"product": {}, "industry": {}}
    editions: dict[tuple[str, int], str | None] = {}
    for child in root.iterdir():
        parsed = _classify_iot_candidate(child)
        if parsed is None:
            continue
        parsed_mode, parsed_year, edition = parsed
        candidates[parsed_mode].setdefault(parsed_year, []).append(child)
        editions[(parsed_mode, parsed_year)] = edition

    available_years = sorted(
        {parsed_year for mapping in candidates.values() for parsed_year in mapping}
    )
    if year is None:
        if len(available_years) > 1:
            raise WrongInput(
                f"More than one FIGARO IOT year is available in {root}. Please specify year."
            )
        if available_years:
            year = available_years[0]
    if year is None:
        raise WrongInput("Could not infer the FIGARO IOT reference year from the selected files.")

    if mode == "auto":
        if candidates["product"].get(year):
            if candidates["industry"].get(year):
                log_time(
                    logger,
                    (
                        "Parser: both FIGARO product and industry IOT files are present; "
                        "defaulting to product-by-product."
                    ),
                    "info",
                )
            mode = "product"
        elif candidates["industry"].get(year):
            mode = "industry"
        else:
            raise WrongInput(f"Could not find a FIGARO IOT file for year {year}.")

    matches = candidates[mode].get(year, [])
    if not matches:
        raise WrongInput(f"Could not find a FIGARO {mode} IOT file for year {year}.")

    iot_path = _pick_one(matches, label=f"{mode} IOT")
    layout = FigaroIOTLayout(
        root=root,
        iot_path=iot_path,
        year=year,
        mode=mode,
        edition=editions.get((mode, year)),
    )
    log_time(
        logger,
        (
            "Parser: detected FIGARO IOT layout "
            f"year={layout.year} mode={layout.mode} edition={layout.edition or 'unknown'} "
            f"file={layout.iot_path.name}"
        ),
        "debug",
    )
    return layout


@contextmanager
def _open_figaro_csv(path: Path):
    """Yield a readable handle for one FIGARO csv, zipped or extracted."""
    if path.suffix.lower() == ".zip":
        with ZipFile(path) as archive:
            members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(members) != 1:
                raise WrongInput(
                    f"Expected exactly one CSV inside {path.name}, found {len(members)}."
                )
            with archive.open(members[0]) as handle:
                yield handle
    else:
        with path.open("rb") as handle:
            yield handle


def _read_figaro_frame(path: Path) -> pd.DataFrame:
    """Read one FIGARO flat file into a tidy dataframe with canonical columns."""
    log_time(logger, f"Parser: reading FIGARO file {path.name}.", "info")
    with _open_figaro_csv(path) as header_handle:
        columns = pd.read_csv(header_handle, nrows=0).columns.tolist()

    try:
        row_column = next(column for column in columns if column.startswith("row"))
        col_column = next(column for column in columns if column.startswith("col"))
    except StopIteration as exc:
        raise WrongInput(f"Could not detect the FIGARO row/column code columns in {path.name}.") from exc

    required_columns = [
        "refArea",
        row_column,
        "counterpartArea",
        col_column,
        "obsValue",
    ]

    with _open_figaro_csv(path) as handle:
        frame = pd.read_csv(
            handle,
            usecols=required_columns,
            dtype={
                "refArea": "string",
                row_column: "string",
                "counterpartArea": "string",
                col_column: "string",
            },
        )

    frame = frame.rename(columns={row_column: "rowCode", col_column: "colCode"})
    frame["obsValue"] = pd.to_numeric(frame["obsValue"], errors="coerce").fillna(0.0)
    return frame


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
        log_time(logger, f"Parser: missing FIGARO {label} metadata for code {code}; keeping the raw code.", "debug")
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
    """Build the canonical factor index used for FIGARO ``Va`` rows."""
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
    path: str | Path,
    *,
    year: int | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], FigaroSUTLayout]:
    """Parse one FIGARO supply/use bundle into split-native MARIO SUT blocks."""
    layout = detect_figaro_sut_layout(path, year=year)
    metadata = load_figaro_metadata()

    region_codes_meta, region_labels = _label_map(metadata, level="r")
    commodity_codes_meta, commodity_labels = _label_map(metadata, level="c")
    activity_codes_meta, activity_labels = _label_map(metadata, level="a")
    factor_codes_meta, factor_labels = _label_map(metadata, level="f")
    final_demand_codes_meta, final_demand_labels = _label_map(metadata, level="n")

    supply = _read_figaro_frame(layout.supply_path)
    use = _read_figaro_frame(layout.use_path)

    region_codes = _ordered_present_codes(
        set(supply["refArea"].astype(str)).union(set(supply["counterpartArea"].astype(str))),
        region_codes_meta,
    )
    commodity_codes = _ordered_present_codes(
        set(supply["rowCode"].astype(str)).union(set(use.loc[use["refArea"] != "W2", "rowCode"].astype(str))),
        commodity_codes_meta,
    )
    activity_codes = _ordered_present_codes(
        set(supply["colCode"].astype(str)).union(set(use.loc[~use["colCode"].isin(final_demand_codes_meta), "colCode"].astype(str))),
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
        _MASTER_INDEX["a"]: pd.DataFrame({"unit": [FIGARO_FACTOR_UNIT] * len(activity_codes)}, index=activity_axis.unique(2)),
        _MASTER_INDEX["c"]: pd.DataFrame({"unit": [FIGARO_FACTOR_UNIT] * len(commodity_codes)}, index=commodity_axis.unique(2)),
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
            "Parser: FIGARO SUT parsed with "
            f"{len(region_codes)} regions, "
            f"{len(activity_codes)} activities, "
            f"{len(commodity_codes)} commodities, "
            f"{len(factor_codes)} factor rows."
        ),
        "info",
    )
    return matrices, indeces, units, layout


def parse_figaro_iot(
    path: str | Path,
    *,
    year: int | None = None,
    mode: str = "auto",
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], FigaroIOTLayout]:
    """Parse one FIGARO IOT bundle into canonical MARIO IOT blocks."""
    layout = detect_figaro_iot_layout(path, year=year, mode=mode)
    metadata = load_figaro_metadata()

    region_codes_meta, region_labels = _label_map(metadata, level="r")
    activity_codes_meta, activity_labels = _label_map(metadata, level="a")
    commodity_codes_meta, commodity_labels = _label_map(metadata, level="c")
    factor_codes_meta, factor_labels = _label_map(metadata, level="f")
    final_demand_codes_meta, final_demand_labels = _label_map(metadata, level="n")

    iot = _read_figaro_frame(layout.iot_path)
    sector_codes_meta = activity_codes_meta if layout.mode == "industry" else commodity_codes_meta
    sector_labels_meta = activity_labels if layout.mode == "industry" else commodity_labels
    sector_label_name = "activity" if layout.mode == "industry" else "commodity"

    region_codes = _ordered_present_codes(
        set(iot.loc[iot["refArea"] != "W2", "refArea"].astype(str)).union(
            set(iot["counterpartArea"].astype(str))
        ),
        region_codes_meta,
    )
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
            "Parser: FIGARO IOT parsed with "
            f"{len(region_codes)} regions, "
            f"{len(sector_codes)} sectors, "
            f"{len(factor_codes)} factor rows, "
            f"mode={layout.mode}."
        ),
        "info",
    )
    return matrices, indeces, units, layout
