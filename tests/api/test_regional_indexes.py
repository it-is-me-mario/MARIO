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
    assert database.search("Activity", "") == ["B", "A"]
    assert database.search("Activity", "", region="DE") == ["A", "B"]


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


def test_search_groups_regional_matches_and_omits_regions_without_matches(regional):
    assert regional.search("Activity", "^A") == {
        "IT": ["A1"],
        "DE": ["A2", "A3"],
    }
    assert regional.search("Activity", "^A2$") == {"DE": ["A2"]}
    assert regional.search("Activity", "missing") == {}
    assert regional.search("Activity", "^IT$") == {}


def test_search_keeps_regional_shape_when_matching_lists_are_equal(regional):
    assert regional.search("Commodity", "^C1$") == {"IT": ["C1"], "DE": ["C1"]}


def test_search_explicit_union_is_ordered_and_deduplicated(regional):
    assert regional.search("Commodity", "^C", flat=True) == ["C1", "C2"]
    assert regional.search("Commodity", "^C1$", flat=True) == ["C1"]
    assert regional.search("Activity", "missing", flat=True) == []


def test_search_can_select_a_region(regional):
    assert regional.search("Activity", "^A", region="DE") == ["A2", "A3"]
    assert regional.search("Commodity", "^C2$", region="DE") == []
    assert regional.search("Factor of production", "^VA$", region="IT") == ["VA"]
    assert regional.search("Region", "^IT$", region="DE") == []


def test_search_empty_regions_and_global_sets_keep_their_result_types():
    database = regional_database(
        {"IT": ["A"]}, {"IT": ["C"]}, {"IT": ["HH"]}, regions=["IT", "Global"]
    )
    assert database.search("Activity", "A") == {"IT": ["A"]}
    assert database.search("Activity", "A", region="Global") == []
    assert database.search("Factor of production", "VA") == ["VA"]
    assert database.search("Factor of production", "missing") == []


def test_search_preserves_aliases_regex_and_positional_case_flag(regional):
    expected = {"IT": ["A1"], "DE": ["A3"]}
    assert regional.search("a", "^a[13]$", True) == expected
    assert regional.search("activities", "^a[13]$", False) == {}
    assert regional.search("activities", "^a[13]$", region="DE") == ["A3"]
    assert regional.search("commodities", "^C1$", flat=True) == ["C1"]


def test_global_search_groups_by_set_then_region(regional):
    assert regional.search("^A") == {"Activity": {"IT": ["A1"], "DE": ["A2", "A3"]}}
    assert regional.search(search="^C1$") == {"Commodity": {"IT": ["C1"], "DE": ["C1"]}}
    assert regional.search("^CO2$") == {"Satellite account": ["CO2"]}
    assert regional.search("^IT$") == {"Region": ["IT"]}
    assert regional.search("missing") == {}


def test_global_search_supports_region_and_union_options(regional):
    assert regional.search("^C1$", flat=True) == {"Commodity": ["C1"]}
    assert regional.search("^A", region="DE") == {"Activity": ["A2", "A3"]}
    assert regional.search("^IT$", region="DE") == {}


@pytest.mark.parametrize("item", [None, "Activity"])
@pytest.mark.parametrize(
    "options",
    [
        {"region": "missing"},
        {"flat": "yes"},
        {"flat": 0},
        {"region": "IT", "flat": True},
    ],
)
def test_search_rejects_invalid_selection_options(regional, item, options):
    with pytest.raises(WrongInput):
        regional.search(item=item, search="missing", **options)


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_uniform_search_preserves_list_outputs_and_order(table):
    database = load_test(table)
    name = "Sector" if table == "IOT" else "Activity"
    members = database.get_index(name)
    assert database.search(name, "") == members
    assert database.search(name, "", flat=True) == members
    region = database.get_index("Region")[0]
    assert database.search(name, "", region=region) == database.get_index(
        name, region=region
    )
    assert database.search("") == database.get_index("all")


def test_search_does_not_mutate_storage_or_materialize_blocks(regional, monkeypatch):
    before = deepcopy(regional._indeces)
    blocks = tuple(regional.matrices["baseline"])
    monkeypatch.setattr(
        regional,
        "calc_all",
        lambda *a, **k: pytest.fail("search must not compute matrices"),
    )
    found = regional.search("Activity", "^A")
    found["DE"].append("unexpected")
    assert regional.search("Activity", "^A3$") == {"DE": ["A3"]}
    assert regional.search("Activity", "unexpected") == {}
    assert regional._indeces == before
    assert tuple(regional.matrices["baseline"]) == blocks


def test_default_clusters_preserve_each_sets_regional_shape(regional):
    defaults = regional.default_clusters
    assert set(defaults) == set(regional.sets)
    assert {name: clusters["all"] for name, clusters in defaults.items()} == {
        "Activity": {"IT": ["A1"], "DE": ["A2", "A3"]},
        "Commodity": {"IT": ["C1", "C2"], "DE": ["C1"]},
        "Consumption category": {"IT": ["HH"], "DE": ["HH", "GOV"]},
        "Region": ["IT", "DE"],
        "Factor of production": ["VA"],
        "Satellite account": ["CO2"],
    }


def test_default_clusters_preserve_regional_axis_order(regional):
    regional._indeces["c"]["main"] = ["C2", "C1"]
    assert regional.default_clusters["Commodity"]["all"] == {
        "IT": ["C1", "C2"],
        "DE": ["C1"],
    }


def test_default_clusters_do_not_create_members_in_empty_regions():
    database = regional_database(
        {"IT": ["A"]}, {"IT": ["C"]}, {"IT": ["HH"]}, regions=["IT", "Global"]
    )
    defaults = database.default_clusters
    assert defaults["Activity"]["all"] == {"IT": ["A"], "Global": []}
    assert defaults["Consumption category"]["all"] == {"IT": ["HH"], "Global": []}
    assert defaults["Region"]["all"] == ["IT", "Global"]
    assert database.get_index("Activity", region="Global") == []


def test_default_clusters_are_independent_and_do_not_compute(regional, monkeypatch):
    before = deepcopy(regional._indeces)
    blocks = tuple(regional.matrices["baseline"])
    monkeypatch.setattr(
        regional,
        "calc_all",
        lambda *a, **k: pytest.fail("default_clusters must not compute matrices"),
    )
    defaults = regional.default_clusters
    defaults["Activity"]["all"]["IT"].append("unexpected")
    assert regional.default_clusters["Activity"]["all"] == {
        "IT": ["A1"],
        "DE": ["A2", "A3"],
    }
    assert regional._indeces == before
    assert tuple(regional.matrices["baseline"]) == blocks


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_default_clusters_preserve_uniform_set_lists(table):
    database = load_test(table)
    defaults = database.default_clusters
    for name in database.sets:
        assert defaults[name]["all"] == database.get_index(name)


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


@pytest.mark.parametrize("code,block", [("f", "Va"), ("k", "Ea")])
@pytest.mark.parametrize("global_scope", ["TOTAL", "WORLD"])
def test_mixed_global_and_regional_extension_scopes_keep_complete_lists(
    regional, code, block, global_scope, monkeypatch
):
    label = MI[code]
    catalog = ["regional", "global_only", "shared"]
    rows = pd.MultiIndex.from_tuples(
        [
            ("IT", "regional"),
            ("DE", "shared"),
            (global_scope, "global_only"),
            (global_scope, "shared"),
        ],
        names=[MI["r"], label],
    )
    regional._indeces[code]["main"] = catalog.copy()
    regional.matrices["baseline"][block] = pd.DataFrame(
        0.0, index=rows, columns=regional.matrices["baseline"][block].columns
    )
    before = deepcopy(regional._indeces)
    block_names = tuple(regional.matrices["baseline"])
    monkeypatch.setattr(
        regional, "calc_all", lambda *a, **k: pytest.fail("Getter must not compute")
    )
    assert regional.get_index(label) == catalog
    assert regional.get_index(label, flat=True) == catalog
    assert regional.get_index(label, region="IT") == catalog
    assert regional.get_index("all")[label] == catalog
    assert regional.search(label, "global_only") == ["global_only"]
    assert regional.default_clusters[label]["all"] == catalog
    regional.get_index(label).append("unexpected")
    assert regional._indeces == before
    assert tuple(regional.matrices["baseline"]) == block_names
