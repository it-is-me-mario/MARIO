"""Parsing and import specifications."""

from __future__ import annotations

from mario.model.conventions import (
    COEFFICIENTS,
    FLOWS,
    HYBRID,
    IOT,
    MONETARY,
    SUT,
    _MASTER_INDEX,
)


INPUT_OPTIONS = {
    "table": [SUT, IOT],
    "mode": [FLOWS, COEFFICIENTS],
    "unit": [MONETARY, HYBRID],
}


EXIO_FACTOR_ROWS = [
    "Taxes less subsidies on products purchased: Total",
    "Other net taxes on production",
    "Compensation of employees; wages, salaries, & employers' social contributions: Low-skilled",
    "Compensation of employees; wages, salaries, & employers' social contributions: Medium-skilled",
    "Compensation of employees; wages, salaries, & employers' social contributions: High-skilled",
    "Operating surplus: Consumption of fixed capital",
    "Operating surplus: Rents on land",
    "Operating surplus: Royalties on resources",
    "Operating surplus: Remaining net operating surplus",
]


EXIO_INDEX_LAYOUT = {
    _MASTER_INDEX["s"]: {
        "matrix": "Z",
        "item": "columns",
        "multi_index": True,
        "del_duplicate": True,
        "level": 1,
    },
    _MASTER_INDEX["r"]: {
        "matrix": "Z",
        "item": "index",
        "multi_index": True,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["k"]: {
        "matrix": "E",
        "item": "index",
        "multi_index": False,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["f"]: {
        "matrix": "V",
        "item": "index",
        "multi_index": False,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["n"]: {
        "matrix": "Y",
        "item": "columns",
        "multi_index": True,
        "del_duplicate": True,
        "level": 1,
    },
}


MRSUT_EXIO_INDEX_LAYOUT = {
    _MASTER_INDEX["s"]: {
        "matrix": "Y",
        "item": "index",
        "multi_index": True,
        "del_duplicate": True,
        "level": 1,
    },
    _MASTER_INDEX["r"]: {
        "matrix": "Z",
        "item": "index",
        "multi_index": True,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["k"]: {
        "matrix": "E",
        "item": "index",
        "multi_index": False,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["f"]: {
        "matrix": "V",
        "item": "index",
        "multi_index": False,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["n"]: {
        "matrix": "Y",
        "item": "columns",
        "multi_index": True,
        "del_duplicate": True,
        "level": 1,
    },
}


HMRSUT_EXTENSIONS = [
    "resource",
    "Land",
    "Emiss",
    "Emis_unreg_w",
    "Unreg_w",
    "waste_sup",
    "waste_use",
    "pack_sup_waste",
    "pack_use_waste",
    "mach_sup_waste",
    "mach_use_waste",
    "stock_addition",
    "crop_res",
]


PYMRIO_IMPORT_LAYOUTS = {
    "v": {"index": 1, "columns": 3, "add_c": [_MASTER_INDEX["s"]]},
    "e": {"index": 1, "columns": 3, "add_c": [_MASTER_INDEX["s"]]},
    "EY": {"index": 1, "columns": 3, "add_c": [_MASTER_INDEX["n"]]},
    "Y": {
        "index": 3,
        "columns": 3,
        "add_c": ["Consumption category"],
        "add_i": [_MASTER_INDEX["s"]],
    },
    "z": {
        "index": 3,
        "columns": 3,
        "add_c": [_MASTER_INDEX["s"]],
        "add_i": [_MASTER_INDEX["s"]],
    },
}
