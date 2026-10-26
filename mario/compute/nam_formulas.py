"""NAM accounting views; no behavioural closure or IO inverse is implied."""

import numpy as np
import pandas as pd
from functools import partial
from scipy import sparse

from mario.internal.nam import _account_projection, _coo
from mario.model.nam import NAM_BLOCKS


def build_nam_account_total(*blocks, resolver, domain):
    """Sum all outgoing payments, retaining activity in signed zero accounts."""
    accounts = resolver.dataset.nam_schema.accounts(domain)
    totals = np.zeros(len(accounts))
    active = np.zeros(len(accounts), dtype=bool)
    for block in blocks:
        values = _coo(block)
        positions = accounts.get_indexer(_account_projection(block.columns))
        if np.any(positions < 0):
            raise ValueError("NAM total inputs contain accounts outside the requested set.")
        np.add.at(totals, positions, np.asarray(values.sum(axis=0)).ravel())
        active[positions[values.col[values.data != 0]]] = True
    result = pd.DataFrame(totals, index=accounts, columns=["production"])
    result.attrs["nam_nonzero_payments"] = active.tolist()
    return result


def build_nam_coefficient(flow, total, *, resolver, source):
    """Normalize native columns by full account totals without dropping detail."""
    values = total.iloc[:, 0].to_numpy(dtype=float)
    active = np.asarray(total.attrs["nam_nonzero_payments"], dtype=bool)
    undefined = (values == 0) & active
    if undefined.any():
        raise ValueError(f"{source.lower()}: zero account total with nonzero signed payments; "
                         f"normalization is undefined for {total.index[undefined].tolist()[:8]}.")
    inverse = np.zeros_like(values)
    np.divide(1., values, out=inverse, where=values != 0)
    positions = total.index.get_indexer(_account_projection(flow.columns))
    if np.any(positions < 0):
        raise ValueError("NAM coefficient columns have no matching account total.")
    result = _coo(flow).tocsr().multiply(inverse[positions]).tocsr()
    if not np.isfinite(result.data).all():
        raise ValueError(f"{source.lower()}: coefficient normalization produced nonfinite values.")
    return pd.DataFrame.sparse.from_spmatrix(result, index=flow.index, columns=flow.columns)


def get_formula(name):
    """Build registry-backed implementations without one function per block."""
    target = name.removeprefix("build_nam_")
    if target in {"T", "B9_d", "B9_f"}:
        return globals().get(name)
    block = NAM_BLOCKS.get(target, {})
    if target == "X" or "account_set" in block:
        return partial(build_nam_account_total, domain=block["rows"])
    if block.get("role") == "coefficient":
        return partial(build_nam_coefficient, source=block["source"])
    return None


def build_nam_T(*blocks, resolver):
    """Project native descriptors onto national nodes without discarding detail."""
    accounts = resolver.dataset.nam_schema.accounts()
    rows, columns, data = [], [], []
    for block in blocks:
        values = _coo(block)
        row_positions = accounts.get_indexer(_account_projection(block.index))
        col_positions = accounts.get_indexer(_account_projection(block.columns))
        rows.extend(row_positions[values.row])
        columns.extend(col_positions[values.col])
        data.extend(values.data)
    matrix = sparse.coo_matrix((data, (rows, columns)), shape=(len(accounts), len(accounts))).tocsr()
    return pd.DataFrame.sparse.from_spmatrix(matrix, index=accounts, columns=accounts)


def _build_nam_B9(AF, LF, *, resolver, domain):
    """Financial-side net lending; reconciliation to nonfinancial accounts is later work."""
    accounts = resolver.dataset.nam_schema.accounts(domain)
    assets = pd.Series(np.asarray(_coo(AF).sum(axis=0)).ravel(), index=_account_projection(AF.columns))
    liabilities = pd.Series(np.asarray(_coo(LF).sum(axis=1)).ravel(), index=_account_projection(LF.index))
    assets = assets.groupby(level=[0, 1, 2], sort=False).sum().reindex(accounts)
    liabilities = liabilities.groupby(level=[0, 1, 2], sort=False).sum().reindex(accounts)
    return pd.DataFrame([assets - liabilities], index=pd.Index(["B9"], name="Balancing item"), columns=accounts)


def build_nam_B9_d(AF, LF, *, resolver):
    return _build_nam_B9(AF, LF, resolver=resolver, domain="capital_resident")


def build_nam_B9_f(AF, LF, *, resolver):
    return _build_nam_B9(AF, LF, resolver=resolver, domain="capital_nonresident")
