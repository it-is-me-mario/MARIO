# -*- coding: utf-8 -*-
"""
This module contains all the constants of the code
"""
from mario.settings.settings import Index, Nomenclature


_MASTER_INDEX = Index()
_ENUM = Nomenclature()

SUT = "SUT"
IOT = "IOT"

FLOWS = "flows"
COEFFICIENTS = "coefficients"

MONETARY = "Monetary"
HYBRID = "Hybrid"

# represents different levels of aggregation
_LEVELS = {
    SUT: {_MASTER_INDEX[i]: i for i in ["a", "c", "f", "k", "n", "r"]},
    IOT: {_MASTER_INDEX[i]: i for i in ["f", "k", "n", "r", "s"]},
}


_INDEX_NAMES = {"3levels": (_MASTER_INDEX["r"], "Level", "Item"), "1level": ("Item")}


_ACCEPTABLES = {
    "table": [SUT, IOT],
    "mode": [FLOWS, COEFFICIENTS],
    'unit': [MONETARY, HYBRID],
}


_UNITS = {
    SUT: {_MASTER_INDEX[i]: i for i in ["a", "c", "f", "k"]},
    IOT: {_MASTER_INDEX[i]: i for i in ["s", "f", "k"]},
}


_EXIO_FACTORS = [
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


_SHOCK_LEVELS = {"SUT": ["Activity", "Commodity"], "IOT": ["Sector"]}


_FORMAT = {
    "border": 1,
    "bg_color": "#C6EFCE",
    "bold": True,
    "text_wrap": False,
    "valign": "vcenter",
    "indent": 1,
}


_ADD_SECTOR_SHEETS = {
    "if": {"sheet": "input_from", "rows": 3, "cols": 3},
    "it": {"sheet": "input_to", "rows": 3, "cols": 3},
    "sf": {"sheet": "self consumption", "rows": 3, "cols": 3},
    "fp": {"sheet": "Factor of production", "rows": 1, "cols": 3},
    "sa": {"sheet": "Satellite account", "rows": 1, "cols": 3},
    "fd": {"sheet": "Final consumption", "rows": 3, "cols": 3},
    "un": {"sheet": "units", "rows": 1, "cols": 1},
    "of": {"sheet": "output_from", "rows": 3, "cols": 3},
}


_CALC = {
    _ENUM.F: (
        "calc_F(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'].sum(1))",
        dict(enum0=_ENUM.f, enum1=_ENUM.Y),
    ),
    _ENUM.M: (
        "calc_F(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'].sum(1))",
        dict(enum0=_ENUM.m, enum1=_ENUM.Y),
    ),
    _ENUM.m: (
        "calc_f(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
        dict(enum0=_ENUM.v, enum1=_ENUM.w),
    ),
    _ENUM.V: (
        "calc_E(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
        dict(enum0=_ENUM.v, enum1=_ENUM.X),
    ),
    _ENUM.v: (
        "calc_e(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
        dict(enum0=_ENUM.V, enum1=_ENUM.X),
    ),
    _ENUM.f: (
        "calc_f(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
        dict(enum0=_ENUM.e, enum1=_ENUM.w),
    ),
    _ENUM.e: (
        "calc_e(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
        dict(enum0=_ENUM.E, enum1=_ENUM.X),
    ),
    _ENUM.E: (
        "calc_E(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
        dict(enum0=_ENUM.e, enum1=_ENUM.X),
    ),
    _ENUM.z: (
        "calc_z(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
        dict(enum0=_ENUM.Z, enum1=_ENUM.X),
    ),
    _ENUM.Z: (
        "calc_Z(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
        dict(enum0=_ENUM.z, enum1=_ENUM.X),
    ),
    _ENUM.b: (
        "calc_b(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
        dict(enum0=_ENUM.X, enum1=_ENUM.Z),
    ),
    _ENUM.w: ("calc_w(self.matrices['{scenario}']['{enum0}'])", dict(enum0=_ENUM.z)),
    _ENUM.g: ("calc_w(self.matrices['{scenario}']['{enum0}'])", dict(enum0=_ENUM.b)),
    _ENUM.y: ("calc_y(self.matrices['{scenario}']['{enum0}'])", dict(enum0=_ENUM.Y)),
    _ENUM.s: (
        "self.matrices['{scenario}']['{enum0}'].loc[(slice(None),_MASTER_INDEX['a'],slice(None)),(slice(None),_MASTER_INDEX['c'],slice(None))]",
        dict(enum0=_ENUM.z),
    ),
    _ENUM.S: (
        "self.matrices['{scenario}']['{enum0}'].loc[(slice(None),_MASTER_INDEX['a'],slice(None)),(slice(None),_MASTER_INDEX['c'],slice(None))]",
        dict(enum0=_ENUM.Z),
    ),
    _ENUM.u: (
        "self.matrices['{scenario}']['{enum0}'].loc[(slice(None),_MASTER_INDEX['c'],slice(None)),(slice(None),_MASTER_INDEX['a'],slice(None))]",
        dict(enum0=_ENUM.z),
    ),
    _ENUM.U: (
        "self.matrices['{scenario}']['{enum0}'].loc[(slice(None),_MASTER_INDEX['c'],slice(None)),(slice(None),_MASTER_INDEX['a'],slice(None))]",
        dict(enum0=_ENUM.Z),
    ),
    _ENUM.p: (
        "calc_p(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
        dict(enum0=_ENUM.v, enum1=_ENUM.w),
    ),
    "X_Z": (
        "calc_X(self.matrices['{scenario}']['{enum0}'],self.matrices['{scenario}']['{enum1}'])",
        dict(enum0=_ENUM.Z, enum1=_ENUM.Y),
    ),
    "X_z": (
        "calc_X_from_z(self.matrices['{}']['{enum0}'],self.matrices['{}']['{enum1}'])",
        dict(enum0=_ENUM.z, enum1=_ENUM.Y),
    ),
}


_SHOCKS = {
    "r_reg": "row region",
    "r_lev": "row level",
    "r_sec": "row sector",
    "c_reg": "column region",
    "c_lev": "column level",
    "c_sec": "column sector",
    "d_cat": "demand category",
    "type": "type",
    "value": "value",
}


_EXIO_INDEX = {
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


_MRSUT_EXIO_INDEX = {
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


_HMRSUT_EXTENSIONS = [
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


_MATRICES_NAMES = {
    "Z": "Intersectoral transaction flows",
    "z": "Intersectoral transaction coefficients",
    "Y": "Final demand",
    "V": "Value added transaction flows",
    "v": "Value added transaction coefficients",
    "E": "Satellite transaction flows",
    "e": "Satellite transaction coefficients",
    "EY": "Satellite transaction flows for final use",
    "U": "Use transaction flows",
    "u": "Use transaction coefficients",
    "S": "Supply transaction flows",
    "s": "Supply transaction coefficients",
    "X": "Production vector",
    "p": "Price index vector",
    "F": "Footprints",
    "f": "Footprints coeffients",
}


_ALL_MATRICES = {
    IOT: [
        _ENUM.e,
        _ENUM.E,
        _ENUM.X,
        _ENUM.EY,
        _ENUM.Y,
        _ENUM.y,
        _ENUM.V,
        _ENUM.v,
        _ENUM.F,
        _ENUM.f,
        _ENUM.M,
        _ENUM.m,
        _ENUM.b,
        _ENUM.g,
        _ENUM.w,
        _ENUM.p,
        _ENUM.z,
        _ENUM.Z,
    ],
    SUT: [
        _ENUM.e,
        _ENUM.E,
        _ENUM.X,
        _ENUM.EY,
        _ENUM.Y,
        _ENUM.y,
        _ENUM.V,
        _ENUM.v,
        _ENUM.F,
        _ENUM.f,
        _ENUM.M,
        _ENUM.m,
        _ENUM.b,
        _ENUM.g,
        _ENUM.w,
        _ENUM.p,
        _ENUM.z,
        _ENUM.Z,
        _ENUM.u,
        _ENUM.U,
        _ENUM.s,
        _ENUM.S,
    ],
}


_INDECES = {
    IOT: {
        "Z": {
            "indices": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
        },
        "z": {
            "indices": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
        },
        "Y": {
            "indices": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["n"]],
        },
        "X": {
            "indices": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
            "columns": ["production"],
        },
        "p": {
            "indices": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
            "columns": ["price index"],
        },
        "V": {
            "indices": [_MASTER_INDEX["f"]],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
        },
        "v": {
            "indices": [_MASTER_INDEX["f"]],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
        },
        "E": {
            "indices": [_MASTER_INDEX["k"]],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
        },
        "e": {
            "indices": [_MASTER_INDEX["k"]],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
        },
        "EY": {
            "indices": [_MASTER_INDEX["k"]],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["n"]],
        },
        "F": {
            "indices": [_MASTER_INDEX["k"]],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
        },
        "M": {
            "indices": [_MASTER_INDEX["f"]],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["s"], "Item"],
        },
    },
    SUT: {
        "Z": {
            "indices": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
            "columns": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
        },
        "z": {
            "indices": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
            "columns": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
        },
        "U": {
            "indices": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["c"], "Item"],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["a"], "Item"],
        },
        "u": {
            "indices": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["c"], "Item"],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["a"], "Item"],
        },
        "S": {
            "indices": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["a"], "Item"],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["c"], "Item"],
        },
        "s": {
            "indices": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["a"], "Item"],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["c"], "Item"],
        },
        "Y": {
            "indices": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["n"]],
        },
        "X": {
            "indices": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
            "columns": ["production"],
        },
        "p": {
            "indices": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
            "columns": ["price index"],
        },
        "V": {
            "indices": [_MASTER_INDEX["f"]],
            "columns": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
        },
        "v": {
            "indices": [_MASTER_INDEX["f"]],
            "columns": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
        },
        "E": {
            "indices": [_MASTER_INDEX["k"]],
            "columns": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
        },
        "e": {
            "indices": [_MASTER_INDEX["k"]],
            "columns": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
        },
        "EY": {
            "indices": [_MASTER_INDEX["k"]],
            "columns": [_MASTER_INDEX["r"], "Level", _MASTER_INDEX["n"]],
        },
        "F": {
            "indices": [_MASTER_INDEX["k"]],
            "columns": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
        },
        "M": {
            "indices": [_MASTER_INDEX["f"]],
            "columns": [
                _MASTER_INDEX["r"],
                "Level",
                _MASTER_INDEX["a"],
                _MASTER_INDEX["c"],
                "Item",
            ],
        },
    },
}

_PYMRIO_MATRICES = {
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

_PYMRIO_INDEXING = {
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
