"""Public domain conventions and builders used by MARIO."""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "BlockRole",
    "COMMODITY_ACTIVITY_LABEL",
    "DataTemplate",
    "INDEX_LABELS",
    "IOT",
    "ITEM_LABEL",
    "MATRIX_LABELS",
    "MatrixBuilder",
    "SUT",
    "PRICE_INDEX_LABEL",
    "PRODUCTION_LABEL",
    "TABLE_LEVEL_CODES",
    "TABLE_UNIT_CODES",
    "TableKind",
    "TableSchemaLabels",
    "get_table_schema_labels",
    "level_name",
    "matrix_name",
]


def __getattr__(name: str):
    """Resolve model exports lazily to keep import cost and cycles low."""
    if name in {"DataTemplate", "MatrixBuilder"}:
        module = import_module("mario.model.builders")
        return getattr(module, name)

    if name in {"BlockRole", "TableKind"}:
        module = import_module("mario.model.enums")
        return getattr(module, name)

    if name in {
        "COMMODITY_ACTIVITY_LABEL",
        "INDEX_LABELS",
        "IOT",
        "ITEM_LABEL",
        "MATRIX_LABELS",
        "SUT",
        "PRICE_INDEX_LABEL",
        "PRODUCTION_LABEL",
        "TABLE_LEVEL_CODES",
        "TABLE_UNIT_CODES",
        "TableSchemaLabels",
        "get_table_schema_labels",
        "level_name",
        "matrix_name",
    }:
        module = import_module("mario.model.labels")
        return getattr(module, name)

    raise AttributeError(name)
