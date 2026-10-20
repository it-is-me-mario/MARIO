"""Opt-in integration check against the BONSAI Balanced 20260615 release.

Set MARIO_BONSAI_BALANCED_ZIP to the local, complete ZIP. No data are downloaded.
The independent product validator in the release checks the full imported
economic matrices, rather than just a few sampled graph edges.
"""

import ast
import os
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

import mario
from mario.compute.resolver import resolve
from mario.compute.types import ResolutionContext
from mario.model.conventions import _MASTER_INDEX


@pytest.mark.skipif(
    not os.environ.get("MARIO_BONSAI_BALANCED_ZIP"),
    reason="Set MARIO_BONSAI_BALANCED_ZIP to the local Balanced 20260615 ZIP.",
)
def test_balanced_20260615_demand_based_fc_reports_singular_components(monkeypatch):
    """Guard the current demand-based output convention, not the HIOT model.

    These market Commodity nodes are explicitly not mass-balanced. BONSAI's
    reference-output HIOT has nonsingular corresponding blocks. Update this
    reproducer when the HSUT output convention is changed explicitly.
    """
    pytest.importorskip("scikits.umfpack")
    with pytest.warns(UserWarning, match="362 elementary-flow rows"):
        database = mario.parse_bonsai(os.environ["MARIO_BONSAI_BALANCED_ZIP"])
    database.keep_extensions(
        "Carbon dioxide, fossil | Air | tonnes | 147f8e0a-3638-4a77-a029-45d8acba0184"
    )

    def forbidden(*args, **kwargs):
        pytest.fail("The full singular BONSAI system must be rejected before native LU")

    monkeypatch.setattr("mario.compute.linear_solvers.factorize_umfpack", forbidden)
    with pytest.raises(np.linalg.LinAlgError, match="singular") as error:
        resolve("fc", database, context=ResolutionContext(
            compute_method="solve", linear_solver="umfpack", linear_strategy="direct",
        ))
    assert all(label in str(error.value) for label in ["TW", "C_Beany", "M_Beany", "C_Eggs_ggs", "M_Eggs_ggs"])
    assert not {"fc", "wcc", "waa", "w"}.intersection(database.matrices["baseline"])


@pytest.mark.skipif(
    not os.environ.get("MARIO_BONSAI_BALANCED_ZIP"),
    reason="Set MARIO_BONSAI_BALANCED_ZIP to the local Balanced 20260615 ZIP.",
)
def test_balanced_20260615_matches_published_product_totals():
    path = os.environ["MARIO_BONSAI_BALANCED_ZIP"]
    with pytest.warns(UserWarning, match="362 elementary-flow rows"):
        database = mario.parse_bonsai(path)
    blocks = database.matrices["baseline"]
    assert database.meta.year == 2016
    assert database.is_hybrid
    assert blocks["S"].shape == (51_356, 53_400)
    assert blocks["Yc"].shape == (53_400, 267)
    activities = database.get_index("Activity")
    commodities = database.get_index("Commodity")
    assert isinstance(activities, dict) and isinstance(commodities, dict)
    assert sum(map(len, activities.values())) == 51_356
    assert sum(map(len, commodities.values())) == 53_400
    assert len(activities["IT"]) == 1_177
    assert len(commodities["IT"]) == 1_237
    assert database.get_index("Consumption category", region="Global") == []
    assert len(database.get_index("Activity", flat=True)) == 1_585
    for frame in blocks.values():
        assert all(
            isinstance(t, pd.SparseDtype) and t.fill_value == 0 for t in frame.dtypes
        )
        assert np.isfinite(frame.sparse.to_coo().data).all()
    report = database.info["bonsai"]
    assert len(report["unmatched_extensions"]) == 362
    assert blocks["EY"].sparse.to_coo().nnz == 147

    with ZipFile(path) as archive:
        member = next(
            n
            for n in archive.namelist()
            if n.endswith("/classification.csv") or n == "classification.csv"
        )
        prefix = member.removesuffix("classification.csv")
        with archive.open(member) as handle:
            classification = pd.read_csv(handle, keep_default_na=False)
        with archive.open(prefix + "product_validate_after_balance.csv") as handle:
            validation = pd.read_csv(handle, keep_default_na=False)

    products = classification.loc[
        classification["property"]
        .map(ast.literal_eval)
        .map(lambda p: p.get("object_type") == "product")
    ]
    layer_for_unit = {
        "tonnes": "MASS",
        "tonnes (service)": "WASTE_SERVICE",
        "Meuro": "CURRENCY",
        "TJ": "ENERGY",
        "items": "ITEM_COUNT",
    }
    code_layers = database.units[_MASTER_INDEX["c"]].unit.map(layer_for_unit)
    assert code_layers.notna().all()
    validation = (
        validation.loc[
            validation.id.isin(products.id)
            & validation.property_layer.eq(validation["name"].map(code_layers))
        ]
        .set_index("id")
        .reindex(products.id)
    )
    assert validation.index.is_unique
    assert validation.total_inflow.notna().all()

    axis = pd.MultiIndex.from_arrays(
        [products.location, [_MASTER_INDEX["c"]] * len(products), products["name"]],
        names=blocks["U"].index.names,
    )
    supply = (
        pd.Series(
            np.asarray(blocks["S"].sparse.to_coo().tocsr().sum(axis=0)).ravel(),
            index=blocks["S"].columns,
        )
        .reindex(axis)
        .to_numpy()
    )
    demand = (
        pd.Series(
            np.asarray(blocks["U"].sparse.to_coo().tocsr().sum(axis=1)).ravel()
            + np.asarray(blocks["Yc"].sparse.to_coo().tocsr().sum(axis=1)).ravel(),
            index=blocks["U"].index,
        )
        .reindex(axis)
        .to_numpy()
    )
    np.testing.assert_allclose(supply, validation.total_inflow, rtol=1e-12, atol=1e-7)
    np.testing.assert_allclose(demand, validation.total_outflow, rtol=1e-12, atol=1e-7)

    balance_properties = (
        products.isbalance.str.replace("np.True_", "True", regex=False)
        .str.replace("np.False_", "False", regex=False)
        .map(ast.literal_eval)
    )
    enforced = np.array(
        [
            p.get(layer, False)
            for p, layer in zip(balance_properties, products["name"].map(code_layers))
        ]
    )
    assert enforced.sum() == 45_123
    # Solver tolerances include an absolute floor for very small accounts.
    scaled_error = np.abs(supply - demand) / np.maximum(
        np.maximum(np.abs(supply), np.abs(demand)), 1.0
    )
    assert scaled_error[enforced].max() <= 1e-5
