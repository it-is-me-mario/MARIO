"""Dataset-local custom operators and small operator builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from mario.compute.helpers import (
    as_column_frame,
    as_dense_series,
    dense_values,
    matmul,
    sum_columns,
    sum_rows,
)
from mario.compute.semantics import BlockSpec


class OperatorKind(str, Enum):
    """Internal operator families supported by the prototype registry."""

    RATIO = "ratio"
    MATRIX_PRODUCT = "matrix_product"
    SUM = "sum"
    ZEROS_LIKE = "zeros_like"


@dataclass(frozen=True)
class OperatorSpec:
    """Describe one custom operator that can be resolved by MARIO."""

    name: str
    inputs: tuple[str, ...]
    kind: OperatorKind
    parameters: dict[str, Any] = field(default_factory=dict)
    output_spec: BlockSpec | None = None
    notes: tuple[str, ...] = ()


class OperatorRegistry:
    """Small in-memory registry of custom operators for one dataset."""

    def __init__(self) -> None:
        self._operators: dict[str, OperatorSpec] = {}

    def register(self, spec: OperatorSpec, *, replace: bool = False) -> OperatorSpec:
        """Register one custom operator."""
        if spec.name in self._operators and not replace:
            raise ValueError(f"Custom operator {spec.name!r} is already registered.")
        self._operators[spec.name] = spec
        return spec

    def get(self, name: str) -> OperatorSpec:
        """Return one registered operator."""
        return self._operators[name]

    def names(self) -> tuple[str, ...]:
        """List all registered operator outputs."""
        return tuple(sorted(self._operators))

    def has(self, name: str) -> bool:
        """Return whether one custom operator exists."""
        return name in self._operators


def _get_operator_registry(dataset) -> OperatorRegistry:
    """Return or create the dataset-local operator registry."""
    registry = getattr(dataset, "_custom_operator_registry", None)
    if registry is None:
        registry = OperatorRegistry()
        setattr(dataset, "_custom_operator_registry", registry)
    return registry


def _get_block_spec_registry(dataset) -> dict[str, BlockSpec]:
    """Return or create the dataset-local custom block-spec registry."""
    registry = getattr(dataset, "_custom_block_specs", None)
    if registry is None:
        registry = {}
        setattr(dataset, "_custom_block_specs", registry)
    return registry


def register_operator(dataset, spec: OperatorSpec, *, replace: bool = False) -> OperatorSpec:
    """Register one operator on a dataset-like object."""
    registered = _get_operator_registry(dataset).register(spec, replace=replace)
    if spec.output_spec is not None:
        register_block_spec(dataset, spec.output_spec, replace=replace)
    return registered


def get_registered_operator(dataset, name: str) -> OperatorSpec | None:
    """Return one custom operator if it exists on the dataset."""
    registry = getattr(dataset, "_custom_operator_registry", None)
    if registry is None or not registry.has(name):
        return None
    return registry.get(name)


def list_registered_operator_names(dataset) -> tuple[str, ...]:
    """List the custom operators registered on a dataset."""
    registry = getattr(dataset, "_custom_operator_registry", None)
    if registry is None:
        return ()
    return registry.names()


def register_block_spec(dataset, spec: BlockSpec, *, replace: bool = False) -> BlockSpec:
    """Register one custom block specification on a dataset-like object."""
    registry = _get_block_spec_registry(dataset)
    if spec.name in registry and not replace:
        raise ValueError(f"Custom block spec {spec.name!r} is already registered.")
    registry[spec.name] = spec
    return spec


def get_registered_block_spec(dataset, name: str) -> BlockSpec | None:
    """Return one custom block specification if present."""
    registry = getattr(dataset, "_custom_block_specs", None)
    if registry is None:
        return None
    return registry.get(name)


def list_registered_block_specs(dataset) -> tuple[str, ...]:
    """List the custom block names known to a dataset."""
    registry = getattr(dataset, "_custom_block_specs", None)
    if registry is None:
        return ()
    return tuple(sorted(registry))


def ratio_operator(
    *,
    name: str,
    numerator: str,
    denominator: str,
    align: str = "columns",
    output_spec: BlockSpec | None = None,
    notes: tuple[str, ...] = (),
) -> OperatorSpec:
    """Build a ratio operator aligned along rows or columns."""
    normalized_align = align.lower()
    if normalized_align not in {"columns", "rows"}:
        raise ValueError("align must be either 'columns' or 'rows'.")
    return OperatorSpec(
        name=name,
        inputs=(numerator, denominator),
        kind=OperatorKind.RATIO,
        parameters={"align": normalized_align},
        output_spec=output_spec,
        notes=notes,
    )


def matrix_product_operator(
    *,
    name: str,
    left: str,
    right: str,
    output_spec: BlockSpec | None = None,
    notes: tuple[str, ...] = (),
) -> OperatorSpec:
    """Build an operator that computes a matrix product."""
    return OperatorSpec(
        name=name,
        inputs=(left, right),
        kind=OperatorKind.MATRIX_PRODUCT,
        output_spec=output_spec,
        notes=notes,
    )


def sum_operator(
    *,
    name: str,
    source: str,
    over: str = "columns",
    label: str = "Total",
    output_spec: BlockSpec | None = None,
    notes: tuple[str, ...] = (),
) -> OperatorSpec:
    """Build an operator that sums a block over one axis."""
    normalized_over = over.lower()
    if normalized_over not in {"columns", "rows"}:
        raise ValueError("over must be either 'columns' or 'rows'.")
    return OperatorSpec(
        name=name,
        inputs=(source,),
        kind=OperatorKind.SUM,
        parameters={"over": normalized_over, "label": label},
        output_spec=output_spec,
        notes=notes,
    )


def zeros_like_operator(
    *,
    name: str,
    rows_from: str,
    cols_from: str,
    output_spec: BlockSpec | None = None,
    notes: tuple[str, ...] = (),
) -> OperatorSpec:
    """Build an operator that creates a zero-filled block from two references."""
    return OperatorSpec(
        name=name,
        inputs=(rows_from, cols_from),
        kind=OperatorKind.ZEROS_LIKE,
        parameters={"rows_from": rows_from, "cols_from": cols_from},
        output_spec=output_spec,
        notes=notes,
    )


def execute_registered_operator(dataset, target: str, dependencies: dict[str, object]):
    """Execute one registered operator using resolved dependency values."""
    spec = get_registered_operator(dataset, target)
    if spec is None:
        raise KeyError(target)

    if spec.kind == OperatorKind.RATIO:
        numerator = dependencies[spec.inputs[0]]
        denominator = dependencies[spec.inputs[1]]
        vector = as_dense_series(denominator)
        axis = "columns" if spec.parameters["align"] == "columns" else "index"
        return numerator.divide(vector, axis=axis)

    if spec.kind == OperatorKind.MATRIX_PRODUCT:
        left = dependencies[spec.inputs[0]]
        right = dependencies[spec.inputs[1]]
        return matmul(left, right)

    if spec.kind == OperatorKind.SUM:
        source = dependencies[spec.inputs[0]]
        label = spec.parameters["label"]
        if spec.parameters["over"] == "columns":
            return as_column_frame(sum_rows(source), label)
        summed = sum_columns(source)
        return pd.DataFrame([dense_values(summed)], index=[label], columns=summed.index)

    if spec.kind == OperatorKind.ZEROS_LIKE:
        row_source = dependencies[spec.parameters["rows_from"]]
        col_source = dependencies[spec.parameters["cols_from"]]

        if isinstance(row_source, pd.DataFrame):
            index = row_source.index
        else:
            index = getattr(row_source, "index", pd.Index([]))

        if isinstance(col_source, pd.DataFrame):
            columns = col_source.columns
        elif isinstance(col_source, pd.Series):
            columns = col_source.index
        else:
            columns = getattr(col_source, "index", pd.Index([]))

        return pd.DataFrame(np.zeros((len(index), len(columns)), dtype=float), index=index, columns=columns)

    raise NotImplementedError(f"Unsupported custom operator kind: {spec.kind.value}")
