"""Trade-content projections without explicit inverses or exploded multipliers."""

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, lgmres, lsmr, splu

from mario.compute.helpers import sparse_frame_from_spmatrix
from mario.compute.runtime import choose_linear_strategy
from mario.log_exc.exceptions import WrongInput
from mario.ops.trades import trade_axes, trade_breakdown_index


def sparse_flow(frame):
    """Whether a native flow block can be reduced without dense conversion."""
    return isinstance(frame, pd.DataFrame) and all(
        isinstance(dtype, pd.SparseDtype) for dtype in frame.dtypes
    )


def _csr(frame):
    if not len(frame.columns):
        return sparse.csr_matrix(frame.shape, dtype=float)
    if sparse_flow(frame):
        return frame.fillna(0.0).sparse.to_coo().tocsr()
    return sparse.csr_matrix(frame.to_numpy(dtype=float))


class TradeContentProjection:
    """Apply the existing IOT/SUT content formulas to regional trade vectors.

    SUT totals keep fa_ex/fc_ex ordering; upstream keeps the legacy outer join.
    Only one production vector is solved at a time. Iterative solves apply the
    split coefficient product as an operator, without materializing that product.
    """

    def __init__(
        self,
        direct,
        primary,
        *,
        secondary=None,
        activity_side=False,
        transfer=None,
    ):
        self.primary_index = primary.index
        self.primary = _csr(primary)
        self.secondary = None if secondary is None else _csr(secondary)
        self.activity_side = activity_side
        self.direct = tuple(row.fillna(0.0).to_numpy(dtype=float) for row in direct)
        self.contributors = (
            direct[0].index
            if secondary is None
            else direct[0].index.append(direct[1].index)
        )
        if transfer is not None:
            transfer = transfer.reindex(
                index=self.primary_index, columns=self.primary_index
            )
        self.transfer = (
            None
            if transfer is None
            else (
                _csr(transfer)
                if sparse_flow(transfer)
                else transfer.to_numpy(dtype=float)
            )
        )
        self._factor = None
        self.strategy = choose_linear_strategy(
            size=len(self.primary_index), rhs_count=1
        )
        n = len(self.primary_index)
        left, right = self.primary, self.secondary
        if right is None:
            matvec = lambda x: x - left @ x
            rmatvec = lambda x: x - left.T @ x
            diagonal = 1.0 - left.diagonal()
        else:
            matvec = lambda x: x - left @ (right @ x)
            rmatvec = lambda x: x - right.T @ (left.T @ x)
            diagonal = 1.0 - np.asarray(left.multiply(right.T).sum(axis=1)).ravel()
        self.system = LinearOperator(
            (n, n), matvec=matvec, rmatvec=rmatvec, dtype=float
        )
        diagonal[np.abs(diagonal) < 1e-12] = 1.0
        self.preconditioner = LinearOperator(
            (n, n), matvec=lambda x: x / diagonal, dtype=float
        )

    def _solve(self, rhs):
        if self.transfer is not None:
            return np.asarray(self.transfer @ rhs).ravel()
        if self.strategy == "direct":
            if self._factor is None:
                product = (
                    self.primary
                    if self.secondary is None
                    else self.primary @ self.secondary
                )
                try:
                    self._factor = splu(
                        sparse.eye(len(rhs), format="csc") - product.tocsc()
                    )
                except RuntimeError:
                    # A singular system can still admit a consistent least-squares solution.
                    self.strategy = "iterative"
            if self._factor is not None:
                solved = self._factor.solve(rhs)
                if self._accurate(solved, rhs):
                    return solved
        else:
            solved, info = lgmres(
                self.system,
                rhs,
                M=self.preconditioner,
                rtol=1e-9,
                atol=0.0,
                maxiter=500,
            )
            if info == 0 and self._accurate(solved, rhs):
                return solved
        solved, status, *_ = lsmr(
            self.system, rhs, atol=1e-10, btol=1e-10, maxiter=4000
        )
        if status not in {0, 1, 2} or not self._accurate(solved, rhs):
            raise WrongInput(
                "Trade-content linear solve did not converge to the requested accuracy."
            )
        return solved

    def _accurate(self, solved, rhs):
        return np.isfinite(solved).all() and np.linalg.norm(
            self.system @ solved - rhs
        ) <= 1e-7 * np.linalg.norm(rhs)

    def _contribution(self, rhs, *, upstream):
        if not any(np.any(row) for row in self.direct):
            return np.zeros(len(self.contributors), dtype=float)
        production = self._solve(rhs)
        if self.secondary is None:
            return self.direct[0] * (production - rhs if upstream else production)
        other = self.secondary @ production
        activity, commodity = (
            (production, other) if self.activity_side else (other, production)
        )
        if upstream:
            if self.activity_side:
                activity = activity - rhs
            else:
                commodity = commodity - rhs
        return np.concatenate((self.direct[0] * activity, self.direct[1] * commodity))

    def aggregate(
        self,
        matrix,
        item=None,
        *,
        method,
        breakdown,
        supply=False,
        regions=None,
        region_aggregation=None,
        clusters_direction="both",
    ):
        origins, destinations, origin_codes, destination_codes = trade_axes(
            matrix,
            regions=regions,
            region_aggregation=region_aggregation,
            clusters_direction=clusters_direction,
        )
        item_axis = matrix.columns if supply else matrix.index
        if not isinstance(item_axis, pd.MultiIndex) or item_axis.nlevels < 3:
            raise WrongInput("Trade calculation requires a 3-level item MultiIndex.")
        selected = np.ones(len(item_axis), dtype=bool)
        if item is not None:
            items = item if isinstance(item, list) else [item]
            missing = set(items).difference(item_axis.get_level_values(-1))
            if missing:
                raise WrongInput(
                    f"Items {sorted(missing)!r} do not exist in the matrix item index."
                )
            selected = item_axis.get_level_values(-1).isin(items)
        positions = self.primary_index.get_indexer(matrix.index)
        if (positions < 0).any():
            raise WrongInput(
                "Trade-content production nodes could not be aligned to flow rows."
            )
        entries = _csr(matrix).tocoo()
        keep = selected[entries.col if supply else entries.row] & np.isfinite(
            entries.data
        )
        pairs = (
            origin_codes[entries.row[keep]] * len(destinations)
            + destination_codes[entries.col[keep]]
        )
        rhs = sparse.coo_matrix(
            (entries.data[keep], (positions[entries.row[keep]], pairs)),
            shape=(len(self.primary_index), len(origins) * len(destinations)),
        ).tocsc()
        rhs.eliminate_zeros()
        totals = np.zeros((len(origins), len(destinations)), dtype=float)
        contributors = self.contributors
        if method == "upstream" and self.secondary is not None:
            contributors = contributors.join(self.primary_index, how="outer")
        order = self.contributors.get_indexer(contributors)
        output_rows, output_columns, output_values = [], [], []
        previous_profile, previous_contribution = None, None
        for pair in np.flatnonzero(np.diff(rhs.indptr)):
            start, stop = rhs.indptr[pair : pair + 2]
            rows, values = rhs.indices[start:stop], rhs.data[start:stop]
            scale = values[np.argmax(np.abs(values))]
            normalized = values / scale
            profile = (rows.tobytes(), normalized.tobytes())
            if profile != previous_profile:
                vector = np.zeros(len(self.primary_index), dtype=float)
                vector[rows] = normalized
                previous_contribution = self._contribution(
                    vector, upstream=method == "upstream"
                )
                previous_profile = profile
            # Reuse only exact proportional profiles; retain one vector in memory.
            contribution = previous_contribution * scale
            contribution = contribution[order]
            origin, destination = divmod(pair, len(destinations))
            if breakdown:
                nonzero = np.flatnonzero(contribution)
                output_rows.append(origin * len(self.contributors) + nonzero)
                output_columns.append(np.full(len(nonzero), destination))
                output_values.append(contribution[nonzero])
            else:
                totals[origin, destination] = contribution.sum()
        if not breakdown:
            return pd.DataFrame(totals, index=origins, columns=destinations)
        rows = np.concatenate(output_rows) if output_rows else np.array([], dtype=int)
        columns = (
            np.concatenate(output_columns)
            if output_columns
            else np.array([], dtype=int)
        )
        values = (
            np.concatenate(output_values)
            if output_values
            else np.array([], dtype=float)
        )
        result = sparse.coo_matrix(
            (values, (rows, columns)),
            shape=(len(origins) * len(self.contributors), len(destinations)),
        ).tocsc()
        index = trade_breakdown_index(origins, contributors)
        if sparse_flow(matrix):
            return sparse_frame_from_spmatrix(result, index=index, columns=destinations)
        return pd.DataFrame(result.toarray(), index=index, columns=destinations)
