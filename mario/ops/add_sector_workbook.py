"""Reader and writer helpers for the add-sectors workbook workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from mario.log_exc.exceptions import WrongExcelFormat, WrongInput
from mario.model.conventions import IOT, SUT, _MASTER_INDEX
from mario.ops.add_sector_specs import (
    ADVANCED_ADD_SECTOR_DB_UNITS_SHEET,
    ADVANCED_ADD_SECTOR_INVENTORY_SHEET_COLUMNS,
    ADVANCED_ADD_SECTOR_ITEMS_CLUSTERS_COLUMNS,
    ADVANCED_ADD_SECTOR_ITEMS_CLUSTERS_SHEET,
    ADVANCED_ADD_SECTOR_MASTER_SHEET,
    ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS,
    ADVANCED_ADD_SECTOR_REGIONS_CLUSTERS_COLUMNS,
    ADVANCED_ADD_SECTOR_REGIONS_CLUSTERS_SHEET,
    ADVANCED_ADD_SECTOR_UNCERTAINTIES_SHEET,
    ADVANCED_ADD_SECTOR_UNCERTAINTY_COLUMNS,
    ADVANCED_ADD_SECTOR_UNCERTAINTY_PARAMETERS,
)


@dataclass(frozen=True)
class AddSectorWorkbook:
    """Normalized view of one add-sectors workbook.

    The workbook stores:
    - one master sheet describing the items to add and their workbook-level options;
    - one regions-cluster sheet;
    - one item-cluster sheet;
    - an optional uncertainty-value sheet;
    - one or more inventory sheets referenced by the master sheet.

    This dataclass keeps those pieces together after parsing so ``Database`` can
    attach them to the live object and the engine can consume them without
    repeatedly reopening the Excel file.
    """

    table: str
    master_sheet: pd.DataFrame
    regions_clusters: dict[str, list[str]]
    item_clusters: dict[str, list[str]]
    uncertainty_values: dict[str, float]
    inventories_by_sheet: dict[str, pd.DataFrame]


def build_add_sector_master_sheet(
    table: str,
    new_items: list[str],
    regions: list[str],
    *,
    item: str | None = None,
) -> pd.DataFrame:
    """Build a prefilled master sheet for a new add-sectors workbook.

    Parameters
    ----------
    table:
        ``"IOT"`` or ``"SUT"``.
    new_items:
        Item names to pre-populate in the master sheet. An empty list is valid
        and produces an empty master sheet with only the expected columns.
    regions:
        Regions to pre-populate alongside ``new_items``.
    item:
        For SUT workbooks, controls whether the same ``new_items`` should be
        written as activities, commodities, or both.
    """

    columns = list(ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS[table].values())
    rows: list[dict[str, Any]] = []

    counter = 1
    if table == IOT:
        for region in regions:
            for sector in new_items:
                row = {column: "" for column in columns}
                row[_MASTER_INDEX["r"]] = region
                row[_MASTER_INDEX["s"]] = sector
                row["Inventory sheet"] = f"INV_{counter:03d}"
                row["Add or Split"] = "Add"
                rows.append(row)
                counter += 1
    else:
        for region in regions:
            for value in new_items:
                row = {column: "" for column in columns}
                row[_MASTER_INDEX["r"]] = region
                if item is None:
                    row[_MASTER_INDEX["a"]] = value
                    row[_MASTER_INDEX["c"]] = value
                elif item == _MASTER_INDEX["a"]:
                    row[_MASTER_INDEX["a"]] = value
                    row[_MASTER_INDEX["c"]] = ""
                elif item == _MASTER_INDEX["c"]:
                    row[_MASTER_INDEX["a"]] = ""
                    row[_MASTER_INDEX["c"]] = value
                else:
                    raise WrongInput(
                        f"For SUT add-sectors workbooks, item should be "
                        f"{_MASTER_INDEX['a']}, {_MASTER_INDEX['c']} or None."
                    )
                row["Inventory sheet"] = f"INV_{counter:03d}"
                rows.append(row)
                counter += 1

    return pd.DataFrame(rows, columns=columns)


def build_regions_clusters_sheet(instance) -> pd.DataFrame:
    """Build the default regions-cluster sheet."""

    return pd.DataFrame(
        instance.get_index(_MASTER_INDEX["r"]),
        columns=ADVANCED_ADD_SECTOR_REGIONS_CLUSTERS_COLUMNS,
    )


def build_items_clusters_sheet() -> pd.DataFrame:
    """Build the default item-cluster sheet."""

    return pd.DataFrame(columns=ADVANCED_ADD_SECTOR_ITEMS_CLUSTERS_COLUMNS)


def build_uncertainties_sheet() -> pd.DataFrame:
    """Build the default uncertainty-values sheet."""

    return pd.DataFrame(
        {
            ADVANCED_ADD_SECTOR_UNCERTAINTY_COLUMNS[0]: list(
                ADVANCED_ADD_SECTOR_UNCERTAINTY_PARAMETERS.keys()
            ),
            ADVANCED_ADD_SECTOR_UNCERTAINTY_COLUMNS[1]: list(
                ADVANCED_ADD_SECTOR_UNCERTAINTY_PARAMETERS.values()
            ),
        }
    )


def build_inventory_template() -> pd.DataFrame:
    """Build one empty inventory sheet."""

    return pd.DataFrame(
        columns=list(ADVANCED_ADD_SECTOR_INVENTORY_SHEET_COLUMNS.values())
    )


def build_db_units_sheet(instance) -> pd.DataFrame:
    """Build a flat view of database units for workbook reference."""

    rows = []
    if instance.table_type == SUT:
        keys = [
            _MASTER_INDEX["a"],
            _MASTER_INDEX["c"],
            _MASTER_INDEX["f"],
            _MASTER_INDEX["k"],
        ]
    else:
        keys = [_MASTER_INDEX["s"], _MASTER_INDEX["f"], _MASTER_INDEX["k"]]

    for key in keys:
        units = instance.units[key]
        for item_name, row in units.iterrows():
            rows.append(
                {
                    "Item type": key,
                    "DB Item": item_name,
                    "Unit": row["unit"],
                }
            )

    return pd.DataFrame(rows, columns=["Item type", "DB Item", "Unit"])


def write_add_sector_workbook(
    instance,
    path: str | Path,
    *,
    new_items: list[str],
    regions: list[str],
    item: str | None = None,
    redefine_uncertainties: bool = False,
) -> None:
    """Write an add-sectors workbook to disk.

    The workbook always includes the structural sheets needed by the current
    ``add_sectors`` workflow. When ``new_items`` and ``regions`` are provided,
    the master sheet and the inventory sheets are pre-populated accordingly.
    When they are empty, the file acts as a blank template that users can fill
    manually.
    """

    table = instance.table_type
    master = build_add_sector_master_sheet(table, new_items, regions, item=item)
    regions_clusters = build_regions_clusters_sheet(instance)
    items_clusters = build_items_clusters_sheet()
    db_units = build_db_units_sheet(instance)
    inventory = build_inventory_template()

    item_clusters_sheet = ADVANCED_ADD_SECTOR_ITEMS_CLUSTERS_SHEET[table]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        master.to_excel(
            writer, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET, index=False
        )
        regions_clusters.to_excel(
            writer,
            sheet_name=ADVANCED_ADD_SECTOR_REGIONS_CLUSTERS_SHEET,
            index=False,
        )
        items_clusters.to_excel(writer, sheet_name=item_clusters_sheet, index=False)
        db_units.to_excel(writer, sheet_name=ADVANCED_ADD_SECTOR_DB_UNITS_SHEET, index=False)
        if redefine_uncertainties:
            build_uncertainties_sheet().to_excel(
                writer, sheet_name=ADVANCED_ADD_SECTOR_UNCERTAINTIES_SHEET, index=False
            )
        for sheet_name in master["Inventory sheet"].tolist():
            inventory.to_excel(writer, sheet_name=sheet_name, index=False)


def read_add_sector_workbook(
    path: str | Path,
    *,
    table: str,
) -> AddSectorWorkbook:
    """Read and validate one add-sectors workbook.

    This function does not derive database-specific sets such as
    ``new_sectors`` or ``parented_activities``. It only parses the workbook
    structure into a normalized object. The database layer derives those sets
    later because they depend on the current database contents.
    """

    sheets = pd.read_excel(path, sheet_name=None, header=0)
    item_clusters_sheet = ADVANCED_ADD_SECTOR_ITEMS_CLUSTERS_SHEET[table]

    required = {
        ADVANCED_ADD_SECTOR_MASTER_SHEET,
        ADVANCED_ADD_SECTOR_REGIONS_CLUSTERS_SHEET,
        item_clusters_sheet,
    }
    missing = sorted(required.difference(sheets))
    if missing:
        raise WrongExcelFormat(
            f"Missing required sheets for add-sectors workbook: {missing}"
        )

    master_sheet = sheets[ADVANCED_ADD_SECTOR_MASTER_SHEET]
    expected_columns = list(ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS[table].values())
    missing_columns = [column for column in expected_columns if column not in master_sheet.columns]
    if missing_columns:
        raise WrongExcelFormat(
            f"Add-sectors master sheet is missing columns: {missing_columns}"
        )
    master_sheet = master_sheet.loc[:, expected_columns]

    regions_clusters = _parse_cluster_sheet(
        sheets[ADVANCED_ADD_SECTOR_REGIONS_CLUSTERS_SHEET]
    )
    item_clusters = _parse_cluster_sheet(sheets[item_clusters_sheet])
    uncertainty_values = _parse_uncertainties_sheet(
        sheets.get(ADVANCED_ADD_SECTOR_UNCERTAINTIES_SHEET)
    )

    inventory_names = [
        sheet
        for sheet in master_sheet["Inventory sheet"].dropna().astype(str).tolist()
        if sheet
    ]
    missing_inventories = [sheet for sheet in inventory_names if sheet not in sheets]
    if missing_inventories:
        raise WrongExcelFormat(
            f"Add-sectors workbook is missing inventory sheets: {missing_inventories}"
        )

    inventories_by_sheet = {
        sheet_name: sheets[sheet_name] for sheet_name in inventory_names
    }

    return AddSectorWorkbook(
        table=table,
        master_sheet=master_sheet,
        regions_clusters=regions_clusters,
        item_clusters=item_clusters,
        uncertainty_values=uncertainty_values,
        inventories_by_sheet=inventories_by_sheet,
    )


def derive_add_sector_sets(
    workbook: AddSectorWorkbook,
    *,
    existing_sectors: list[str] | None = None,
    existing_activities: list[str] | None = None,
    existing_commodities: list[str] | None = None,
) -> dict[str, list[str]]:
    """Derive the item sets consumed by the add-sectors engine.

    The workbook stores rows, not semantic groups. This helper turns the raw
    master sheet into the derived sets used by ``Database.add_sectors(...)``,
    such as ``new_sectors``, ``new_activities``, ``parented_*`` and
    ``to_split_sectors``.
    """

    master = workbook.master_sheet
    if workbook.table == IOT:
        if existing_sectors is None:
            raise WrongInput("existing_sectors is required to derive IOT add-sector sets.")
        sectors = [
            sector
            for sector in master[_MASTER_INDEX["s"]].dropna().astype(str).unique().tolist()
            if sector not in existing_sectors
        ]
        parented = []
        parent_column = ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS[IOT]["parent_sector"]
        for sector in sectors:
            parent = master.loc[master[_MASTER_INDEX["s"]] == sector, parent_column].iloc[0]
            if isinstance(parent, str) and parent.strip():
                parented.append(sector)
        split_column = ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS[IOT]["add_mode"]
        to_split = [
            sector
            for sector in master.loc[
                master[split_column].fillna("").astype(str).str.lower() == "split",
                _MASTER_INDEX["s"],
            ]
            .astype(str)
            .unique()
            .tolist()
            if sector in sectors
        ]
        non_parented = [sector for sector in sectors if sector not in parented]
        return {
            "new_sectors": sectors,
            "parented_sectors": parented,
            "non_parented_sectors": non_parented,
            "to_split_sectors": to_split,
        }

    if existing_activities is None or existing_commodities is None:
        raise WrongInput(
            "existing_activities and existing_commodities are required to derive SUT add-sector sets."
        )

    activities = [
        value
        for value in master[_MASTER_INDEX["a"]].dropna().astype(str).unique().tolist()
        if value and value not in existing_activities
    ]
    commodities = [
        value
        for value in master[_MASTER_INDEX["c"]].dropna().astype(str).unique().tolist()
        if value and value not in existing_commodities
    ]
    parented = []
    parent_column = ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS[SUT]["parent_activity"]
    for activity in activities:
        parent = master.loc[master[_MASTER_INDEX["a"]] == activity, parent_column].iloc[0]
        if isinstance(parent, str) and parent.strip():
            parented.append(activity)
    non_parented = [activity for activity in activities if activity not in parented]
    return {
        "new_activities": activities,
        "new_commodities": commodities,
        "parented_activities": parented,
        "non_parented_activities": non_parented,
    }


def _parse_cluster_sheet(sheet: pd.DataFrame) -> dict[str, list[str]]:
    clusters: dict[str, list[str]] = {}
    for column in sheet.columns:
        values = [str(value) for value in sheet[column].dropna().tolist() if str(value).strip()]
        if values:
            clusters[str(column)] = values
    return clusters


def _parse_uncertainties_sheet(sheet: pd.DataFrame | None) -> dict[str, float]:
    if sheet is None:
        return dict(ADVANCED_ADD_SECTOR_UNCERTAINTY_PARAMETERS)
    if list(sheet.columns[:2]) != ADVANCED_ADD_SECTOR_UNCERTAINTY_COLUMNS:
        raise WrongExcelFormat(
            "Add-sectors uncertainties sheet should expose the expected two columns."
        )
    return dict(zip(sheet.iloc[:, 0], sheet.iloc[:, 1]))


def group_inventories_by_target(
    workbook: AddSectorWorkbook,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Group inventory sheets by target item name.

    The engine consumes inventories one target item at a time. This helper maps
    each target item name to the inventory sheets referenced by that item in the
    master sheet.
    """

    master = workbook.master_sheet
    table = workbook.table
    inventory_column = ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS[table]["inventory_sheet"]
    target_column = _MASTER_INDEX["a"] if table == SUT else _MASTER_INDEX["s"]

    grouped: dict[str, dict[str, pd.DataFrame]] = {}
    for _, row in master.iterrows():
        sheet_name = row[inventory_column]
        target = row[target_column]
        if pd.isna(sheet_name) or pd.isna(target):
            continue
        sheet_name = str(sheet_name)
        target = str(target)
        inventory = workbook.inventories_by_sheet.get(sheet_name)
        if inventory is None:
            continue
        grouped.setdefault(target, {})[sheet_name] = inventory

    return grouped


# Backward-compatible aliases for the first port of the workflow.
AdvancedAddSectorWorkbook = AddSectorWorkbook
build_advanced_master_sheet = build_add_sector_master_sheet
write_advanced_add_sector_workbook = write_add_sector_workbook
read_advanced_add_sector_workbook = read_add_sector_workbook
derive_advanced_add_sector_sets = derive_add_sector_sets
group_advanced_inventories_by_target = group_inventories_by_target
