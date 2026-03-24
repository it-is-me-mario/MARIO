"""Direct file-based parsers for WIOD 2016 multiregional Excel workbooks."""

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
    WIOD_FACTOR_LABELS,
    WIOD_FACTOR_ROWS,
    WIOD_FINAL_DEMAND_CODES,
    WIOD_MONETARY_UNIT,
    WIOD_SATELLITE_PLACEHOLDER,
    WIOD_SATELLITE_UNIT,
    WIOD_SOURCE,
    WIOD_SUT_FINAL_DEMAND_CODES,
    WIOD_SUT_FINAL_DEMAND_LABELS,
    WIOD_SUT_SUPPLY_TOTAL_COLUMNS,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_WIOD_IOT_FILE_RE = re.compile(r"^WIOT(?P<year>\d{4}).*_ROW\.xlsb$", flags=re.IGNORECASE)
_WIOD_SUT_FILE_RE = re.compile(r"^intsut(?P<year>\d{2})_nov16\.xlsb$", flags=re.IGNORECASE)
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

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        return self.data_path.stem

    @property
    def price(self) -> str:
        """Return the price metadata stored in MARIO."""
        return "Current prices"

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
) -> WIODLayout:
    """Resolve the WIOD 2016 multiregional workbook selected for one parse request."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    normalized_table = str(table).upper()
    if normalized_table == "IOT":
        pattern = _WIOD_IOT_FILE_RE
        description = "WIOT<year>_Nov16_ROW.xlsb"
        sheet_names_factory = lambda parsed_year: (str(parsed_year),)
    elif normalized_table == "SUT":
        pattern = _WIOD_SUT_FILE_RE
        description = "intsut<yy>_nov16.xlsb"
        sheet_names_factory = lambda parsed_year: (_WIOD_SUT_SUPPLY_SHEET, _WIOD_SUT_USE_SHEET)
    else:
        raise WrongInput("WIOD parsing supports only table='IOT' or table='SUT'.")

    def _parse_candidate(candidate: Path) -> WIODLayout:
        match = pattern.match(candidate.name)
        if match is None:
            raise WrongInput(
                "WIOD parsing currently supports only the WIOD 2016 multiregional "
                f"Excel workbook pattern {description}, not national tables or "
                "other spreadsheet layouts."
            )
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
            sheet_names=sheet_names_factory(parsed_year),
        )

    if source.is_file():
        return _parse_candidate(source)

    candidates = sorted(
        child for child in source.rglob("*.xlsb") if child.is_file() and pattern.match(child.name)
    )
    if not candidates:
        raise WrongInput(
            "No WIOD 2016 multiregional .xlsb workbook matching "
            f"{description} was found in the selected directory."
        )
    if year is not None:
        candidates = [
            child
            for child in candidates
            if _expand_wiod_year(pattern.match(child.name).group("year")) == int(year)
        ]
        if not candidates:
            raise WrongInput(f"No WIOD 2016 workbook was found for year {year}.")
    if len(candidates) > 1:
        years = sorted(_expand_wiod_year(pattern.match(child.name).group("year")) for child in candidates)
        raise WrongInput(
            "More than one WIOD workbook matches the selected directory. "
            f"Please specify year or point to one file. Available years: {years}"
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


def _read_wiod_workbook(path: Path, *, sheet_name: str) -> pd.DataFrame:
    """Read one raw WIOD IOT sheet into a dataframe without headers."""
    _require_pyxlsb()
    log_time(logger, f"Parser: reading WIOD workbook {path.name} sheet {sheet_name}.", "info")
    frame = pd.read_excel(path, sheet_name=sheet_name, engine="pyxlsb", header=None)
    if frame.empty:
        raise WrongFormat("The selected WIOD workbook sheet is empty.")
    return frame


def _read_wiod_table_sheet(path: Path, *, sheet_name: str) -> pd.DataFrame:
    """Read one WIOD SUT table sheet that already stores a header row."""
    _require_pyxlsb()
    log_time(logger, f"Parser: reading WIOD workbook {path.name} sheet {sheet_name}.", "info")
    frame = pd.read_excel(path, sheet_name=sheet_name, engine="pyxlsb", header=0)
    if frame.empty:
        raise WrongFormat("The selected WIOD workbook sheet is empty.")
    return frame


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
    layout = WIODLayout(
        root=source.parent,
        data_path=source,
        year=int(year),
        table="IOT",
        sheet_names=(str(year),),
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

    sector_row_mask = row_meta["region"].ne("TOT")
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
    source_path: str | Path | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    WIODLayout,
]:
    """Transform WIOD 2016 multiregional supply/use sheets into MARIO SUT blocks."""
    source = Path(source_path or f"intsut{str(year)[-2:]}_nov16.xlsb")
    layout = WIODLayout(
        root=source.parent,
        data_path=source,
        year=int(year),
        table="SUT",
        sheet_names=(_WIOD_SUT_SUPPLY_SHEET, _WIOD_SUT_USE_SHEET),
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
    commodity_regions = list(dict.fromkeys(use_commodity_rows["PAR"].tolist()))
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
    factor_labels = [WIOD_FACTOR_LABELS[code] for code in factor_codes]
    final_demand_labels = [WIOD_SUT_FINAL_DEMAND_LABELS[code] for code in final_demand_codes]
    satellite_axis = pd.Index([WIOD_SATELLITE_PLACEHOLDER], name=None)
    factor_axis = pd.Index(factor_labels, name=None)

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
        block = use_commodity_rows.loc[use_commodity_rows["REP"] == region].copy()
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
        Va_data[:, activity_slices[region]] = block.loc[factor_codes, activity_codes].to_numpy(
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
    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: WIOD SUT payload ready with shapes "
            f"S={S.shape}, U={U.shape}, Yc={Yc.shape}, Va={Va.shape}."
        ),
        "info",
    )
    return matrices, indeces, units, layout


def parse_wiod_iot(
    path: str | Path,
    *,
    year: int | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    WIODLayout,
]:
    """Parse one WIOD 2016 multiregional IOT workbook into MARIO blocks."""
    layout = detect_wiod_layout(path, table="IOT", year=year)
    frame = _read_wiod_workbook(layout.data_path, sheet_name=layout.sheet_names[0])
    return build_wiod_iot_from_frame(frame, year=layout.year, source_path=layout.data_path)


def parse_wiod_sut(
    path: str | Path,
    *,
    year: int | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    WIODLayout,
]:
    """Parse one WIOD 2016 multiregional SUT workbook into split-native MARIO blocks."""
    layout = detect_wiod_layout(path, table="SUT", year=year)
    supply = _read_wiod_table_sheet(layout.data_path, sheet_name=_WIOD_SUT_SUPPLY_SHEET)
    use = _read_wiod_table_sheet(layout.data_path, sheet_name=_WIOD_SUT_USE_SHEET)
    return build_wiod_sut_from_frames(
        supply,
        use,
        year=layout.year,
        source_path=layout.data_path,
    )
