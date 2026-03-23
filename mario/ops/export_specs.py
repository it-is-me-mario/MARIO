"""Export-specific layout specifications."""

from __future__ import annotations

FLAT_DATA_COLUMNS = (
    "Scenario",
    "Matrix",
    "Region_from",
    "Level_from",
    "Item_from",
    "Region_to",
    "Level_to",
    "Item_to",
    "Value",
)

FLAT_UNIT_COLUMNS = ("Level", "Item", "Unit")


PYMRIO_EXPORT_LAYOUTS = {
    "E": dict(
        keep_index=[0],
        keep_columns=[0, -1],
        index_name="stressor",
        columns_name=["region", "sector"],
    ),
    "EY": dict(
        keep_index=[0],
        keep_columns=[0, -1],
        index_name="stressor",
        columns_name=["region", "sector"],
    ),
    "V": dict(
        keep_index=[0],
        keep_columns=[0, -1],
        index_name="stressor",
        columns_name=["region", "sector"],
    ),
    "Z": dict(
        keep_index=[0, -1],
        keep_columns=[0, -1],
        index_name=["region", "sector"],
        columns_name=["region", "sector"],
    ),
    "Y": dict(
        keep_index=[0, -1],
        keep_columns=[0, -1],
        index_name=["region", "sector"],
        columns_name=["region", "category"],
    ),
}
