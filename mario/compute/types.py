"""Typed planner metadata for the new MARIO 2 compute engine.

These types are internal to catalog/planner/resolver work. They should not leak
into the long-term public dataset API, where users should just ask for blocks
that exist regardless of how they were materialized.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

from mario.model.enums import TableKind


class StrategyKind(str, Enum):
    PARSED = "parsed"
    EXTRACT = "extract"
    CONCAT = "concat"
    FORMULA = "formula"


class MatrixStatus(str, Enum):
    KEEP = "keep"
    ADD = "add"


@dataclass(frozen=True)
class MatrixKey:
    table_kind: TableKind
    name: str


@dataclass(frozen=True)
class AxisSpec:
    rows: tuple[str, ...]
    cols: tuple[str, ...]


@dataclass(frozen=True)
class ParsedStrategy:
    required: bool
    notes: tuple[str, ...] = ()

    @property
    def kind(self) -> StrategyKind:
        return StrategyKind.PARSED

    @property
    def dependencies(self) -> tuple[str, ...]:
        return ()


@dataclass(frozen=True)
class ExtractStrategy:
    source: str
    extractor: str
    spreadsheet_expr: str
    notes: tuple[str, ...] = ()

    @property
    def kind(self) -> StrategyKind:
        return StrategyKind.EXTRACT

    @property
    def dependencies(self) -> tuple[str, ...]:
        return (self.source,)


@dataclass(frozen=True)
class ConcatStrategy:
    sources: tuple[str, ...]
    builder: str
    spreadsheet_expr: str
    notes: tuple[str, ...] = ()

    @property
    def kind(self) -> StrategyKind:
        return StrategyKind.CONCAT

    @property
    def dependencies(self) -> tuple[str, ...]:
        return self.sources


@dataclass(frozen=True)
class FormulaStrategy:
    inputs: tuple[str, ...]
    function: str
    spreadsheet_expr: str
    notes: tuple[str, ...] = ()

    @property
    def kind(self) -> StrategyKind:
        return StrategyKind.FORMULA

    @property
    def dependencies(self) -> tuple[str, ...]:
        return self.inputs


Strategy: TypeAlias = ParsedStrategy | ExtractStrategy | ConcatStrategy | FormulaStrategy


@dataclass(frozen=True)
class MatrixSpec:
    key: MatrixKey
    status: MatrixStatus
    axes: AxisSpec
    strategies: tuple[Strategy, ...]
    notes: tuple[str, ...] = ()
    todo: str | None = None
    alternate_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolutionContext:
    table_kind: TableKind | None = None
    materialized: frozenset[str] = frozenset()
    prefer_materialized_views: bool = True
    allow_formula: bool = True


@dataclass(frozen=True)
class ResolutionResult:
    key: MatrixKey
    strategy_kind: StrategyKind
    dependencies: tuple[str, ...] = ()
    materialized: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)
