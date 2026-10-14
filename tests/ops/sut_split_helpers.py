"""Shared helpers for the SUT split tests.

The fixtures live in ``tests/mocks/sut_split`` and are all in MARIO Excel format:

- ``sut_test_original.xlsx``: the aggregated SUT that is split.
- ``sut_test_disaggregated.xlsx``: the reference (ground truth) disaggregated SUT. Its parents are
  called ``a2a`` and ``c2a``.
- ``add_sector_sut_split_example.xlsx``: the add-sectors workbook of the split.

The one-sided variants have their own fixtures (the parents keep their original names):

- ``sut_test_disaggregated_act.xlsx`` / ``add_sector_sut_split_act_example.xlsx``: only ``a2`` is split
  into ``a2`` and ``a2b``;
- ``sut_test_disaggregated_com.xlsx`` / ``add_sector_sut_split_com_example.xlsx``: only ``c2`` is split
  into ``c2`` and ``c2b``.
"""

from __future__ import annotations

import pandas as pd

import mario

from .._paths import MOCKS_ROOT

SPLIT_DIR = MOCKS_ROOT / "sut_split"
ADD_SECTOR_PATH = SPLIT_DIR / "add_sector_sut_split_example.xlsx"
ORIGINAL_PATH = SPLIT_DIR / "sut_test_original.xlsx"
DISAGGREGATED_PATH = SPLIT_DIR / "sut_test_disaggregated.xlsx"

VARIANT_ACTIVITIES, VARIANT_COMMODITIES = "act", "com"
VARIANT_ADD_SECTOR_PATHS = {
    variant: SPLIT_DIR / f"add_sector_sut_split_{variant}_example.xlsx"
    for variant in (VARIANT_ACTIVITIES, VARIANT_COMMODITIES)
}
VARIANT_DISAGGREGATED_PATHS = {
    variant: SPLIT_DIR / f"sut_test_disaggregated_{variant}.xlsx"
    for variant in (VARIANT_ACTIVITIES, VARIANT_COMMODITIES)
}

VALUE_ADDED = "Value added"
# parent names in the reference table -> parent names in the original table
REFERENCE_PARENTS = {"a2a": "a2", "c2a": "c2"}


def _parse(path):
    return mario.parse_from_excel(path, table="SUT", mode="flows", data_sheet="flows")


def build_example_database():
    """Parse the aggregated SUT (``sut_test_original.xlsx``) as a MARIO ``Database``."""

    return _parse(ORIGINAL_PATH)


def read_expected() -> dict[str, pd.DataFrame]:
    """Reference disaggregated matrices ``Z, Y, V, E``, with the parents named as in the original."""

    db = _parse(DISAGGREGATED_PATH)

    def rename(frame):
        frame = frame.rename(index=REFERENCE_PARENTS, columns=REFERENCE_PARENTS)
        return frame

    return {"Z": rename(db.Z), "Y": rename(db.Y), "V": rename(db.V), "E": rename(db.E)}


def read_variant_truth(variant: str):
    """Parse the ground-truth disaggregated table of a one-sided variant (``"act"`` or ``"com"``)."""

    return _parse(VARIANT_DISAGGREGATED_PATHS[variant])


def write_modified_workbook(path, tmp_path, modify):
    """Copy an add-sectors workbook after ``modify(sheets)`` changed its dict of sheets."""

    sheets = pd.read_excel(path, sheet_name=None)
    modify(sheets)
    target = tmp_path / "modified.xlsx"
    with pd.ExcelWriter(target) as writer:
        for name, sheet in sheets.items():
            sheet.to_excel(writer, sheet_name=name, index=False)
    return target
