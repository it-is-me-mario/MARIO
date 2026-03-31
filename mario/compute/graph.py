"""Dependency graph explanation helpers for MARIO 2 resolution."""

from __future__ import annotations

from dataclasses import dataclass, field

from mario.compute import ghosh_formulas, iot_formulas, sut_formulas, views
from mario.compute.operators import get_registered_operator
from mario.compute.planner import ResolutionStore, candidate_strategies, resolve_table_kind
from mario.compute.types import ResolutionContext, Strategy, StrategyKind


@dataclass(frozen=True)
class DependencyNode:
    """One node in a dependency explanation tree."""

    name: str
    status: str
    strategy_kind: StrategyKind | None = None
    detail: str | None = None
    children: tuple["DependencyNode", ...] = field(default_factory=tuple)


def _has_implementation(name: str) -> bool:
    """Return ``True`` when a named compute callable exists in the engine."""
    for module in (views, iot_formulas, sut_formulas, ghosh_formulas):
        value = getattr(module, name, None)
        if callable(value):
            return True
    return False


def build_dependency_graph(
    target: str,
    dataset,
    scenario: str = "baseline",
    context: ResolutionContext | None = None,
) -> DependencyNode:
    """Build a dependency tree explaining how ``target`` would be resolved."""
    context = context or ResolutionContext()
    store = ResolutionStore(dataset, scenario=scenario)
    _ = resolve_table_kind(dataset, context)

    def visit(name: str, stack: tuple[str, ...]) -> DependencyNode:
        if store.has(name) or name in context.materialized:
            return DependencyNode(name=name, status="materialized")

        if name in stack:
            return DependencyNode(
                name=name,
                status="cycle",
                detail=" -> ".join(stack + (name,)),
            )

        strategies = candidate_strategies(name, dataset, scenario, context)
        blocked: list[DependencyNode] = []

        for strategy in strategies:
            node = _visit_strategy(name, strategy, dataset, scenario, context, stack, visit)
            if node.status in {"planned", "materialized"}:
                return node
            blocked.append(node)

        return DependencyNode(
            name=name,
            status="unresolved",
            detail="no viable strategy",
            children=tuple(blocked),
        )

    return visit(target, ())


def _visit_strategy(
    name: str,
    strategy: Strategy,
    dataset,
    scenario: str,
    context: ResolutionContext,
    stack: tuple[str, ...],
    visit,
) -> DependencyNode:
    """Evaluate one strategy branch inside the dependency explanation tree."""
    store = ResolutionStore(dataset, scenario=scenario)

    if strategy.kind == StrategyKind.PARSED:
        if store.has(name):
            return DependencyNode(name=name, status="materialized", strategy_kind=strategy.kind)
        return DependencyNode(
            name=name,
            status="blocked",
            strategy_kind=strategy.kind,
            detail="parsed block is not materialized",
        )

    if strategy.kind == StrategyKind.EXTRACT:
        source = strategy.dependencies[0]
        if store.has(source) or source in context.materialized:
            return DependencyNode(
                name=name,
                status="planned",
                strategy_kind=strategy.kind,
                detail=f"extract from {source}",
                children=(DependencyNode(name=source, status="materialized"),),
            )
        return DependencyNode(
            name=name,
            status="blocked",
            strategy_kind=strategy.kind,
            detail=f"extract source {source} is not materialized",
        )

    if strategy.kind == StrategyKind.CONCAT:
        children = tuple(
            visit(dep, stack + (name,)) if dep not in stack else DependencyNode(
                name=dep,
                status="cycle",
                detail=" -> ".join(stack + (name, dep)),
            )
            for dep in strategy.dependencies
        )
        if any(child.status in {"unresolved", "blocked", "cycle"} for child in children):
            return DependencyNode(
                name=name,
                status="blocked",
                strategy_kind=strategy.kind,
                detail=f"concat {name} has unresolved dependencies",
                children=children,
            )
        return DependencyNode(
            name=name,
            status="planned",
            strategy_kind=strategy.kind,
            detail=f"concat from {', '.join(strategy.dependencies)}",
            children=children,
        )

    if strategy.kind == StrategyKind.OPERATOR:
        operator = get_registered_operator(dataset, name)
        children = tuple(
            visit(dep, stack + (name,)) if dep not in stack else DependencyNode(
                name=dep,
                status="cycle",
                detail=" -> ".join(stack + (name, dep)),
            )
            for dep in strategy.dependencies
        )
        if operator is None:
            return DependencyNode(
                name=name,
                status="blocked",
                strategy_kind=strategy.kind,
                detail="custom operator is not registered",
            )
        if any(child.status in {"unresolved", "blocked", "cycle"} for child in children):
            return DependencyNode(
                name=name,
                status="blocked",
                strategy_kind=strategy.kind,
                detail=f"operator {operator.kind.value} has unresolved dependencies",
                children=children,
            )
        return DependencyNode(
            name=name,
            status="planned",
            strategy_kind=strategy.kind,
            detail=f"operator {operator.kind.value}",
            children=children,
        )

    function_name = getattr(strategy, "function", None)
    if function_name is not None and not _has_implementation(function_name):
        return DependencyNode(
            name=name,
            status="blocked",
            strategy_kind=strategy.kind,
            detail=f"formula {function_name} is not implemented",
        )

    children = tuple(
        visit(dep, stack + (name,)) if dep not in stack else DependencyNode(
            name=dep,
            status="cycle",
            detail=" -> ".join(stack + (name, dep)),
        )
        for dep in strategy.dependencies
    )
    if any(child.status in {"unresolved", "blocked", "cycle"} for child in children):
        return DependencyNode(
            name=name,
            status="blocked",
            strategy_kind=strategy.kind,
            detail=f"formula {getattr(strategy, 'function', '<unknown>')} has unresolved dependencies",
            children=children,
        )
    return DependencyNode(
        name=name,
        status="planned",
        strategy_kind=strategy.kind,
        detail=f"formula {getattr(strategy, 'function', '<unknown>')}",
        children=children,
    )


def render_dependency_graph(node: DependencyNode, indent: int = 0) -> str:
    """Render a dependency tree into a readable multi-line text explanation."""
    prefix = "  " * indent
    strategy = f" [{node.strategy_kind.value}]" if node.strategy_kind is not None else ""
    detail = f": {node.detail}" if node.detail else ""
    lines = [f"{prefix}- {node.name} <{node.status}>{strategy}{detail}"]
    for child in node.children:
        lines.append(render_dependency_graph(child, indent + 1))
    return "\n".join(lines)
