# -*- coding: utf-8 -*-
"""
This module contains all the constants of the code
"""

_MASTER_INDEX = {
    "r": "Region",
    "a": "Activity",
    "c": "Commodity",
    "s": "Sector",
    "k": "Satellite account",
    "f": "Factor of production",
    "n": "Consumption category",
}


# represents different levels of aggregation
_LEVELS = {
    "SUT": {_MASTER_INDEX[i]: i for i in ["a", "c", "f", "k", "n", "r"]},
    "IOT": {_MASTER_INDEX[i]: i for i in ["f", "k", "n", "r", "s"]},
}


_INDEX_NAMES = {"3levels": (_MASTER_INDEX["r"], "Level", "Item"), "1level": ("Item")}


_ACCEPTABLES = {
    "table": ["SUT", "IOT"],
}


_UNITS = {
    "SUT": {_MASTER_INDEX[i]: i for i in ["a", "c", "f", "k"]},
    "IOT": {_MASTER_INDEX[i]: i for i in ["s", "f", "k"]},
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
    "m": "calc_f(self.matrices['{}']['v'],self.matrices['{}']['w'])",
    "M": "calc_F(self.matrices['{}']['m'],self.matrices['{}']['Y'].sum(1))",
    "V": "calc_E(self.matrices['{}']['v'],self.matrices['{}']['X'])",
    "v": "calc_e(self.matrices['{}']['V'],self.matrices['{}']['X'])",
    "f": "calc_f(self.matrices['{}']['e'],self.matrices['{}']['w'])",
    "F": "calc_F(self.matrices['{}']['f'],self.matrices['{}']['Y'].sum(1))",
    "e": "calc_e(self.matrices['{}']['E'],self.matrices['{}']['X'])",
    "E": "calc_E(self.matrices['{}']['e'],self.matrices['{}']['X'])",
    "z": "calc_z(self.matrices['{}']['Z'],self.matrices['{}']['X'])",
    "Z": "calc_Z(self.matrices['{}']['z'],self.matrices['{}']['X'])",
    "w": "calc_w(self.matrices['{}']['z'])",
    "g": "calc_w(self.matrices['{}']['b'])",
    "b": "calc_b(self.matrices['{}']['X'],self.matrices['{}']['Z'])",
    "y": "calc_y(self.matrices['{}']['Y'])",
    "s": "self.matrices['{}']['z'].loc[(slice(None),_MASTER_INDEX['a'],slice(None)),(slice(None),_MASTER_INDEX['c'],slice(None))]",
    "S": "self.matrices['{}']['Z'].loc[(slice(None),_MASTER_INDEX['a'],slice(None)),(slice(None),_MASTER_INDEX['c'],slice(None))]",
    "u": "self.matrices['{}']['z'].loc[(slice(None),_MASTER_INDEX['c'],slice(None)),(slice(None),_MASTER_INDEX['a'],slice(None))]",
    "U": "self.matrices['{}']['Z'].loc[(slice(None),_MASTER_INDEX['c'],slice(None)),(slice(None),_MASTER_INDEX['a'],slice(None))]",
    "p": "calc_p(self.matrices['{}']['v'],self.matrices['{}']['w'])",
    "X_Z": "calc_X(self.matrices['{}']['Z'],self.matrices['{}']['Y'])",
    "X_z": "calc_X_from_z(self.matrices['{}']['z'],self.matrices['{}']['Y'])",
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
    "IOT": [
        "e",
        "E",
        "X",
        "EY",
        "Y",
        "y",
        "V",
        "v",
        "F",
        "f",
        "M",
        "m",
        "b",
        "g",
        "w",
        "p",
        "z",
        "Z",
    ],
    "SUT": [
        "e",
        "E",
        "X",
        "EY",
        "Y",
        "y",
        "V",
        "v",
        "F",
        "f",
        "M",
        "m",
        "b",
        "g",
        "w",
        "p",
        "z",
        "Z",
        "u",
        "U",
        "s",
        "S",
    ],
}


_INDECES = {
    "IOT": {
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
    "SUT": {
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


