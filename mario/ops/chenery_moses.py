"""Sparse-native Isard to Chenery-Moses transformations on observed nodes."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
from scipy import sparse

from mario.compute.helpers import _is_sparse_backed_dataframe
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.model.conventions import _MASTER_INDEX as MI


FLOW_BLOCKS = ("U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY")


def as_csr(frame):
    if not len(frame.columns):
        return sparse.csr_matrix(frame.shape, dtype=float)
    if _is_sparse_backed_dataframe(frame):
        if any(dtype.fill_value != 0 for dtype in frame.dtypes):
            raise WrongInput(
                "Chenery-Moses transformation requires zero-fill sparse flows."
            )
        result = frame.sparse.to_coo().tocsr()
    else:
        result = sparse.csr_matrix(frame.to_numpy(dtype=float))
    if not np.isfinite(result.data).all():
        raise WrongInput("Chenery-Moses transformation requires finite flow values.")
    result.eliminate_zeros()
    return result


def as_frame(matrix, *, index, columns, like):
    if _is_sparse_backed_dataframe(like):
        return pd.DataFrame.sparse.from_spmatrix(
            matrix, index=index, columns=columns
        ).fillna(0.0)
    return pd.DataFrame(matrix.toarray(), index=index, columns=columns)


def reindex_flow(frame, *, index=None, columns=None):
    """Add or reorder observed axes without a dense intermediate or NaN gaps."""
    index = frame.index if index is None else index
    columns = frame.columns if columns is None else columns
    if frame.index.equals(index) and frame.columns.equals(columns):
        return frame.copy()
    rows = index.get_indexer(frame.index)
    cols = columns.get_indexer(frame.columns)
    if (rows < 0).any() or (cols < 0).any():
        raise WrongInput("Chenery-Moses axis alignment would discard existing nodes.")
    coo = as_csr(frame).tocoo()
    matrix = sparse.coo_matrix(
        (coo.data, (rows[coo.row], cols[coo.col])), shape=(len(index), len(columns))
    )
    return as_frame(matrix, index=index, columns=columns, like=frame)


def align_markets(blocks, markets):
    result = dict(blocks)
    for name in ("U", "Yc"):
        result[name] = reindex_flow(blocks[name], index=markets)
    for name in ("S", "Ec", "Vc"):
        result[name] = reindex_flow(blocks[name], columns=markets)
    return result


def read_flows(database, scenario):
    """Read native blocks; missing direct final-demand accounts are zero."""
    blocks = database.query(matrices=list(FLOW_BLOCKS[:8]), scenarios=scenario)
    for name, extension in (("EY", "Ea"), ("VY", "Va")):
        if database.has_matrix(name, scenario=scenario):
            blocks[name] = database.query(name, scenarios=scenario)
        else:
            rows = blocks[extension].index
            columns = blocks["Yc"].columns
            blocks[name] = as_frame(
                sparse.csr_matrix((len(rows), len(columns))),
                index=rows,
                columns=columns,
                like=blocks[extension],
            )
    return blocks


def convert_flows(blocks, regions, *, scenario):
    """Move origin-labelled use to destination markets and allocate supply.

    P[i,j] is the fraction of origin commodity i used in destination market j.
    U/Yc are collapsed by destination and commodity label; S/Ec/Vc are right
    multiplied by P. Activity rows/columns, Ya, Ea/Va and EY/VY are preserved.
    """
    supply = blocks["S"]
    activities, commodities = supply.index, supply.columns
    fd = blocks["Yc"].columns
    for axis in (activities, commodities, fd):
        if (
            not isinstance(axis, pd.MultiIndex)
            or axis.nlevels != 3
            or not axis.is_unique
        ):
            raise WrongInput(
                "Chenery-Moses transformation requires unique Region/Level/Item axes."
            )
    blocks = dict(blocks)
    blocks["U"] = reindex_flow(blocks["U"], index=commodities, columns=activities)
    blocks["Yc"] = reindex_flow(blocks["Yc"], index=commodities)
    blocks["Ya"] = reindex_flow(blocks["Ya"], index=activities, columns=fd)
    regions = pd.Index(regions)
    a_regions = regions.get_indexer(activities.get_level_values(0))
    c_regions = regions.get_indexer(commodities.get_level_values(0))
    n_regions = regions.get_indexer(fd.get_level_values(0))
    if any((values < 0).any() for values in (a_regions, c_regions, n_regions)):
        raise WrongInput("Chenery-Moses flow axes contain unknown regions.")
    S = as_csr(supply)
    supplied = S.tocoo()
    if np.any(a_regions[supplied.row] != c_regions[supplied.col]):
        raise NotImplementable(
            f"scenario {scenario} is already in Chenery-Moses format"
        )

    U, Yc = as_csr(blocks["U"]).tocoo(), as_csr(blocks["Yc"]).tocoo()
    codes = pd.Index(commodities.get_level_values(2).unique())
    c_codes = codes.get_indexer(commodities.get_level_values(2))
    count = len(codes)
    old_keys = c_regions * count + c_codes
    u_keys = a_regions[U.col] * count + c_codes[U.row]
    y_keys = n_regions[Yc.col] * count + c_codes[Yc.row]
    needed = np.unique(np.concatenate([u_keys, y_keys]))
    added = needed[~np.isin(needed, old_keys)]
    extra = (
        pd.MultiIndex.from_tuples(
            [(regions[key // count], MI["c"], codes[key % count]) for key in added],
            names=commodities.names,
        )
        if len(added)
        else commodities[:0]
    )
    markets = commodities.append(extra)
    market_keys = pd.Index(np.concatenate([old_keys, added]))
    domestic_U = sparse.coo_matrix(
        (U.data, (market_keys.get_indexer(u_keys), U.col)),
        shape=(len(markets), len(activities)),
    ).tocsr()
    domestic_Yc = sparse.coo_matrix(
        (Yc.data, (market_keys.get_indexer(y_keys), Yc.col)),
        shape=(len(markets), len(fd)),
    ).tocsr()

    trade = sparse.coo_matrix(
        (
            np.concatenate([U.data, Yc.data]),
            (
                np.concatenate([U.row, Yc.row]),
                np.concatenate([a_regions[U.col], n_regions[Yc.col]]),
            ),
        ),
        shape=(len(commodities), len(regions)),
    ).tocsr()
    trade.eliminate_zeros()
    totals = np.asarray(trade.sum(axis=1)).ravel()
    if not np.isfinite(totals).all():
        raise WrongInput("Chenery-Moses regional flow totals must be finite.")
    flows = trade.tocoo()
    undefined = (totals == 0) & (np.diff(trade.indptr) != 0)
    if undefined.any():
        nodes = commodities[undefined].tolist()
        raise WrongInput(
            "Chenery-Moses sourcing shares are undefined for zero net use with "
            f"nonzero regional trade flows. Nodes: {nodes[:20]}"
        )
    destinations = market_keys.get_indexer(flows.col * count + c_codes[flows.row])
    inactive = np.flatnonzero(totals == 0)
    # An unused commodity keeps its original supply/accounts, including any
    # source imbalance. No balancing or zero-output data correction is applied.
    allocation = sparse.coo_matrix(
        (
            np.concatenate([flows.data / totals[flows.row], np.ones(len(inactive))]),
            (
                np.concatenate([flows.row, inactive]),
                np.concatenate([destinations, inactive]),
            ),
        ),
        shape=(len(commodities), len(markets)),
    ).tocsr()
    result = dict(blocks)
    result["U"] = as_frame(
        domestic_U, index=markets, columns=activities, like=blocks["U"]
    )
    result["Yc"] = as_frame(domestic_Yc, index=markets, columns=fd, like=blocks["Yc"])
    for name, source in (("S", S), ("Ec", None), ("Vc", None)):
        frame = reindex_flow(blocks[name], columns=commodities)
        source = as_csr(frame) if source is None else source
        result[name] = as_frame(
            source @ allocation, index=frame.index, columns=markets, like=frame
        )
    return result


def transform(database, scenarios):
    """Stage selected transformations and keep all scenario market axes aligned."""
    if database.table_type != "SUT":
        raise NotImplementable("This test is implementable only on SUT tables")
    regions = database.get_index(MI["r"])
    if len(regions) == 1:
        raise NotImplementable("This test is not implementable on single-region tables")
    requested = (
        database.scenarios
        if scenarios is None
        else ([scenarios] if isinstance(scenarios, str) else scenarios)
    )
    selected = list(dict.fromkeys(database._validate_scenario(s) for s in requested))
    if not selected:
        return
    staged = {
        s: convert_flows(
            read_flows(database, s), regions, scenario=database._public_scenario_name(s)
        )
        for s in selected
    }
    # A newly introduced import market is a structural axis shared by all
    # scenarios. Unselected flow values are preserved by zero extension.
    baseline = database._validate_scenario("baseline")
    base_axis = database.query("S", scenarios=baseline).columns
    markets = base_axis
    for blocks in staged.values():
        additions = blocks["S"].columns[~blocks["S"].columns.isin(markets)]
        markets = markets.append(additions)
    if not markets.equals(base_axis):
        for scenario in database._storage_scenarios():
            if scenario not in staged:
                staged[scenario] = read_flows(database, scenario)
        staged = {s: align_markets(blocks, markets) for s, blocks in staged.items()}
    for scenario, blocks in staged.items():
        database.matrices[scenario] = blocks
    if isinstance(database._indeces["c"]["main"], Mapping):
        database._indeces["c"]["main"] = {
            region: markets[markets.get_level_values(0) == region]
            .get_level_values(2)
            .tolist()
            for region in regions
        }
    if len(markets) > len(base_axis):
        database.meta._add_history(
            f"Chenery-Moses: added {len(markets) - len(base_axis)} commodity destination markets; "
            "aligned all scenario axes."
        )
    for scenario in selected:
        database.meta._add_history(
            f"Transformation of the database from into Chenery-Moses for scenario {database._public_scenario_name(scenario)}"
        )
