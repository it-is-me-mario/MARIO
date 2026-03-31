"""Compute internals for the parallel MARIO 2 core."""

from mario.compute.catalog import (
    CATALOG_OPEN_QUESTIONS,
    COMPUTE_CATALOG,
    available_matrix_names,
    get_matrix_spec,
)
from mario.compute.operators import (
    OperatorSpec,
    matrix_product_operator,
    ratio_operator,
    sum_operator,
    zeros_like_operator,
)
from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.resolver import ResolutionError, explain, resolve, resolve_many
from mario.compute.semantics import AxisRef, BlockSpec, axis_ref, block_spec

__all__ = [
    "AxisRef",
    "BlockSpec",
    "CATALOG_OPEN_QUESTIONS",
    "COMPUTE_CATALOG",
    "OperatorSpec",
    "ResolutionError",
    "SUTUnifiedOrderingPolicy",
    "available_matrix_names",
    "axis_ref",
    "block_spec",
    "explain",
    "get_matrix_spec",
    "matrix_product_operator",
    "ratio_operator",
    "resolve",
    "resolve_many",
    "sum_operator",
    "zeros_like_operator",
]
