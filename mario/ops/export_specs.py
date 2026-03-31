"""Export-specific layout specifications."""

from __future__ import annotations

FLAT_AXIS_SETS = (
    "Region",
    "Sector",
    "Activity",
    "Commodity",
    "Factor of production",
    "Satellite account",
    "Consumption category",
)


FLAT_DATA_COLUMNS = (
    "Scenario",
    "Matrix",
    *(f"{item}_from" for item in FLAT_AXIS_SETS),
    *(f"{item}_to" for item in FLAT_AXIS_SETS),
    "Value",
)


def flat_data_columns_for_sets(*, from_sets=(), to_sets=()):
    """Return the flat export column order for one concrete set subset."""
    return (
        "Scenario",
        "Matrix",
        *(f"{item}_from" for item in from_sets),
        *(f"{item}_to" for item in to_sets),
        "Value",
    )

LEGACY_FLAT_DATA_COLUMNS = (
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
