"""SUT-specific helpers for the split workflow of ``Database.add_sectors``.

An IOT split starts from the non-split insertion and refines it. A SUT split is
different: the new activities and commodities are carved out of their parents
directly, so the a-priori Use (``U0``), Make (``M0``), Final demand (``Y0``) and
Value added (``V0``) matrices are built from the original table plus the
split-support sheets of the add-sectors workbook, and then handed to CVXLab.

Naming used throughout this module:

- *stable*: activity/commodity that is neither split nor a parent;
- *parent*: existing activity/commodity that is split;
- *new*: activity/commodity created by the split.

All frames handled here use a two-level ``(Region, Item)`` axis (the ``Level``
of the MARIO index is re-introduced by :func:`assemble_sut_split_flows`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import pint

from mario.log_exc.exceptions import LackOfInput, NotImplementable, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import SUT, TABLE_LEVELS, _ENUM, _MASTER_INDEX as MI
from mario.ops.add_sector_specs import (
    ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_COLUMNS,
    ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_SHEET,
    ADD_SECTOR_SPLIT_OUTPUT_SHEET,
    ADD_SECTOR_SPLIT_SUPPLY_COEF_COLUMNS,
    ADD_SECTOR_SPLIT_SUPPLY_COEF_SHEET,
    ADD_SECTOR_SPLIT_SUPPLY_EXCLUSION_COLUMNS,
    ADD_SECTOR_SPLIT_SUPPLY_EXCLUSION_SHEET,
    ADD_SECTOR_SPLIT_SUT_OUTPUT_COLUMNS,
    ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS,
    ADD_SECTOR_SPLIT_TOLERANCE_DEFAULTS,
    ADD_SECTOR_SPLIT_TOLERANCE_SHEET,
    ADD_SECTOR_SPLIT_USE_EXCLUSION_COLUMNS,
    ADD_SECTOR_SPLIT_USE_EXCLUSION_SHEET,
    ADVANCED_ADD_SECTOR_INVENTORY_SHEET_COLUMNS as INV,
    ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS,
)


MSC = ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS[SUT]
REGION, ITEM = "Region", "Item"
_TINY_NEGATIVE = 1e-9
sn = slice(None)

# Variants of the SUT split: which kind of item the workbook splits.
MODE_ACTIVITIES = "activities"
MODE_COMMODITIES = "commodities"
MODE_BOTH = "both"

# tolerances (delta, eps) above this value trigger a warning
SUT_SPLIT_TOLERANCE_WARNING = 1e-2


# ---------------------------------------------------------------------------
# Structure of the split (who is parent / child / stable)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SutSplitStructure:
    """Parent/child relations and master rows of one SUT split workbook."""

    regions: list[str]
    activities: list[str]
    commodities: list[str]
    new_activities: list[str]
    new_commodities: list[str]
    activity_parent: dict[str, str]
    commodity_parent: dict[str, str]
    master_rows: pd.DataFrame = field(repr=False)

    @property
    def mode(self) -> str:
        """Variant of the split: only activities, only commodities, or both."""
        if self.new_activities and self.new_commodities:
            return MODE_BOTH
        return MODE_COMMODITIES if self.new_commodities else MODE_ACTIVITIES

    @property
    def all_activities(self) -> list[str]:
        return list(self.activities) + list(self.new_activities)

    @property
    def all_commodities(self) -> list[str]:
        return list(self.commodities) + list(self.new_commodities)

    @property
    def parent_activities(self) -> list[str]:
        return [a for a in self.activities if a in set(self.activity_parent.values())]

    @property
    def parent_commodities(self) -> list[str]:
        return [c for c in self.commodities if c in set(self.commodity_parent.values())]

    @property
    def stable_activities(self) -> list[str]:
        parents = set(self.parent_activities)
        return [a for a in self.activities if a not in parents]

    @property
    def stable_commodities(self) -> list[str]:
        parents = set(self.parent_commodities)
        return [c for c in self.commodities if c not in parents]

    @property
    def activity_children(self) -> dict[str, list[str]]:
        return _invert_parent_map(self.activity_parent)

    @property
    def commodity_children(self) -> dict[str, list[str]]:
        return _invert_parent_map(self.commodity_parent)

    def activity_category(self, activity: str) -> str:
        if activity in self.activity_parent:
            return "new"
        return "parent" if activity in set(self.activity_parent.values()) else "stable"

    def commodity_category(self, commodity: str) -> str:
        if commodity in self.commodity_parent:
            return "new"
        return "parent" if commodity in set(self.commodity_parent.values()) else "stable"

    def aggregate_activity(self, activity: str) -> str:
        """Return the original (pre-split) activity a disaggregated one belongs to."""
        return self.activity_parent.get(activity, activity)

    def aggregate_commodity(self, commodity: str) -> str:
        """Return the original (pre-split) commodity a disaggregated one belongs to."""
        return self.commodity_parent.get(commodity, commodity)


def _invert_parent_map(parent_map: Mapping[str, str]) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {}
    for child, parent in parent_map.items():
        children.setdefault(parent, []).append(child)
    return children


def _is_blank(value) -> bool:
    return value is None or (not isinstance(value, str) and pd.isna(value)) or str(value).strip() == ""


def build_sut_split_structure(instance) -> SutSplitStructure:
    """Derive and validate parent/child relations from the master sheet."""

    master = instance.add_sectors_master
    regions = list(instance.get_index(MI["r"]))
    db_activities = list(instance.get_index(MI["a"]))
    db_commodities = list(instance.get_index(MI["c"]))

    activity_parent: dict[str, str] = {}
    commodity_parent: dict[str, str] = {}
    rows = []
    for position, row in master.iterrows():
        sheet_row = int(position) + 2
        activity, commodity = row[MI["a"]], row[MI["c"]]
        region = str(row[MSC["region"]]).strip()
        if region not in regions:
            raise WrongInput(
                f"Master sheet row {sheet_row}: region {region!r} is not a region of the database."
            )
        has_activity, has_commodity = not _is_blank(activity), not _is_blank(commodity)
        if has_activity == has_commodity:
            raise WrongInput(
                f"Master sheet row {sheet_row}: a 'Split' row must define exactly one of "
                f"'{MI['a']}' or '{MI['c']}'."
            )
        if has_activity:
            kind, item = "activity", str(activity).strip()
            parent = row[MSC["parent_activity"]]
            existing, parents = db_activities, activity_parent
            other_parent = row[MSC["parent_commodity"]]
            parent_label = MSC["parent_activity"]
        else:
            kind, item = "commodity", str(commodity).strip()
            parent = row[MSC["parent_commodity"]]
            existing, parents = db_commodities, commodity_parent
            other_parent = row[MSC["parent_activity"]]
            parent_label = MSC["parent_commodity"]
        if _is_blank(parent):
            raise WrongInput(
                f"Master sheet row {sheet_row}: split {kind} {item!r} needs a value in column '{parent_label}'."
            )
        if not _is_blank(other_parent):
            raise WrongInput(
                f"Master sheet row {sheet_row}: split {kind} {item!r} should only fill '{parent_label}'."
            )
        parent = str(parent).strip()
        if item in existing:
            raise WrongInput(f"Master sheet row {sheet_row}: {kind} {item!r} already exists in the database.")
        if parent not in existing:
            raise WrongInput(
                f"Master sheet row {sheet_row}: parent {kind} {parent!r} of {item!r} is not in the database."
            )
        if parents.setdefault(item, parent) != parent:
            raise WrongInput(f"Split {kind} {item!r} is assigned to different parents in the master sheet.")
        rows.append(
            {
                "kind": kind,
                "item": item,
                "region": region,
                "inventory": row[MSC["inventory_sheet"]],
                "unit": row[MSC["unit"]],
                "sheet_row": sheet_row,
            }
        )

    if not rows:
        raise WrongInput("No sectors are marked as 'Split' in the add-sectors workbook.")

    return SutSplitStructure(
        regions=regions,
        activities=db_activities,
        commodities=db_commodities,
        new_activities=list(activity_parent),
        new_commodities=list(commodity_parent),
        activity_parent=activity_parent,
        commodity_parent=commodity_parent,
        master_rows=pd.DataFrame(rows),
    )


# ---------------------------------------------------------------------------
# Validation and normalisation of the split-support sheets
# ---------------------------------------------------------------------------
def validate_sut_split_parameters(
    instance,
    *,
    cvxlab_path,
    input_data_files_type: str,
    only_input_data_gen: bool,
) -> None:
    """Validate user-facing split parameters before running heavy computations."""

    if instance.table_type != SUT:
        raise NotImplementable("SUT split validation is only available for SUT databases.")

    if not getattr(instance, "to_split_activities", []) and not getattr(instance, "to_split_commodities", []):
        raise WrongInput(
            "No sectors are marked as 'Split' in the add-sectors workbook. "
            "Set 'Add or Split' to 'Split' for the new activities/commodities before using split=True."
        )

    if not cvxlab_path:
        raise WrongInput(
            "cvxlab_path is required when split=True so MARIO can generate the CVXLab model directory."
        )

    if input_data_files_type not in {"xlsx", "csv"}:
        raise WrongInput("input_data_files_type should be either 'xlsx' or 'csv'.")

    if not Path(cvxlab_path).exists():
        raise FileNotFoundError(
            f"Directory where to create the CVXLab model '{cvxlab_path}' does not exist."
        )


def _numeric(frame: pd.DataFrame, column: str, sheet: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any():
        raise WrongInput(f"Invalid numeric values found in column '{column}' of split sheet '{sheet}'.")
    return values.astype(float)


def _clean_text_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    frame = frame.copy()
    for column in columns:
        frame[column] = frame[column].map(lambda value: "" if _is_blank(value) else str(value).strip())
    return frame


def _check_membership(values, allowed, *, sheet: str, label: str) -> None:
    unknown = sorted(set(values).difference(allowed))
    if unknown:
        raise WrongInput(f"Split sheet '{sheet}' contains unknown {label}: {unknown}")


def prepare_sut_split_support(instance) -> SutSplitStructure:
    """Normalize and validate the SUT split-support sheets.

    The normalized sheets replace ``instance.split_info``. The validated
    :class:`SutSplitStructure` is returned and also stored on
    ``instance.sut_split_structure``.
    """

    split_info = getattr(instance, "split_info", None)
    if not split_info:
        raise LackOfInput(
            "Split-support sheets are not loaded. Read the add-sectors workbook with split=True first."
        )

    structure = build_sut_split_structure(instance)
    regions = set(structure.regions)
    all_activities = set(structure.all_activities)
    all_commodities = set(structure.all_commodities)
    categories = set(instance.get_index(MI["n"]))
    normalized = {name: frame.copy() for name, frame in split_info.items()}

    # --- sheets the variant does not use ----------------------------------
    # Supply coef describes new activities and Final dem share new commodities: a split of
    # only one kind never reads the other sheet, so it is ignored (with a warning) if filled.
    unused_sheet = {
        MODE_COMMODITIES: ADD_SECTOR_SPLIT_SUPPLY_COEF_SHEET,
        MODE_ACTIVITIES: ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_SHEET,
    }.get(structure.mode)
    if unused_sheet is not None and not normalized[unused_sheet].dropna(how="all").empty:
        warnings.warn(
            f"Split sheet '{unused_sheet}' is not used by a {structure.mode}-only split and is ignored."
        )
        normalized[unused_sheet] = normalized[unused_sheet].iloc[0:0]

    # --- Total outputs --------------------------------------------------
    cols = ADD_SECTOR_SPLIT_SUT_OUTPUT_COLUMNS
    outputs = normalized[ADD_SECTOR_SPLIT_OUTPUT_SHEET]
    outputs = outputs.dropna(subset=[cols["region"]]).copy()
    outputs = _clean_text_columns(outputs, [cols["activity"], cols["commodity"], cols["region"]])
    both = (outputs[cols["activity"]] != "") == (outputs[cols["commodity"]] != "")
    if both.any():
        raise WrongInput(
            f"Split sheet '{ADD_SECTOR_SPLIT_OUTPUT_SHEET}': each row must define exactly one of "
            f"'{cols['activity']}' or '{cols['commodity']}'. Check rows: {(outputs.index[both] + 2).tolist()}"
        )
    _check_membership(
        outputs.loc[outputs[cols["activity"]] != "", cols["activity"]],
        structure.new_activities,
        sheet=ADD_SECTOR_SPLIT_OUTPUT_SHEET,
        label="activities not marked for split",
    )
    _check_membership(
        outputs.loc[outputs[cols["commodity"]] != "", cols["commodity"]],
        structure.new_commodities,
        sheet=ADD_SECTOR_SPLIT_OUTPUT_SHEET,
        label="commodities not marked for split",
    )
    _check_membership(outputs[cols["region"]], regions, sheet=ADD_SECTOR_SPLIT_OUTPUT_SHEET, label="regions")
    outputs[cols["quantity"]] = _numeric(outputs, cols["quantity"], ADD_SECTOR_SPLIT_OUTPUT_SHEET)
    if (outputs[cols["quantity"]] < 0).any():
        raise WrongInput("Split total outputs cannot contain negative quantities.")
    outputs["__item__"] = np.where(
        outputs[cols["activity"]] != "", outputs[cols["activity"]], outputs[cols["commodity"]]
    )
    if outputs.duplicated(subset=["__item__", cols["region"]]).any():
        raise WrongInput(
            f"Split sheet '{ADD_SECTOR_SPLIT_OUTPUT_SHEET}' defines the same item and region more than once."
        )
    required = {(row.item, row.region) for row in structure.master_rows.itertuples()}
    missing = sorted(required.difference(set(zip(outputs["__item__"], outputs[cols["region"]]))))
    if missing:
        raise WrongInput(
            f"Split sheet '{ADD_SECTOR_SPLIT_OUTPUT_SHEET}' is missing total output rows for "
            f"(item, region): {missing}"
        )
    unexpected = sorted(set(zip(outputs["__item__"], outputs[cols["region"]])).difference(required))
    if unexpected:
        raise WrongInput(
            f"Split sheet '{ADD_SECTOR_SPLIT_OUTPUT_SHEET}' has total output rows without a row in the "
            f"Master sheet for (item, region): {unexpected}"
        )
    outputs = _convert_total_output_units(instance, structure, outputs)
    normalized[ADD_SECTOR_SPLIT_OUTPUT_SHEET] = outputs.drop(columns="__item__").reset_index(drop=True)

    # --- Supply coefficients -------------------------------------------
    cols = ADD_SECTOR_SPLIT_SUPPLY_COEF_COLUMNS
    supply = normalized[ADD_SECTOR_SPLIT_SUPPLY_COEF_SHEET]
    supply = supply.dropna(how="all", subset=[cols["region_from"], cols["region_to"]]).copy()
    supply = _clean_text_columns(
        supply, [cols["region_from"], cols["region_to"], cols["activity_from"], cols["commodity_to"]]
    )
    _check_membership(
        pd.concat([supply[cols["region_from"]], supply[cols["region_to"]]]),
        regions,
        sheet=ADD_SECTOR_SPLIT_SUPPLY_COEF_SHEET,
        label="regions",
    )
    _check_membership(
        supply[cols["activity_from"]],
        structure.new_activities,
        sheet=ADD_SECTOR_SPLIT_SUPPLY_COEF_SHEET,
        label="activities not marked for split",
    )
    new_commodities_listed = sorted(set(supply[cols["commodity_to"]]).intersection(structure.new_commodities))
    if new_commodities_listed:
        raise WrongInput(
            f"Split sheet '{ADD_SECTOR_SPLIT_SUPPLY_COEF_SHEET}' lists new commodities "
            f"{new_commodities_listed}: their supply must be defined in the commodity inventory sheets."
        )
    _check_membership(
        supply[cols["commodity_to"]],
        structure.commodities,
        sheet=ADD_SECTOR_SPLIT_SUPPLY_COEF_SHEET,
        label="commodities",
    )
    supply[cols["coefficient"]] = _numeric(supply, cols["coefficient"], ADD_SECTOR_SPLIT_SUPPLY_COEF_SHEET)
    if (supply[cols["coefficient"]] < 0).any():
        raise WrongInput("Split supply coefficients cannot be negative.")
    key = [cols["region_from"], cols["region_to"], cols["activity_from"], cols["commodity_to"]]
    if supply.duplicated(subset=key).any():
        raise WrongInput(f"Split sheet '{ADD_SECTOR_SPLIT_SUPPLY_COEF_SHEET}' contains duplicated rows.")
    normalized[ADD_SECTOR_SPLIT_SUPPLY_COEF_SHEET] = supply.reset_index(drop=True)

    # --- Final demand shares -------------------------------------------
    cols = ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_COLUMNS
    shares = normalized[ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_SHEET]
    shares = shares.dropna(how="all", subset=[cols["region_from"], cols["region_to"]]).copy()
    shares = _clean_text_columns(
        shares,
        [cols["region_from"], cols["region_to"], cols["commodity"], cols["consumption_category"]],
    )
    _check_membership(
        pd.concat([shares[cols["region_from"]], shares[cols["region_to"]]]),
        regions,
        sheet=ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_SHEET,
        label="regions",
    )
    _check_membership(
        shares[cols["commodity"]],
        structure.new_commodities,
        sheet=ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_SHEET,
        label="commodities not marked for split",
    )
    _check_membership(
        shares[cols["consumption_category"]],
        categories,
        sheet=ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_SHEET,
        label="consumption categories",
    )
    shares[cols["share"]] = _numeric(shares, cols["share"], ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_SHEET)
    if ((shares[cols["share"]] < -1) | (shares[cols["share"]] > 1)).any():
        raise WrongInput("Split final demand shares should be between -1 and 1.")
    key = [cols["region_from"], cols["region_to"], cols["commodity"], cols["consumption_category"]]
    if shares.duplicated(subset=key).any():
        raise WrongInput(f"Split sheet '{ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_SHEET}' contains duplicated rows.")
    normalized[ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_SHEET] = shares.reset_index(drop=True)

    # --- Exclusions (optional) -----------------------------------------
    cols = ADD_SECTOR_SPLIT_USE_EXCLUSION_COLUMNS
    use_excl = normalized.get(ADD_SECTOR_SPLIT_USE_EXCLUSION_SHEET, pd.DataFrame(columns=list(cols.values())))
    use_excl = use_excl.dropna(how="all", subset=[cols["region_from"], cols["region_to"]]).copy()
    use_excl = _clean_text_columns(
        use_excl, [cols["region_from"], cols["region_to"], cols["commodity_from"], cols["activity_to"]]
    )
    _check_membership(
        pd.concat([use_excl[cols["region_from"]], use_excl[cols["region_to"]]]),
        regions,
        sheet=ADD_SECTOR_SPLIT_USE_EXCLUSION_SHEET,
        label="regions",
    )
    _check_membership(
        use_excl[cols["commodity_from"]], all_commodities, sheet=ADD_SECTOR_SPLIT_USE_EXCLUSION_SHEET, label="commodities"
    )
    _check_membership(
        use_excl[cols["activity_to"]], all_activities, sheet=ADD_SECTOR_SPLIT_USE_EXCLUSION_SHEET, label="activities"
    )
    normalized[ADD_SECTOR_SPLIT_USE_EXCLUSION_SHEET] = use_excl.reset_index(drop=True)

    cols = ADD_SECTOR_SPLIT_SUPPLY_EXCLUSION_COLUMNS
    supply_excl = normalized.get(
        ADD_SECTOR_SPLIT_SUPPLY_EXCLUSION_SHEET, pd.DataFrame(columns=list(cols.values()))
    )
    supply_excl = supply_excl.dropna(how="all", subset=[cols["region_from"], cols["region_to"]]).copy()
    supply_excl = _clean_text_columns(
        supply_excl, [cols["region_from"], cols["region_to"], cols["activity_from"], cols["commodity_to"]]
    )
    _check_membership(
        pd.concat([supply_excl[cols["region_from"]], supply_excl[cols["region_to"]]]),
        regions,
        sheet=ADD_SECTOR_SPLIT_SUPPLY_EXCLUSION_SHEET,
        label="regions",
    )
    _check_membership(
        supply_excl[cols["activity_from"]],
        all_activities,
        sheet=ADD_SECTOR_SPLIT_SUPPLY_EXCLUSION_SHEET,
        label="activities",
    )
    _check_membership(
        supply_excl[cols["commodity_to"]],
        all_commodities,
        sheet=ADD_SECTOR_SPLIT_SUPPLY_EXCLUSION_SHEET,
        label="commodities",
    )
    normalized[ADD_SECTOR_SPLIT_SUPPLY_EXCLUSION_SHEET] = supply_excl.reset_index(drop=True)

    # --- Tolerances (optional) -----------------------------------------
    name_col = ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS["name"]
    value_col = ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS["value"]
    tolerances = normalized.get(
        ADD_SECTOR_SPLIT_TOLERANCE_SHEET, pd.DataFrame(columns=[name_col, value_col])
    )
    tolerances = tolerances.dropna(how="all")
    if tolerances.empty:
        tolerances = pd.DataFrame(ADD_SECTOR_SPLIT_TOLERANCE_DEFAULTS, columns=[name_col, value_col])
    present = set(tolerances[name_col].dropna().astype(str).str.strip())
    required_tol = {name for name, _ in ADD_SECTOR_SPLIT_TOLERANCE_DEFAULTS}
    if not required_tol.issubset(present):
        raise WrongInput(f"Split sheet '{ADD_SECTOR_SPLIT_TOLERANCE_SHEET}' should define at least {sorted(required_tol)}.")
    tolerances = tolerances.loc[:, [name_col, value_col]].copy()
    tolerances[name_col] = tolerances[name_col].astype(str).str.strip()
    tolerances[value_col] = _numeric(tolerances, value_col, ADD_SECTOR_SPLIT_TOLERANCE_SHEET)
    extra = sorted(set(tolerances[name_col]) - required_tol)
    if extra:
        warnings.warn(
            f"Split sheet '{ADD_SECTOR_SPLIT_TOLERANCE_SHEET}': the tolerances {extra} are not used by the "
            f"SUT split models and are ignored."
        )
        tolerances = tolerances[tolerances[name_col].isin(required_tol)]
    if (tolerances[value_col] < 0).any():
        raise WrongInput(f"Split sheet '{ADD_SECTOR_SPLIT_TOLERANCE_SHEET}' cannot contain negative tolerances.")
    large = tolerances[tolerances[value_col] > SUT_SPLIT_TOLERANCE_WARNING]
    if not large.empty:
        warnings.warn(
            f"Split sheet '{ADD_SECTOR_SPLIT_TOLERANCE_SHEET}': {dict(zip(large[name_col], large[value_col]))} "
            f"exceed {SUT_SPLIT_TOLERANCE_WARNING:g}; the split flows may deviate noticeably from the original table "
            f"and from the known totals."
        )
    normalized[ADD_SECTOR_SPLIT_TOLERANCE_SHEET] = tolerances.reset_index(drop=True)

    instance.split_info = normalized
    instance.sut_split_structure = structure
    return structure


def _convert_total_output_units(instance, structure: SutSplitStructure, outputs: pd.DataFrame) -> pd.DataFrame:
    """Convert ``Total outputs`` quantities to the database unit of the parent item."""

    cols = ADD_SECTOR_SPLIT_SUT_OUTPUT_COLUMNS
    converted = outputs.copy()
    if converted.empty:
        return converted

    ureg = pint.UnitRegistry()
    for idx, row in converted.iterrows():
        if row[cols["activity"]] != "":
            level, item = MI["a"], row[cols["activity"]]
            parent = structure.activity_parent[item]
        else:
            level, item = MI["c"], row[cols["commodity"]]
            parent = structure.commodity_parent[item]
        target_unit = instance.units[level].loc[parent, "unit"]
        source_unit = row[cols["unit"]]
        if _is_blank(source_unit) or str(source_unit).strip() == str(target_unit):
            converted.at[idx, cols["unit"]] = target_unit
            continue
        try:
            factor = ureg(str(source_unit)).to(str(target_unit)).magnitude
        except Exception as exc:  # noqa: BLE001
            raise WrongInput(
                f"Split quantity unit '{source_unit}' for {item!r} is not convertible to '{target_unit}'."
            ) from exc
        converted.at[idx, cols["quantity"]] = float(row[cols["quantity"]]) * factor
        converted.at[idx, cols["unit"]] = target_unit
    return converted


# ---------------------------------------------------------------------------
# Inventories
# ---------------------------------------------------------------------------
@dataclass
class _ActivityInventory:
    use: pd.Series  # (Region, Item) -> coefficient, commodities consumed per unit of output
    factors: pd.Series  # factor -> coefficient
    satellites: pd.Series  # satellite account -> coefficient


def _inventory_frame(instance, row) -> pd.DataFrame:
    workbook = getattr(instance, "add_sectors_workbook", None)
    sheets = workbook.inventories_by_sheet if workbook is not None else {}
    name = row.inventory
    if _is_blank(name) or str(name) not in sheets:
        raise WrongInput(
            f"Inventory sheet {name!r} (master sheet row {row.sheet_row}) was not found in the add-sectors workbook."
        )
    frame = sheets[str(name)].copy()
    required = [INV["quantity"], INV["item_type"], INV["db_item"], INV["db_region"]]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise WrongInput(f"Inventory sheet {name!r} is missing columns: {missing}")
    frame = frame.dropna(subset=[INV["db_item"]])
    frame = _clean_text_columns(frame, [INV["item_type"], INV["db_item"], INV["db_region"]])
    quantity = pd.to_numeric(frame[INV["quantity"]], errors="coerce")
    if quantity.isna().any():
        raise WrongInput(f"Inventory sheet {name!r} contains non-numeric quantities.")
    frame[INV["quantity"]] = quantity.astype(float)
    return frame


def _read_activity_inventory(instance, structure: SutSplitStructure, row) -> _ActivityInventory:
    frame = _inventory_frame(instance, row)
    allowed = {MI["c"], MI["f"], MI["k"]}
    unexpected = sorted(set(frame[INV["item_type"]]).difference(allowed))
    if unexpected:
        raise WrongInput(
            f"Inventory sheet {row.inventory!r} of activity {row.item!r} has unexpected item types: {unexpected}. "
            f"Use {sorted(allowed)}."
        )

    commodities = frame[frame[INV["item_type"]] == MI["c"]]
    _check_membership(commodities[INV["db_item"]], structure.all_commodities, sheet=str(row.inventory), label="commodities")
    if (commodities[INV["db_region"]] == "").any():
        raise WrongInput(f"Inventory sheet {row.inventory!r}: commodity rows need a '{INV['db_region']}'.")
    _check_membership(commodities[INV["db_region"]], structure.regions, sheet=str(row.inventory), label="regions")
    use = commodities.groupby([INV["db_region"], INV["db_item"]])[INV["quantity"]].sum()
    use.index.names = [REGION, ITEM]

    factors = frame[frame[INV["item_type"]] == MI["f"]]
    _check_membership(
        factors[INV["db_item"]], instance.get_index(MI["f"]), sheet=str(row.inventory), label="factors of production"
    )
    satellites = frame[frame[INV["item_type"]] == MI["k"]]
    _check_membership(
        satellites[INV["db_item"]], instance.get_index(MI["k"]), sheet=str(row.inventory), label="satellite accounts"
    )
    return _ActivityInventory(
        use=use,
        factors=factors.groupby(INV["db_item"])[INV["quantity"]].sum(),
        satellites=satellites.groupby(INV["db_item"])[INV["quantity"]].sum(),
    )


def _read_commodity_inventory(instance, structure: SutSplitStructure, row) -> pd.Series:
    """Return the share of the commodity output made by each ``(Region, Activity)``."""

    frame = _inventory_frame(instance, row)
    unexpected = sorted(set(frame[INV["item_type"]]).difference({MI["a"]}))
    if unexpected:
        raise WrongInput(
            f"Inventory sheet {row.inventory!r} of commodity {row.item!r} should only list "
            f"'{MI['a']}' rows, found: {unexpected}."
        )
    _check_membership(frame[INV["db_item"]], structure.all_activities, sheet=str(row.inventory), label="activities")
    if (frame[INV["db_region"]] == "").any():
        raise WrongInput(f"Inventory sheet {row.inventory!r}: activity rows need a '{INV['db_region']}'.")
    _check_membership(frame[INV["db_region"]], structure.regions, sheet=str(row.inventory), label="regions")
    shares = frame.groupby([INV["db_region"], INV["db_item"]])[INV["quantity"]].sum()
    shares.index.names = [REGION, ITEM]
    return shares


# ---------------------------------------------------------------------------
# Original flows
# ---------------------------------------------------------------------------
def _get_flow(instance, key: str, scenario: str) -> pd.DataFrame:
    if instance.has_matrix(key, scenario=scenario):
        return instance.get_block_as_pandas(key, scenario=scenario)
    return instance.resolve(key, scenario=scenario)


def _two_level_index(index: pd.Index) -> pd.MultiIndex:
    return pd.MultiIndex.from_arrays(
        [index.get_level_values(0), index.get_level_values(-1)], names=[REGION, ITEM]
    )


def _select_level(frame: pd.DataFrame, level: str, *, axis: int) -> pd.DataFrame:
    """Keep the entries of one MARIO ``Level`` on an axis and flatten it to ``(Region, Item)``."""

    labels = frame.index if axis == 0 else frame.columns
    keep = labels.get_level_values(1) == level
    selected = frame.loc[keep, :] if axis == 0 else frame.loc[:, keep]
    if axis == 0:
        selected = selected.copy()
        selected.index = _two_level_index(selected.index)
    else:
        selected = selected.copy()
        selected.columns = _two_level_index(selected.columns)
    return selected


@dataclass
class SutOriginalFlows:
    """Original (aggregated) SUT flows in two-level ``(Region, Item)`` form."""

    U: pd.DataFrame  # commodity x activity
    M: pd.DataFrame  # activity x commodity (Make / supply flows)
    Y: pd.DataFrame  # commodity x (Region, consumption category)
    V: pd.DataFrame  # factor x activity
    Vc: pd.DataFrame  # factor x commodity columns (usually zero)
    E: pd.DataFrame  # satellite x activity
    Ec: pd.DataFrame  # satellite x commodity columns
    EY: pd.DataFrame
    VY: pd.DataFrame
    Xa: pd.Series
    Xc: pd.Series
    axis_names: list[str]


def collect_original_sut_flows(instance, scenario: str = "baseline") -> SutOriginalFlows:
    """Read the original flows of one scenario as two-level frames."""

    U = _select_level(_select_level(_get_flow(instance, _ENUM["U"], scenario), MI["c"], axis=0), MI["a"], axis=1)
    M = _select_level(_select_level(_get_flow(instance, _ENUM["S"], scenario), MI["a"], axis=0), MI["c"], axis=1)
    Y = _select_level(_get_flow(instance, _ENUM["Y"], scenario), MI["c"], axis=0)
    Y.columns = _two_level_index(Y.columns)
    V_all = _get_flow(instance, _ENUM["V"], scenario)
    E_all = _get_flow(instance, _ENUM["E"], scenario)
    flows = SutOriginalFlows(
        U=U,
        M=M,
        Y=Y,
        V=_select_level(V_all, MI["a"], axis=1),
        Vc=_select_level(V_all, MI["c"], axis=1),
        E=_select_level(E_all, MI["a"], axis=1),
        Ec=_select_level(E_all, MI["c"], axis=1),
        EY=_get_flow(instance, _ENUM["EY"], scenario),
        VY=_get_flow(instance, _ENUM["VY"], scenario),
        Xa=M.sum(axis=1),
        Xc=M.sum(axis=0),
        axis_names=list(_get_flow(instance, _ENUM["U"], scenario).index.names),
    )
    return flows


# ---------------------------------------------------------------------------
# Priors
# ---------------------------------------------------------------------------
@dataclass
class SutSplitPriors:
    """A-priori matrices and masks consumed by the SUT CVXLab split model.

    All matrices are expressed at the disaggregated granularity (parent, new and
    stable items). Cells that the optimization does not use as a prior are zero.
    A prior that the model of the split variant does not consume is ``None``:
    ``U0`` and ``V0`` for a commodity-only split, ``Y0`` for an activity-only split.
    """

    structure: SutSplitStructure
    original: SutOriginalFlows
    Xa: pd.Series  # prior output of every (Region, activity)
    Xc: pd.Series  # prior output of every (Region, commodity)
    # known total of the new items, indexed by (Region, item): the total cost of the new
    # activities, or the total use of the new commodities for a commodity-only split
    Xnew: pd.Series
    U0: pd.DataFrame | None
    M0: pd.DataFrame
    Y0: pd.DataFrame | None
    V0: pd.DataFrame | None
    zero_U: pd.DataFrame  # 1 where the cell is known to be zero
    zero_M: pd.DataFrame
    inventories: dict = field(default_factory=dict, repr=False)
    mode: str = MODE_BOTH


def _warn_and_clip(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    values = frame.to_numpy(dtype=float)
    negative = values < 0
    if negative.any():
        if (values[negative] < -_TINY_NEGATIVE).any():
            warnings.warn(f"Negative values found in split prior {label}. They are clipped to zero.")
        values = np.where(negative, 0.0, values)
        return pd.DataFrame(values, index=frame.index, columns=frame.columns)
    return frame


def _output_series(index: pd.MultiIndex, old: pd.Series) -> pd.Series:
    return old.reindex(index).fillna(0.0)


def build_sut_split_priors(
    instance,
    structure: SutSplitStructure | None = None,
    *,
    base_scenario: str = "baseline",
    residue=None,
) -> SutSplitPriors:
    """Build U0, M0, Y0, V0, the new-activity outputs and the zero masks."""

    structure = structure or instance.sut_split_structure
    split_info = instance.split_info
    original = collect_original_sut_flows(instance, base_scenario)

    A_all, C_all, regions = structure.all_activities, structure.all_commodities, structure.regions
    act_index = pd.MultiIndex.from_product([regions, A_all], names=[REGION, ITEM])
    com_index = pd.MultiIndex.from_product([regions, C_all], names=[REGION, ITEM])

    Uold, Mold, Yold, Vold = original.U, original.M, original.Y, original.V
    if residue is not None:
        threshold = float(residue)
        Uold, Mold, Yold, Vold = (
            frame.where(frame.abs() >= threshold, 0.0) for frame in (Uold, Mold, Yold, Vold)
        )

    # --- outputs ---------------------------------------------------------
    Xa = _output_series(act_index, original.Xa)
    Xc = _output_series(com_index, original.Xc)
    mode = structure.mode
    Xnew = pd.Series(0.0, index=com_index if mode == MODE_COMMODITIES else act_index, name="production")
    out_cols = ADD_SECTOR_SPLIT_SUT_OUTPUT_COLUMNS
    outputs = split_info[ADD_SECTOR_SPLIT_OUTPUT_SHEET]
    for _, row in outputs.iterrows():
        region, quantity = row[out_cols["region"]], float(row[out_cols["quantity"]])
        if row[out_cols["activity"]] != "":
            item = row[out_cols["activity"]]
            parent = structure.activity_parent[item]
            series, label = Xa, "activity"
            Xnew[(region, item)] = quantity
        else:
            item = row[out_cols["commodity"]]
            parent = structure.commodity_parent[item]
            series, label = Xc, "commodity"
            if mode == MODE_COMMODITIES:
                Xnew[(region, item)] = quantity
        parent_output = float(series[(region, parent)])
        if quantity > parent_output + _TINY_NEGATIVE:
            raise WrongInput(
                f"Split {label} output larger than parent {label}: {item!r} in region {region!r} has output "
                f"{quantity} which exceeds parent {parent!r} output {parent_output}."
            )
        series[(region, item)] = quantity
        series[(region, parent)] = parent_output - quantity
    for series, label in ((Xa, "activity"), (Xc, "commodity")):
        negatives = series[series < -_TINY_NEGATIVE]
        if not negatives.empty:
            raise WrongInput(
                f"Split total outputs generate negative parent-{label} outputs. "
                f"Check rows: {negatives.index.tolist()}"
            )
        series[series < 0] = 0.0

    # --- inventories -----------------------------------------------------
    inventories: dict = {}
    for row in structure.master_rows.itertuples():
        key = (row.kind, row.item, row.region)
        inventories[key] = (
            _read_activity_inventory(instance, structure, row)
            if row.kind == "activity"
            else _read_commodity_inventory(instance, structure, row)
        )
        _warn_if_not_unitary(row, inventories[key])

    # --- U0 and V0 ---------------------------------------------------------
    U0 = V0 = None
    if mode != MODE_COMMODITIES:
        old_U = Uold.reindex(index=com_index, columns=act_index).fillna(0.0)
        old_V = Vold.reindex(columns=act_index).fillna(0.0)
        stable_rows = pd.MultiIndex.from_product([regions, structure.stable_commodities], names=[REGION, ITEM])
        all_rows = com_index
        U0 = old_U.copy()
        V0 = old_V.copy()
        changed_columns = [
            col for col in act_index if col[1] in structure.activity_parent or col[1] in structure.parent_activities
        ]
        # unknown cells (parent and new columns) start at zero and are filled below
        U0[changed_columns] = 0.0
        V0[changed_columns] = 0.0

        for row in structure.master_rows[structure.master_rows.kind == "activity"].itertuples():
            inv: _ActivityInventory = inventories[("activity", row.item, row.region)]
            column = (row.region, row.item)
            output = float(Xa[column])
            U0[column] = inv.use.reindex(all_rows).fillna(0.0).to_numpy() * output
            if inv.factors.empty:
                # no value-added rows in the inventory: value added closes the activity balance
                # (output minus inputs), distributed like the value added of the parent
                parent_va = old_V[(row.region, structure.activity_parent[row.item])]
                composition = parent_va / parent_va.sum() if parent_va.sum() > 0 else parent_va * 0 + 1 / len(parent_va)
                V0[column] = composition.to_numpy() * max(1.0 - float(inv.use.sum()), 0.0) * output
            else:
                V0[column] = inv.factors.reindex(V0.index).fillna(0.0).to_numpy() * output

        for parent in structure.parent_activities:
            children = structure.activity_children[parent]
            for region in regions:
                column = (region, parent)
                child_columns = [(region, child) for child in children]
                U0.loc[stable_rows, column] = old_U.loc[stable_rows, column] - U0.loc[stable_rows, child_columns].sum(axis=1)
                V0[column] = old_V[column] - V0[child_columns].sum(axis=1)
        U0 = _warn_and_clip(U0, "U0")
        V0 = _warn_and_clip(V0, "V0")

    # --- M0 -----------------------------------------------------------------
    M0 = Mold.reindex(index=act_index, columns=com_index).fillna(0.0)
    for item in structure.new_activities:
        for region in regions:
            M0.loc[(region, item), :] = 0.0
    for item in structure.new_commodities:
        for region in regions:
            M0[(region, item)] = 0.0

    supply = split_info[ADD_SECTOR_SPLIT_SUPPLY_COEF_SHEET]
    sc = ADD_SECTOR_SPLIT_SUPPLY_COEF_COLUMNS
    for _, row in supply.iterrows():
        output = Xc[(row[sc["region_to"]], row[sc["commodity_to"]])]
        M0.loc[(row[sc["region_from"]], row[sc["activity_from"]]), (row[sc["region_to"]], row[sc["commodity_to"]])] = (
            float(row[sc["coefficient"]]) * float(output)
        )

    for row in structure.master_rows[structure.master_rows.kind == "commodity"].itertuples():
        shares: pd.Series = inventories[("commodity", row.item, row.region)]
        M0[(row.region, row.item)] = shares.reindex(act_index).fillna(0.0).to_numpy() * float(Xc[(row.region, row.item)])

    # remainders: every disaggregated cell of an aggregated (parent, parent) cell
    for parent_a in structure.parent_activities + structure.stable_activities:
        a_group = [parent_a] + structure.activity_children.get(parent_a, [])
        for parent_c in structure.parent_commodities + structure.stable_commodities:
            c_group = [parent_c] + structure.commodity_children.get(parent_c, [])
            if len(a_group) == 1 and len(c_group) == 1:
                continue
            for region_a in regions:
                rows = [(region_a, a) for a in a_group]
                for region_c in regions:
                    cols = [(region_c, c) for c in c_group]
                    block = M0.loc[rows, cols]
                    total = float(Mold.loc[(region_a, parent_a), (region_c, parent_c)]) if (
                        (region_a, parent_a) in Mold.index and (region_c, parent_c) in Mold.columns
                    ) else 0.0
                    remainder = total - (block.to_numpy().sum() - float(block.iloc[0, 0]))
                    M0.loc[(region_a, parent_a), (region_c, parent_c)] = remainder
    M0 = _warn_and_clip(M0, "M0")

    # --- Y0 ------------------------------------------------------------------
    Y0 = None
    if mode != MODE_ACTIVITIES:
        Y0 = Yold.reindex(index=com_index).fillna(0.0)
        fd = ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_COLUMNS
        shares_sheet = split_info[ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_SHEET]
        share_lookup = {
            (r_from, r_to, commodity, category): float(share)
            for r_from, r_to, commodity, category, share in zip(
                shares_sheet[fd["region_from"]],
                shares_sheet[fd["region_to"]],
                shares_sheet[fd["commodity"]],
                shares_sheet[fd["consumption_category"]],
                shares_sheet[fd["share"]],
            )
        }
        missing_shares = set()
        for child, parent in structure.commodity_parent.items():
            for region in regions:
                parent_row = Yold.loc[(region, parent)]
                new_row = pd.Series(0.0, index=Y0.columns)
                for column in Y0.columns:
                    share = share_lookup.get((region, column[0], child, column[1]))
                    if share is None:
                        missing_shares.add((region, column[0], child, column[1]))
                        share = 0.0
                    new_row[column] = float(parent_row[column]) * share
                Y0.loc[(region, child)] = new_row.to_numpy()
                Y0.loc[(region, parent)] = Y0.loc[(region, parent)].to_numpy() - new_row.to_numpy()
        if missing_shares:
            warnings.warn(
                f"Split sheet '{ADD_SECTOR_SPLIT_FINAL_DEMAND_SHARE_SHEET}' has no share for "
                f"(Region_from, Region_to, Commodity, Consumption category) = {sorted(missing_shares)[:5]}"
                f"{' ...' if len(missing_shares) > 5 else ''}; a share of 0 is assumed."
            )

    # --- zero masks -----------------------------------------------------------
    zero_U = _structural_zero_mask(
        Uold,
        row_map=[(r, structure.aggregate_commodity(c)) for r, c in com_index],
        col_map=[(r, structure.aggregate_activity(a)) for r, a in act_index],
        index=com_index,
        columns=act_index,
    )
    zero_M = _structural_zero_mask(
        Mold,
        row_map=[(r, structure.aggregate_activity(a)) for r, a in act_index],
        col_map=[(r, structure.aggregate_commodity(c)) for r, c in com_index],
        index=act_index,
        columns=com_index,
    )
    uc = ADD_SECTOR_SPLIT_USE_EXCLUSION_COLUMNS
    _apply_exclusions(
        zero_U,
        split_info[ADD_SECTOR_SPLIT_USE_EXCLUSION_SHEET],
        row_keys=(uc["region_from"], uc["commodity_from"]),
        col_keys=(uc["region_to"], uc["activity_to"]),
    )
    sx = ADD_SECTOR_SPLIT_SUPPLY_EXCLUSION_COLUMNS
    _apply_exclusions(
        zero_M,
        split_info[ADD_SECTOR_SPLIT_SUPPLY_EXCLUSION_SHEET],
        row_keys=(sx["region_from"], sx["activity_from"]),
        col_keys=(sx["region_to"], sx["commodity_to"]),
    )

    return SutSplitPriors(
        structure=structure,
        original=original,
        Xa=Xa,
        Xc=Xc,
        Xnew=Xnew,
        U0=U0,
        M0=M0,
        Y0=Y0,
        V0=V0,
        zero_U=zero_U,
        zero_M=zero_M,
        inventories=inventories,
        mode=mode,
    )


def _warn_if_not_unitary(row, inventory) -> None:
    if row.kind == "activity":
        total = float(inventory.use.sum() + inventory.factors.sum())
        label = "inputs plus value added"
        if inventory.factors.empty and total <= 1.0 + 1e-3:
            return  # value added closes the balance
    else:
        total = float(inventory.sum())
        label = "supply shares"
    if abs(total - 1.0) > 1e-3:
        warnings.warn(
            f"Inventory sheet {row.inventory!r} ({row.kind} {row.item!r}, region {row.region!r}): "
            f"{label} sum to {total:.6g} instead of 1."
        )


def _structural_zero_mask(
    old: pd.DataFrame,
    *,
    row_map: list[tuple],
    col_map: list[tuple],
    index: pd.MultiIndex,
    columns: pd.MultiIndex,
) -> pd.DataFrame:
    """Flag the disaggregated cells whose aggregated original cell is zero."""

    expanded = old.reindex(index=pd.MultiIndex.from_tuples(row_map), columns=pd.MultiIndex.from_tuples(col_map))
    values = expanded.fillna(0.0).to_numpy() == 0
    return pd.DataFrame(values, index=index, columns=columns)


def _apply_exclusions(mask: pd.DataFrame, exclusions: pd.DataFrame, *, row_keys, col_keys) -> None:
    if exclusions is None or exclusions.empty:
        return
    rows = mask.index.get_indexer(
        pd.MultiIndex.from_arrays([exclusions[row_keys[0]], exclusions[row_keys[1]]])
    )
    cols = mask.columns.get_indexer(
        pd.MultiIndex.from_arrays([exclusions[col_keys[0]], exclusions[col_keys[1]]])
    )
    if (rows < 0).any() or (cols < 0).any():
        raise WrongInput("Split exclusions refer to cells that are not in the disaggregated table.")
    values = mask.to_numpy().copy()
    values[rows, cols] = True
    mask.loc[:, :] = values


# ---------------------------------------------------------------------------
# Assembly of MARIO flows
# ---------------------------------------------------------------------------
def _productive_index(structure: SutSplitStructure, names: list[str]) -> pd.MultiIndex:
    entries = [(r, MI["a"], a) for r in structure.regions for a in structure.all_activities]
    entries += [(r, MI["c"], c) for r in structure.regions for c in structure.all_commodities]
    return pd.MultiIndex.from_tuples(entries, names=names)


def _with_level(index: pd.MultiIndex, level: str, names: list[str]) -> pd.MultiIndex:
    return pd.MultiIndex.from_arrays(
        [index.get_level_values(0), [level] * len(index), index.get_level_values(1)], names=names
    )


def _split_columns_proportionally(
    frame: pd.DataFrame,
    *,
    children: Mapping[str, str],
    old_output: pd.Series,
    new_output: pd.Series,
    columns: pd.MultiIndex,
    regions: list[str],
    overrides: pd.DataFrame | None = None,
    label: str,
) -> pd.DataFrame:
    """Create columns for new items with the parent's intensity; reduce the parent accordingly.

    ``overrides`` may hold explicit per-unit intensities (same rows as ``frame``) for some
    ``(Region, Item)`` columns of new items.
    """

    out = frame.reindex(columns=columns).fillna(0.0)
    for child, parent in children.items():
        for region in regions:
            parent_col, child_col = (region, parent), (region, child)
            parent_output = float(old_output.get((region, parent), 0.0))
            child_output = float(new_output.get(child_col, 0.0))
            if overrides is not None and child_col in overrides.columns:
                intensity = overrides[child_col].to_numpy(dtype=float)
            elif parent_output > 0:
                intensity = frame[parent_col].to_numpy(dtype=float) / parent_output
            else:
                intensity = np.zeros(len(frame))
            out[child_col] = intensity * child_output
    for parent in set(children.values()):
        for region in regions:
            child_cols = [(region, child) for child, p in children.items() if p == parent]
            out[(region, parent)] = out[(region, parent)] - out[child_cols].sum(axis=1)
    return _warn_and_clip(out, label)


def assemble_sut_split_flows(
    structure: SutSplitStructure,
    original: SutOriginalFlows,
    priors: SutSplitPriors,
    *,
    U: pd.DataFrame | None,
    M: pd.DataFrame,
    Y: pd.DataFrame | None,
    V: pd.DataFrame | None,
    Xa: pd.Series,
    Xc: pd.Series,
) -> dict[str, pd.DataFrame]:
    """Assemble full MARIO flow matrices (``Z, E, V, Y, EY, VY, X``) from two-level blocks.

    ``Xa``/``Xc`` are the final outputs used to scale the satellite accounts and
    commodity-side columns of the new items.
    """

    # a block without a prior (None) keeps the original values; new items start at zero
    U = original.U if U is None else U
    Y = original.Y if Y is None else Y
    V = original.V if V is None else V

    names = original.axis_names
    productive = _productive_index(structure, names)
    act_index = pd.MultiIndex.from_product([structure.regions, structure.all_activities], names=[REGION, ITEM])
    com_index = pd.MultiIndex.from_product([structure.regions, structure.all_commodities], names=[REGION, ITEM])
    act3 = _with_level(act_index, MI["a"], names)
    com3 = _with_level(com_index, MI["c"], names)

    Z = pd.DataFrame(0.0, index=productive, columns=productive)
    Z.loc[act3, com3] = M.reindex(index=act_index, columns=com_index).fillna(0.0).to_numpy()
    Z.loc[com3, act3] = U.reindex(index=com_index, columns=act_index).fillna(0.0).to_numpy()

    X = pd.DataFrame(0.0, index=productive, columns=["production"])
    X.loc[act3, "production"] = Xa.reindex(act_index).fillna(0.0).to_numpy()
    X.loc[com3, "production"] = Xc.reindex(com_index).fillna(0.0).to_numpy()

    fd_columns = original.Y.columns
    fd3 = pd.MultiIndex.from_arrays(
        [fd_columns.get_level_values(0), [MI["n"]] * len(fd_columns), fd_columns.get_level_values(1)], names=names
    )
    Y_full = pd.DataFrame(0.0, index=productive, columns=fd3)
    Y_full.loc[com3, :] = Y.reindex(index=com_index).fillna(0.0).to_numpy()

    # Value added and satellite accounts (activity columns come from the solved/prior blocks).
    old_Xa, old_Xc = original.Xa, original.Xc
    act_children, com_children = structure.activity_parent, structure.commodity_parent

    def _side(activity_columns, commodity_source, *, label):
        commodity_columns = _split_columns_proportionally(
            commodity_source,
            children=com_children,
            old_output=old_Xc,
            new_output=Xc,
            columns=com_index,
            regions=structure.regions,
            label=f"{label} (commodity columns)",
        )
        out = pd.concat([activity_columns, commodity_columns], axis=1)
        out.columns = productive
        return out

    V_full = _side(V.reindex(columns=act_index).fillna(0.0), original.Vc, label="V")

    overrides = _satellite_overrides(structure, priors, original.E.index, act_index)
    E_act = _split_columns_proportionally(
        original.E,
        children=act_children,
        old_output=old_Xa,
        new_output=Xa,
        columns=act_index,
        regions=structure.regions,
        overrides=overrides,
        label="E (activity columns)",
    )
    E_full = _side(E_act, original.Ec, label="E")

    return {
        _ENUM["Z"]: Z,
        _ENUM["E"]: E_full,
        _ENUM["V"]: V_full,
        _ENUM["Y"]: Y_full,
        _ENUM["EY"]: original.EY.copy(),
        _ENUM["VY"]: original.VY.copy(),
        _ENUM["X"]: X,
    }


def _satellite_overrides(structure, priors, satellite_index, act_index) -> pd.DataFrame | None:
    """Per-unit satellite intensities given in the activity inventories (Satellite account rows)."""

    entries = {}
    for (kind, item, region), inventory in priors.inventories.items():
        if kind != "activity" or inventory.satellites.empty:
            continue
        entries[(region, item)] = inventory.satellites
    if not entries:
        return None
    # missing satellite rows in an inventory that lists some are taken as 0
    frame = pd.DataFrame(
        {column: series.reindex(satellite_index).fillna(0.0) for column, series in entries.items()}
    )
    frame.columns = pd.MultiIndex.from_tuples(frame.columns, names=[REGION, ITEM])
    return frame


# ---------------------------------------------------------------------------
# Prior scenario
# ---------------------------------------------------------------------------
def build_sut_split_scenario(
    instance,
    *,
    base_scenario: str = "baseline",
    scenario_label: str = "baseline",
    residue=None,
) -> tuple[str, SutSplitPriors]:
    """Create the deterministic ``split_<scenario>`` scenario from the priors.

    Cells that the priors leave undetermined are zero in this scenario; it is the
    starting point handed to CVXLab, not a balanced table.
    """

    structure = instance.sut_split_structure
    priors = build_sut_split_priors(instance, structure, base_scenario=base_scenario, residue=residue)
    flows = assemble_sut_split_flows(
        structure,
        priors.original,
        priors,
        U=priors.U0,
        M=priors.M0,
        Y=priors.Y0,
        V=priors.V0,
        Xa=priors.Xa,
        Xc=priors.Xc,
    )
    split_scenario = f"split_{scenario_label}"
    instance.matrices[split_scenario] = flows
    instance.sut_split_priors = priors
    return split_scenario, priors


MODE_LABELS = {MODE_ACTIVITIES: "activity-only", MODE_COMMODITIES: "commodity-only", MODE_BOTH: "combined"}


def log_sut_split_scenario(logger, split_scenario: str, structure: SutSplitStructure) -> None:
    log_time(
        logger,
        f"Split scenario '{split_scenario}' generated for activities {structure.new_activities} "
        f"and commodities {structure.new_commodities} ({MODE_LABELS[structure.mode]} split).",
    )


# ---------------------------------------------------------------------------
# Residuals of the solved split
# ---------------------------------------------------------------------------
_RESIDUAL_REFERENCE_MIN = 1e-9


def _aggregate(frame: pd.DataFrame, *, row_fn=None, col_fn=None) -> pd.DataFrame:
    """Sum the cells of ``frame`` that map to the same original (parent) item."""

    def mapped(axis_index, fn):
        return pd.MultiIndex.from_tuples([(region, fn(item)) for region, item in axis_index], names=[REGION, ITEM])

    out = frame
    if row_fn is not None:
        out = out.set_axis(mapped(out.index, row_fn), axis=0).groupby(level=[0, 1], sort=False).sum()
    if col_fn is not None:
        out = out.T.set_axis(mapped(out.columns, col_fn), axis=0).groupby(level=[0, 1], sort=False).sum().T
    return out


def _max_relative_gap(value, reference) -> float:
    """Largest ``|value - reference| / |reference|`` over the cells with a non-zero reference."""

    value, reference = value.align(reference, join="right", fill_value=0.0)
    reference = reference.astype(float)
    keep = reference.abs() > _RESIDUAL_REFERENCE_MIN
    gap = ((value - reference).abs() / reference.abs()).where(keep)
    values = np.asarray(gap, dtype=float)
    return float(np.nanmax(values)) if np.isfinite(values).any() else 0.0


def compute_sut_split_residuals(priors: SutSplitPriors, blocks: Mapping[str, pd.DataFrame]) -> dict[str, tuple[str, float]]:
    """Largest relative residual of each constraint family of the solved split.

    Returns ``{label: (tolerance name, residual)}`` for the constraints that the model of the
    split variant has: the balances (``delta``) and the consistency with the original table and
    the known totals of the new items (``eps``).
    """

    structure, original, mode = priors.structure, priors.original, priors.mode
    U, M, Y, V = blocks["U"], blocks["M"], blocks["Y"], blocks["V"]
    residuals: dict[str, tuple[str, float]] = {}

    def involved(items, category):
        return [item for item in items if category(item) != "stable"]

    parent_new_commodities = involved(structure.all_commodities, structure.commodity_category)
    parent_new_activities = involved(structure.all_activities, structure.activity_category)

    if mode in {MODE_COMMODITIES, MODE_BOTH}:
        rows = pd.MultiIndex.from_product([structure.regions, parent_new_commodities], names=[REGION, ITEM])
        use = U.reindex(rows).sum(axis=1) + Y.reindex(rows).sum(axis=1)
        residuals["commodity balance"] = ("delta", _max_relative_gap(use, M[rows].sum(axis=0)))
    if mode in {MODE_ACTIVITIES, MODE_BOTH}:
        cols = pd.MultiIndex.from_product([structure.regions, parent_new_activities], names=[REGION, ITEM])
        cost = U[cols].sum(axis=0) + V[cols].sum(axis=0)
        residuals["activity balance"] = ("delta", _max_relative_gap(cost, M.reindex(cols).sum(axis=1)))

    aggregate_c, aggregate_a = structure.aggregate_commodity, structure.aggregate_activity
    residuals["Use vs original"] = (
        "eps", _max_relative_gap(_aggregate(U, row_fn=aggregate_c, col_fn=aggregate_a), original.U)
    )
    residuals["Make vs original"] = (
        "eps", _max_relative_gap(_aggregate(M, row_fn=aggregate_a, col_fn=aggregate_c), original.M)
    )
    if mode in {MODE_COMMODITIES, MODE_BOTH}:
        residuals["Final demand vs original"] = ("eps", _max_relative_gap(_aggregate(Y, row_fn=aggregate_c), original.Y))
    if mode in {MODE_ACTIVITIES, MODE_BOTH}:
        residuals["Value added vs original"] = ("eps", _max_relative_gap(_aggregate(V, col_fn=aggregate_a), original.V))

    known = priors.Xnew[priors.Xnew > _RESIDUAL_REFERENCE_MIN]
    if not known.empty:
        if mode == MODE_COMMODITIES:
            total = U.reindex(known.index).sum(axis=1) + Y.reindex(known.index).sum(axis=1)
        else:
            total = U[known.index].sum(axis=0) + V[known.index].sum(axis=0)
        residuals["known total of the new items"] = ("eps", _max_relative_gap(total, known))
    return residuals


def log_sut_split_residuals(logger, priors: SutSplitPriors, blocks: Mapping[str, pd.DataFrame], tolerances: pd.DataFrame) -> None:
    """Log the largest relative residuals and warn about those above their tolerance."""

    name_col, value_col = ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS["name"], ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS["value"]
    limits = dict(zip(tolerances[name_col].astype(str), tolerances[value_col].astype(float)))
    residuals = compute_sut_split_residuals(priors, blocks)
    summary = "; ".join(f"{label} {value:.2e} ({tol})" for label, (tol, value) in residuals.items())
    log_time(logger, f"Largest relative residuals of the {MODE_LABELS[priors.mode]} split: {summary}.")
    for label, (tol, value) in residuals.items():
        limit = limits.get(tol)
        if limit is not None and value > limit * 1.01 + 1e-9:
            log_time(
                logger,
                f"The {label} of the split deviates by {value:.2e} (relative), above the tolerance "
                f"{tol} = {limit:.2e}.",
                "warning",
            )


# ---------------------------------------------------------------------------
# Parent renames
# ---------------------------------------------------------------------------
def normalize_sut_split_parent_renames(
    structure: SutSplitStructure,
    *,
    parent_name=None,
    parent_names=None,
) -> dict[str, dict[str, str]]:
    """Normalize the optional rename of the parents left after a SUT split.

    Returns ``{"Activity": {old: new}, "Commodity": {old: new}}`` (empty when no
    rename is requested). Accepted payloads:

    - ``parent_name="Other"`` when exactly one parent (activity or commodity) is split;
    - a mapping ``{name: new}`` whose keys are split children or parents; a name that
      is a parent both as an activity and as a commodity renames both;
    - a nested mapping ``{"Activity": {...}, "Commodity": {...}}`` to be explicit.
    """

    renames: dict[str, dict[str, str]] = {MI["a"]: {}, MI["c"]: {}}
    if parent_name is not None and parent_names is not None:
        raise WrongInput("Use either parent_name or parent_names, not both.")
    payload = parent_names if parent_names is not None else parent_name
    if payload is None:
        return renames

    parents = {
        MI["a"]: set(structure.activity_parent.values()),
        MI["c"]: set(structure.commodity_parent.values()),
    }
    children = {MI["a"]: structure.activity_parent, MI["c"]: structure.commodity_parent}

    def parent_of(level: str, name: str) -> str | None:
        if name in children[level]:
            return children[level][name]
        return name if name in parents[level] else None

    def register(level: str, name: str, target: str) -> bool:
        parent = parent_of(level, name)
        if parent is None:
            return False
        previous = renames[level].get(parent)
        if previous is not None and previous != target:
            raise WrongInput(f"Conflicting parent rename instructions for {parent!r}: {previous!r} and {target!r}.")
        renames[level][parent] = target
        return True

    if isinstance(payload, str):
        total = len(parents[MI["a"]]) + len(parents[MI["c"]])
        if total != 1:
            raise WrongInput(
                "parent_name as a string is supported only when exactly one parent is split; "
                "use parent_names with a mapping instead."
            )
        level = MI["a"] if parents[MI["a"]] else MI["c"]
        renames[level][next(iter(parents[level]))] = payload.strip()
    elif isinstance(payload, Mapping):
        for key, value in payload.items():
            if isinstance(value, Mapping):
                if key not in (MI["a"], MI["c"]):
                    raise WrongInput(
                        f"Nested parent_names keys should be '{MI['a']}' or '{MI['c']}', found {key!r}."
                    )
                for name, target in value.items():
                    if not register(key, str(name).strip(), str(target).strip()):
                        raise WrongInput(f"{name!r} is not a split {key.lower()} or parent {key.lower()}.")
                continue
            target = str(value).strip()
            matched = [register(level, str(key).strip(), target) for level in (MI["a"], MI["c"])]
            if not any(matched):
                raise WrongInput(
                    f"{key!r} is not a valid split child or parent activity/commodity for this split workflow."
                )
    else:
        raise WrongInput(
            "parent_name should be a string, and parent_names should be a mapping of split item "
            "or parent label -> new parent label."
        )

    existing = {MI["a"]: set(structure.all_activities), MI["c"]: set(structure.all_commodities)}
    for level, mapping in renames.items():
        for source, target in mapping.items():
            if not target:
                raise WrongInput("Parent rename targets cannot be empty.")
            if target != source and target in existing[level].difference({source}):
                raise WrongInput(f"Cannot rename parent {source!r} to {target!r} because that label already exists.")
        if len(set(mapping.values())) != len(mapping):
            raise WrongInput("Parent rename targets should be unique.")
    return renames


def _rename_item_axis(axis, level: str, rename_map: Mapping[str, str]):
    if not isinstance(axis, pd.MultiIndex) or axis.nlevels < 3:
        return axis
    changed = False
    tuples = []
    for entry in axis.tolist():
        values = list(entry)
        if values[1] == level and values[-1] in rename_map:
            values[-1] = rename_map[values[-1]]
            changed = True
        tuples.append(tuple(values))
    return pd.MultiIndex.from_tuples(tuples, names=axis.names) if changed else axis


def apply_sut_split_parent_renames(
    instance,
    renames: Mapping[str, Mapping[str, str]],
    *,
    scenarios: list[str],
) -> None:
    """Rename the split parents in matrices, units, indexes and master sheet."""

    if not any(renames.values()):
        return

    for scenario in scenarios:
        if scenario not in instance.matrices:
            continue
        for matrix_name, matrix in list(instance.matrices[scenario].items()):
            if not isinstance(matrix, pd.DataFrame):
                continue
            renamed = matrix.copy()
            for level, mapping in renames.items():
                renamed.index = _rename_item_axis(renamed.index, level, mapping)
                renamed.columns = _rename_item_axis(renamed.columns, level, mapping)
            instance.matrices[scenario][matrix_name] = renamed

    codes = TABLE_LEVELS[instance.table_type]
    for level, mapping in renames.items():
        if not mapping:
            continue
        units = instance.units[level].copy()
        units.index = pd.Index([mapping.get(str(label), str(label)) for label in units.index], name=units.index.name)
        instance.units[level] = units[~units.index.duplicated(keep="first")]

        code = codes[level]
        if code in instance._indeces and "main" in instance._indeces[code]:
            instance._indeces[code]["main"] = list(
                dict.fromkeys(mapping.get(str(label), str(label)) for label in instance._indeces[code]["main"])
            )

    # the productive index ("s") lists activities then commodities
    if "s" in instance._indeces:
        instance._indeces["s"]["main"] = list(instance._indeces["a"]["main"]) + list(instance._indeces["c"]["main"])

    for level, column in ((MI["a"], MSC["parent_activity"]), (MI["c"], MSC["parent_commodity"])):
        if renames.get(level):
            instance.add_sectors_master[column] = instance.add_sectors_master[column].replace(dict(renames[level]))


def register_sut_split_items(instance, structure: SutSplitStructure) -> None:
    """Add the new activities/commodities to the units and index dictionaries.

    New items take the unit of their parent in the database.
    """

    for level, children, code in (
        (MI["a"], structure.activity_parent, "a"),
        (MI["c"], structure.commodity_parent, "c"),
    ):
        units = instance.units[level]
        additions = pd.DataFrame(
            {"unit": [units.loc[parent, "unit"] for parent in children.values()]},
            index=pd.Index(list(children), name=units.index.name),
        )
        instance.units[level] = pd.concat([units, additions.loc[~additions.index.isin(units.index)]])
        existing = structure.activities if code == "a" else structure.commodities
        instance._indeces[code]["main"] = list(existing) + list(children)
    if "s" in instance._indeces:
        instance._indeces["s"]["main"] = structure.all_activities + structure.all_commodities
