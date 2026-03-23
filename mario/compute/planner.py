"""Planning utilities for MARIO 2 block resolution."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping

from mario.compute.catalog import get_matrix_spec
from mario.compute.types import (
    ConcatStrategy,
    ExtractStrategy,
    FormulaStrategy,
    MatrixKey,
    ParsedStrategy,
    ResolutionContext,
    ResolutionResult,
    Strategy,
    StrategyKind,
)
from mario.model.enums import TableKind


class ResolutionStore:
    """Minimal adapter over databases and in-memory mappings."""

    def __init__(self, dataset, scenario: str = "baseline") -> None:
        self.dataset = dataset
        self.scenario = scenario

    def _scenario_mapping(self) -> MutableMapping:
        dataset = self.dataset

        if hasattr(dataset, "list_blocks") and hasattr(dataset, "get_block"):
            return {name: dataset.get_block(name, scenario=self.scenario) for name in dataset.list_blocks(self.scenario)}

        if hasattr(dataset, "matrices"):
            return dataset.matrices[self.scenario]

        if isinstance(dataset, MutableMapping):
            if self.scenario in dataset and isinstance(dataset[self.scenario], MutableMapping):
                return dataset[self.scenario]
            return dataset

        raise TypeError("Unsupported dataset type for resolution store.")

    def has(self, name: str) -> bool:
        dataset = self.dataset
        if hasattr(dataset, "has_block"):
            return bool(dataset.has_block(name, scenario=self.scenario))
        return name in self._scenario_mapping()

    def get(self, name: str):
        dataset = self.dataset
        if hasattr(dataset, "get_block"):
            return dataset.get_block(name, scenario=self.scenario)
        return self._scenario_mapping()[name]

    def set(self, name: str, value) -> None:
        dataset = self.dataset
        if hasattr(dataset, "set_block"):
            dataset.set_block(name, value, scenario=self.scenario)
            return
        self._scenario_mapping()[name] = value

    def names(self) -> tuple[str, ...]:
        dataset = self.dataset
        if hasattr(dataset, "list_blocks"):
            return tuple(dataset.list_blocks(self.scenario))
        return tuple(self._scenario_mapping().keys())


def resolve_table_kind(dataset, context: ResolutionContext | None = None) -> TableKind:
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
    store = ResolutionStore(dataset, scenario=scenario)

    if isinstance(strategy, ParsedStrategy):
        return store.has(target)

    if isinstance(strategy, ExtractStrategy):
        return store.has(strategy.source)

    if isinstance(strategy, ConcatStrategy):
        return all(store.has(source) for source in strategy.sources)

    if isinstance(strategy, FormulaStrategy):
        return all(store.has(source) for source in strategy.inputs)

    return False


def strategy_cost_hint(
    strategy: Strategy,
    target: str,
    dataset,
    scenario: str = "baseline",
    context: ResolutionContext | None = None,
) -> tuple[int, int, int]:
    priority = {
        StrategyKind.PARSED: 1,
        StrategyKind.EXTRACT: 2,
        StrategyKind.CONCAT: 3,
        StrategyKind.FORMULA: 4,
    }[strategy.kind]
    available_penalty = 0 if strategy_is_immediately_available(strategy, target, dataset, scenario, context) else 10
    return (priority + available_penalty, len(strategy.dependencies), 0)


def candidate_strategies(
    target: str,
    dataset,
    scenario: str = "baseline",
    context: ResolutionContext | None = None,
) -> tuple[Strategy, ...]:
    table_kind = resolve_table_kind(dataset, context)
    spec = get_matrix_spec(table_kind, target)
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

        if isinstance(strategy, FormulaStrategy):
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

    return None
