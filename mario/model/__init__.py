"""Core model primitives for the parallel MARIO 2 architecture."""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "Block",
    "BlockRole",
    "COMMODITY_ACTIVITY_LABEL",
    "DataTemplate",
    "Dataset",
    "DatasetMetadata",
    "INDEX_LABELS",
    "IOT",
    "ITEM_LABEL",
    "MATRIX_LABELS",
    "MatrixBuilder",
    "SUT",
    "PRICE_INDEX_LABEL",
    "PRODUCTION_LABEL",
    "Scenario",
    "TABLE_LEVEL_CODES",
    "TABLE_UNIT_CODES",
    "TableKind",
    "TableSchemaLabels",
    "get_table_schema_labels",
    "level_name",
    "matrix_name",
]


def __getattr__(name: str):
    if name == "Block":
        from mario.model.block import Block

        return Block

    if name == "Dataset":
        from mario.model.dataset import Dataset

        return Dataset

    if name == "DatasetMetadata":
        from mario.model.metadata import DatasetMetadata

        return DatasetMetadata

    if name == "Scenario":
        from mario.model.scenario import Scenario

        return Scenario

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
