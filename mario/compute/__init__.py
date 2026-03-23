"""Compute internals for the parallel MARIO 2 core."""

from mario.compute.catalog import (
    CATALOG_OPEN_QUESTIONS,
    COMPUTE_CATALOG,
    available_matrix_names,
    get_matrix_spec,
)
from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.resolver import ResolutionError, explain, resolve, resolve_many

__all__ = [
    "CATALOG_OPEN_QUESTIONS",
    "COMPUTE_CATALOG",
    "ResolutionError",
    "SUTUnifiedOrderingPolicy",
    "available_matrix_names",
    "explain",
    "get_matrix_spec",
    "resolve",
    "resolve_many",
]
