"""Database equality compares regional classifications and retains legacy scope."""

import pytest

from mario.model.conventions import TABLE_LEVELS
from mario.test.mario_test import load_test
from tests.api.test_regional_indexes import regional_database


@pytest.mark.parametrize("level", ["Activity", "Commodity", "Consumption category"])
def test_same_regions_and_global_union_do_not_hide_changed_membership(level):
    domains = {
        "Activity": {"IT": ["A", "B"], "DE": ["A", "C"]},
        "Commodity": {"IT": ["X", "Y"], "DE": ["X", "Z"]},
        "Consumption category": {"IT": ["HH", "INV"], "DE": ["HH", "GOV"]},
    }
    original = regional_database(*domains.values())
    changed_domains = dict(domains)
    changed_domains[level] = {"IT": domains[level]["DE"], "DE": domains[level]["IT"]}
    changed = regional_database(*changed_domains.values())
    assert original.get_index("Region") == changed.get_index("Region")
    assert set(original.get_index(level, flat=True)) == set(
        changed.get_index(level, flat=True)
    )
    assert {r: len(v) for r, v in original.get_index(level).items()} == {
        r: len(v) for r, v in changed.get_index(level).items()
    }
    assert original != changed
    assert changed != original
    assert not (original == changed)


def test_region_and_member_order_do_not_affect_equality():
    original = regional_database(
        {"IT": ["A", "B"], "DE": ["A", "C"]},
        {"IT": ["X", "Y"], "DE": ["X"]},
        {"IT": ["HH"], "DE": ["HH", "GOV"]},
    )
    reordered = regional_database(
        {"DE": ["C", "A"], "IT": ["B", "A"]},
        {"DE": ["X"], "IT": ["Y", "X"]},
        {"DE": ["GOV", "HH"], "IT": ["HH"]},
    )
    assert original == original
    assert original == original.copy()
    assert original == reordered
    assert reordered == original
    assert not (original != reordered)


def test_members_cannot_move_into_an_empty_region_without_changing_equality():
    original = regional_database({"IT": ["A"], "DE": []}, {"IT": ["X"], "DE": ["X"]})
    changed = regional_database({"IT": [], "DE": ["A"]}, {"IT": ["X"], "DE": ["X"]})
    assert original.get_index("Activity", flat=True) == changed.get_index(
        "Activity", flat=True
    )
    assert original != changed
    assert changed != original


def test_uniform_and_regional_memberships_with_the_same_union_are_different():
    common = regional_database(
        {"IT": ["A", "B"], "DE": ["A", "B"]}, {"IT": ["X"], "DE": ["X"]}
    )
    regional = regional_database(
        {"IT": ["A", "B"], "DE": ["A"]}, {"IT": ["X"], "DE": ["X"]}
    )
    assert type(common.get_index("Activity")) is list
    assert type(regional.get_index("Activity")) is dict
    assert common.get_index("Activity", flat=True) == regional.get_index(
        "Activity", flat=True
    )
    assert common != regional
    assert regional != common


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_uniform_databases_still_compare_lists_without_order(table):
    original = load_test(table)
    reordered = original.copy()
    for code in TABLE_LEVELS[table].values():
        reordered._indeces[code]["main"].reverse()
    assert original == reordered
    assert reordered == original
    assert not (original != reordered)


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_equality_keeps_its_existing_index_only_scope(table):
    original = load_test(table)
    changed = original.copy()
    name = "Z" if table == "IOT" else "U"
    block = changed.query(name)
    changed.matrices["baseline"][name] = block * 2
    assert not block.equals(changed.matrices["baseline"][name])
    assert original == changed
    assert changed == original


def test_different_table_sets_are_still_different():
    assert load_test("IOT") != load_test("SUT")
