"""The public index view preserves common lists and exposes regional domains."""

from copy import deepcopy

import pandas as pd
import pytest
from scipy import sparse

from mario import Database
from mario.internal import ModelState
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from mario.test.mario_test import load_test


def regional_database(activities, commodities, demands=None, *, regions=None):
    regions = list(regions or activities)
    demands = demands or {r: ["HH"] for r in regions}
    members = {"a": activities, "c": commodities, "n": demands}
    axes = {
        kind: pd.MultiIndex.from_tuples(
            [(r, MI[kind], item) for r, items in groups.items() for item in items],
            names=[MI["r"], "Level", "Item"],
        )
        for kind, groups in members.items()
    }
    axes.update(f=pd.Index(["VA"], name="Item"), k=pd.Index(["CO2"], name="Item"))
    pairs = {
        "S": ("a", "c"),
        "U": ("c", "a"),
        "Ya": ("a", "n"),
        "Yc": ("c", "n"),
        "Va": ("f", "a"),
        "Vc": ("f", "c"),
        "Ea": ("k", "a"),
        "Ec": ("k", "c"),
        "EY": ("k", "n"),
    }
    blocks = {
        key: pd.DataFrame.sparse.from_spmatrix(
            sparse.csr_matrix((len(axes[row]), len(axes[col]))),
            index=axes[row],
            columns=axes[col],
        ).fillna(0)
        for key, (row, col) in pairs.items()
    }
    indexes = {
        code: {
            "main": list(
                dict.fromkeys(item for items in groups.values() for item in items)
            )
        }
        for code, groups in members.items()
    }
    indexes.update(r={"main": regions}, f={"main": ["VA"]}, k={"main": ["CO2"]})
    units = {
        MI[code]: pd.DataFrame({"unit": unit}, index=indexes[code]["main"])
        for code, unit in (("a", "None"), ("c", "tonnes"), ("f", "EUR"), ("k", "kg"))
    }
    return Database(
        table="SUT",
        calc_all=False,
        init_by_parsers={
            "matrices": {"baseline": blocks},
            "_indeces": indexes,
            "units": units,
        },
    )


@pytest.fixture
def regional():
    return regional_database(
        {"IT": ["A1"], "DE": ["A2", "A3"]},
        {"IT": ["C1", "C2"], "DE": ["C1"]},
        {"IT": ["HH"], "DE": ["HH", "GOV"]},
    )


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_uniform_database_keeps_exact_legacy_lists(table):
    database = load_test(table)
    from mario.model.conventions import TABLE_LEVELS

    expected = {
        name: deepcopy(database._indeces[code]["main"])
        for name, code in TABLE_LEVELS[table].items()
    }
    assert database.get_index("all") == expected
    for name, items in expected.items():
        assert type(database.get_index(name)) is list
        assert database.get_index(name) == items
        assert f"{name} = {len(items)}\n" in str(database)


def test_summary_reports_per_region_count_ranges(regional):
    summary = str(regional)
    assert "Activity = from 1 to 2 per region\n" in summary
    assert "Commodity = from 1 to 2 per region\n" in summary
    assert "Consumption category = from 1 to 2 per region\n" in summary
    assert "Region = 2\n" in summary
    assert "Factor of production = 1\n" in summary
    assert "Satellite account = 1\n" in summary
    assert repr(regional) == summary


def test_summary_includes_regions_without_members():
    database = regional_database(
        {"IT": ["A"]}, {"IT": ["C"]}, {"IT": ["HH"]}, regions=["IT", "Global"]
    )
    summary = str(database)
    for name in ("Activity", "Commodity", "Consumption category"):
        assert f"{name} = from 0 to 1 per region\n" in summary


def test_summary_of_different_regional_members_with_equal_counts():
    database = regional_database(
        {"IT": ["A1"], "DE": ["A2"]}, {"IT": ["C"], "DE": ["C"]}
    )
    assert "Activity = from 1 to 1 per region\n" in str(database)
    assert "Commodity = 1\n" in str(database)


def test_each_set_has_its_own_regional_shape(regional):
    assert regional.get_index("Activity") == {"IT": ["A1"], "DE": ["A2", "A3"]}
    assert regional.get_index("Commodity") == {"IT": ["C1", "C2"], "DE": ["C1"]}
    assert regional.get_index("Consumption category") == {
        "IT": ["HH"],
        "DE": ["HH", "GOV"],
    }
    assert regional.get_index("Region") == ["IT", "DE"]
    assert regional.get_index("Factor of production") == ["VA"]
    assert regional.get_index("Satellite account") == ["CO2"]
    assert regional.get_index("all")["Activity"] == regional.get_index("Activity")


def test_equal_counts_with_different_members_require_a_dict():
    database = regional_database(
        {"IT": ["A1"], "DE": ["A2"]}, {"IT": ["C"], "DE": ["C"]}
    )
    assert database.get_index("a") == {"IT": ["A1"], "DE": ["A2"]}
    assert database.get_index("c") == ["C"]


def test_same_members_in_different_orders_keep_legacy_order():
    database = regional_database(
        {"IT": ["B", "A"], "DE": ["A", "B"]}, {"IT": ["C"], "DE": ["C"]}
    )
    assert database.get_index("Activity") == ["B", "A"]
    assert database.get_index("Activity", region="DE") == ["A", "B"]


def test_empty_regions_are_preserved():
    database = regional_database(
        {"IT": ["A"]}, {"IT": ["C"]}, {"IT": ["HH"]}, regions=["IT", "Global"]
    )
    assert database.get_index("Activity") == {"IT": ["A"], "Global": []}
    assert database.get_index("Consumption category", region="Global") == []


def test_region_selection_and_explicit_union(regional):
    assert regional.get_index("Activity", region="DE") == ["A2", "A3"]
    assert regional.get_index("Activity", flat=True) == ["A1", "A2", "A3"]
    assert regional.get_index("all", region="IT")["Region"] == ["IT"]
    assert regional.get_index("all", flat=True)["Commodity"] == ["C1", "C2"]


def test_getter_does_not_resolve_values_or_change_storage(regional, monkeypatch):
    before = deepcopy(regional._indeces)
    blocks = tuple(regional.matrices["baseline"])
    monkeypatch.setattr(
        regional,
        "calc_all",
        lambda *a, **k: pytest.fail("get_index must not compute matrices"),
    )
    result = regional.get_index("Activity")
    result["DE"].append("unexpected")
    assert regional.get_index("Activity")["DE"] == ["A2", "A3"]
    assert regional._indeces == before
    assert tuple(regional.matrices["baseline"]) == blocks
    state = ModelState.from_database(regional)
    assert state.get_index("a") == tuple(before["a"]["main"])


def test_alias_access_uses_the_regional_view(regional):
    assert regional.get_index("activities") == regional.get_index("Activity")
    assert regional.activities == regional.get_index("Activity")


def test_aggregated_levels_are_unchanged(regional):
    frame = pd.DataFrame(
        {"Aggregation": ["AG1", "AG2", "AG2"]}, index=["A1", "A2", "A3"]
    )
    regional._indeces["a"]["aggregated"] = frame
    pd.testing.assert_frame_equal(regional.get_index("Activity", "aggregated"), frame)
    assert regional.get_index("all", "aggregated")["Commodity"] is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"region": "missing"},
        {"region": "IT", "flat": True},
        {"flat": "yes"},
        {"level": "aggregated", "flat": True},
    ],
)
def test_invalid_options_are_explicit(regional, kwargs):
    with pytest.raises(WrongInput):
        regional.get_index("Activity", **kwargs)


def test_getter_tracks_replaced_axes_without_stale_cache(regional):
    assert isinstance(regional.get_index("Activity"), dict)
    axis = pd.MultiIndex.from_tuples(
        [("IT", MI["a"], "A1"), ("DE", MI["a"], "A1")], names=[MI["r"], "Level", "Item"]
    )
    regional.matrices["baseline"]["S"] = regional.matrices["baseline"]["S"].reindex(
        index=axis, fill_value=0
    )
    assert regional.get_index("Activity") == ["A1"]


def test_native_coefficient_axes_keep_regional_members(regional):
    flows = regional.matrices["baseline"]
    regional.matrices["baseline"] = {"u": flows["U"], "s": flows["S"]}
    assert regional.get_index("Activity") == {"IT": ["A1"], "DE": ["A2", "A3"]}
    assert regional.get_index("Commodity") == {"IT": ["C1", "C2"], "DE": ["C1"]}


def test_unified_sut_axes_keep_regional_members(regional):
    unified = regional.query("Z")
    regional.matrices["baseline"] = {"Z": unified}
    assert regional.get_index("Activity") == {"IT": ["A1"], "DE": ["A2", "A3"]}
    assert regional.get_index("Commodity") == {"IT": ["C1", "C2"], "DE": ["C1"]}


def test_semantic_two_level_axes_keep_regional_members(regional):
    for block in regional.matrices["baseline"].values():
        for side in ("index", "columns"):
            axis = getattr(block, side)
            if isinstance(axis, pd.MultiIndex):
                label = axis.get_level_values(1)[0]
                setattr(block, side, axis.droplevel(1).set_names([MI["r"], label]))
    assert regional.get_index("Activity") == {"IT": ["A1"], "DE": ["A2", "A3"]}
    assert regional.get_index("Commodity", region="IT") == ["C1", "C2"]
    assert regional.get_index("Consumption category") == {
        "IT": ["HH"],
        "DE": ["HH", "GOV"],
    }


def test_irregular_iot_sector_axes_are_regional(regional):
    source = regional.matrices["baseline"]
    axis = source["S"].index.set_levels([MI["s"]], level=1)
    blocks = {
        "Z": pd.DataFrame(0.0, index=axis, columns=axis),
        "Y": source["Ya"].set_axis(axis),
        "E": source["Ea"].set_axis(axis, axis=1),
        "V": source["Va"].set_axis(axis, axis=1),
        "EY": source["EY"],
    }
    indexes = {
        k: deepcopy(v) for k, v in regional._indeces.items() if k not in ("a", "c")
    }
    indexes["s"] = deepcopy(regional._indeces["a"])
    units = {
        name: frame.copy()
        for name, frame in regional.units.items()
        if name not in (MI["a"], MI["c"])
    }
    units[MI["s"]] = regional.units[MI["a"]].copy()
    database = Database(
        table="IOT",
        calc_all=False,
        init_by_parsers={
            "matrices": {"baseline": blocks},
            "_indeces": indexes,
            "units": units,
        },
    )
    assert database.get_index("Sector") == {"IT": ["A1"], "DE": ["A2", "A3"]}
    assert database.get_index("Sector", flat=True) == ["A1", "A2", "A3"]
    assert "Sector = from 1 to 2 per region\n" in str(database)


def test_explicit_regional_extension_axes_are_detected(regional):
    rows = pd.MultiIndex.from_tuples(
        [("IT", "tax"), ("DE", "labour")], names=[MI["r"], MI["f"]]
    )
    regional.matrices["baseline"]["Va"] = pd.DataFrame(
        0.0, index=rows, columns=regional.matrices["baseline"]["S"].index
    )
    regional._indeces["f"]["main"] = ["tax", "labour"]
    assert regional.get_index("Factor of production") == {
        "IT": ["tax"],
        "DE": ["labour"],
    }
