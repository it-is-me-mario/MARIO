"""SUT-to-IOT transformations on native flows and observed regional axes."""

from copy import deepcopy

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import splu

from mario.compute.helpers import (
    _is_sparse_backed_dataframe,
    sparse_frame_from_spmatrix,
)
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from mario.ops.chenery_moses import read_flows


METHODS = ("A", "B", "C", "D")


def _csr(frame):
    if not len(frame.columns):
        return sparse.csr_matrix(frame.shape, dtype=float)
    if _is_sparse_backed_dataframe(frame):
        if any(t.fill_value != 0 for t in frame.dtypes):
            # pandas can retain fill=NaN on fully stored columns (for example
            # a one-row account). That is storage metadata, not missing data.
            # Read stored coordinates directly; never replace actual gaps.
            values, positions, pointers = [], [], [0]
            for _, column in frame.items():
                array = column.array
                if array.fill_value != 0 and len(array.sp_values) != len(column):
                    raise WrongInput(
                        "SUT-to-IOT requires finite flows and zero-fill sparse gaps."
                    )
                values.extend(array.sp_values)
                positions.extend(array.sp_index.indices)
                pointers.append(len(values))
            result = sparse.csc_matrix(
                (values, positions, pointers), shape=frame.shape, dtype=float
            ).tocsr()
        else:
            result = frame.sparse.to_coo().tocsr()
    else:
        result = sparse.csr_matrix(frame.to_numpy(dtype=float))
    if not np.isfinite(result.data).all():
        raise WrongInput("SUT-to-IOT requires finite flow values.")
    result.eliminate_zeros()
    return result


def _align(frame, *, index, columns):
    """Reorder existing labels; never fill a missing economic node with zero."""
    if not frame.index.is_unique or not frame.columns.is_unique:
        raise WrongInput("SUT-to-IOT requires unique native block axes.")
    rows, cols = frame.index.get_indexer(index), frame.columns.get_indexer(columns)
    if (
        not index.is_unique
        or not columns.is_unique
        or len(index) != len(frame.index)
        or len(columns) != len(frame.columns)
        or (rows < 0).any()
        or (cols < 0).any()
    ):
        raise WrongInput("SUT-to-IOT found inconsistent native block axes.")
    return _csr(frame)[rows, :][:, cols]


def _reciprocal(output, axis, *, method, used):
    """Zero is defined only for an entirely inactive node, never a flow sink."""
    if not np.isfinite(output).all():
        raise WrongInput("SUT-to-IOT requires finite output totals.")
    bad = (output == 0) & used
    if bad.any():
        raise WrongInput(
            f"SUT-to-IOT method {method}: zero output with nonzero flows or accounts; "
            f"allocation is undefined. Nodes: {axis[bad].tolist()}"
        )
    return np.divide(1.0, output, out=np.zeros_like(output), where=output != 0)


def _active(matrix, axis):
    return np.diff((matrix.tocsr() if axis == 0 else matrix.tocsc()).indptr) != 0


def _solve_columns(factor, rhs, *, transpose=False):
    """Solve a bounded batch of RHS columns, storing only the requested result.

    A/C can intrinsically produce dense IOTs. Avoid a separate dense inverse
    and bound the dense workspace to at most 64 RHS vectors (about 8 MiB).
    """
    if not rhs.shape[1]:
        return sparse.csr_matrix(rhs.shape)
    width = max(1, min(64, 1024 * 1024 // max(1, rhs.shape[0])))
    pieces = []
    for start in range(0, rhs.shape[1], width):
        values = factor.solve(
            rhs[:, start : start + width].toarray(), trans="T" if transpose else "N"
        )
        if not np.isfinite(values).all():
            raise WrongInput("SUT-to-IOT supply solve produced non-finite values.")
        pieces.append(sparse.csr_matrix(values))
    return sparse.hstack(pieces, format="csr")


def convert(database, method):
    """Return staged IOT matrices, catalogs and units, without changing the SUT.

    B/D eliminate one side of the split flow system. Nonzero Ya and commodity
    accounts are allocated to productive and final uses, preserving their sums.
    A/C retain their classical supply-inverse definitions, requiring square,
    nonsingular supply and zero activity final demand.
    """
    if method not in METHODS:
        raise WrongInput(
            f"'{method}' is not an acceptable input for 'method'. "
            f"Acceptable values are {list(METHODS)}"
        )
    supply = database.query("S")
    if method in ("A", "C") and supply.shape[0] != supply.shape[1]:
        raise NotImplementable(
            f"Method {method} requires square supply: commodities number must match "
            f"activities number ({supply.shape[1]} commodities, {supply.shape[0]} activities)."
        )
    activities, commodities = supply.index, supply.columns
    for axis in (activities, commodities):
        if (
            not isinstance(axis, pd.MultiIndex)
            or axis.nlevels != 3
            or not axis.is_unique
        ):
            raise WrongInput("SUT-to-IOT requires unique Region/Level/Item axes.")
    blocks = read_flows(database, "baseline")
    fd = blocks["Yc"].columns
    S = _csr(supply)
    U = _align(blocks["U"], index=commodities, columns=activities)
    Ya = _align(blocks["Ya"], index=activities, columns=fd)
    Yc = _align(blocks["Yc"], index=commodities, columns=fd)
    accounts = {}
    for prefix in ("E", "V"):
        rows = blocks[prefix + "a"].index
        for suffix, columns in (("a", activities), ("c", commodities), ("Y", fd)):
            name = prefix + suffix
            accounts[name] = _align(blocks[name], index=rows, columns=columns)
    if method in ("A", "C") and Ya.nnz:
        raise NotImplementable(
            f"Method {method} requires zero activity final demand (Ya). "
            "Use B or D to preserve nonzero Ya."
        )

    g = np.asarray(S.sum(axis=1) + Ya.sum(axis=1)).ravel()
    q = np.asarray(U.sum(axis=1) + Yc.sum(axis=1)).ravel()
    if not np.isfinite(g).all() or not np.isfinite(q).all():
        raise WrongInput("SUT-to-IOT requires finite output totals.")
    product = method in ("A", "B")
    axis = commodities if product else activities
    level = "c" if product else "a"
    sectors = pd.MultiIndex.from_arrays(
        [axis.get_level_values(0), [MI["s"]] * len(axis), axis.get_level_values(2)],
        names=[MI["r"], "Level", "Item"],
    )
    direct = {prefix: accounts[prefix + "Y"].copy() for prefix in ("E", "V")}

    if method == "B":
        used = _active(S, 0) | _active(Ya, 0) | _active(U, 1)
        for prefix in ("E", "V"):
            used |= _active(accounts[prefix + "a"], 1)
        inv_g = _reciprocal(g, activities, method=method, used=used)
        normalized_use = U.multiply(inv_g).tocsr()
        Z = normalized_use @ S
        Y = Yc + normalized_use @ Ya
        result_accounts = {}
        for prefix in ("E", "V"):
            normalized = accounts[prefix + "a"].multiply(inv_g).tocsr()
            result_accounts[prefix] = normalized @ S + accounts[prefix + "c"]
            direct[prefix] += normalized @ Ya
    elif method == "D":
        used = _active(S, 1) | _active(U, 0) | _active(Yc, 0)
        for prefix in ("E", "V"):
            used |= _active(accounts[prefix + "c"], 1)
        inv_q = _reciprocal(q, commodities, method=method, used=used)
        shares = S.multiply(inv_q).tocsr()
        Z = shares @ U
        Y = Ya + shares @ Yc
        result_accounts = {}
        for prefix in ("E", "V"):
            normalized = accounts[prefix + "c"].multiply(inv_q).tocsr()
            result_accounts[prefix] = accounts[prefix + "a"] + normalized @ U
            direct[prefix] += normalized @ Yc
    else:
        try:
            factor = splu(S.tocsc())
        except RuntimeError as exc:
            raise WrongInput(
                f"SUT-to-IOT method {method} requires an invertible supply matrix; "
                "supply is singular. No pseudoinverse or data adjustment was applied."
            ) from exc
        if method == "A":
            Z = _solve_columns(factor, U.T).T.multiply(q).tocsr()
            Y = Yc
            result_accounts = {
                prefix: _solve_columns(factor, accounts[prefix + "a"].T)
                .T.multiply(q)
                .tocsr()
                + accounts[prefix + "c"]
                for prefix in ("E", "V")
            }
        else:
            Z = _solve_columns(factor, U, transpose=True).multiply(g[:, None]).tocsr()
            Y = _solve_columns(factor, Yc, transpose=True).multiply(g[:, None]).tocsr()
            result_accounts = {}
            used = _active(U, 0) | _active(Yc, 0) | _active(S, 1)
            for prefix in ("E", "V"):
                used |= _active(accounts[prefix + "c"], 1)
            inv_q = _reciprocal(q, commodities, method=method, used=used)
            for prefix in ("E", "V"):
                normalized = accounts[prefix + "c"].multiply(inv_q).tocsr()
                result_accounts[prefix] = accounts[prefix + "a"] + normalized @ U
                direct[prefix] += normalized @ Yc

    sparse_output = any(
        len(frame.columns) and _is_sparse_backed_dataframe(frame)
        for frame in blocks.values()
    )

    def frame(matrix, index, columns):
        matrix = matrix.tocsr()
        matrix.eliminate_zeros()
        if not np.isfinite(matrix.data).all():
            raise WrongInput("SUT-to-IOT produced non-finite flow values.")
        if sparse_output:
            return sparse_frame_from_spmatrix(matrix, index=index, columns=columns)
        return pd.DataFrame(matrix.toarray(), index=index, columns=columns)

    flows = {"Z": frame(Z, sectors, sectors), "Y": frame(Y, sectors, fd)}
    for prefix in ("E", "V"):
        rows = blocks[prefix + "a"].index.copy()
        flows[prefix] = frame(result_accounts[prefix], rows, sectors)
        flows[prefix + "Y"] = frame(direct[prefix], rows, fd)
    flows["X"] = pd.DataFrame(
        np.asarray(Z.sum(axis=1) + Y.sum(axis=1)).ravel(),
        index=sectors,
        columns=["production"],
    )
    indices = deepcopy(dict(database._indeces))
    indices["s"] = indices[level]
    units = {name: value.copy(deep=True) for name, value in database.units.items()}
    units[MI["s"]] = units[MI[level]]
    for code in ("a", "c"):
        del indices[code]
        del units[MI[code]]
    return {"baseline": flows}, indices, units
