import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.model.conventions import _MASTER_INDEX
from mario.test.mario_test import load_test

A, C, N, R = (
    _MASTER_INDEX["a"],
    _MASTER_INDEX["c"],
    _MASTER_INDEX["n"],
    _MASTER_INDEX["r"],
)


def _observed_trade_flows(database, commodity):
    """Origin-by-destination flows of one commodity on the Isard use side."""
    regions = database.get_index(R)
    rows = [(region, C, commodity) for region in regions]
    U = database.U
    Y = database.Y
    flows = (
        U.loc[rows, :].T.groupby(level=R, sort=False).sum().T
        + Y.loc[rows, :].T.groupby(level=R, sort=False).sum().T
    )
    flows.index = regions
    return flows.reindex(columns=regions, fill_value=0.0)


def test_pool_trade_preserves_totals_and_derives_observed_shares():
    database = load_test("SUT")
    X_before = database.X.copy()
    trade_flows = _observed_trade_flows(database, "Goods")

    database.pool_trade("Goods")

    assert database.get_index(A) == ["Manufacturing", "Services", "Goods - supply"]
    assert database.get_index(C) == ["Goods", "Services", "Goods - need"]
    assert database.meta.pooled_trade_map == {
        "Goods": {"supply": "Goods - supply", "need": "Goods - need"}
    }
    goods_unit = database.units[C].loc["Goods", "unit"]
    assert database.units[A].loc["Goods - supply", "unit"] == goods_unit
    assert database.units[C].loc["Goods - need", "unit"] == goods_unit

    # the pooling is a representation change: original items keep their
    # production levels and the table stays balanced.
    X_after = database.X
    common = [row for row in X_before.index if row in X_after.index]
    np.testing.assert_allclose(
        X_before.loc[common].to_numpy(dtype=float),
        X_after.loc[common].to_numpy(dtype=float),
    )

    regions = database.get_index(R)
    X = database.query("X")
    for region in regions:
        assert X.loc[(region, A, "Goods - supply"), "production"] == pytest.approx(
            float(trade_flows.loc[region, :].sum())
        )
        assert X.loc[(region, C, "Goods - need"), "production"] == pytest.approx(
            float(trade_flows.loc[:, region].sum())
        )

    # the initial market shares in s equal the observed origin shares of each
    # destination's total use, and the pass-through consumes only the
    # domestic commodity (unitary use coefficient).
    database.reset_to_coefficients("baseline")
    s = database.get_block_as_pandas("s", scenario="baseline")
    u = database.get_block_as_pandas("u", scenario="baseline")
    supply_rows = [(region, A, "Goods - supply") for region in regions]
    for destination in regions:
        observed = trade_flows.loc[:, destination]
        expected = (observed / observed.sum()).to_numpy(dtype=float)
        np.testing.assert_allclose(
            s.loc[supply_rows, (destination, C, "Goods - need")].to_numpy(dtype=float),
            expected,
        )
        assert u.loc[
            (destination, C, "Goods"), (destination, A, "Goods - supply")
        ] == pytest.approx(1.0)

    # the original commodity rows no longer serve the buyers directly.
    goods_rows = [(region, C, "Goods") for region in regions]
    buyer_cols = [
        col
        for col in u.columns
        if col[2] in {"Manufacturing", "Services"}
    ]
    assert float(u.loc[goods_rows, buyer_cols].abs().to_numpy().sum()) == pytest.approx(0.0)


def test_pool_trade_multiple_commodities_does_not_worsen_balance():
    database = load_test("SUT")
    # the packaged test table carries a tiny float32 imbalance; pooling must
    # not add anything on top of that baseline noise.
    before = database.is_balanced("flows", as_dataframe=True)
    baseline_noise = float(np.abs(before.to_numpy(dtype=float)).max())

    database.pool_trade(["Goods", "Services"])

    assert set(database.meta.pooled_trade_map) == {"Goods", "Services"}
    after = database.is_balanced("flows", as_dataframe=True)
    residual = 0.0 if after.empty else float(np.abs(after.to_numpy(dtype=float)).max())
    assert residual <= baseline_noise * 1.001 + 1e-6


def test_pool_trade_validation():
    database = load_test("SUT")

    with pytest.raises(WrongInput, match="unknown commodities"):
        database.pool_trade("Missing commodity")

    with pytest.raises(WrongInput, match="non-empty"):
        database.pool_trade([])

    iot = load_test("IOT")
    with pytest.raises(NotImplementable, match="SUT"):
        iot.pool_trade("Agriculture")

    database.pool_trade("Goods")
    with pytest.raises(WrongInput, match="already pooled|naming collision|already exist"):
        database.pool_trade("Goods")


def test_pool_trade_drops_other_scenarios_with_warning(caplog):
    database = load_test("SUT")
    database.clone_scenario("baseline", "policy")

    with caplog.at_level("WARN"):
        database.pool_trade("Goods")

    assert any("non-baseline scenarios" in message for message in caplog.messages)
    assert database.scenarios == ["baseline"]


def test_pool_trade_inplace_false_returns_copy():
    database = load_test("SUT")
    activities_before = list(database.get_index(A))

    pooled = database.pool_trade("Goods", inplace=False)

    assert database.get_index(A) == activities_before
    assert "Goods - supply" in pooled.get_index(A)
    assert "Goods - need" in pooled.get_index(C)


def test_pool_trade_supports_custom_suffixes():
    database = load_test("SUT")

    database.pool_trade("Goods", supply_suffix=" market supply", need_suffix=" market")

    assert "Goods market supply" in database.get_index(A)
    assert "Goods market" in database.get_index(C)
    assert database.meta.pooled_trade_map["Goods"] == {
        "supply": "Goods market supply",
        "need": "Goods market",
    }


def test_pool_trade_e2e_trade_and_supply_mix_are_decoupled():
    database = load_test("SUT")
    trade_flows = _observed_trade_flows(database, "Goods")
    database.pool_trade("Goods")
    regions = database.get_index(R)

    database.clone_scenario("baseline", "policy")

    # 1. rewrite the sourcing of Region 1's pooled market...
    database.update_trade_mix(
        {"Region 1": {"Region 1": 0.4, "Region 2": 0.6}},
        items="Goods - supply",
        commodities="Goods - need",
        scenario="policy",
    )
    # 2. ...and the technology mix on the domestic Goods market of Region 1.
    database.update_supply_mix(
        {"Region 1": {"Manufacturing": 0.5, "Services": 0.5}},
        level=A,
        commodities="Goods",
        scenario="policy",
    )

    s = database.get_block_as_pandas("s", scenario="policy")
    need_r1 = ("Region 1", C, "Goods - need")
    goods_r1 = ("Region 1", C, "Goods")

    # trade mix applied on the pooled market...
    assert s.loc[("Region 1", A, "Goods - supply"), need_r1] == pytest.approx(0.4)
    assert s.loc[("Region 2", A, "Goods - supply"), need_r1] == pytest.approx(0.6)
    # ...technology mix applied on the domestic market...
    assert s.loc[("Region 1", A, "Manufacturing"), goods_r1] == pytest.approx(0.5)
    assert s.loc[("Region 1", A, "Services"), goods_r1] == pytest.approx(0.5)
    # ...and the two updates do not interfere: Region 2's market keeps the
    # observed sourcing.
    observed_r2 = trade_flows.loc[:, "Region 2"] / trade_flows.loc[:, "Region 2"].sum()
    np.testing.assert_allclose(
        s.loc[
            [(region, A, "Goods - supply") for region in regions],
            ("Region 2", C, "Goods - need"),
        ].to_numpy(dtype=float),
        observed_r2.to_numpy(dtype=float),
    )
