"""Schemas and defaults for the workbook-driven add-sector workflow."""

from __future__ import annotations

from mario.model.conventions import IOT, SUT, _MASTER_INDEX


ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS = {
    SUT: {
        "region": _MASTER_INDEX["r"],
        "activity": _MASTER_INDEX["a"],
        "commodity": _MASTER_INDEX["c"],
        "inventory_sheet": "Inventory sheet",
        "quantity": "Quantity",
        "unit": "Unit",
        "market_share": "Market share",
        "final_consumption": "Final consumption",
        "consumption_category": _MASTER_INDEX["n"],
        "parent_activity": f"Parent {_MASTER_INDEX['a']}",
        "leave_empty": "Leave empty",
        "source": "Source",
        "notes": "Notes",
    },
    IOT: {
        "region": _MASTER_INDEX["r"],
        "sector": _MASTER_INDEX["s"],
        "inventory_sheet": "Inventory sheet",
        "quantity": "Quantity",
        "unit": "Unit",
        "final_consumption": "Final consumption",
        "consumption_category": _MASTER_INDEX["n"],
        "parent_sector": f"Parent {_MASTER_INDEX['s']}",
        "leave_empty": "Leave empty",
        "source": "Source",
        "notes": "Notes",
        "add_mode": "Add or Split",
    },
}


ADVANCED_ADD_SECTOR_INVENTORY_SHEET_COLUMNS = {
    "quantity": "Quantity",
    "unit": "Unit",
    "input": "Input",
    "item_type": "Item type",
    "db_item": "DB Item",
    "db_region": f"DB {_MASTER_INDEX['r']}",
    "change_type": "Change type",
    "source": "Source",
    "notes": "Notes",
}


ADVANCED_ADD_SECTOR_REGIONS_CLUSTERS_SHEET = "Regions Clusters"
ADVANCED_ADD_SECTOR_FACTORS_CLUSTERS_SHEET = "Factors Clusters"
ADVANCED_ADD_SECTOR_ITEMS_CLUSTERS_SHEET = {
    SUT: "Commodities Clusters",
    IOT: "Sectors Clusters",
}
ADVANCED_ADD_SECTOR_MASTER_SHEET = "Master"
ADVANCED_ADD_SECTOR_DB_UNITS_SHEET = "DB units"
ADVANCED_ADD_SECTOR_UNCERTAINTIES_SHEET = "Uncertainties"


ADVANCED_ADD_SECTOR_REGIONS_CLUSTERS_COLUMNS = ["GLOBAL"]
ADVANCED_ADD_SECTOR_ITEMS_CLUSTERS_COLUMNS = ["Cluster1"]


ADVANCED_ADD_SECTOR_UNCERTAINTY_PARAMETERS = {
    "certain": 1.0,
    "original s specific, r cluster": 0.95,
    "original s specific_no parent, r cluster": 0.9,
    "original s cluster, r specific": 0.75,
    "original s cluster_no parent, r specific": 0.7,
    "original s cluster, r cluster": 0.65,
    "original s cluster_no parent, r cluster": 0.6,
    "disag s specific, r cluster": 0.55,
    "disag s cluster, r specific": 0.4,
    "disag s cluster_no parent, r specific": 0.35,
    "disag s cluster, r cluster": 0.3,
    "disag s specific_no parent, r cluster": 0.25,
    "disag s cluster_no parent, r cluster": 0.2,
    "no info": 0.1,
    "forced zero": 0.005,
}


ADVANCED_ADD_SECTOR_UNCERTAINTY_COLUMNS = [
    "Inventory data categories",
    "New uncertainty values",
]


ADD_SECTOR_SPLIT_OUTPUT_SHEET = "Total outputs"
ADD_SECTOR_SPLIT_OUTPUT_COLUMNS = {
    "sector": _MASTER_INDEX["s"],
    "region": _MASTER_INDEX["r"],
    "quantity": "Quantity",
    "unit": "Unit",
    "source": "Source",
    "notes": "Notes",
}


ADD_SECTOR_SPLIT_TRADE_SHEET = "Trades"
ADD_SECTOR_SPLIT_TRADE_COLUMNS = {
    "sector_from": f"{_MASTER_INDEX['s']}_from",
    "region_from": f"{_MASTER_INDEX['r']}_from",
    "region_to": f"{_MASTER_INDEX['r']}_to",
    "quantity": "Quantity",
    "unit": "Unit",
    "source": "Source",
    "notes": "Notes",
}


ADD_SECTOR_SPLIT_EXCLUSION_SHEET = "Exclusions"
ADD_SECTOR_SPLIT_EXCLUSION_COLUMNS = {
    "sector_from": f"{_MASTER_INDEX['s']}_from",
    "sector_to": f"{_MASTER_INDEX['s']}_to",
    "notes": "Notes",
}


ADD_SECTOR_SPLIT_TOLERANCE_SHEET = "Tolerances"
ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS = {
    "name": "tol_Name",
    "value": "values",
}
ADD_SECTOR_SPLIT_TOLERANCE_DEFAULTS = (
    ("delta", 1e-5),
    ("eps", 1e-5),
)
