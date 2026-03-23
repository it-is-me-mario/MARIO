"""Legacy-aware labels reused by the new MARIO 2 core."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from mario.model.enums import TableKind
from mario.settings.settings import Index, Nomenclature

ITEM_LABEL = "Item"
PRODUCTION_LABEL = "production"
PRICE_INDEX_LABEL = "price index"
COMMODITY_ACTIVITY_LABEL = "Commodity/Activity"


@lru_cache(maxsize=1)
def _index_labels() -> dict[str, str]:
    return dict(Index().items())


@lru_cache(maxsize=1)
def _matrix_labels() -> dict[str, str]:
    return dict(Nomenclature().items())


INDEX_LABELS = _index_labels()
MATRIX_LABELS = _matrix_labels()

TABLE_LEVEL_CODES = {
    TableKind.IOT: ("f", "k", "n", "r", "s"),
    TableKind.SUT: ("a", "c", "f", "k", "n", "r"),
}

TABLE_UNIT_CODES = {
    TableKind.IOT: ("s", "f", "k"),
    TableKind.SUT: ("a", "c", "f", "k"),
}


@dataclass(frozen=True)
class TableSchemaLabels:
    """Logical dimension labels for one table kind."""

    table: TableKind
    dimension_codes: tuple[str, ...]
    unit_codes: tuple[str, ...]

    @property
    def dimension_labels(self) -> tuple[str, ...]:
        return tuple(level_name(code) for code in self.dimension_codes)

    @property
    def unit_labels(self) -> tuple[str, ...]:
        return tuple(level_name(code) for code in self.unit_codes)


def level_name(code: str) -> str:
    return INDEX_LABELS[code]


def matrix_name(code: str) -> str:
    return MATRIX_LABELS[code]


def get_table_schema_labels(table: "TableKind | str") -> TableSchemaLabels:
    kind = TableKind.coerce(table)
    return TableSchemaLabels(
        table=kind,
        dimension_codes=TABLE_LEVEL_CODES[kind],
        unit_codes=TABLE_UNIT_CODES[kind],
    )
