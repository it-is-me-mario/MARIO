"""Planning utilities for MARIO 2 block resolution."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping

from mario.compute.catalog import get_matrix_spec
from mario.compute.operators import get_registered_operator
from mario.compute.runtime import (
    should_prefer_solve_for_iot_target,
    should_prefer_solve_for_sut_target,
)
from mario.compute.types import (
    ConcatStrategy,
    ExtractStrategy,
    FormulaStrategy,
    MatrixKey,
    OperatorStrategy,
    ParsedStrategy,
    ResolutionContext,
    ResolutionResult,
    Strategy,
    StrategyKind,
)
from mario.model.enums import TableKind

_IOT_SOLVE_FORMULAS = {
    "build_iot_X_from_z_Y",
    "build_iot_m_from_v_z",
    "build_iot_f_from_e_z",
    "build_iot_p_from_v_z",
}
_IOT_INVERSE_FORMULAS = {
    "build_iot_X_from_w_Y",
    "build_iot_m_from_v_w",
    "build_iot_f_from_e_w",
    "build_iot_p_from_v_w",
}
_SUT_SOLVE_FORMULAS = {
    "build_sut_Xc_from_u_s_Yc",
    "build_sut_ma_from_va_s_u",
    "build_sut_mc_from_va_s_u",
    "build_sut_fa_from_ea_s_u",
    "build_sut_fc_from_ea_s_u",
    "build_sut_pc_from_v_s_u",
    "build_sut_pa_from_v_s_u",
}
_SUT_INVERSE_FORMULAS = {
    "build_sut_Xc_from_wcc_Yc",
    "build_sut_ma_from_va_waa",
    "build_sut_mc_from_va_s_wcc",
    "build_sut_fa_from_ea_waa",
    "build_sut_fc_from_ea_s_wcc",
    "build_sut_pc_from_vc",
    "build_sut_pa_from_va",
}


class ResolutionStore:
    """Minimal adapter over databases and in-memory mappings."""

    def __init__(self, dataset, scenario: str = "baseline") -> None:
        """Bind the planner to one dataset-like object and scenario."""
        self.dataset = dataset
        self.scenario = scenario

    def _scenario_mapping(self) -> MutableMapping:
        """Return the mutable mapping that stores blocks for the scenario."""
        dataset = self.dataset

        if hasattr(dataset, "list_matrices") and hasattr(dataset, "get_block"):
            return {
                name: dataset.get_block(name, scenario=self.scenario)
                for name in dataset.list_matrices(self.scenario)
            }

        if hasattr(dataset, "matrices"):
            return dataset.matrices[self.scenario]

        if isinstance(dataset, MutableMapping):
            if self.scenario in dataset and isinstance(dataset[self.scenario], MutableMapping):
                return dataset[self.scenario]
            return dataset

        raise TypeError("Unsupported dataset type for resolution store.")

    def has(self, name: str) -> bool:
        """Return ``True`` when the scenario already materializes ``name``."""
        dataset = self.dataset
        if hasattr(dataset, "has_matrix"):
            return bool(dataset.has_matrix(name, scenario=self.scenario))
        if hasattr(dataset, "has_block"):
            return bool(dataset.has_block(name, scenario=self.scenario))
        return name in self._scenario_mapping()

    def get(self, name: str):
        """Read one block from the wrapped dataset or mapping."""
        dataset = self.dataset
        if hasattr(dataset, "get_block"):
            return dataset.get_block(name, scenario=self.scenario)
        return self._scenario_mapping()[name]

    def set(self, name: str, value) -> None:
        """Persist one materialized block back to the wrapped dataset."""
        dataset = self.dataset
        if hasattr(dataset, "set_block"):
            dataset.set_block(name, value, scenario=self.scenario)
            return
        self._scenario_mapping()[name] = value

    def names(self) -> tuple[str, ...]:
        """Return the block names already present in the scenario."""
        dataset = self.dataset
        if hasattr(dataset, "list_matrices"):
            return tuple(dataset.list_matrices(self.scenario))
        return tuple(self._scenario_mapping().keys())


def resolve_table_kind(dataset, context: ResolutionContext | None = None) -> TableKind:
    """Infer the table kind from explicit context or dataset metadata."""
    if context is not None and context.table_kind is not None:
        return TableKind.coerce(context.table_kind)

    if hasattr(dataset, "table_kind"):
        return TableKind.coerce(dataset.table_kind)

    if hasattr(dataset, "table_type"):
        return TableKind.coerce(dataset.table_type)

    if hasattr(dataset, "meta") and hasattr(dataset.meta, "table"):
        return TableKind.coerce(dataset.meta.table)

    if isinstance(dataset, Mapping):
        value = dataset.get("__table_kind__")
        if value is not None:
            return TableKind.coerce(value)

    raise ValueError("Cannot infer table kind from dataset; pass it through ResolutionContext.")


def strategy_is_immediately_available(
    strategy: Strategy,
    target: str,
    dataset,
    scenario: str = "baseline",
    context: ResolutionContext | None = None,
) -> bool:
    """Return ``True`` when a strategy can run without resolving dependencies."""
    store = ResolutionStore(dataset, scenario=scenario)

    if isinstance(strategy, ParsedStrategy):
        return store.has(target)

    if isinstance(strategy, ExtractStrategy):
        return store.has(strategy.source)

    if isinstance(strategy, ConcatStrategy):
        return all(store.has(source) for source in strategy.sources)

    if isinstance(strategy, FormulaStrategy):
        return all(store.has(source) for source in strategy.inputs)

    if isinstance(strategy, OperatorStrategy):
        return all(store.has(source) for source in strategy.inputs)

    return False


def strategy_cost_hint(
    strategy: Strategy,
    target: str,
    dataset,
    scenario: str = "baseline",
    context: ResolutionContext | None = None,
) -> tuple[int, int, int]:
    """Return a sortable hint used to rank candidate strategies."""
    priority = {
        StrategyKind.PARSED: 1,
        StrategyKind.EXTRACT: 2,
        StrategyKind.CONCAT: 3,
        StrategyKind.FORMULA: 4,
        StrategyKind.OPERATOR: 4,
    }[strategy.kind]
    available_penalty = 0 if strategy_is_immediately_available(strategy, target, dataset, scenario, context) else 10
    method_penalty = 0
    if isinstance(strategy, FormulaStrategy):
        table_kind = resolve_table_kind(dataset, context)
        if table_kind == TableKind.IOT:
            size = _estimate_iot_entity_size(dataset, scenario=scenario)
            prefer_solve = should_prefer_solve_for_iot_target(target, size=size, context=context)
            if strategy.function in _IOT_SOLVE_FORMULAS:
                method_penalty = 0 if prefer_solve else 5
            elif strategy.function in _IOT_INVERSE_FORMULAS:
                method_penalty = 5 if prefer_solve else 0
        elif table_kind == TableKind.SUT:
            size = _estimate_sut_system_size(dataset, target=target, scenario=scenario)
            prefer_solve = should_prefer_solve_for_sut_target(target, size=size, context=context)
            if strategy.function in _SUT_SOLVE_FORMULAS:
                method_penalty = 0 if prefer_solve else 5
            elif strategy.function in _SUT_INVERSE_FORMULAS:
                method_penalty = 5 if prefer_solve else 0
    return (priority + available_penalty, method_penalty, len(strategy.dependencies))


def classify_iot_formula_strategy(strategy: Strategy) -> str | None:
    """Classify one formula strategy as ``solve`` or ``inverse`` when relevant."""
    if not isinstance(strategy, FormulaStrategy):
        return None
    if strategy.function in _IOT_SOLVE_FORMULAS:
        return "solve"
    if strategy.function in _IOT_INVERSE_FORMULAS:
        return "inverse"
    if strategy.function in _SUT_SOLVE_FORMULAS:
        return "solve"
    if strategy.function in _SUT_INVERSE_FORMULAS:
        return "inverse"
    return None


def _estimate_iot_entity_size(dataset, *, scenario: str = "baseline") -> int | None:
    """Estimate the square IOT entity size from visible blocks."""
    store = ResolutionStore(dataset, scenario=scenario)
    for name in ("w", "z", "Z", "X"):
        if not store.has(name):
            continue
        block = store.get(name)
        if hasattr(block, "shape"):
            return int(block.shape[0])
        if hasattr(block, "index"):
            return int(len(block.index))
    return None


def _estimate_sut_system_size(dataset, *, target: str, scenario: str = "baseline") -> int | None:
    """Estimate the relevant square SUT system size for one target."""
    store = ResolutionStore(dataset, scenario=scenario)

    if target in {"Xc", "mc", "fc", "pc", "wcc", "wca"}:
        candidates = ("wcc", "Xc", "Yc", "U", "u")
    elif target in {"ma", "fa", "pa", "waa", "wac"}:
        candidates = ("waa", "Xa", "Ya", "S", "s")
    else:
        return None

    for name in candidates:
        if not store.has(name):
            continue
        block = store.get(name)
        if hasattr(block, "shape"):
            return int(block.shape[0])
        if hasattr(block, "index"):
            return int(len(block.index))
    return None


def candidate_strategies(
    target: str,
    dataset,
    scenario: str = "baseline",
    context: ResolutionContext | None = None,
) -> tuple[Strategy, ...]:
    """Return candidate strategies ordered by the planner priority rules."""
    table_kind = resolve_table_kind(dataset, context)
    try:
        spec = get_matrix_spec(table_kind, target)
    except KeyError:
        operator = get_registered_operator(dataset, target)
        if operator is None:
            raise
        return (
            OperatorStrategy(
                inputs=operator.inputs,
                operator_kind=operator.kind.value,
                notes=operator.notes,
            ),
        )
    return tuple(
        sorted(
            spec.strategies,
            key=lambda strategy: strategy_cost_hint(strategy, target, dataset, scenario, context),
        )
    )


def build_plan(
    target: str,
    dataset,
    scenario: str = "baseline",
    context: ResolutionContext | None = None,
) -> list[ResolutionResult]:
    """Build the ordered execution plan needed to materialize ``target``."""
    context = context or ResolutionContext()
    store = ResolutionStore(dataset, scenario=scenario)
    table_kind = resolve_table_kind(dataset, context)
    planning: list[ResolutionResult] = []
    seen: set[str] = set()
    active: tuple[str, ...] = ()

    def plan_for(name: str, stack: tuple[str, ...]) -> None:
        if store.has(name) or name in context.materialized or name in seen:
            return

        if name in stack:
            raise RuntimeError(f"Dependency cycle detected while planning {name}: {' -> '.join(stack + (name,))}")

        strategy = _select_strategy(name, dataset, scenario, context, stack)
        if strategy is None:
            raise LookupError(f"No viable strategy found while planning {name}.")

        # The planner resolves recursive dependencies for formula and concat
        # strategies so the executor can materialize them in-order later on.
        if isinstance(strategy, FormulaStrategy):
            for dependency in strategy.inputs:
                plan_for(dependency, stack + (name,))
        elif isinstance(strategy, OperatorStrategy):
            for dependency in strategy.inputs:
                plan_for(dependency, stack + (name,))
        elif isinstance(strategy, ConcatStrategy):
            for dependency in strategy.sources:
                plan_for(dependency, stack + (name,))
        elif isinstance(strategy, ExtractStrategy):
            if not store.has(strategy.source) and strategy.source not in context.materialized:
                raise LookupError(
                    f"Extract strategy for {name} requires already materialized source {strategy.source}."
                )
        elif isinstance(strategy, ParsedStrategy):
            raise LookupError(f"Parsed block {name} is not materialized in the dataset.")

        planning.append(
            ResolutionResult(
                key=MatrixKey(table_kind=table_kind, name=name),
                strategy_kind=strategy.kind,
                dependencies=strategy.dependencies,
                notes=strategy.notes,
            )
        )
        seen.add(name)

    plan_for(target, active)
    return planning


def _select_strategy(
    target: str,
    dataset,
    scenario: str,
    context: ResolutionContext,
    stack: tuple[str, ...],
) -> Strategy | None:
    """Select the first viable strategy for ``target`` under the current context."""
    store = ResolutionStore(dataset, scenario=scenario)

    for strategy in candidate_strategies(target, dataset, scenario, context):
        if isinstance(strategy, ParsedStrategy):
            if store.has(target):
                return strategy
            continue

        if isinstance(strategy, ExtractStrategy):
            if store.has(strategy.source) or strategy.source in context.materialized:
                return strategy
            continue

        if isinstance(strategy, ConcatStrategy):
            if any(dependency in stack for dependency in strategy.sources):
                continue
            return strategy

        if isinstance(strategy, FormulaStrategy):
            if not context.allow_formula:
                continue
            if any(dependency in stack for dependency in strategy.inputs):
                continue
            return strategy

        if isinstance(strategy, OperatorStrategy):
            if any(dependency in stack for dependency in strategy.inputs):
                continue
            return strategy

    return None
