"""Equivalence tests for the vectorised IOT split flow scenario.

``build_split_flow_scenario`` is compared against a label-based reference that keeps the
original (slow) pandas formulation of the same maths.
"""

import copy
import statistics
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mario.compute.primitives import calc_E, calc_V, calc_Z
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _ENUM, _MASTER_INDEX as MI
from mario.ops.add_sector_specs import ADD_SECTOR_SPLIT_OUTPUT_COLUMNS, ADD_SECTOR_SPLIT_OUTPUT_SHEET
from mario.ops.add_sector_split import build_split_flow_scenario

sn = slice(None)
REGIONS = ["R1", "R2", "R3", "R4"]
OLD_SECTORS = ["a", "b", "c", "d"]


def _build_instance(seed, new_to_parent, zero_parent_region=None):
    rng = np.random.default_rng(seed)
    sectors = OLD_SECTORS + list(new_to_parent)
    idx = pd.MultiIndex.from_product([REGIONS, [MI["s"]], sectors], names=[MI["r"], "Level", MI["s"]])
    n = len(idx)

    X = pd.DataFrame({"production": rng.uniform(50, 100, n)}, index=idx)
    if zero_parent_region is not None:
        parent = next(iter(new_to_parent.values()))
        X.loc[(zero_parent_region, MI["s"], parent), "production"] = 0.0
    z = pd.DataFrame(rng.uniform(0, 0.3, (n, n)), index=idx, columns=idx)
    e = pd.DataFrame(rng.uniform(0, 0.3, (2, n)), index=["e1", "e2"], columns=idx)
    v = pd.DataFrame(rng.uniform(0, 0.3, (2, n)), index=["v1", "v2"], columns=idx)
    fd_cols = pd.MultiIndex.from_product([REGIONS, ["Consumption category"], ["c1", "c2"]])
    Y = pd.DataFrame(rng.uniform(1, 5, (n, len(fd_cols))), index=idx, columns=fd_cols)
    EY = pd.DataFrame(rng.uniform(0, 1, (2, len(fd_cols))), index=["e1", "e2"], columns=fd_cols)
    VY = pd.DataFrame(rng.uniform(0, 1, (2, len(fd_cols))), index=["v1", "v2"], columns=fd_cols)

    quantities = []
    for sector, parent in new_to_parent.items():
        for region in REGIONS:
            parent_output = X.loc[(region, MI["s"], parent), "production"]
            quantities.append(
                {
                    ADD_SECTOR_SPLIT_OUTPUT_COLUMNS["sector"]: sector,
                    ADD_SECTOR_SPLIT_OUTPUT_COLUMNS["region"]: region,
                    ADD_SECTOR_SPLIT_OUTPUT_COLUMNS["quantity"]: float(rng.uniform(0.1, 0.4) * parent_output),
                }
            )

    blocks = {_ENUM["z"]: z, _ENUM["e"]: e, _ENUM["v"]: v, _ENUM["Y"]: Y,
              _ENUM["EY"]: EY, _ENUM["VY"]: VY, _ENUM["X"]: X}
    instance = SimpleNamespace(
        X=X,
        matrices={"baseline": blocks},
        to_split_sectors=list(new_to_parent),
        add_sectors_master=pd.DataFrame(
            {MI["s"]: list(new_to_parent), f"Parent {MI['s']}": list(new_to_parent.values())}
        ),
        split_info={ADD_SECTOR_SPLIT_OUTPUT_SHEET: pd.DataFrame(quantities)},
        uncertainty_matrix=None,
        get_index=lambda level: REGIONS,
        get_block_as_pandas=lambda name, scenario: instance.matrices[scenario][name],
    )
    return instance


def _reference_split_flow(instance, base_scenario="baseline"):
    """Label-based version of the split flow scenario (original formulation)."""

    parents = dict(zip(instance.add_sectors_master[MI["s"]], instance.add_sectors_master.iloc[:, 1]))
    split_sectors = list(instance.to_split_sectors)
    split_output = instance.split_info[ADD_SECTOR_SPLIT_OUTPUT_SHEET]
    old_X = copy.deepcopy(instance.X)
    X = copy.deepcopy(old_X)
    for sector in split_sectors:
        rows = split_output[split_output[MI["s"]] == sector]
        for _, row in rows.iterrows():
            X.loc[(row[MI["r"]], MI["s"], sector), "production"] = float(row["Quantity"])

    blocks = instance.matrices[base_scenario]
    z, e, v = blocks[_ENUM["z"]], blocks[_ENUM["e"]], blocks[_ENUM["v"]]
    Y = blocks[_ENUM["Y"]].copy()
    Z, E, V = calc_Z(z, X), calc_E(e, X), calc_V(v, X)

    for sector in split_sectors:
        parent_sector = parents[sector]
        for mat in (Z, E, V):
            row_shares = {row: [] for row in mat.index}
            overflow = []
            for region in REGIONS:
                child_col = mat.loc[:, (region, MI["s"], sector)]
                parent_col = mat.loc[:, (region, MI["s"], parent_sector)]
                if (child_col > parent_col).any():
                    overflow.append(region)
                else:
                    for row in mat.index:
                        p, c = float(parent_col.loc[row]), float(child_col.loc[row])
                        if p > 0:
                            row_shares[row].append(c / p)
            row_median = {r: statistics.median(s) if s else 0.0 for r, s in row_shares.items()}
            for region in overflow:
                parent_col = mat.loc[:, (region, MI["s"], parent_sector)]
                for row in mat.index:
                    mat.loc[row, (region, MI["s"], sector)] = float(parent_col.loc[row]) * row_median[row]
            for region in REGIONS:
                mat.loc[:, (region, MI["s"], parent_sector)] -= mat.loc[:, (region, MI["s"], sector)]
        for region in REGIONS:
            child_output = float(X.loc[(region, MI["s"], sector), "production"])
            parent_output = float(X.loc[(region, MI["s"], parent_sector), "production"])
            X.loc[(region, MI["s"], parent_sector), "production"] = parent_output - child_output

    Z, E, V = calc_Z(z, X), calc_E(e, X), calc_V(v, X)
    Z[Z < 0] = 0.0

    old_sectors = sorted(set(X.index.get_level_values(2)).difference(split_sectors))
    for sector in split_sectors:
        parent_sector = parents[sector]
        for region in REGIONS:
            parent_old_output = float(old_X.loc[(region, MI["s"], parent_sector), "production"])
            if parent_old_output == 0:
                continue
            X_cut = X.loc[(sn, MI["s"], old_sectors)].squeeze()
            z_row = z.loc[(region, MI["s"], parent_sector), (sn, MI["s"], old_sectors)]
            X_cut.index = z_row.index
            new_Z_row = z_row * X_cut
            new_Z_row.name = (region, MI["s"], sector)
            Z.loc[(region, MI["s"], sector), (sn, MI["s"], old_sectors)] = new_Z_row
            child_output = float(X.loc[(region, MI["s"], sector), "production"])
            parent_new_output = float(X.loc[(region, MI["s"], parent_sector), "production"])
            new_Y_row = Y.loc[(region, MI["s"], parent_sector), :] * child_output / parent_old_output
            Y.loc[(region, MI["s"], sector), :] = new_Y_row
            Y.loc[(region, MI["s"], parent_sector), :] = (
                Y.loc[(region, MI["s"], parent_sector), :] * parent_new_output / parent_old_output
            )
    return {_ENUM["Z"]: Z, _ENUM["E"]: E, _ENUM["V"]: V, _ENUM["Y"]: Y, _ENUM["X"]: X}


@pytest.mark.parametrize(
    "new_to_parent, zero_parent_region",
    [
        ({"n1": "a"}, None),
        ({"n1": "a", "n2": "a"}, None),
        ({"n1": "a", "n2": "b"}, None),
        ({"n1": "a", "n2": "a"}, "R2"),
    ],
)
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_build_split_flow_scenario_matches_label_based_reference(seed, new_to_parent, zero_parent_region):
    instance = _build_instance(seed, new_to_parent, zero_parent_region)
    expected = _reference_split_flow(instance)

    with np.errstate(all="ignore"):
        scenario = build_split_flow_scenario(instance)
    result = instance.matrices[scenario]

    for name, frame in expected.items():
        pd.testing.assert_frame_equal(frame, result[name], rtol=1e-10, atol=1e-12, obj=name)


def test_cap_branch_is_exercised():
    """The synthetic data must hit the overflow (median share) branch, otherwise the test is vacuous."""

    instance = _build_instance(0, {"n1": "a", "n2": "a"})
    X = instance.matrices["baseline"][_ENUM["X"]]
    z = instance.matrices["baseline"][_ENUM["z"]]
    overflow_hits = 0
    for sector in ("n1", "n2"):
        for region in REGIONS:
            child = z.loc[:, (region, MI["s"], sector)] * X.loc[(region, MI["s"], sector), "production"]
            parent = z.loc[:, (region, MI["s"], "a")] * X.loc[(region, MI["s"], "a"), "production"]
            overflow_hits += int((child > parent).any())
    assert overflow_hits > 0


@pytest.mark.parametrize("scale", [1e-6, 1.0, 1e6])
@pytest.mark.parametrize("excess", [0.0, 1e-9])
def test_fully_allocated_parent_only_accepts_floating_point_roundoff(scale, excess):
    instance = _build_instance(0, {"n1": "a", "n2": "a"})
    for region in REGIONS:
        instance.X.loc[(region, MI["s"], "a"), "production"] = 0.3 * scale
    targets = instance.split_info[ADD_SECTOR_SPLIT_OUTPUT_SHEET]
    targets.loc[targets.Sector.eq("n1"), "Quantity"] = 0.1 * scale
    targets.loc[targets.Sector.eq("n2"), "Quantity"] = (0.2 + excess) * scale
    if excess:
        with pytest.raises(WrongInput, match="negative parent-sector outputs"):
            build_split_flow_scenario(instance)
        return
    scenario = build_split_flow_scenario(instance)
    output = instance.matrices[scenario][_ENUM["X"]]
    for region in REGIONS:
        assert output.at[(region, MI["s"], "a"), "production"] >= 0
        assert output.at[(region, MI["s"], "n1"), "production"] == 0.1 * scale
        assert output.at[(region, MI["s"], "n2"), "production"] == 0.2 * scale
        assert output.loc[(region, MI["s"], ["a", "n1", "n2"]), "production"].sum() == pytest.approx(0.3 * scale, rel=4e-16, abs=0)
