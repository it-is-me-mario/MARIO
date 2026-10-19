"""Sparse linkage reductions over actual production nodes."""

import logging
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import LinearOperator, lgmres, lsmr, splu

from mario.compute.runtime import choose_linear_strategy
from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time

logger = logging.getLogger(__name__)


def as_sparse(frame):
    """Read sparse structural gaps as zeros, without a dense transaction view."""
    if not len(frame.columns):
        return sparse.csr_matrix(frame.shape, dtype=float)
    if all(isinstance(t, pd.SparseDtype) for t in frame.dtypes):
        return frame.fillna(0.0).sparse.to_coo().tocsr()
    return sparse.csr_matrix(frame.to_numpy(dtype=float))


def selected_inverse_diagonal(factor, lhs=None):
    """Exact selected inversion of LU when row/column permutations coincide.

    Compute inverse entries on the transposed LU pattern by reverse elimination,
    retaining only that sparse pattern. No full dense inverse is allocated.
    See Jacquelin, Lin and Yang (2017), arXiv:1708.04539, section 2.
    """
    if not np.array_equal(factor.perm_r, factor.perm_c):
        return None
    lower, upper = factor.L.tocsc(), factor.U.tocsr()
    lower.sort_indices()
    upper.sort_indices()
    lower_pattern, upper_pattern = lower.copy(), upper.copy()
    lower_pattern.data[:] = 1.0
    upper_pattern.data[:] = 1.0
    selected = (lower_pattern + upper_pattern).T.tocsr()
    del lower_pattern, upper_pattern
    selected.sort_indices()
    selected.data[:] = 0.0
    for i in range(lower.shape[0] - 1, -1, -1):
        start, stop = lower.indptr[i : i + 2]
        lrows, lvalues = lower.indices[start:stop], lower.data[start:stop]
        start, stop = upper.indptr[i : i + 2]
        ucols, uvalues = upper.indices[start:stop], upper.data[start:stop]
        inverse_pivot = 1.0 / uvalues[ucols == i][0]
        lvalues = lvalues[lrows > i]
        lrows = lrows[lrows > i]
        uvalues = uvalues[ucols > i] * inverse_pivot
        ucols = ucols[ucols > i]
        trailing = selected[ucols, :][:, lrows]
        column = -(trailing @ lvalues)
        row = -np.asarray(uvalues @ trailing).ravel()
        for target, value in zip(ucols, column):
            start, stop = selected.indptr[target : target + 2]
            offset = start + np.searchsorted(selected.indices[start:stop], i)
            if offset == stop or selected.indices[offset] != i:
                return None
            selected.data[offset] = value
        start, stop = selected.indptr[i : i + 2]
        offsets = start + np.searchsorted(selected.indices[start:stop], lrows)
        if len(offsets) and (
            np.any(offsets >= stop)
            or not np.array_equal(selected.indices[offsets], lrows)
        ):
            return None
        selected.data[offsets] = row
        offset = start + np.searchsorted(selected.indices[start:stop], i)
        selected.data[offset] = inverse_pivot - uvalues @ column
    if lhs is not None:
        order = np.argsort(factor.perm_r)
        permuted = lhs[order, :][:, order]
        residual = np.asarray(permuted.multiply(selected.T).sum(axis=1)).ravel() - 1.0
        if not np.isfinite(residual).all() or np.max(np.abs(residual)) > 1e-7:
            return None
    return selected.diagonal()[factor.perm_r]


class SparseLinkageSystem:
    """Reuse sparse factors or solve one RHS at a time with residual checks."""

    def __init__(self, coefficients):
        self.coefficients = coefficients.tocsr()
        self.coefficients.eliminate_zeros()
        self.lhs = (
            sparse.eye(coefficients.shape[0], format="csc") - coefficients.tocsc()
        )
        self.strategy = choose_linear_strategy(size=coefficients.shape[0], rhs_count=1)
        self.factor = None
        self._components = None
        diagonal = self.lhs.diagonal().copy()
        diagonal[np.abs(diagonal) < 1e-12] = 1.0
        self.preconditioner = LinearOperator(
            self.lhs.shape, matvec=lambda x: x / diagonal, dtype=float
        )

    def components(self):
        if self._components is None:
            _, labels = connected_components(
                self.coefficients, directed=True, connection="strong"
            )
            self._components = labels, np.bincount(labels)
        return self._components

    def singular_components(self):
        """Diagnose singular diagonal blocks of a generic sparse system.

        A strong-component permutation is block triangular, so any singular
        diagonal block makes the complete system singular. Small blocks can be
        checked directly; large blocks remain subject to residual validation.
        """
        labels, sizes = self.components()
        singular = []
        for group in np.flatnonzero(sizes > 1):
            positions = np.flatnonzero(labels == group)
            block = self.lhs[positions, :][:, positions]
            if len(positions) <= 128:
                values = np.linalg.svd(block.toarray(), compute_uv=False)
                tolerance = np.finfo(float).eps * len(positions) * values[0]
                deficient = values[-1] <= tolerance
            else:
                # A constant left/right null vector also proves singularity for
                # large closed components, without a dense rank calculation.
                scale = max(1.0, float(abs(block).sum(axis=1).max()))
                tolerance = np.finfo(float).eps * len(positions) * scale
                deficient = (
                    np.max(np.abs(np.asarray(block.sum(axis=1)).ravel())) <= tolerance
                    or np.max(np.abs(np.asarray(block.sum(axis=0)).ravel()))
                    <= tolerance
                )
            if deficient:
                singular.append(positions)
        singular.extend(
            np.array([position])
            for position in np.flatnonzero(
                (sizes[labels] == 1) & (self.lhs.diagonal() == 0)
            )
        )
        return singular

    def solve(self, rhs, *, transpose=False):
        if not np.any(rhs):
            return np.zeros_like(rhs)
        system = self.lhs.T if transpose else self.lhs
        if self.strategy == "direct":
            if self.factor is None:
                try:
                    self.factor = splu(
                        self.lhs,
                        permc_spec="MMD_AT_PLUS_A",
                        diag_pivot_thresh=0.0,
                        options={"SymmetricMode": True},
                    )
                except RuntimeError:
                    self.strategy = "iterative"
            if self.factor is not None:
                result = self.factor.solve(rhs, trans="T" if transpose else "N")
                if self._accurate(system, result, rhs):
                    return result
        result, info = lgmres(
            system, rhs, M=self.preconditioner, rtol=1e-9, atol=0.0, maxiter=500
        )
        if info == 0 and self._accurate(system, result, rhs):
            return result
        result, status, *_ = lsmr(system, rhs, atol=1e-10, btol=1e-10, maxiter=4000)
        if status not in {0, 1, 2} or not self._accurate(system, result, rhs):
            raise WrongInput(
                "Linkage linear solve did not converge to the requested accuracy."
            )
        return result

    @staticmethod
    def _accurate(system, result, rhs):
        return np.isfinite(result).all() and np.linalg.norm(
            system @ result - rhs
        ) <= 1e-7 * np.linalg.norm(rhs)

    def diagonal(self, positions):
        labels, sizes = self.components()
        isolated = sizes[labels[positions]] == 1
        diagonal = np.empty(len(positions))
        diagonal[isolated] = 1.0 / self.lhs.diagonal()[positions[isolated]]
        remaining = positions[~isolated]
        if (
            len(remaining)
            and self.factor is not None
            and len(remaining) > self.lhs.shape[0] // 4
        ):
            selected = selected_inverse_diagonal(self.factor, self.lhs)
            if selected is not None and np.isfinite(selected).all():
                diagonal[~isolated] = selected[remaining]
                return diagonal
        # Exact streamed solves also handle pivoted factors and a selected node set.
        for offset, position in zip(np.flatnonzero(~isolated), remaining):
            rhs = np.zeros(self.lhs.shape[0])
            rhs[position] = 1.0
            diagonal[offset] = self.solve(rhs)[position]
        return diagonal


def linkage_frame(index, totals, local, *, multi_mode, normalized):
    measures = ["Total Forward", "Total Backward", "Direct Forward", "Direct Backward"]
    if multi_mode:
        values = np.empty((len(index), 8))
        values[:, 0::2] = local
        values[:, 1::2] = totals - local
        result = pd.DataFrame(
            values,
            index=index,
            columns=pd.MultiIndex.from_product([measures, ["Local", "Foreign"]]),
        )
        shares = {}
        for i, measure in enumerate(measures):
            denominator = pd.Series(totals[:, i], index=index).where(totals[:, i] != 0)
            shares[measure, "Local Share"] = result[measure, "Local"] / denominator
            shares[measure, "Foreign Share"] = result[measure, "Foreign"] / denominator
        result = pd.concat([result, pd.DataFrame(shares, index=index)], axis=1)
        if normalized:
            log_time(
                logger,
                "Normalization not available for multi-regional mode.",
                "warning",
            )
        return result
    result = pd.DataFrame(totals, index=index, columns=measures)
    ratios = pd.DataFrame(
        {
            "Forward Amplification": result["Total Forward"]
            / result["Direct Forward"].where(result["Direct Forward"] != 0),
            "Backward Amplification": result["Total Backward"]
            / result["Direct Backward"].where(result["Direct Backward"] != 0),
        },
        index=index,
    )
    if normalized:
        result = result / result.mean(axis=0)
    return pd.concat([result, ratios], axis=1)


def check_linkage_system(coefficients, index, *, name):
    """Reject mathematically singular components without changing the data."""
    system = SparseLinkageSystem(coefficients)
    singular = system.singular_components()
    if singular:
        involved = [
            {"nodes": list(index.take(group[:20])), "count": len(group)}
            for group in singular
        ]
        raise WrongInput(
            f"Total linkages are undefined: the {name} system is singular. "
            f"Singular production components: {involved!r}. "
            "The source matrices have not been modified."
        )
    return system


def sparse_linkages(backward, forward, index, *, normalized, cut_diag, multi_mode):
    n = len(index)
    positions = np.arange(n)
    ones = np.ones(n)
    regions = index.get_level_values(0).to_numpy()
    totals = np.zeros((n, 4))
    local = np.zeros((n, 4))
    for column, coefficients, transpose in [(0, forward, False), (1, backward, True)]:
        system = check_linkage_system(
            coefficients, index, name="Ghosh" if column == 0 else "Leontief"
        )
        totals[:, column] = system.solve(ones, transpose=transpose)
        oriented = coefficients.T.tocsr() if transpose else coefficients
        totals[:, column + 2] = np.asarray(oriented.sum(axis=1)).ravel()
        if multi_mode:
            for region in pd.unique(regions[positions]):
                mask = regions == region
                solved = system.solve(mask.astype(float), transpose=transpose)
                local[mask, column] = solved[mask]
            entries = oriented.tocoo()
            keep = regions[entries.row] == regions[entries.col]
            np.add.at(local[:, column + 2], entries.row[keep], entries.data[keep])
        if cut_diag:
            inverse_diagonal = system.diagonal(positions)
            direct_diagonal = coefficients.diagonal()[positions]
            totals[positions, column] -= inverse_diagonal
            totals[positions, column + 2] -= direct_diagonal
            local[positions, column] -= inverse_diagonal
            local[positions, column + 2] -= direct_diagonal
    return linkage_frame(
        index, totals, local, multi_mode=multi_mode, normalized=normalized
    ).iloc[positions]
