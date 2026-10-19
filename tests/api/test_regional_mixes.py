"""Mix updates preserve actual regional nodes and selected bundle totals."""

import numpy as np
import pandas as pd
import pytest

from mario import Database
from mario.log_exc.exceptions import WrongInput
from tests.api.test_regional_indexes import regional_database


@pytest.fixture(params=[False, True], ids=["dense", "sparse"])
def database(request):
    db = regional_database(
        {"IT": ["A", "B", "extra"], "DE": ["A", "D"], "FR": ["F"], "Global": []},
        {"IT": ["X", "Y"], "DE": ["X", "Z"], "FR": ["W"], "Global": []},
        {"IT": ["HH"], "DE": ["HH", "GOV"], "FR": ["GOV"], "Global": []},
    )
    for name, frame in list(db.matrices["baseline"].items()):
        values = (np.arange(frame.size).reshape(frame.shape) + 1) % 7
        result = pd.DataFrame(
            values, index=frame.index, columns=frame.columns, dtype=float
        )
        if request.param:
            result = result.astype(pd.SparseDtype(float, 0.0))
        db.matrices["baseline"][name] = result
    return db


def dense(frame):
    if all(isinstance(dtype, pd.SparseDtype) for dtype in frame.dtypes):
        return frame.sparse.to_dense()
    return frame.copy()


def prepare(db):
    baseline = {name: frame.copy() for name, frame in db.matrices["baseline"].items()}
    db.clone_scenario("baseline", "policy")
    db.reset_to_coefficients("policy")
    before = {name: frame.copy() for name, frame in db.matrices["policy"].items()}
    return baseline, before


def reference(frame, bundles, *, weight_level, column_predicate):
    """Independent scalar reference, grouping only explicitly requested rows."""
    expected = dense(frame)
    original = expected.copy()
    for key, rows, weights in bundles:
        total_weight = sum(weights.values())
        for column in expected.columns:
            if column_predicate(key, column):
                total = sum(original.loc[row, column] for row in rows)
                for row in rows:
                    label = row[weight_level]
                    expected.loc[row, column] = total * weights[label] / total_weight
    return expected


def assert_results(db, baseline, before, expected):
    for name, source in baseline.items():
        pd.testing.assert_frame_equal(db.matrices["baseline"][name], source)
    for name, source in before.items():
        actual = db.matrices["policy"][name]
        assert actual.index.equals(source.index)
        assert actual.columns.equals(source.columns)
        if name in expected:
            pd.testing.assert_frame_equal(dense(actual), expected[name])
        else:
            pd.testing.assert_frame_equal(actual, source)
        assert all(isinstance(t, pd.SparseDtype) for t in actual.dtypes) == all(
            isinstance(t, pd.SparseDtype) for t in source.dtypes
        )


@pytest.mark.parametrize("explicit_level", [False, True])
def test_supply_activity_regional_bundles_preserve_other_producers(
    database, explicit_level
):
    baseline, before = prepare(database)
    mixes = {"IT": {"A": 0.25, "B": 0.75}, "DE": {"A": 0.6, "D": 0.4}}
    bundles = [
        (region, [(region, "Activity", item) for item in weights], weights)
        for region, weights in mixes.items()
    ]
    expected = reference(
        before["s"],
        bundles,
        weight_level=2,
        column_predicate=lambda _, col: col[0] in {"IT", "DE"} and col[2] in {"X", "Y"},
    )
    database.update_supply_mix(
        mixes,
        scenario="policy",
        commodities=["X", "Y"],
        column_regions=["IT", "DE"],
        **({"level": "Activity"} if explicit_level else {}),
    )
    assert_results(database, baseline, before, {"s": expected})


@pytest.mark.parametrize("filtered", [False, True])
def test_supply_commodity_filters_use_actual_buyer_and_demand_columns(
    database, filtered
):
    baseline, before = prepare(database)
    mixes = {"IT": {"X": 1.0, "Y": 3.0}, "DE": {"X": 2.0, "Z": 3.0}}
    bundles = [
        (region, [(region, "Commodity", item) for item in weights], weights)
        for region, weights in mixes.items()
    ]
    expected = {
        name: reference(
            before[name],
            bundles,
            weight_level=2,
            column_predicate=lambda _, col: not filtered
            or (
                col[0] in {"DE", "FR"}
                and col[2] in ({"D", "F"} if name == "u" else {"GOV"})
            ),
        )
        for name in ("u", "Yc")
    }
    database.update_supply_mix(
        mixes,
        scenario="policy",
        rescale=True,
        **(
            {
                "column_regions": ["DE", "FR"],
                "column_sectors": ["D", "F"],
                "column_categories": "GOV",
            }
            if filtered
            else {}
        ),
    )
    assert_results(database, baseline, before, expected)


@pytest.mark.parametrize("activity", [False, True])
def test_trade_mix_accepts_destination_without_local_origin_item(database, activity):
    baseline, before = prepare(database)
    level, item = ("Activity", "A") if activity else ("Commodity", "X")
    mixes = {"FR": {"DE": 0.8, "IT": 0.2}, "IT": {"IT": 1.0}}
    bundles = [
        (destination, [(origin, level, item) for origin in weights], weights)
        for destination, weights in mixes.items()
    ]
    names = ["s"] if activity else ["u", "Yc"]
    expected = {
        name: reference(
            before[name],
            bundles,
            weight_level=0,
            column_predicate=lambda dest, col: col[0] == dest
            and (
                col[2] == "W"
                if activity
                else col[2] in ({"F", "B"} if name == "u" else {"GOV"})
            ),
        )
        for name in names
    }
    database.update_trade_mix(
        mixes,
        items=item,
        scenario="policy",
        **(
            {"commodities": "W"}
            if activity
            else {"column_sectors": ["F", "B"], "column_categories": "GOV"}
        ),
    )
    assert_results(database, baseline, before, expected)
    assert item not in database.get_index(level, region="FR")


@pytest.mark.parametrize("kind", ["supply", "trade"])
@pytest.mark.parametrize("level,item", [("Activity", "D"), ("Commodity", "Z")])
def test_missing_regional_pairs_raise_before_reset(database, kind, level, item):
    original = {
        name: frame.copy() for name, frame in database.matrices["baseline"].items()
    }
    kwargs = {"level": level}
    if level == "Activity":
        kwargs["commodities"] = "X"
    with pytest.raises(WrongInput, match=f"IT.*unknown {level} labels.*{item}"):
        if kind == "supply":
            database.update_supply_mix({"IT": {item: 1.0}}, **kwargs)
        else:
            database.update_trade_mix({"DE": {"IT": 1.0}}, items=item, **kwargs)
    assert set(database.matrices["baseline"]) == set(original)
    for name, source in original.items():
        pd.testing.assert_frame_equal(database.matrices["baseline"][name], source)


def test_trade_multiple_items_checks_each_origin_including_zero_weights(database):
    with pytest.raises(WrongInput, match="DE.*unknown Commodity labels.*Y"):
        database.update_trade_mix(
            {"FR": {"IT": 1.0, "DE": 0.0}},
            items=["X", "Y"],
            level="Commodity",
        )


@pytest.mark.parametrize("kind", ["supply", "trade"])
def test_empty_region_cannot_supply_a_mix(database, kind):
    with pytest.raises(WrongInput, match="Global.*unknown Commodity labels"):
        if kind == "supply":
            database.update_supply_mix({"Global": {"X": 1.0}}, level="Commodity")
        else:
            database.update_trade_mix({"IT": {"Global": 1.0}}, items="X")


def test_supply_level_inference_uses_region_not_global_label_union():
    db = regional_database(
        {"IT": ["shared"], "DE": ["generator"]},
        {"IT": ["product"], "DE": ["shared"]},
    )
    # The same string exists as a commodity elsewhere, but only as an activity in IT.
    db.update_supply_mix({"IT": {"shared": 1.0}}, commodities="product")
    assert db.get_index("Activity", region="IT") == ["shared"]


def test_trade_level_inference_uses_origin_memberships():
    db = regional_database(
        {"IT": ["shared"], "DE": ["generator"]},
        {"IT": ["product"], "DE": ["shared"]},
    )
    db.update_trade_mix({"DE": {"IT": 1.0}}, items="shared", commodities="shared")
    assert db.get_index("Activity", region="IT") == ["shared"]


@pytest.mark.parametrize("kind", ["supply", "trade"])
def test_ambiguity_in_actual_regions_still_requires_explicit_level(kind):
    db = regional_database(
        {"IT": ["shared", "A"], "DE": ["shared"]},
        {"IT": ["shared"], "DE": ["shared", "C"]},
    )

    def update(**kwargs):
        if kind == "supply":
            db.update_supply_mix({"IT": {"shared": 1.0}}, **kwargs)
        else:
            db.update_trade_mix({"DE": {"IT": 1.0}}, items="shared", **kwargs)

    with pytest.raises(WrongInput, match="Could not infer"):
        update()
    update(level="Commodity")


@pytest.mark.parametrize("kind", ["supply", "trade"])
def test_multiple_trade_items_keep_independent_totals_and_sparse_precision(kind):
    db = regional_database(
        {"IT": ["A", "B"], "DE": ["D"]},
        {"IT": ["X", "Y"], "DE": ["X", "Y", "Z"]},
    )
    for name, frame in list(db.matrices["baseline"].items()):
        db.matrices["baseline"][name] = pd.DataFrame(
            (np.arange(frame.size).reshape(frame.shape) + 1) / 10,
            index=frame.index,
            columns=frame.columns,
        ).astype(pd.SparseDtype(np.float32, 0.0))
    baseline, before = prepare(db)
    if kind == "supply":
        mixes = {"IT": {"X": 0.1, "Y": 0.9}}
        bundles = [
            ("IT", [("IT", "Commodity", item) for item in ["X", "Y"]], mixes["IT"])
        ]
        expected = {
            name: reference(
                before[name],
                bundles,
                weight_level=2,
                column_predicate=lambda _, col: True,
            )
            for name in ("u", "Yc")
        }
        db.update_supply_mix(mixes, scenario="policy")
    else:
        weights = {"DE": 0.7, "IT": 0.3}
        bundles = [
            ("DE", [(origin, "Commodity", item) for origin in weights], weights)
            for item in ["Y", "X"]
        ]
        expected = {
            name: reference(
                before[name],
                bundles,
                weight_level=0,
                column_predicate=lambda dest, col: col[0] == dest,
            )
            for name in ("u", "Yc")
        }
        db.update_trade_mix({"DE": weights}, items=["Y", "X"], scenario="policy")
    for name in expected:
        expected[name] = expected[name].astype(dense(before[name]).dtypes.to_dict())
    assert_results(db, baseline, before, expected)


@pytest.mark.parametrize("kind", ["supply", "trade"])
def test_irregular_iot_updates_actual_sector_nodes(database, kind):
    source = database.matrices["baseline"]
    axis = source["S"].index.set_levels(["Sector"], level=1)
    z = pd.DataFrame(
        np.arange(len(axis) ** 2).reshape(len(axis), -1) / 100,
        index=axis,
        columns=axis,
    )
    if all(isinstance(t, pd.SparseDtype) for t in source["S"].dtypes):
        z = z.astype(pd.SparseDtype(float, 0.0))
    db = Database(
        table="IOT",
        calc_all=False,
        init_by_parsers={
            "matrices": {
                "baseline": {
                    "Z": z,
                    "Y": source["Ya"].set_axis(axis),
                    "EY": source["EY"],
                    "E": source["Ea"].set_axis(axis, axis=1),
                    "V": source["Va"].set_axis(axis, axis=1),
                }
            },
            "_indeces": {
                **{k: v for k, v in database._indeces.items() if k not in ("a", "c")},
                "s": database._indeces["a"],
            },
            "units": {
                **{
                    k: v
                    for k, v in database.units.items()
                    if k not in ("Activity", "Commodity")
                },
                "Sector": database.units["Activity"],
            },
        },
    )
    baseline, before = prepare(db)
    if kind == "supply":
        weights = {"A": 0.2, "B": 0.8}
        bundles = [("IT", [("IT", "Sector", item) for item in weights], weights)]
        expected = {
            name: reference(
                before[name],
                bundles,
                weight_level=2,
                column_predicate=lambda _, col: col[0] == "DE",
            )
            for name in ("z", "Y")
        }
        db.update_supply_mix({"IT": weights}, scenario="policy", column_regions="DE")
    else:
        weights = {"IT": 0.1, "DE": 0.9}
        bundles = [("FR", [(region, "Sector", "A") for region in weights], weights)]
        expected = {
            name: reference(
                before[name],
                bundles,
                weight_level=0,
                column_predicate=lambda dest, col: col[0] == dest,
            )
            for name in ("z", "Y")
        }
        db.update_trade_mix({"FR": weights}, items="A", scenario="policy")
    assert_results(db, baseline, before, expected)
    assert db.get_index("Sector", region="Global") == []


def test_commodity_aggregation_retains_regional_memberships(database):
    database.update_supply_mix(
        {"IT": {"A": 0.3, "B": 0.7}},
        level="Activity",
        aggregate_commodity={"combined": ["X", "Y"]},
    )
    assert database.get_index("Commodity") == {
        "IT": ["combined"],
        "DE": ["combined", "Z"],
        "FR": ["W"],
        "Global": [],
    }
    s = dense(database.query("s"))
    for col in s.columns:
        if col[2] == "combined":
            total = (
                s.loc[("IT", "Activity", "A"), col]
                + s.loc[("IT", "Activity", "B"), col]
            )
            assert s.loc[("IT", "Activity", "A"), col] == pytest.approx(total * 0.3)


def test_sparse_mix_updates_do_not_densify_blocks(database, monkeypatch):
    if not all(
        isinstance(t, pd.SparseDtype) for t in database.matrices["baseline"]["S"].dtypes
    ):
        pytest.skip("Sparse storage guard")
    original = pd.DataFrame.to_numpy

    def guarded(frame, *args, **kwargs):
        if all(isinstance(dtype, pd.SparseDtype) for dtype in frame.dtypes):
            raise AssertionError("A sparse block was converted to a dense array")
        return original(frame, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_numpy", guarded)
    database.update_supply_mix({"IT": {"A": 0.4, "B": 0.6}}, commodities="X")
    database.update_trade_mix({"FR": {"IT": 0.2, "DE": 0.8}}, items="X")
    database.update_trade_mix(
        {"FR": {"IT": 0.2, "DE": 0.8}}, items="A", commodities="W"
    )
    assert set(database.matrices["baseline"]) <= {
        "u",
        "s",
        "Yc",
        "Ya",
        "ea",
        "ec",
        "va",
        "vc",
        "EY",
        "VY",
    }
