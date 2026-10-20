"""Chenery-Moses uses observed import markets and preserves native accounts."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.ops.chenery_moses import FLOW_BLOCKS
from mario.ops.transform_engine import ISARD_TO_CHENERY_MOSES
from mario.test.mario_test import load_test
from tests.api.test_regional_indexes import regional_database


def dense(frame):
    return (
        frame.sparse.to_dense()
        if all(isinstance(t, pd.SparseDtype) for t in frame.dtypes)
        else frame.copy()
    )


@pytest.fixture(params=[False, True], ids=["dense", "sparse"])
def database(request):
    db = regional_database(
        {"IT": ["A", "B"], "DE": ["D"], "FR": ["F"], "Global": []},
        {"IT": ["X"], "DE": ["Y", "X"], "FR": ["Z"], "Global": ["unused"]},
        {"IT": ["HH"], "DE": ["HH", "GOV"], "FR": ["GOV"], "Global": []},
    )
    entries = {
        "S": [(0, 0, 12), (1, 0, 8), (2, 1, 15), (2, 2, 4), (3, 3, 10)],
        "U": [
            (0, 2, 3),
            (0, 3, 2),
            (1, 0, 4),
            (1, 1, 1),
            (1, 3, 2),
            (2, 0, 1),
            (3, 1, 1),
            (3, 2, 2),
        ],
        "Yc": [(0, 0, 15), (1, 1, 8), (2, 0, 3), (3, 3, 7)],
        "Ya": [(0, 2, 1.25), (3, 0, 0.75)],
    }
    for name, frame in list(db.matrices["baseline"].items()):
        value = pd.DataFrame(0.0, index=frame.index, columns=frame.columns)
        if name in entries:
            for row, col, amount in entries[name]:
                value.iloc[row, col] = amount
        else:
            value.iloc[:, :] = np.arange(frame.size).reshape(frame.shape) + 1.0
        if request.param:
            value = value.astype(pd.SparseDtype(float, 0.0))
        db.matrices["baseline"][name] = value
    ey = db.matrices["baseline"]["EY"]
    db.matrices["baseline"]["VY"] = ey.copy() * 2
    return db


def expected_flows(source, markets):
    """Small scalar oracle: no production helper, sparse mapping or matrix product."""
    old = {k: dense(v) for k, v in source.items()}
    result = {k: v.copy() for k, v in old.items()}
    for name in ("U", "Yc"):
        result[name] = pd.DataFrame(0.0, index=markets, columns=old[name].columns)
        for origin in old[name].index:
            for buyer in old[name].columns:
                value = old[name].loc[origin, buyer]
                if value:
                    result[name].loc[(buyer[0], "Commodity", origin[2]), buyer] += value
    for name in ("S", "Ec", "Vc"):
        result[name] = pd.DataFrame(0.0, index=old[name].index, columns=markets)
    for origin in old["U"].index:
        amounts = {}
        for name in ("U", "Yc"):
            for buyer in old[name].columns:
                amounts[buyer[0]] = (
                    amounts.get(buyer[0], 0.0) + old[name].loc[origin, buyer]
                )
        total = sum(amounts.values())
        if total == 0:
            amounts = {origin[0]: 1.0}
            total = 1.0
        for region, amount in amounts.items():
            if not amount:
                continue
            target = (region, "Commodity", origin[2])
            for name in ("S", "Ec", "Vc"):
                for row in old[name].index:
                    result[name].loc[row, target] += (
                        old[name].loc[row, origin] * amount / total
                    )
    return result


def assert_source_unchanged(database, source):
    for name, frame in source.items():
        pd.testing.assert_frame_equal(database.matrices["baseline"][name], frame)


def test_regional_values_match_scalar_reference_without_padding(database):
    source = {k: v.copy() for k, v in database.matrices["baseline"].items()}
    converted = database.to_chenery_moses(inplace=False)
    blocks = converted.matrices["baseline"]
    markets = blocks["U"].index
    assert set(markets) == set(source["U"].index) | {
        ("FR", "Commodity", "X"),
        ("IT", "Commodity", "Y"),
        ("FR", "Commodity", "Y"),
        ("IT", "Commodity", "Z"),
        ("DE", "Commodity", "Z"),
    }
    assert markets[: len(source["U"])].equals(source["U"].index)
    expected = expected_flows(source, markets)
    for name in FLOW_BLOCKS:
        pd.testing.assert_frame_equal(dense(blocks[name]), expected[name])
        assert all(isinstance(t, pd.SparseDtype) for t in blocks[name].dtypes) == all(
            isinstance(t, pd.SparseDtype) for t in source[name].dtypes
        )
    for name in ("Ya", "Ea", "Va", "EY", "VY"):
        pd.testing.assert_frame_equal(blocks[name], source[name])
    for name in ("Ec", "Vc"):
        np.testing.assert_allclose(
            dense(blocks[name]).sum(axis=1), dense(source[name]).sum(axis=1)
        )
    np.testing.assert_allclose(
        dense(blocks["S"]).sum(axis=1), dense(source["S"]).sum(axis=1)
    )
    assert blocks["S"].index.equals(source["S"].index)
    assert blocks["U"].columns.equals(source["U"].columns)
    assert converted.get_index("Consumption category") == database.get_index(
        "Consumption category"
    )
    assert_source_unchanged(database, source)
    assert set(blocks) == set(FLOW_BLOCKS)
    coefficients = converted.query(["u", "s", "Xa", "Xc"])
    assert coefficients["u"].shape == blocks["U"].shape
    assert coefficients["s"].shape == blocks["S"].shape
    np.testing.assert_allclose(
        coefficients["Xa"].to_numpy(), database.query("Xa").to_numpy()
    )


def test_ya_is_preserved_also_for_uniform_sut():
    source = load_test("SUT")
    source.reset_to_flows("baseline")
    ya = source.query("Ya")
    ya.iloc[0, 0] = 2.5
    source.update_scenarios("baseline", Ya=ya)
    converted = source.to_chenery_moses(inplace=False)
    pd.testing.assert_frame_equal(converted.query("Ya"), ya)
    np.testing.assert_allclose(
        converted.query("Xa").to_numpy(), source.query("Xa").to_numpy(), rtol=1e-6
    )


def test_selected_scenario_expands_other_scenarios_without_changing_flows(database):
    source = {k: v.copy() for k, v in database.matrices["baseline"].items()}
    database.query(["u", "s", "Xc"])
    database.clone_scenario("baseline", "policy")
    database.rename_baseline_scenario("reference")
    database.to_chenery_moses(scenarios="policy")
    markets = database.matrices["policy"]["U"].index
    assert database.scenarios == ["reference", "policy"]
    assert database.matrices["baseline"]["U"].index.equals(markets)
    for name, original in source.items():
        frame = dense(database.matrices["baseline"][name])
        wanted = dense(original)
        if name in ("U", "Yc"):
            wanted = wanted.reindex(index=markets, fill_value=0.0)
        if name in ("S", "Ec", "Vc"):
            wanted = wanted.reindex(columns=markets, fill_value=0.0)
        pd.testing.assert_frame_equal(frame, wanted)
    assert set(database.matrices["baseline"]) == set(FLOW_BLOCKS)
    assert not database.is_chenerymoses(scenario="reference")
    assert database.is_chenerymoses(scenario="policy")
    assert set(database.get_index("Commodity", flat=True)) == set(
        database._indeces["c"]["main"]
    )


def test_all_scenarios_share_new_markets_and_keep_their_own_values(database):
    database.clone_scenario("baseline", "policy")
    source = {k: v.copy() for k, v in database.matrices["policy"].items()}
    database.matrices["policy"]["U"] *= 2
    policy_source = {k: v.copy() for k, v in database.matrices["policy"].items()}
    database.to_chenery_moses()
    for scenario, original in (("baseline", source), ("policy", policy_source)):
        result = database.matrices[scenario]
        expected = expected_flows(original, result["U"].index)
        for name, frame in result.items():
            pd.testing.assert_frame_equal(dense(frame), expected[name])


def test_zero_use_keeps_supply_imbalance_and_commodity_accounts(database):
    original = database.matrices["baseline"]
    for name in ("U", "Yc"):
        frame = dense(original[name])
        frame.iloc[0, :] = 0.0
        original[name] = frame.astype(original[name].dtypes.to_dict())
    source = {k: v.copy() for k, v in original.items()}
    old_s = dense(original["S"])
    converted = database.to_chenery_moses(inplace=False)
    target = ("IT", "Commodity", "X")
    for activity in [("IT", "Activity", "A"), ("IT", "Activity", "B")]:
        assert (
            dense(converted.query("S")).loc[activity, target]
            == old_s.loc[activity, target]
        )
    expected = expected_flows(source, converted.query("U").index)
    pd.testing.assert_frame_equal(dense(converted.query("Ec")), expected["Ec"])


def test_undefined_zero_net_trade_errors_without_data_adjustment(database):
    for name in ("U", "Yc"):
        frame = dense(database.matrices["baseline"][name])
        frame.iloc[0, :] = 0.0
        if name == "U":
            frame.iloc[0, 0], frame.iloc[0, 2] = 3.0, -3.0
        database.matrices["baseline"][name] = frame
    source = {k: v.copy() for k, v in database.matrices["baseline"].items()}
    history = deepcopy(database.meta._history)
    with pytest.raises(WrongInput, match="zero net use.*Nodes:.*IT.*X"):
        database.to_chenery_moses()
    assert_source_unchanged(database, source)
    assert database.meta._history == history


def test_signed_flows_keep_their_values_and_sourcing_weights(database):
    source = database.matrices["baseline"]
    yc = dense(source["Yc"])
    yc.iloc[0, 3] = -4.0
    source["Yc"] = yc.astype(source["Yc"].dtypes.to_dict())
    before = {name: frame.copy() for name, frame in source.items()}
    converted = database.to_chenery_moses(inplace=False)
    expected = expected_flows(before, converted.query("U").index)
    for name in FLOW_BLOCKS:
        pd.testing.assert_frame_equal(
            dense(converted.matrices["baseline"][name]), expected[name]
        )


def test_nonfinite_flows_are_rejected_without_repair(database):
    source = database.matrices["baseline"]
    frame = dense(source["U"])
    frame.iloc[0, 0] = np.nan
    source["U"] = frame.astype(source["U"].dtypes.to_dict())
    with pytest.raises(WrongInput, match="finite flow values"):
        database.to_chenery_moses()
    assert np.isnan(dense(source["U"]).iloc[0, 0])


def test_custom_account_row_indexes_and_product_technology_are_retained(database):
    database.change_assumption("PT")
    for name in ("Ea", "Ec", "Va", "Vc", "EY", "VY"):
        frame = database.matrices["baseline"][name]
        index = pd.MultiIndex.from_tuples(
            [("origin", item) for item in frame.index],
            names=["Origin label", "Account"],
        )
        database.matrices["baseline"][name] = frame.set_axis(index)
    source = {
        name: frame.copy() for name, frame in database.matrices["baseline"].items()
    }
    converted = database.to_chenery_moses(inplace=False)
    expected = expected_flows(source, converted.query("U").index)
    for name in FLOW_BLOCKS:
        pd.testing.assert_frame_equal(
            dense(converted.matrices["baseline"][name]), expected[name]
        )
    assert converted.meta.tech_assumption == database.meta.tech_assumption


def test_sparse_path_has_no_dense_conversion_diagonal_or_unified_queries(
    database, monkeypatch
):
    if not all(
        isinstance(t, pd.SparseDtype) for t in database.matrices["baseline"]["S"].dtypes
    ):
        pytest.skip("Sparse allocation guard")
    original = pd.DataFrame.to_numpy

    def guarded(frame, *args, **kwargs):
        if all(isinstance(t, pd.SparseDtype) for t in frame.dtypes):
            raise AssertionError("Sparse flow densified")
        return original(frame, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_numpy", guarded)
    for name in ("diag", "diagflat"):
        monkeypatch.setattr(
            np, name, lambda *a, **k: pytest.fail("Dense diagonal allocated")
        )
    monkeypatch.setattr(
        np.linalg, "inv", lambda *a, **k: pytest.fail("Inverse requested")
    )
    query = database.query

    def native_query(matrices=None, *args, **kwargs):
        names = [matrices] if isinstance(matrices, str) else list(matrices or [])
        assert not set(names) & {"Z", "Y", "X", "V", "E", "s", "u", "wcc", "waa"}
        return query(matrices, *args, **kwargs)

    monkeypatch.setattr(database, "query", native_query)
    database.to_chenery_moses()
    assert set(database.matrices["baseline"]) == set(FLOW_BLOCKS)


def test_compatibility_engine_returns_consistent_views(database):
    z, y = ISARD_TO_CHENERY_MOSES(database, "baseline")
    converted = database.to_chenery_moses(inplace=False)
    pd.testing.assert_frame_equal(z, converted.query("Z"))
    pd.testing.assert_frame_equal(y, converted.query("Y"))


def test_already_converted_and_invalid_scenarios_are_explicit(database):
    with pytest.raises(WrongInput):
        database.to_chenery_moses(scenarios=["missing"])
    database.to_chenery_moses()
    with pytest.raises(NotImplementable, match="already in Chenery-Moses"):
        database.to_chenery_moses()


def test_explicit_regional_index_storage_tracks_added_markets(database):
    database._indeces["c"]["main"] = database.get_index("Commodity")
    database.to_chenery_moses()
    assert "Y" in database.get_index("Commodity", region="IT")
    assert "Z" in database.get_index("Commodity", region="DE")
