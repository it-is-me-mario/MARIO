"""Parser helpers for GTAP-style MRIO bundles.

The current implementation targets the GTAP Power MRIO layout that was used in
the historical MARIO branch. The parser surface is structured so new GTAP
branches can be added later without changing the public entry point shape.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    GTAP_INPUT_FORMATS,
    GTAP_LAYOUTS,
    GTAP_MONETARY_UNIT,
    GTAP_POWER_MRIO_CSV_FILES,
    GTAP_POWER_MRIO_GDX_FILES,
    GTAP_POWER_MRIO_SOURCE,
    GTAP_VARIANTS,
)
from mario.utils import delete_duplicates, rename_index, sort_frames

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GTAPLayout:
    """Filesystem layout and metadata for one GTAP parse request."""

    root: Path
    variant: str
    layout: str
    input_format: str
    region_workbook: Path | None = None

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        variant_label = self.variant.upper() if self.variant != "power" else "Power"
        return f"GTAP {variant_label} {self.layout}"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        return GTAP_POWER_MRIO_SOURCE


def _normalize_gtap_variant(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in {item.lower() for item in GTAP_VARIANTS}:
        raise WrongInput(f"GTAP variant should be one of {list(GTAP_VARIANTS)}.")
    return normalized


def _normalize_gtap_layout(value: str) -> str:
    normalized = str(value).strip().upper()
    if normalized not in {item.upper() for item in GTAP_LAYOUTS}:
        raise WrongInput(f"GTAP layout should be one of {list(GTAP_LAYOUTS)}.")
    return normalized


def _normalize_gtap_input_format(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in {item.lower() for item in GTAP_INPUT_FORMATS}:
        raise WrongInput(f"GTAP input_format should be one of {list(GTAP_INPUT_FORMATS)}.")
    return normalized


def _expected_gtap_files(*, variant: str, layout: str, input_format: str) -> dict[str, str]:
    if variant != "power" or layout != "MRIO":
        raise NotImplementedError("Only GTAP Power MRIO is currently implemented.")
    if input_format == "csv":
        return dict(GTAP_POWER_MRIO_CSV_FILES)
    if input_format == "gdx":
        return dict(GTAP_POWER_MRIO_GDX_FILES)
    raise ValueError(input_format)


def detect_gtap_layout(
    path: str | Path,
    *,
    variant: str = "power",
    layout: str = "MRIO",
    input_format: str = "auto",
) -> GTAPLayout:
    """Resolve one GTAP bundle root and its input format.

    Parameters
    ----------
    path:
        Directory containing the GTAP bundle or one file inside that directory.
    variant:
        GTAP family. Only ``power`` is currently implemented.
    layout:
        GTAP bundle layout. Only ``MRIO`` is currently implemented.
    input_format:
        One of ``auto``, ``csv`` or ``gdx``.
    """

    normalized_variant = _normalize_gtap_variant(variant)
    normalized_layout = _normalize_gtap_layout(layout)
    normalized_format = _normalize_gtap_input_format(input_format)

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    root = source if source.is_dir() else source.parent
    region_workbook = root / "162regions.xlsx"

    def _available(fmt: str) -> tuple[bool, list[str]]:
        expected = _expected_gtap_files(
            variant=normalized_variant,
            layout=normalized_layout,
            input_format=fmt,
        )
        missing = [filename for filename in expected.values() if not (root / filename).exists()]
        return len(missing) == 0, missing

    if normalized_format == "auto":
        csv_ok, csv_missing = _available("csv")
        gdx_ok, gdx_missing = _available("gdx")
        if csv_ok:
            normalized_format = "csv"
        elif gdx_ok:
            normalized_format = "gdx"
        else:
            raise WrongInput(
                "The selected directory does not contain a complete GTAP Power MRIO bundle. "
                f"Missing CSV files: {csv_missing}; missing GDX files: {gdx_missing}"
            )
    else:
        available, missing = _available(normalized_format)
        if not available:
            raise WrongInput(
                f"The selected directory does not contain a complete GTAP Power MRIO {normalized_format.upper()} bundle. "
                f"Missing files: {missing}"
            )

    return GTAPLayout(
        root=root,
        variant=normalized_variant,
        layout=normalized_layout,
        input_format=normalized_format,
        region_workbook=region_workbook if region_workbook.exists() else None,
    )


def _gtap_row_unit(row_name: str) -> str:
    if row_name.startswith("EMI") or row_name.startswith("E_P"):
        return "M ton"
    if row_name.startswith("ENE"):
        return "M toe"
    return GTAP_MONETARY_UNIT


def _gtap_units(indexes: dict[str, list[str]]) -> dict[str, pd.DataFrame]:
    return {
        _MASTER_INDEX["s"]: pd.DataFrame(
            {"unit": [GTAP_MONETARY_UNIT] * len(indexes["s"])},
            index=pd.Index(indexes["s"], name=None),
        ),
        _MASTER_INDEX["n"]: pd.DataFrame(
            {"unit": [GTAP_MONETARY_UNIT] * len(indexes["n"])},
            index=pd.Index(indexes["n"], name=None),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [GTAP_MONETARY_UNIT] * len(indexes["f"])},
            index=pd.Index(indexes["f"], name=None),
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": [_gtap_row_unit(row) for row in indexes["k"]]},
            index=pd.Index(indexes["k"], name=None),
        ),
    }


def _gtap_finalize_iot(
    *,
    Z: pd.DataFrame,
    Y: pd.DataFrame,
    V: pd.DataFrame,
    VY: pd.DataFrame,
    E: pd.DataFrame,
    EY: pd.DataFrame,
    regions: list[str],
    sectors: list[str],
    final_demand: list[str],
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame]]:
    raw_sector_columns = Z.columns
    raw_final_demand_columns = Y.columns
    sector_axis = pd.MultiIndex.from_arrays(
        [
            Z.index.get_level_values(0),
            [_MASTER_INDEX["s"]] * len(Z.index),
            Z.index.get_level_values(-1),
        ]
    )
    final_demand_axis = pd.MultiIndex.from_arrays(
        [
            Y.columns.get_level_values(0),
            [_MASTER_INDEX["n"]] * len(Y.columns),
            Y.columns.get_level_values(-1),
        ]
    )

    Z = Z.copy()
    Y = Y.copy()
    V = V.copy()
    VY = VY.copy()
    E = E.copy()
    EY = EY.copy()

    Z.index = sector_axis
    Z.columns = sector_axis

    Y.index = sector_axis
    Y.columns = final_demand_axis

    V = V.reindex(columns=raw_sector_columns, fill_value=0.0)
    E = E.reindex(columns=raw_sector_columns, fill_value=0.0)
    VY = VY.reindex(columns=raw_final_demand_columns, fill_value=0.0)
    EY = EY.reindex(columns=raw_final_demand_columns, fill_value=0.0)

    V.columns = sector_axis
    E.columns = sector_axis
    VY.columns = final_demand_axis
    EY.columns = final_demand_axis

    matrices = {
        "baseline": {
            "Z": Z,
            "Y": Y,
            "V": V,
            "VY": VY,
            "E": E,
            "EY": EY,
        }
    }
    indexes = {
        "r": {"main": list(regions)},
        "s": {"main": list(sectors)},
        "n": {"main": list(final_demand)},
        "f": {"main": V.index.tolist()},
        "k": {"main": E.index.tolist()},
    }
    units = _gtap_units(
        {
            "s": indexes["s"]["main"],
            "n": indexes["n"]["main"],
            "f": indexes["f"]["main"],
            "k": indexes["k"]["main"],
        }
    )
    rename_index(matrices["baseline"])
    sort_frames(matrices["baseline"])
    return matrices, indexes, units


def _csv_missing(df: pd.DataFrame, variant: str, indexes: dict[str, dict[str, list[str]]]) -> pd.DataFrame:
    regions = list(indexes["r"]["main"])
    sectors = list(indexes["s"]["main"])
    final_demand = list(indexes["n"]["main"])
    agents = sectors + final_demand

    if variant == "dom":
        base = df.copy()
        if "DST" in base.columns:
            base = base.drop(columns=["DST"])
        filled = (
            base.set_index(["COMM", "AGENT", "SRC"])
            .reindex(
                pd.MultiIndex.from_product([sectors, agents, regions], names=["COMM", "AGENT", "SRC"]),
                fill_value=0,
            )
            .reset_index()
        )
        filled["DST"] = filled["SRC"]
        return filled

    if variant == "general":
        return (
            df.set_index(["COMM", "AGENT", "SRC", "DST"])
            .reindex(
                pd.MultiIndex.from_product(
                    [sectors, agents, regions, regions],
                    names=["COMM", "AGENT", "SRC", "DST"],
                ),
                fill_value=0,
            )
            .reset_index()
        )

    if variant == "tax":
        return (
            df.set_index(["COMM", "SRC", "DST"])
            .reindex(
                pd.MultiIndex.from_product([sectors, regions, regions], names=["COMM", "SRC", "DST"]),
                fill_value=0,
            )
            .reset_index()
        )

    if variant == "ptax":
        base = df.copy()
        extra_cols = [column for column in base.columns if column not in {"COMM", "DST", "VALUE"}]
        if extra_cols:
            base = base.drop(columns=extra_cols)
        return (
            base.set_index(["COMM", "DST"])
            .reindex(
                pd.MultiIndex.from_product([sectors, regions], names=["COMM", "DST"]),
                fill_value=0,
            )
            .reset_index()
        )

    if variant == "single_region":
        return (
            df.set_index(["COMM", "AGENT", "REG"])
            .reindex(
                pd.MultiIndex.from_product([sectors, agents, regions], names=["COMM", "AGENT", "REG"]),
                fill_value=0,
            )
            .reset_index()
        )

    if variant == "single_region_va":
        row_categories = delete_duplicates(df["COMM"].astype(str))
        return (
            df.set_index(["COMM", "AGENT", "REG"])
            .reindex(
                pd.MultiIndex.from_product([row_categories, sectors, regions], names=["COMM", "AGENT", "REG"]),
                fill_value=0,
            )
            .reset_index()
        )

    if variant in {"emi_dom", "emi_imp", "ene_dom", "ene_imp"}:
        group_col = "EM" if variant.startswith("emi") else "COMM"
        item_col = "COMM"
        activity_col = "AGT"
        frames: list[pd.DataFrame] = []
        for _, group_frame in df.groupby(group_col, sort=False):
            item_values = delete_duplicates(group_frame[item_col].astype(str))
            names = [item_col, activity_col, "SRC", "DST"]
            index = pd.MultiIndex.from_product([item_values, agents, regions, regions], names=names)
            if variant.endswith("dom"):
                index = index[index.get_level_values("SRC") == index.get_level_values("DST")]
            reindexed = (
                group_frame.set_index(names)
                .reindex(index, fill_value=0)
                .reset_index()
            )
            if group_col not in reindexed.columns:
                reindexed[group_col] = group_frame.iloc[0][group_col]
            frames.append(reindexed)
        return pd.concat(frames, ignore_index=True) if frames else df.copy()

    raise ValueError(f"Unrecognized GTAP csv fill variant: {variant}")


def _csv_to_matrix(
    df: pd.DataFrame,
    *,
    var: str,
    variant_missing: str,
    indexes: dict[str, dict[str, list[str]]],
    pivot_index: list[str],
    pivot_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    filtered = df.loc[df["VAR"] == var].drop(columns=["VAR"]).copy()
    filled = _csv_missing(filtered, variant_missing, indexes)
    intermediate = filled.loc[filled["AGENT"].isin(indexes["s"]["main"])]
    final = filled.loc[filled["AGENT"].isin(indexes["n"]["main"])]
    Z = intermediate.pivot_table(
        index=pivot_index,
        columns=pivot_columns,
        values="VALUE",
        aggfunc="sum",
    ).fillna(0.0)
    Y = final.pivot_table(
        index=pivot_index,
        columns=pivot_columns,
        values="VALUE",
        aggfunc="sum",
    ).fillna(0.0)
    return Z, Y


def _csv_to_matrix_rowname(
    df: pd.DataFrame,
    *,
    var: str,
    variant_missing: str,
    indexes: dict[str, dict[str, list[str]]],
    row_name_setting: str,
    row_name_categ: str,
    row_name_reg: str = "",
    pivot_index: list[str],
    pivot_columns: list[str],
    split_agent: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    filtered = df.loc[df["VAR"] == var].drop(columns=["VAR"]).copy()
    filled = _csv_missing(filtered, variant_missing, indexes)

    if row_name_setting == "only_region":
        filled["row_name"] = row_name_categ + "_" + filled[row_name_reg].astype(str)
    elif row_name_setting == "reg_comm":
        filled["row_name"] = (
            row_name_categ + "_" + filled[row_name_reg].astype(str) + "_" + filled["COMM"].astype(str)
        )
        filled = filled.drop(columns=["COMM", row_name_reg])
    elif row_name_setting == "only_comm":
        filled["row_name"] = row_name_categ + "_REG_" + filled["COMM"].astype(str)
    elif row_name_setting == "only_categ":
        filled["row_name"] = row_name_categ + "_REG"
    elif row_name_setting == "emi_dom":
        filled["row_name"] = (
            row_name_categ
            + "_"
            + filled["EM"].astype(str)
            + "_dms_"
            + filled["COMM"].astype(str)
        )
        filled = filled.drop(columns=["EM", "COMM", "SRC"])
    elif row_name_setting == "emi_imp":
        filled["row_name"] = (
            row_name_categ
            + "_"
            + filled["EM"].astype(str)
            + "_"
            + filled["SRC"].astype(str)
            + "_"
            + filled["COMM"].astype(str)
        )
        filled = filled.drop(columns=["EM", "COMM", "SRC"])
    elif row_name_setting == "ene_dom":
        filled["row_name"] = row_name_categ + "_dms_" + filled["COMM"].astype(str)
        filled = filled.drop(columns=["COMM", "SRC"])
    elif row_name_setting == "ene_imp":
        filled["row_name"] = (
            row_name_categ + "_" + filled["SRC"].astype(str) + "_" + filled["COMM"].astype(str)
        )
        filled = filled.drop(columns=["COMM", "SRC"])
    else:
        raise ValueError(f"Unsupported GTAP csv row naming mode: {row_name_setting}")

    activity_column = "AGENT" if "AGENT" in filled.columns else "AGT"
    if split_agent:
        V = filled.loc[filled[activity_column].isin(indexes["s"]["main"])].pivot_table(
            index=pivot_index,
            columns=pivot_columns,
            values="VALUE",
            aggfunc="sum",
        ).fillna(0.0)
        VY = filled.loc[filled[activity_column].isin(indexes["n"]["main"])].pivot_table(
            index=pivot_index,
            columns=pivot_columns,
            values="VALUE",
            aggfunc="sum",
        ).fillna(0.0)
        return V, VY

    return filled.pivot_table(
        index=pivot_index,
        columns=pivot_columns,
        values="VALUE",
        aggfunc="sum",
    ).fillna(0.0)


def build_gtap_mrio_from_csv_frames(
    frames: dict[str, pd.DataFrame],
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame]]:
    """Build canonical MARIO IOT blocks from GTAP Power MRIO csv frames."""
    srcxdst = frames["SRCxDST"].copy()
    value_added = frames["V"].copy()
    value_taxes = frames["V - Tax"].copy()
    emissions = frames["E+EY - Emissions"].copy()
    energy = frames["E+EY - Energy"].copy()

    for frame in [srcxdst, value_added, value_taxes, emissions, energy]:
        frame.columns = [str(column).strip() for column in frame.columns]

    srcxdst["COMM"] = srcxdst["COMM"].astype(str)
    srcxdst["AGENT"] = srcxdst["AGENT"].astype(str)
    srcxdst["SRC"] = srcxdst["SRC"].astype(str)
    srcxdst["DST"] = srcxdst["DST"].astype(str)

    sectors = delete_duplicates(srcxdst["COMM"].tolist())
    sector_set = set(sectors)
    final_demand = [item for item in delete_duplicates(srcxdst["AGENT"].tolist()) if item not in sector_set]
    regions = delete_duplicates(pd.concat([srcxdst["SRC"], srcxdst["DST"]]).astype(str).tolist())

    indexes = {
        "r": {"main": regions},
        "s": {"main": sectors},
        "n": {"main": final_demand},
    }

    log_time(logger, "Parser: building GTAP Power MRIO matrices from CSV frames.", "info")
    Z_dom, Y_dom = _csv_to_matrix(
        srcxdst,
        var="DOM",
        variant_missing="dom",
        indexes=indexes,
        pivot_index=["SRC", "COMM"],
        pivot_columns=["DST", "AGENT"],
    )
    Z_imp, Y_imp = _csv_to_matrix(
        srcxdst,
        var="VFOB",
        variant_missing="general",
        indexes=indexes,
        pivot_index=["SRC", "COMM"],
        pivot_columns=["DST", "AGENT"],
    )
    Z = Z_dom.add(Z_imp, fill_value=0.0)
    Y = Y_dom.add(Y_imp, fill_value=0.0)

    V_mtax, VY_mtax = _csv_to_matrix_rowname(
        srcxdst,
        var="MTAX",
        variant_missing="general",
        indexes=indexes,
        row_name_setting="reg_comm",
        row_name_categ="MTAX",
        row_name_reg="SRC",
        pivot_index=["row_name"],
        pivot_columns=["DST", "AGENT"],
        split_agent=True,
    )
    V_ittm, VY_ittm = _csv_to_matrix_rowname(
        srcxdst,
        var="ITTM",
        variant_missing="general",
        indexes=indexes,
        row_name_setting="reg_comm",
        row_name_categ="ITTM",
        row_name_reg="SRC",
        pivot_index=["row_name"],
        pivot_columns=["DST", "AGENT"],
        split_agent=True,
    )
    V = pd.concat([V_mtax, V_ittm], axis=0)
    VY = pd.concat([VY_mtax, VY_ittm], axis=0)

    V_etax = _csv_to_matrix_rowname(
        value_taxes,
        var="ETAX",
        variant_missing="tax",
        indexes=indexes,
        row_name_setting="only_region",
        row_name_categ="ETAX",
        row_name_reg="DST",
        pivot_index=["row_name"],
        pivot_columns=["SRC", "COMM"],
    )
    V_ptax = _csv_to_matrix_rowname(
        value_taxes,
        var="PTAX",
        variant_missing="ptax",
        indexes=indexes,
        row_name_setting="only_categ",
        row_name_categ="PTAX",
        pivot_index=["row_name"],
        pivot_columns=["DST", "COMM"],
    )
    V = pd.concat([V, V_etax, V_ptax], axis=0)

    V_va = _csv_to_matrix_rowname(
        value_added,
        var="VA",
        variant_missing="single_region_va",
        indexes=indexes,
        row_name_setting="only_comm",
        row_name_categ="VAAD",
        pivot_index=["row_name"],
        pivot_columns=["REG", "AGENT"],
    )
    V_vtax = _csv_to_matrix_rowname(
        value_added,
        var="VTAX",
        variant_missing="single_region_va",
        indexes=indexes,
        row_name_setting="only_comm",
        row_name_categ="VTAX",
        pivot_index=["row_name"],
        pivot_columns=["REG", "AGENT"],
    )
    V_idtax, VY_idtax = _csv_to_matrix_rowname(
        value_added,
        var="IDTAX",
        variant_missing="single_region",
        indexes=indexes,
        row_name_setting="only_comm",
        row_name_categ="DTAX",
        pivot_index=["row_name"],
        pivot_columns=["REG", "AGENT"],
        split_agent=True,
    )
    V_imtax, VY_imtax = _csv_to_matrix_rowname(
        value_added,
        var="IMTAX",
        variant_missing="single_region",
        indexes=indexes,
        row_name_setting="only_comm",
        row_name_categ="ITAX",
        pivot_index=["row_name"],
        pivot_columns=["REG", "AGENT"],
        split_agent=True,
    )
    V = pd.concat([V, V_va, V_vtax, V_idtax, V_imtax], axis=0)
    VY = pd.concat([VY, VY_idtax, VY_imtax], axis=0)

    E_dom, EY_dom = _csv_to_matrix_rowname(
        emissions,
        var="DOM",
        variant_missing="emi_dom",
        indexes=indexes,
        row_name_setting="emi_dom",
        row_name_categ="EMI",
        pivot_index=["row_name"],
        pivot_columns=["DST", "AGT"],
        split_agent=True,
    )
    E_imp, EY_imp = _csv_to_matrix_rowname(
        emissions,
        var="IMP",
        variant_missing="emi_imp",
        indexes=indexes,
        row_name_setting="emi_imp",
        row_name_categ="EMI",
        pivot_index=["row_name"],
        pivot_columns=["DST", "AGT"],
        split_agent=True,
    )
    E_ene_dom, EY_ene_dom = _csv_to_matrix_rowname(
        energy,
        var="DOM",
        variant_missing="ene_dom",
        indexes=indexes,
        row_name_setting="ene_dom",
        row_name_categ="ENE",
        pivot_index=["row_name"],
        pivot_columns=["DST", "AGT"],
        split_agent=True,
    )
    E_ene_imp, EY_ene_imp = _csv_to_matrix_rowname(
        energy,
        var="IMP",
        variant_missing="ene_imp",
        indexes=indexes,
        row_name_setting="ene_imp",
        row_name_categ="ENE",
        pivot_index=["row_name"],
        pivot_columns=["DST", "AGT"],
        split_agent=True,
    )

    E = pd.concat([E_dom, E_imp, E_ene_dom, E_ene_imp], axis=0)
    EY = pd.concat([EY_dom, EY_imp, EY_ene_dom, EY_ene_imp], axis=0)

    return _gtap_finalize_iot(
        Z=Z,
        Y=Y,
        V=V,
        VY=VY,
        E=E,
        EY=EY,
        regions=regions,
        sectors=sectors,
        final_demand=final_demand,
    )


def _gdx_missing(df: pd.DataFrame, variant: str, indexes: dict[str, dict[str, list[str]]]) -> pd.DataFrame:
    regions = list(indexes["r"]["main"])
    sectors = list(indexes["s"]["main"])
    final_demand = list(indexes["n"]["main"])
    agents = sectors + final_demand

    if variant == "dom":
        filled = (
            df.set_index(["COMM", "agt", "REG"])
            .reindex(
                pd.MultiIndex.from_product([sectors, agents, regions], names=["COMM", "agt", "REG"]),
                fill_value=0,
            )
            .reset_index()
        )
        filled["DST"] = filled["REG"]
        filled = filled.rename(columns={"REG": "SRC"})
        return filled

    if variant == "general":
        return (
            df.set_index(["COMM", "agt", "SRC", "DST"])
            .reindex(
                pd.MultiIndex.from_product(
                    [sectors, agents, regions, regions],
                    names=["COMM", "agt", "SRC", "DST"],
                ),
                fill_value=0,
            )
            .reset_index()
        )

    if variant == "tax":
        return (
            df.set_index(["COMM", "SRC", "DST"])
            .reindex(
                pd.MultiIndex.from_product([sectors, regions, regions], names=["COMM", "SRC", "DST"]),
                fill_value=0,
            )
            .reset_index()
        )

    if variant == "ptax":
        base = df.drop(columns=["acts"]).copy() if "acts" in df.columns else df.copy()
        return (
            base.set_index(["COMM", "REG"])
            .reindex(
                pd.MultiIndex.from_product([sectors, regions], names=["COMM", "REG"]),
                fill_value=0,
            )
            .reset_index()
        )

    if variant == "single_region":
        return (
            df.set_index(["COMM", "agt", "DST"])
            .reindex(
                pd.MultiIndex.from_product([sectors, agents, regions], names=["COMM", "agt", "DST"]),
                fill_value=0,
            )
            .reset_index()
        )

    if variant == "single_region_va":
        endw = delete_duplicates(df["ENDW"].astype(str))
        return (
            df.set_index(["ENDW", "acts", "DST"])
            .reindex(
                pd.MultiIndex.from_product([endw, sectors, regions], names=["ENDW", "acts", "DST"]),
                fill_value=0,
            )
            .reset_index()
        )

    if variant in {"emi_dom", "emi_imp", "emi_proc", "ene_dom", "ene_imp"}:
        if variant.startswith("emi"):
            group_col = "em"
            key_cols = {
                "emi_dom": ["inputs", "agt", "SRC", "DST"],
                "emi_imp": ["inputs", "agt", "SRC", "DST"],
                "emi_proc": ["comm", "acts", "REG"],
            }[variant]
        else:
            group_col = "ERG"
            key_cols = {
                "ene_dom": ["ERG", "agt", "SRC", "DST"],
                "ene_imp": ["ERG", "agt", "SRC", "DST"],
            }[variant]

        frames: list[pd.DataFrame] = []
        for group_value, group_frame in df.groupby(group_col, sort=False):
            indexed = group_frame.set_index(key_cols)
            if variant == "emi_dom":
                item_values = delete_duplicates(group_frame["inputs"].astype(str))
                index = pd.MultiIndex.from_product(
                    [item_values, agents, regions, regions],
                    names=["inputs", "agt", "SRC", "DST"],
                )
                index = index[index.get_level_values("SRC") == index.get_level_values("DST")]
            elif variant == "emi_imp":
                item_values = delete_duplicates(group_frame["inputs"].astype(str))
                index = pd.MultiIndex.from_product(
                    [item_values, agents, regions, regions],
                    names=["inputs", "agt", "SRC", "DST"],
                )
            elif variant == "emi_proc":
                item_values = delete_duplicates(group_frame["comm"].astype(str))
                index = pd.MultiIndex.from_product(
                    [item_values, agents, regions],
                    names=["comm", "acts", "REG"],
                )
            elif variant == "ene_dom":
                item_values = delete_duplicates(group_frame["ERG"].astype(str))
                index = pd.MultiIndex.from_product(
                    [item_values, agents, regions, regions],
                    names=["ERG", "agt", "SRC", "DST"],
                )
                index = index[index.get_level_values("SRC") == index.get_level_values("DST")]
            else:
                item_values = delete_duplicates(group_frame["ERG"].astype(str))
                index = pd.MultiIndex.from_product(
                    [item_values, agents, regions, regions],
                    names=["ERG", "agt", "SRC", "DST"],
                )

            for column in indexed.columns:
                if getattr(indexed[column].dtype, "name", "") == "category":
                    indexed[column] = indexed[column].astype(str)

            reindexed = indexed.reindex(index, fill_value=0).reset_index()
            reindexed[group_col] = group_value
            frames.append(reindexed)
        return pd.concat(frames, ignore_index=True) if frames else df.copy()

    raise ValueError(f"Unrecognized GTAP gdx fill variant: {variant}")


def _gdx_to_matrix(
    container: Any,
    *,
    var: str,
    variant_missing: str,
    indexes: dict[str, dict[str, list[str]]],
    pivot_index: list[str],
    pivot_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        filtered = container.data[var].records
    except KeyError as exc:
        raise WrongFormat(f"GTAP GDX bundle is missing symbol {var!r}.") from exc
    filled = _gdx_missing(filtered.copy(), variant_missing, indexes)
    Z = filled.loc[filled["agt"].isin(indexes["s"]["main"])].pivot_table(
        index=pivot_index,
        columns=pivot_columns,
        values="value",
        aggfunc="sum",
    ).fillna(0.0)
    Y = filled.loc[filled["agt"].isin(indexes["n"]["main"])].pivot_table(
        index=pivot_index,
        columns=pivot_columns,
        values="value",
        aggfunc="sum",
    ).fillna(0.0)
    return Z, Y


def _gdx_to_matrix_rowname(
    container: Any,
    *,
    var: str,
    variant_missing: str,
    indexes: dict[str, dict[str, list[str]]],
    row_name_setting: str,
    row_name_categ: str,
    row_name_reg: str = "",
    pivot_index: list[str],
    pivot_columns: list[str],
    split_agent: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    try:
        filtered = container.data[var].records.copy()
    except KeyError as exc:
        raise WrongFormat(f"GTAP GDX bundle is missing symbol {var!r}.") from exc

    filled = _gdx_missing(filtered, variant_missing, indexes)

    if row_name_setting == "only_region":
        filled["row_name"] = row_name_categ + "_" + filled[row_name_reg].astype(str)
    elif row_name_setting == "only_categ":
        filled["row_name"] = row_name_categ + "_REG"
    elif row_name_setting == "reg_comm":
        filled["row_name"] = (
            row_name_categ + "_" + filled[row_name_reg].astype(str) + "_" + filled["COMM"].astype(str)
        )
        filled = filled.drop(columns=["SRC", "COMM"])
    elif row_name_setting == "only_endw":
        filled["row_name"] = row_name_categ + "_REG_" + filled["ENDW"].astype(str)
    elif row_name_setting == "only_comm":
        filled["row_name"] = row_name_categ + "_REG_" + filled["COMM"].astype(str)
    else:
        raise ValueError(f"Unsupported GTAP gdx row naming mode: {row_name_setting}")

    if split_agent:
        V = filled.loc[filled["agt"].isin(indexes["s"]["main"])].pivot_table(
            index=pivot_index,
            columns=pivot_columns,
            values="value",
            aggfunc="sum",
        ).fillna(0.0)
        VY = filled.loc[filled["agt"].isin(indexes["n"]["main"])].pivot_table(
            index=pivot_index,
            columns=pivot_columns,
            values="value",
            aggfunc="sum",
        ).fillna(0.0)
        return V, VY

    return filled.pivot_table(
        index=pivot_index,
        columns=pivot_columns,
        values="value",
        aggfunc="sum",
    ).fillna(0.0)


def _gdx_to_matrix_satellite(
    container: Any,
    *,
    var: str,
    variant_missing: str,
    indexes: dict[str, dict[str, list[str]]],
    row_name_setting: str,
    row_name_categ: str,
    pivot_index: list[str],
    pivot_columns: list[str],
    split_agent: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    try:
        filtered = container.data[var].records.copy()
    except KeyError as exc:
        raise WrongFormat(f"GTAP GDX bundle is missing symbol {var!r}.") from exc

    filter_config = {
        "emi_dom": ("source", "DOM"),
        "emi_imp": ("source", "IMP"),
        "ene_dom": ("SOURCE", "DOM"),
        "ene_imp": ("SOURCE", "IMP"),
    }
    if row_name_setting in filter_config:
        column, value = filter_config[row_name_setting]
        filtered = filtered.loc[filtered[column] == value].drop(columns=[column])

    filled = _gdx_missing(filtered, variant_missing, indexes)

    if row_name_setting == "emi_dom":
        filled["row_name"] = (
            row_name_categ + "_" + filled["em"].astype(str) + "_dms_" + filled["inputs"].astype(str)
        )
        filled = filled.drop(columns=["em", "SRC", "inputs"])
    elif row_name_setting == "emi_imp":
        filled["row_name"] = (
            row_name_categ
            + "_"
            + filled["em"].astype(str)
            + "_"
            + filled["SRC"].astype(str)
            + "_"
            + filled["inputs"].astype(str)
        )
        filled = filled.drop(columns=["em", "SRC", "inputs"])
    elif row_name_setting == "emi_proc":
        filled["row_name"] = (
            row_name_categ + "_" + filled["em"].astype(str) + "_REG_" + filled["comm"].astype(str)
        )
        filled = filled.drop(columns=["em", "comm"])
    elif row_name_setting == "ene_dom":
        filled["row_name"] = row_name_categ + "_dms_" + filled["ERG"].astype(str)
        filled = filled.drop(columns=["SRC", "ERG"])
    elif row_name_setting == "ene_imp":
        filled["row_name"] = (
            row_name_categ + "_" + filled["SRC"].astype(str) + "_" + filled["ERG"].astype(str)
        )
        filled = filled.drop(columns=["SRC", "ERG"])
    else:
        raise ValueError(f"Unsupported GTAP gdx satellite row naming mode: {row_name_setting}")

    if split_agent:
        if row_name_setting == "emi_proc":
            V = filled.loc[filled["acts"].isin(indexes["s"]["main"])].pivot_table(
                index=pivot_index,
                columns=pivot_columns,
                values="value",
                aggfunc="sum",
            ).fillna(0.0)
            VY = filled.loc[filled["acts"].isin(indexes["n"]["main"])].pivot_table(
                index=pivot_index,
                columns=pivot_columns,
                values="value",
                aggfunc="sum",
            ).fillna(0.0)
        else:
            V = filled.loc[filled["agt"].isin(indexes["s"]["main"])].pivot_table(
                index=pivot_index,
                columns=pivot_columns,
                values="value",
                aggfunc="sum",
            ).fillna(0.0)
            VY = filled.loc[filled["agt"].isin(indexes["n"]["main"])].pivot_table(
                index=pivot_index,
                columns=pivot_columns,
                values="value",
                aggfunc="sum",
            ).fillna(0.0)
        return V, VY

    return filled.pivot_table(
        index=pivot_index,
        columns=pivot_columns,
        values="value",
        aggfunc="sum",
    ).fillna(0.0)


def _optional_gdx_satellite_symbol(
    container: Any,
    symbol: str,
    callback,
):
    if symbol not in container.data:
        return None
    return callback()


def _require_gdx_symbol(container: Any, symbol: str, *, file_label: str) -> Any:
    """Return one mandatory symbol from a GDX container or raise a parser error."""
    if symbol not in container.data:
        raise WrongFormat(
            f"The GTAP Power MRIO {file_label} GDX file is missing the required symbol {symbol!r}."
        )
    return container.data[symbol]


def build_gtap_mrio_from_gdx_containers(
    containers: dict[str, Any],
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame]]:
    """Build canonical MARIO IOT blocks from GTAP Power MRIO GDX containers."""
    srcxdst = containers["SRCxDST"]
    sectors = _require_gdx_symbol(srcxdst, "comm", file_label="GSDFSRCxDST").records["uni"].astype(str).tolist()
    regions = _require_gdx_symbol(srcxdst, "REG", file_label="GSDFSRCxDST").records["uni"].astype(str).tolist()
    agents = _require_gdx_symbol(srcxdst, "agt", file_label="GSDFSRCxDST").records["uni"].astype(str).tolist()
    sector_set = set(sectors)
    final_demand = [item for item in agents if item not in sector_set]
    indexes = {
        "r": {"main": regions},
        "s": {"main": sectors},
        "n": {"main": final_demand},
    }

    log_time(logger, "Parser: building GTAP Power MRIO matrices from GDX containers.", "info")
    Z_dom, Y_dom = _gdx_to_matrix(
        srcxdst,
        var="VDBA",
        variant_missing="dom",
        indexes=indexes,
        pivot_index=["SRC", "COMM"],
        pivot_columns=["DST", "agt"],
    )
    Z_imp, Y_imp = _gdx_to_matrix(
        srcxdst,
        var="VFOB",
        variant_missing="general",
        indexes=indexes,
        pivot_index=["SRC", "COMM"],
        pivot_columns=["DST", "agt"],
    )
    Z = Z_dom.add(Z_imp, fill_value=0.0)
    Y = Y_dom.add(Y_imp, fill_value=0.0)

    V_mtax, VY_mtax = _gdx_to_matrix_rowname(
        srcxdst,
        var="MTAX",
        variant_missing="general",
        indexes=indexes,
        row_name_setting="reg_comm",
        row_name_categ="MTAX",
        row_name_reg="SRC",
        pivot_index=["row_name"],
        pivot_columns=["DST", "agt"],
        split_agent=True,
    )
    V_ittm, VY_ittm = _gdx_to_matrix_rowname(
        srcxdst,
        var="ITTM",
        variant_missing="general",
        indexes=indexes,
        row_name_setting="reg_comm",
        row_name_categ="ITTM",
        row_name_reg="SRC",
        pivot_index=["row_name"],
        pivot_columns=["DST", "agt"],
        split_agent=True,
    )
    V = pd.concat([V_mtax, V_ittm], axis=0)
    VY = pd.concat([VY_mtax, VY_ittm], axis=0)

    V_etax = _gdx_to_matrix_rowname(
        containers["V-Tax"],
        var="ETAX",
        variant_missing="tax",
        indexes=indexes,
        row_name_setting="only_region",
        row_name_categ="ETAX",
        row_name_reg="DST",
        pivot_index=["row_name"],
        pivot_columns=["SRC", "COMM"],
    )
    V_ptax = _gdx_to_matrix_rowname(
        containers["V-Tax"],
        var="PTAX",
        variant_missing="ptax",
        indexes=indexes,
        row_name_setting="only_categ",
        row_name_categ="PTAX",
        pivot_index=["row_name"],
        pivot_columns=["REG", "COMM"],
    )
    V = pd.concat([V, V_etax, V_ptax], axis=0)

    V_va = _gdx_to_matrix_rowname(
        containers["V"],
        var="VA",
        variant_missing="single_region_va",
        indexes=indexes,
        row_name_setting="only_endw",
        row_name_categ="VAAD",
        pivot_index=["row_name"],
        pivot_columns=["DST", "acts"],
    )
    V_vtax = _gdx_to_matrix_rowname(
        containers["V"],
        var="VTAX",
        variant_missing="single_region_va",
        indexes=indexes,
        row_name_setting="only_endw",
        row_name_categ="VTAX",
        pivot_index=["row_name"],
        pivot_columns=["DST", "acts"],
    )
    V_idtax, VY_idtax = _gdx_to_matrix_rowname(
        containers["V"],
        var="IDTAX",
        variant_missing="single_region",
        indexes=indexes,
        row_name_setting="only_comm",
        row_name_categ="DTAX",
        pivot_index=["row_name"],
        pivot_columns=["DST", "agt"],
        split_agent=True,
    )
    V_imtax, VY_imtax = _gdx_to_matrix_rowname(
        containers["V"],
        var="IMTAX",
        variant_missing="single_region",
        indexes=indexes,
        row_name_setting="only_comm",
        row_name_categ="ITAX",
        pivot_index=["row_name"],
        pivot_columns=["DST", "agt"],
        split_agent=True,
    )
    V = pd.concat([V, V_va, V_vtax, V_idtax, V_imtax], axis=0)
    VY = pd.concat([VY, VY_idtax, VY_imtax], axis=0)

    emission_blocks: list[pd.DataFrame] = []
    emission_y_blocks: list[pd.DataFrame] = []
    emissions = containers["Emissions"]

    for symbol, row_setting, category in [
        ("Emi_COMB", "emi_dom", "EMI"),
        ("Emi_COMB", "emi_imp", "EMI"),
        ("Emi", "emi_dom", "EMI"),
        ("Emi", "emi_imp", "EMI"),
    ]:
        result = _optional_gdx_satellite_symbol(
            emissions,
            symbol,
            lambda symbol=symbol, row_setting=row_setting, category=category: _gdx_to_matrix_satellite(
                emissions,
                var=symbol,
                variant_missing=row_setting,
                indexes=indexes,
                row_name_setting=row_setting,
                row_name_categ=category,
                pivot_index=["row_name"],
                pivot_columns=["DST", "agt"],
                split_agent=True,
            ),
        )
        if result is None:
            continue
        block, block_y = result
        emission_blocks.append(block)
        emission_y_blocks.append(block_y)

    process_result = _optional_gdx_satellite_symbol(
        emissions,
        "Emi_Proc",
        lambda: _gdx_to_matrix_satellite(
            emissions,
            var="Emi_Proc",
            variant_missing="emi_proc",
            indexes=indexes,
            row_name_setting="emi_proc",
            row_name_categ="E_P",
            pivot_index=["row_name"],
            pivot_columns=["REG", "acts"],
            split_agent=True,
        ),
    )
    if process_result is not None:
        block, block_y = process_result
        emission_blocks.append(block)
        emission_y_blocks.append(block_y)

    energy_dom, energy_y_dom = _gdx_to_matrix_satellite(
        containers["Energy"],
        var="NRG",
        variant_missing="ene_dom",
        indexes=indexes,
        row_name_setting="ene_dom",
        row_name_categ="ENE",
        pivot_index=["row_name"],
        pivot_columns=["DST", "agt"],
        split_agent=True,
    )
    energy_imp, energy_y_imp = _gdx_to_matrix_satellite(
        containers["Energy"],
        var="NRG",
        variant_missing="ene_imp",
        indexes=indexes,
        row_name_setting="ene_imp",
        row_name_categ="ENE",
        pivot_index=["row_name"],
        pivot_columns=["DST", "agt"],
        split_agent=True,
    )

    E = pd.concat([*emission_blocks, energy_dom, energy_imp], axis=0)
    EY = pd.concat([*emission_y_blocks, energy_y_dom, energy_y_imp], axis=0)

    return _gtap_finalize_iot(
        Z=Z,
        Y=Y,
        V=V,
        VY=VY,
        E=E,
        EY=EY,
        regions=regions,
        sectors=sectors,
        final_demand=final_demand,
    )


def _import_gams_transfer():
    try:
        from gams import transfer as gt
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "GTAP GDX parsing requires the GAMS Python API (`gams.transfer`) in the current environment."
        ) from exc
    return gt


def parse_gtap_mrio_csv(
    path: str | Path,
    *,
    layout: GTAPLayout | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    GTAPLayout,
]:
    """Parse GTAP Power MRIO csv files from one local bundle."""
    resolved = layout or detect_gtap_layout(path, variant="power", layout="MRIO", input_format="csv")
    files = _expected_gtap_files(variant=resolved.variant, layout=resolved.layout, input_format="csv")
    frames = {
        key: pd.read_csv(resolved.root / filename)
        for key, filename in files.items()
    }
    matrices, indexes, units = build_gtap_mrio_from_csv_frames(frames)
    return matrices, indexes, units, resolved


def parse_gtap_mrio_gdx(
    path: str | Path,
    *,
    layout: GTAPLayout | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    GTAPLayout,
]:
    """Parse GTAP Power MRIO GDX files from one local bundle."""
    resolved = layout or detect_gtap_layout(path, variant="power", layout="MRIO", input_format="gdx")
    gt = _import_gams_transfer()
    files = _expected_gtap_files(variant=resolved.variant, layout=resolved.layout, input_format="gdx")
    containers = {
        key: gt.Container(str(resolved.root / filename))
        for key, filename in files.items()
    }
    matrices, indexes, units = build_gtap_mrio_from_gdx_containers(containers)
    return matrices, indexes, units, resolved
