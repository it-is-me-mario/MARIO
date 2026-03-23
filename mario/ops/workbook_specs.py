"""Workbook layouts used by Excel-facing utilities."""

from __future__ import annotations

from mario.model.conventions import IOT, SUT


SHOCK_LEVEL_NAMES = {SUT: ["Activity", "Commodity"], IOT: ["Sector"]}


HEADER_CELL_FORMAT = {
    "border": 1,
    "bg_color": "#C6EFCE",
    "bold": True,
    "text_wrap": False,
    "valign": "vcenter",
    "indent": 1,
}


ADD_SECTOR_SHEETS = {
    "if": {"sheet": "input_from", "rows": 3, "cols": 3},
    "it": {"sheet": "input_to", "rows": 3, "cols": 3},
    "sf": {"sheet": "self consumption", "rows": 3, "cols": 3},
    "fp": {"sheet": "Factor of production", "rows": 1, "cols": 3},
    "sa": {"sheet": "Satellite account", "rows": 1, "cols": 3},
    "fd": {"sheet": "Final consumption", "rows": 3, "cols": 3},
    "un": {"sheet": "units", "rows": 1, "cols": 1},
    "of": {"sheet": "output_from", "rows": 3, "cols": 3},
}


SHOCK_COLUMNS = {
    "r_reg": "row region",
    "r_lev": "row level",
    "r_sec": "row sector",
    "c_reg": "column region",
    "c_lev": "column level",
    "c_sec": "column sector",
    "d_cat": "demand category",
    "type": "type",
    "value": "value",
    "s_sec": "sector",
}
