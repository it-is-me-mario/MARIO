"""Shared structural conventions for MARIO tables."""

from __future__ import annotations

from mario.settings.settings import Index, Nomenclature


_MASTER_INDEX = Index()
_ENUM = Nomenclature()

SUT = "SUT"
IOT = "IOT"

FLOWS = "flows"
COEFFICIENTS = "coefficients"

MONETARY = "Monetary"
HYBRID = "Hybrid"


TABLE_LEVELS = {
    SUT: {_MASTER_INDEX[i]: i for i in ["a", "c", "f", "k", "n", "r"]},
    IOT: {_MASTER_INDEX[i]: i for i in ["f", "k", "n", "r", "s"]},
}


INDEX_NAME_LAYOUTS = {
    "3levels": (_MASTER_INDEX["r"], "Level", "Item"),
    "1level": "Item",
}


TABLE_UNIT_LEVELS = {
    SUT: {_MASTER_INDEX[i]: i for i in ["a", "c", "f", "k"]},
    IOT: {_MASTER_INDEX[i]: i for i in ["s", "f", "k"]},
}


MATRIX_TITLES = {
    "Z": "Intersectoral transaction flows",
    "z": "Intersectoral transaction coefficients",
    "Y": "Final demand",
    "V": "Value added transaction flows",
    "v": "Value added transaction coefficients",
    "E": "Satellite transaction flows",
    "e": "Satellite transaction coefficients",
    "EY": "Satellite transaction flows for final use",
    "VY": "Value added transaction flows for final use",
    "U": "Use transaction flows",
    "u": "Use transaction coefficients",
    "c": "Commodity technology coefficients",
    "S": "Supply transaction flows",
    "s": "Supply transaction coefficients",
    "X": "Production vector",
    "p": "Price index vector",
    "F": "Footprints",
    "f": "Footprints coeffients",
}


TABLE_MATRIX_INDEX_LAYOUTS = {
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
        "VY": {
            "indices": [_MASTER_INDEX["f"]],
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
        "c": {
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
        "VY": {
            "indices": [_MASTER_INDEX["f"]],
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
