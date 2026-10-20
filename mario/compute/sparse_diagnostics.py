"""Structural diagnostics shared by sparse linear-system consumers."""

import numpy as np
from scipy.sparse.csgraph import connected_components


class PartialResultWarning(RuntimeWarning):
    """Some coefficients cannot be certified because the system is singular."""


def component_details(index, components):
    """Describe singular blocks without printing arbitrarily large node lists."""
    return [
        {"nodes": list(index.take(group[:20])), "count": len(group)}
        for group in components
    ]


def raise_singular_system(index, components):
    """Reject a singular system without changing its data or choosing a solution."""
    raise np.linalg.LinAlgError(
        "The linear system is singular at float64 precision. "
        f"Singular production components: {component_details(index, components)!r}. "
        "The source matrices have not been modified. A full inverse does not exist."
    )


def dependent_positions(lhs, seeds):
    """Find variables depending on seeds in the actual system ``lhs @ x = b``.

    A nonzero entry at (i, j) means x_i depends on x_j. Traverse columns to
    rows, including descendants outside the singular strong components.
    """
    graph = lhs.tocsc(copy=True)
    graph.eliminate_zeros()
    affected = np.zeros(lhs.shape[0], dtype=bool)
    pending = list(np.asarray(seeds, dtype=int))
    affected[pending] = True
    while pending:
        column = pending.pop()
        rows = graph.indices[graph.indptr[column]:graph.indptr[column + 1]]
        new = rows[~affected[rows]]
        affected[new] = True
        pending.extend(new)
    return np.flatnonzero(affected)


def singular_components(lhs, *, components=None):
    """Find singular diagonal SCC blocks without a full dense rank calculation.

    A strong-component permutation is block triangular. Small blocks use the
    usual float64 SVD rank tolerance; large closed blocks can be identified by
    a constant left or right null vector. Other large blocks remain subject to
    the native solver and residual checks.
    """
    if components is None:
        _, labels = connected_components(lhs, directed=True, connection="strong")
        sizes = np.bincount(labels)
    else:
        labels, sizes = components
    singular = []
    for group in np.flatnonzero(sizes > 1):
        positions = np.flatnonzero(labels == group)
        block = lhs[positions, :][:, positions]
        if len(positions) <= 128:
            values = np.linalg.svd(block.toarray(), compute_uv=False)
            tolerance = np.finfo(float).eps * len(positions) * values[0]
            deficient = values[-1] <= tolerance
        else:
            scale = max(1.0, float(abs(block).sum(axis=1).max()))
            tolerance = np.finfo(float).eps * len(positions) * scale
            deficient = (
                np.max(np.abs(np.asarray(block.sum(axis=1)).ravel())) <= tolerance
                or np.max(np.abs(np.asarray(block.sum(axis=0)).ravel())) <= tolerance
            )
        if deficient:
            singular.append(positions)
    singular.extend(
        np.array([position])
        for position in np.flatnonzero((sizes[labels] == 1) & (lhs.diagonal() == 0))
    )
    return singular
