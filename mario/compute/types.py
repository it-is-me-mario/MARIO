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
    """Kinds of resolution strategy supported by the compute planner."""

    PARSED = "parsed"
    EXTRACT = "extract"
    CONCAT = "concat"
    FORMULA = "formula"
    OPERATOR = "operator"


class MatrixStatus(str, Enum):
    """Migration status of a matrix specification within the catalog."""

    KEEP = "keep"
    ADD = "add"


class ExecutionMode(str, Enum):
    """High-level execution intent exposed by the advanced compute API."""

    AUTO = "auto"
    PREFER_SPEED = "prefer_speed"
    PREFER_MEMORY = "prefer_memory"
    DEBUG = "debug"


class PlanningOverride(str, Enum):
    """Optional override for the planning phase of one compute request."""

    AUTO = "auto"
    PREFER_EXPLICIT_INTERMEDIATES = "prefer_explicit_intermediates"
    PREFER_DIRECT_TARGETS = "prefer_direct_targets"


class BackendOverride(str, Enum):
    """Optional override for the numerical backend used by one request."""

    AUTO = "auto"
    DENSE_INVERSE = "dense_inverse"
    DENSE_SOLVE = "dense_solve"
    SPARSE_DIRECT = "sparse_direct"
    SPARSE_ITERATIVE = "sparse_iterative"


class MaterializationMode(str, Enum):
    """Policy that controls which resolved blocks remain materialized."""

    AUTO = "auto"
    REQUESTED_ONLY = "requested_only"
    REUSE_HEAVY = "reuse_heavy"
    ALL = "all"
    NONE = "none"


@dataclass(frozen=True)
class MatrixKey:
    """Unique matrix identifier inside the compute catalog."""

    table_kind: TableKind
    name: str


@dataclass(frozen=True)
class AxisSpec:
    """Semantic labels expected on the row and column axes of a matrix."""

    rows: tuple[str, ...]
    cols: tuple[str, ...]


@dataclass(frozen=True)
class ParsedStrategy:
    """Strategy stating that a block must already exist in dataset storage."""

    required: bool
    notes: tuple[str, ...] = ()

    @property
    def kind(self) -> StrategyKind:
        """Return the planner tag used for parsed blocks."""
        return StrategyKind.PARSED

    @property
    def dependencies(self) -> tuple[str, ...]:
        """Return the blocks required before execution of this strategy."""
        return ()


@dataclass(frozen=True)
class ExtractStrategy:
    """Strategy that derives a split or unified view from one source block."""

    source: str
    extractor: str
    spreadsheet_expr: str
    notes: tuple[str, ...] = ()

    @property
    def kind(self) -> StrategyKind:
        """Return the planner tag used for view extraction."""
        return StrategyKind.EXTRACT

    @property
    def dependencies(self) -> tuple[str, ...]:
        """Return the source block required for extraction."""
        return (self.source,)


@dataclass(frozen=True)
class ConcatStrategy:
    """Strategy that concatenates already resolved sub-blocks into one view."""

    sources: tuple[str, ...]
    builder: str
    spreadsheet_expr: str
    notes: tuple[str, ...] = ()

    @property
    def kind(self) -> StrategyKind:
        """Return the planner tag used for block concatenation."""
        return StrategyKind.CONCAT

    @property
    def dependencies(self) -> tuple[str, ...]:
        """Return the ordered inputs required by the concat builder."""
        return self.sources


@dataclass(frozen=True)
class FormulaStrategy:
    """Strategy that materializes a block through a pure numerical formula."""

    inputs: tuple[str, ...]
    function: str
    spreadsheet_expr: str
    notes: tuple[str, ...] = ()

    @property
    def kind(self) -> StrategyKind:
        """Return the planner tag used for formula execution."""
        return StrategyKind.FORMULA

    @property
    def dependencies(self) -> tuple[str, ...]:
        """Return the ordered inputs required by the formula."""
        return self.inputs


@dataclass(frozen=True)
class OperatorStrategy:
    """Strategy that materializes a block through a registered custom operator."""

    inputs: tuple[str, ...]
    operator_kind: str
    notes: tuple[str, ...] = ()

    @property
    def kind(self) -> StrategyKind:
        """Return the planner tag used for custom operators."""
        return StrategyKind.OPERATOR

    @property
    def dependencies(self) -> tuple[str, ...]:
        """Return the ordered inputs required by the operator."""
        return self.inputs


Strategy: TypeAlias = ParsedStrategy | ExtractStrategy | ConcatStrategy | FormulaStrategy | OperatorStrategy


@dataclass(frozen=True)
class MatrixSpec:
    """Full compute specification for one matrix on one table kind."""

    key: MatrixKey
    status: MatrixStatus
    axes: AxisSpec
    strategies: tuple[Strategy, ...]
    notes: tuple[str, ...] = ()
    todo: str | None = None
    alternate_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComputeOptions:
    """Advanced compute options carried by one resolution request."""

    execution_mode: ExecutionMode | str = ExecutionMode.AUTO
    planning_override: PlanningOverride | str = PlanningOverride.AUTO
    backend_override: BackendOverride | str = BackendOverride.AUTO
    materialization: MaterializationMode | str = MaterializationMode.REQUESTED_ONLY
    auto_memory_fraction: float | None = None
    auto_inverse_overhead_factor: float | None = None
    debug_explain_decisions: bool = False
    allow_fallbacks: bool = True


@dataclass(frozen=True)
class ResolutionContext:
    """Planner options that influence strategy selection and explanation."""

    table_kind: TableKind | None = None
    materialized: frozenset[str] = frozenset()
    prefer_materialized_views: bool = True
    allow_formula: bool = True
    compute: ComputeOptions | None = None
    # Legacy compute overrides kept for backward compatibility while the
    # advanced compute API is rolled out across the public surface.
    compute_method: str | None = None
    linear_solver: str | None = None
    linear_strategy: str | None = None
    auto_w_memory_fraction: float | None = None
    auto_w_overhead_factor: float | None = None


@dataclass(frozen=True)
class ResolutionResult:
    """One planned materialization step emitted by the planner."""

    key: MatrixKey
    strategy_kind: StrategyKind
    dependencies: tuple[str, ...] = ()
    materialized: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)
