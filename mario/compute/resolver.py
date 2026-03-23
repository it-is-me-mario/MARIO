"""Execution engine for resolving blocks from the compute catalog."""

from __future__ import annotations

import inspect
import logging

from mario.compute import ghosh_formulas, iot_formulas, sut_formulas, views
from mario.compute.graph import build_dependency_graph, render_dependency_graph
from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.planner import ResolutionStore, build_plan, candidate_strategies, resolve_table_kind
from mario.compute.types import (
    ConcatStrategy,
    ExtractStrategy,
    FormulaStrategy,
    ParsedStrategy,
    ResolutionContext,
)
from mario.log_exc.logger import log_time
from mario.model.enums import TableKind

logger = logging.getLogger(__name__)


class ResolutionError(LookupError):
    """Raised when a block cannot be resolved from the current dataset state."""


def _lookup_callable(name: str):
    for module in (views, iot_formulas, sut_formulas, ghosh_formulas):
        function = getattr(module, name, None)
        if callable(function):
            return function
    return None


def _collect_blocks(store: ResolutionStore):
    blocks = {}
    for name in store.names():
        try:
            blocks[name] = store.get(name)
        except KeyError:
            continue
    return blocks


def _build_ordering(store: ResolutionStore, extra_blocks: dict[str, object] | None = None):
    blocks = _collect_blocks(store)
    if extra_blocks:
        blocks.update(extra_blocks)

    kwargs = {name: block for name, block in blocks.items() if name in inspect.signature(SUTUnifiedOrderingPolicy.from_blocks).parameters}
    return SUTUnifiedOrderingPolicy.from_blocks(**kwargs)


def _execute_strategy(strategy, target: str, store: ResolutionStore, table_kind: TableKind, dependencies: dict[str, object]):
    if isinstance(strategy, ParsedStrategy):
        if store.has(target):
            return store.get(target)
        raise ResolutionError(f"Parsed block {target} is not materialized.")

    if isinstance(strategy, ExtractStrategy):
        function = _lookup_callable(strategy.extractor)
        if function is None:
            raise ResolutionError(f"Extractor implementation {strategy.extractor} is missing.")

        source = store.get(strategy.source)
        if table_kind == TableKind.SUT:
            ordering = _build_ordering(store, {strategy.source: source})
            return function(source, ordering)
        return function(source)

    if isinstance(strategy, ConcatStrategy):
        function = _lookup_callable(strategy.builder)
        if function is None:
            raise ResolutionError(f"View builder implementation {strategy.builder} is missing.")

        blocks = [store.get(source) for source in strategy.sources]
        if table_kind == TableKind.SUT:
            ordering = _build_ordering(store, {name: value for name, value in zip(strategy.sources, blocks)})
            return function(*blocks, ordering)
        return function(*blocks)

    if isinstance(strategy, FormulaStrategy):
        function = _lookup_callable(strategy.function)
        if function is None:
            raise ResolutionError(f"Formula implementation {strategy.function} is missing.")
        args = [dependencies[name] for name in strategy.inputs]
        return function(*args)

    raise ResolutionError(f"Unsupported strategy for {target}.")


class Resolver:
    def __init__(self, dataset, scenario: str = "baseline", context: ResolutionContext | None = None) -> None:
        self.dataset = dataset
        self.scenario = scenario
        self.context = context or ResolutionContext()
        self.store = ResolutionStore(dataset, scenario=scenario)
        self.table_kind = resolve_table_kind(dataset, self.context)
        self._memo: dict[str, object] = {}
        self._active: list[str] = []

    def resolve(self, target: str):
        root_request = not self._active
        if target in self._memo:
            return self._memo[target]

        if self.store.has(target):
            value = self.store.get(target)
            self._memo[target] = value
            if root_request:
                log_time(logger, f"Resolver: {target} already materialized in {self.scenario}.", "debug")
            return value

        if target in self._active:
            raise ResolutionError(f"Dependency cycle detected: {' -> '.join(self._active + [target])}")

        if root_request:
            log_time(logger, f"Resolver: resolving {target} for {self.scenario}.", "info")
        self._active.append(target)
        errors: list[str] = []

        try:
            for strategy in candidate_strategies(target, self.dataset, self.scenario, self.context):
                try:
                    if isinstance(strategy, ParsedStrategy):
                        value = _execute_strategy(strategy, target, self.store, self.table_kind, {})
                    elif isinstance(strategy, ExtractStrategy):
                        if not self.store.has(strategy.source):
                            errors.append(f"{strategy.kind.value}: source {strategy.source} is not materialized")
                            continue
                        value = _execute_strategy(strategy, target, self.store, self.table_kind, {})
                    elif isinstance(strategy, ConcatStrategy):
                        for dependency in strategy.sources:
                            self.resolve(dependency)
                        value = _execute_strategy(strategy, target, self.store, self.table_kind, {})
                    else:
                        dependencies = {}
                        for dependency in strategy.inputs:
                            dependencies[dependency] = self.resolve(dependency)
                        value = _execute_strategy(strategy, target, self.store, self.table_kind, dependencies)

                    self.store.set(target, value)
                    self._memo[target] = value
                    if root_request:
                        log_time(
                            logger,
                            f"Resolver: resolved {target} via {strategy.kind.value}.",
                            "info",
                        )
                    return value
                except ResolutionError as exc:
                    errors.append(f"{strategy.kind.value}: {exc}")
                    continue
        finally:
            self._active.pop()

        explanation = self.explain(target)
        if root_request:
            log_time(logger, f"Resolver: failed to resolve {target}.", "warning")
        raise ResolutionError(f"Unable to resolve {target}.\n" + "\n".join(errors) + "\n" + explanation)

    def resolve_many(self, targets: list[str] | tuple[str, ...]):
        return {target: self.resolve(target) for target in targets}

    def explain(self, target: str) -> str:
        graph = build_dependency_graph(target, self.dataset, self.scenario, self.context)
        return render_dependency_graph(graph)

    def build_plan(self, target: str):
        return build_plan(target, self.dataset, self.scenario, self.context)


def resolve(target: str, dataset, scenario: str = "baseline", context: ResolutionContext | None = None):
    return Resolver(dataset, scenario=scenario, context=context).resolve(target)


def resolve_many(
    targets: list[str] | tuple[str, ...],
    dataset,
    scenario: str = "baseline",
    context: ResolutionContext | None = None,
):
    return Resolver(dataset, scenario=scenario, context=context).resolve_many(targets)


def explain(target: str, dataset, scenario: str = "baseline", context: ResolutionContext | None = None) -> str:
    return Resolver(dataset, scenario=scenario, context=context).explain(target)
