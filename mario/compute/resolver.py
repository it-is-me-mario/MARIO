"""Execution engine for resolving blocks from the compute catalog."""

from __future__ import annotations

import inspect
import logging

from mario.compute import iot_formulas, sut_formulas, views
from mario.compute.graph import build_dependency_graph, render_dependency_graph
from mario.compute.operators import execute_registered_operator
from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.planner import (
    ResolutionStore,
    build_plan,
    candidate_strategies,
    classify_iot_formula_strategy,
    resolve_table_kind,
)
from mario.compute.runtime import effective_compute_options
from mario.compute.types import (
    ConcatStrategy,
    ExtractStrategy,
    FormulaStrategy,
    MaterializationMode,
    OperatorStrategy,
    ParsedStrategy,
    ResolutionContext,
)
from mario.log_exc.logger import log_time
from mario.log_exc.exceptions import NotImplementable
from mario.model.enums import TableKind

logger = logging.getLogger(__name__)


class ResolutionError(LookupError):
    """Raised when a block cannot be resolved from the current dataset state."""


def _lookup_callable(name: str):
    """Look up a compute implementation by name across compute modules."""
    for module in (views, iot_formulas, sut_formulas):
        function = getattr(module, name, None)
        if callable(function):
            return function
    return None


def _collect_blocks(store: ResolutionStore):
    """Read all materialized blocks visible through the store."""
    blocks = {}
    for name in store.names():
        try:
            blocks[name] = store.get(name)
        except KeyError:
            continue
    return blocks


def _normalize_materialization_mode(context: ResolutionContext | None) -> str:
    """Return the effective persistence mode for one resolution request."""
    compute = getattr(context, "compute", None)
    value = getattr(compute, "materialization", MaterializationMode.REQUESTED_ONLY)
    if isinstance(value, MaterializationMode):
        return value.value
    if value is None:
        return MaterializationMode.REQUESTED_ONLY.value
    return str(value).strip().lower()


def _build_ordering(
    store: ResolutionStore,
    extra_blocks: dict[str, object] | None = None,
    *,
    visible_blocks: dict[str, object] | None = None,
):
    """Build the unified SUT ordering policy from visible blocks and overrides."""
    blocks = _collect_blocks(store)
    if visible_blocks:
        blocks.update(visible_blocks)
    if extra_blocks:
        blocks.update(extra_blocks)

    kwargs = {name: block for name, block in blocks.items() if name in inspect.signature(SUTUnifiedOrderingPolicy.from_blocks).parameters}
    return SUTUnifiedOrderingPolicy.from_blocks(**kwargs)


def _execute_strategy(
    strategy,
    target: str,
    store: ResolutionStore,
    table_kind: TableKind,
    dependencies: dict[str, object],
    *,
    resolver=None,
):
    """Execute one selected strategy against the current store state."""
    visible_get = getattr(resolver, "_visible_get", store.get)

    if isinstance(strategy, ParsedStrategy):
        if store.has(target):
            return store.get(target)
        raise ResolutionError(f"Parsed block {target} is not materialized.")

    if isinstance(strategy, ExtractStrategy):
        function = _lookup_callable(strategy.extractor)
        if function is None:
            raise ResolutionError(f"Extractor implementation {strategy.extractor} is missing.")

        source = visible_get(strategy.source)
        if table_kind == TableKind.SUT:
            ordering = _build_ordering(
                store,
                {strategy.source: source},
                visible_blocks=getattr(resolver, "_memo", None),
            )
            return function(source, ordering)
        return function(source)

    if isinstance(strategy, ConcatStrategy):
        function = _lookup_callable(strategy.builder)
        if function is None:
            raise ResolutionError(f"View builder implementation {strategy.builder} is missing.")

        blocks = [visible_get(source) for source in strategy.sources]
        if table_kind == TableKind.SUT:
            ordering = _build_ordering(
                store,
                {name: value for name, value in zip(strategy.sources, blocks)},
                visible_blocks=getattr(resolver, "_memo", None),
            )
            return function(*blocks, ordering)
        return function(*blocks)

    if isinstance(strategy, FormulaStrategy):
        function = _lookup_callable(strategy.function)
        if function is None:
            raise ResolutionError(f"Formula implementation {strategy.function} is missing.")
        args = [dependencies[name] for name in strategy.inputs]
        parameters = inspect.signature(function).parameters
        kwargs = {}
        if "context" in parameters:
            kwargs["context"] = getattr(resolver, "context", None)
        if "resolver" in parameters:
            kwargs["resolver"] = resolver
        return function(*args, **kwargs)

    if isinstance(strategy, OperatorStrategy):
        try:
            return execute_registered_operator(store.dataset, target, dependencies)
        except KeyError as exc:
            raise ResolutionError(f"Custom operator {target} is not registered.") from exc

    raise ResolutionError(f"Unsupported strategy for {target}.")


def _format_root_resolution_log(strategy, target: str, table_kind: TableKind, context) -> str:
    """Return a human-readable info log for one resolved target."""
    if isinstance(strategy, FormulaStrategy):
        message = f"Resolver: resolved {target} via formula {strategy.function}."
        runtime_kind = classify_iot_formula_strategy(strategy)
        if runtime_kind is not None and table_kind in {TableKind.IOT, TableKind.SUT}:
            options = effective_compute_options(context)
            if runtime_kind == "solve":
                message = (
                    f"{message[:-1]} "
                    f"(compute_method={options.compute_method}, runtime={runtime_kind})."
                )
            else:
                message = (
                    f"{message[:-1]} "
                    f"(compute_method={options.compute_method}, runtime={runtime_kind})."
                )
        return message
    return f"Resolver: resolved {target} via {strategy.kind.value}."


def _should_emit_info_resolution_log(*, root_request: bool, strategy) -> bool:
    """Return whether one successful resolution step should be logged at info level."""
    if root_request:
        return True
    return classify_iot_formula_strategy(strategy) is not None


def _format_root_attempt_log(strategy, target: str, table_kind: TableKind, context) -> str:
    """Return a human-readable info log before one root strategy starts."""
    if not isinstance(strategy, FormulaStrategy):
        return f"Resolver: trying {target} via {strategy.kind.value}."

    message = f"Resolver: trying {target} via formula {strategy.function}."
    runtime_kind = classify_iot_formula_strategy(strategy)
    if runtime_kind is not None and table_kind in {TableKind.IOT, TableKind.SUT}:
        options = effective_compute_options(context)
        if runtime_kind == "solve":
            return (
                f"{message[:-1]} "
                f"(compute_method={options.compute_method}, runtime={runtime_kind})."
            )
        return (
            f"{message[:-1]} "
            f"(compute_method={options.compute_method}, runtime={runtime_kind})."
        )
    return message


class Resolver:
    """Resolve matrices from the compute catalog against one scenario state."""

    def __init__(self, dataset, scenario: str = "baseline", context: ResolutionContext | None = None) -> None:
        """Initialize a resolver bound to one dataset-like object."""
        self.dataset = dataset
        self.scenario = scenario
        self.context = context or ResolutionContext()
        self.store = ResolutionStore(dataset, scenario=scenario)
        self.table_kind = resolve_table_kind(dataset, self.context)
        self._memo: dict[str, object] = {}
        self._active: list[str] = []
        self._linear_solver_cache: dict[tuple[object, ...], object] = {}
        self._requested_targets: set[str] = set()
        self._materialization_mode = _normalize_materialization_mode(self.context)

    def _visible_has(self, target: str) -> bool:
        """Return whether one block is visible through persisted or memoized state."""
        return target in self._memo or self.store.has(target)

    def _visible_get(self, target: str):
        """Read one block from memoized state first, then persisted storage."""
        if target in self._memo:
            return self._memo[target]
        return self.store.get(target)

    def _should_persist(self, target: str) -> bool:
        """Return whether one resolved block should remain materialized."""
        if self._materialization_mode == MaterializationMode.ALL.value:
            return True
        if self._materialization_mode == MaterializationMode.NONE.value:
            return False
        return target in self._requested_targets

    def mark_requested_targets(self, targets: list[str] | tuple[str, ...] | set[str]) -> None:
        """Mark a set of user-requested targets as persistent outputs."""
        self._requested_targets.update(targets)
        for target in targets:
            if target in self._memo and not self.store.has(target) and self._should_persist(target):
                self.store.set(target, self._memo[target])

    def resolve_requested(self, target: str):
        """Resolve one user-requested target and persist it according to policy."""
        self.mark_requested_targets([target])
        value = self.resolve(target)
        if not self.store.has(target) and self._should_persist(target):
            self.store.set(target, value)
        return value

    def resolve(self, target: str):
        """Materialize one target block and store it back into the dataset."""
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
        strategies = candidate_strategies(target, self.dataset, self.scenario, self.context)

        try:
            # Strategies are attempted in planner order until one succeeds.
            for strategy in strategies:
                try:
                    if root_request:
                        log_time(
                            logger,
                            _format_root_attempt_log(
                                strategy,
                                target,
                                self.table_kind,
                                self.context,
                            ),
                            "info",
                        )
                    if isinstance(strategy, ParsedStrategy):
                        value = _execute_strategy(strategy, target, self.store, self.table_kind, {}, resolver=self)
                    elif isinstance(strategy, ExtractStrategy):
                        if not self._visible_has(strategy.source):
                            errors.append(f"{strategy.kind.value}: source {strategy.source} is not materialized")
                            continue
                        value = _execute_strategy(strategy, target, self.store, self.table_kind, {}, resolver=self)
                    elif isinstance(strategy, ConcatStrategy):
                        for dependency in strategy.sources:
                            self.resolve(dependency)
                        value = _execute_strategy(strategy, target, self.store, self.table_kind, {}, resolver=self)
                    elif isinstance(strategy, OperatorStrategy):
                        dependencies = {}
                        for dependency in strategy.inputs:
                            dependencies[dependency] = self.resolve(dependency)
                        value = _execute_strategy(
                            strategy,
                            target,
                            self.store,
                            self.table_kind,
                            dependencies,
                            resolver=self,
                        )
                    else:
                        dependencies = {}
                        for dependency in strategy.inputs:
                            dependencies[dependency] = self.resolve(dependency)
                        value = _execute_strategy(
                            strategy,
                            target,
                            self.store,
                            self.table_kind,
                            dependencies,
                            resolver=self,
                        )

                    self._memo[target] = value
                    if self._should_persist(target):
                        self.store.set(target, value)
                    if _should_emit_info_resolution_log(root_request=root_request, strategy=strategy):
                        log_time(
                            logger,
                            _format_root_resolution_log(
                                strategy,
                                target,
                                self.table_kind,
                                self.context,
                            ),
                            "info",
                        )
                    return value
                except (ResolutionError, NotImplementable) as exc:
                    errors.append(f"{strategy.kind.value}: {exc}")
                    continue
        finally:
            self._active.pop()

        explanation = self.explain(target)
        if root_request:
            log_time(logger, f"Resolver: failed to resolve {target}.", "warning")
        raise ResolutionError(f"Unable to resolve {target}.\n" + "\n".join(errors) + "\n" + explanation)

    def resolve_many(self, targets: list[str] | tuple[str, ...]):
        """Resolve several targets and return them as a name-to-block mapping."""
        self.mark_requested_targets(targets)
        return {target: self.resolve(target) for target in targets}

    def explain(self, target: str) -> str:
        """Return a human-readable dependency explanation for one target."""
        graph = build_dependency_graph(target, self.dataset, self.scenario, self.context)
        return render_dependency_graph(graph)

    def build_plan(self, target: str):
        """Return the planned execution steps for one target."""
        return build_plan(target, self.dataset, self.scenario, self.context)


def resolve(target: str, dataset, scenario: str = "baseline", context: ResolutionContext | None = None):
    """Convenience wrapper that resolves one block with a temporary resolver."""
    return Resolver(dataset, scenario=scenario, context=context).resolve_requested(target)


def resolve_many(
    targets: list[str] | tuple[str, ...],
    dataset,
    scenario: str = "baseline",
    context: ResolutionContext | None = None,
):
    """Convenience wrapper that resolves several blocks with one resolver."""
    return Resolver(dataset, scenario=scenario, context=context).resolve_many(targets)


def explain(target: str, dataset, scenario: str = "baseline", context: ResolutionContext | None = None) -> str:
    """Convenience wrapper that explains how one target would be resolved."""
    return Resolver(dataset, scenario=scenario, context=context).explain(target)
