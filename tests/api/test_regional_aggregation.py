"""Grouped workbook mappings operate on real regional nodes and preserve flows."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import DataMissing, WrongInput
from mario.ops.aggregation_engine import _aggregate_axis
from mario.ops.aggregation_engine import _clear_zero_output_sut_flow_overrides
from mario.ops.aggregation_inputs import classification_groups, format_regions
from tests.api.test_regional_indexes import regional_database
from tests.api.test_regional_clusters import numerical_database
from mario.test.mario_test import load_test


@pytest.fixture
def database():
    return regional_database(
        {
            "IT": ["A", "B"],
            "FR": ["B", "A"],
            "DE": ["A", "C"],
            "ES": ["A", "C"],
            "GB": ["A", "D"],
        },
        {
            "IT": ["X", "Y"],
            "FR": ["X", "Y"],
            "DE": ["X"],
            "ES": ["X", "Z"],
            "GB": ["W"],
        },
    )


def grouped(*rows):
    return pd.DataFrame(rows, columns=["Regions", "Item", "Aggregation"])


def test_groups_compare_complete_sets_not_individual_labels(database, tmp_path):
    path = tmp_path / "groups.xlsx"
    database.get_aggregation_excel(path)
    with pd.ExcelFile(path) as book:
        activity = book.parse("Activity", keep_default_na=False)
        assert activity.columns.tolist() == ["Regions", "Item", "Aggregation"]
        assert activity[["Regions", "Item"]].values.tolist() == [
            ["IT, FR", "A"],
            ["IT, FR", "B"],
            ["DE, ES", "A"],
            ["DE, ES", "C"],
            ["GB", "A"],
            ["GB", "D"],
        ]
        commodity = book.parse("Commodity", keep_default_na=False)
        assert commodity["Regions"].tolist() == [
            "IT, FR",
            "IT, FR",
            "DE",
            "ES",
            "ES",
            "GB",
        ]
        regions = book.parse("Region", keep_default_na=False)
        assert regions.columns.tolist() == ["Regions", "Region", "Aggregation"]
        assert regions[["Regions", "Region"]].values.tolist() == [
            ["IT, FR", "IT"],
            ["IT, FR", "FR"],
        ]
    database.read_aggregated_index(path, ignore_nan=True)
    assert database.get_index("Region", "aggregated")["Aggregation"].to_dict() == {
        r: r for r in database.get_index("Region")
    }
    activity = database.get_index("Activity", "aggregated")
    assert activity.index.names == ["Region", "Item"]
    assert len(activity) == 10
    assert activity.loc[("GB", "D"), "Aggregation"] == "D"


def test_region_compatibility_includes_final_demand_and_empty_groups(tmp_path):
    database = regional_database(
        {"IT": ["A"], "FR": ["A"]},
        {"IT": ["X"], "FR": ["X"]},
        {"IT": ["HH"], "FR": ["HH", "GOV"]},
    )
    path = tmp_path / "empty.xlsx"
    database.get_aggregation_excel(path)
    assert pd.read_excel(path, sheet_name="Region").empty
    database.read_aggregated_index(path, ignore_nan=True)
    assert database.get_index("Region", "aggregated")["Aggregation"].tolist() == [
        "IT",
        "FR",
    ]
    with pytest.raises(WrongInput, match="different labels"):
        database.aggregate(
            None, levels="Region", region_aggregation={"EU": ["IT", "FR"]}
        )


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_uniform_templates_keep_legacy_format_and_identity(table, tmp_path):
    database = load_test(table)
    path = tmp_path / f"{table}.xlsx"
    database.get_aggregation_excel(path)
    with pd.ExcelFile(path) as book:
        for level in database.sets:
            frame = book.parse(level, index_col=0)
            assert frame.columns.tolist() == ["Aggregation"]
            assert frame.index.fillna("None").tolist() == database.get_index(level)
    database.read_aggregated_index(path, ignore_nan=True)


def test_grouped_mapping_applies_only_to_its_group_and_keeps_singletons(database):
    source = grouped(
        ("IT, FR", "A", "AB"),
        ("IT, FR", "B", "AB"),
        ("GB", "A", "GB-total"),
        ("GB", "D", "GB-total"),
    )
    before = source.copy(deep=True)
    database.read_aggregated_index({"Activity": source}, levels="Activity")
    pd.testing.assert_frame_equal(source, before)
    mapping = database.get_index("Activity", "aggregated")["Aggregation"].to_dict()
    assert mapping[("IT", "A")] == mapping[("FR", "B")] == "AB"
    assert mapping[("DE", "A")] == "A"
    assert mapping[("ES", "C")] == "C"
    assert mapping[("GB", "D")] == "GB-total"
    assert ("GB", "B") not in mapping


@pytest.mark.parametrize(
    "frame",
    [
        grouped(("IT, DE", "A", "bad")),
        grouped(("GB", "B", "bad")),
        grouped(("IT, missing", "A", "bad")),
        grouped(("IT, IT", "A", "bad")),
        grouped(("IT, FR", "A", "ok"), ("IT", "A", "duplicate")),
        grouped(("", "A", "bad")),
    ],
)
def test_bad_grouped_inputs_rejected_without_mutating_stored_maps(database, frame):
    database.read_aggregated_index(
        {"Activity": grouped(("GB", "D", "kept"))}, levels="Activity"
    )
    before = deepcopy(database.get_index("all", "aggregated"))
    with pytest.raises(WrongInput):
        database.read_aggregated_index({"Activity": frame}, levels="Activity")
    for level, mapping in before.items():
        if mapping is not None:
            pd.testing.assert_frame_equal(
                database.get_index(level, "aggregated"), mapping
            )


def test_missing_targets_identity_and_legacy_flat_rules(database):
    frame = grouped(("GB", "A", None))
    with pytest.raises(DataMissing):
        database.read_aggregated_index({"Activity": frame}, levels="Activity")
    database.read_aggregated_index(
        {"Activity": frame}, levels="Activity", ignore_nan=True
    )
    assert (
        database.get_index("Activity", "aggregated").loc[("GB", "A"), "Aggregation"]
        == "A"
    )
    legacy = pd.DataFrame({"Aggregation": ["common-A"]}, index=["A"])
    database.read_aggregated_index({"Activity": legacy}, levels="Activity")
    mapping = database.get_index("Activity", "aggregated")["Aggregation"]
    assert all(
        mapping.loc[(r, "A")] == "common-A" for r in database.get_index("Region")
    )
    assert mapping.loc[("GB", "D")] == "D"


@pytest.mark.parametrize(
    "mapping",
    [
        {"World": ["IT", "DE"]},
        {"DE": ["IT"]},
        {"World": ["DE", "ES"]},
    ],
)
def test_incompatible_geographic_mergers_rejected_for_presets_and_templates(
    database, tmp_path, mapping
):
    with pytest.raises(WrongInput, match="different labels"):
        database.aggregate(
            None, levels="Region", region_aggregation=mapping, inplace=False
        )
    path = tmp_path / "protected.xlsx"
    path.write_bytes(b"original")
    with pytest.raises(WrongInput, match="different labels"):
        database.get_aggregation_excel(path, region_aggregation=mapping, overwrite=True)
    assert path.read_bytes() == b"original"


def test_reader_rejects_cross_group_region_targets_atomically(database):
    mappings = {
        "Activity": grouped(("GB", "D", "new-D")),
        "Region": pd.DataFrame({"Aggregation": ["World", "World"]}, index=["IT", "DE"]),
    }
    with pytest.raises(WrongInput, match="different labels"):
        database.read_aggregated_index(mappings, levels=list(mappings))
    assert database.get_index("all", "aggregated")["Activity"] is None


def test_joint_merger_uses_original_regions_and_checks_mapped_labels(database):
    region = pd.DataFrame({"Aggregation": ["EU", "EU"]}, index=["IT", "FR"])
    with pytest.raises(WrongInput, match="mapped Activity"):
        database.read_aggregated_index(
            {"Region": region, "Activity": grouped(("IT", "A", "new"))},
            levels=["Region", "Activity"],
        )
    database.read_aggregated_index(
        {"Region": region, "Activity": grouped(("IT, FR", "A", "new"))},
        levels=["Region", "Activity"],
    )
    axis = database.matrices["baseline"]["S"].index
    expected = [
        ("EU", "Activity", "new"),
        ("EU", "Activity", "B"),
        ("EU", "Activity", "B"),
        ("EU", "Activity", "new"),
    ]
    result = _aggregate_axis(
        database,
        "S",
        axis,
        side="index",
        agg_indeces=database.get_index("all", "aggregated"),
    )
    assert result.tolist()[:4] == expected
    semantic = axis.droplevel(1).set_names(["Region", "Activity"])
    result = _aggregate_axis(
        database,
        "S",
        semantic,
        side="index",
        agg_indeces=database.get_index("all", "aggregated"),
    )
    assert result.tolist()[:4] == [(r, item) for r, _, item in expected]


@pytest.mark.parametrize("sparse", [False, True])
def test_numeric_aggregation_preserves_flows_and_regional_membership(database, sparse):
    for name, block in list(database.matrices["baseline"].items()):
        values = np.arange(block.size, dtype=float).reshape(block.shape) + 1
        block = pd.DataFrame(values, index=block.index, columns=block.columns)
        if sparse:
            block = block.astype(pd.SparseDtype(float, 0))
        database.matrices["baseline"][name] = block
    mappings = {
        "Region": pd.DataFrame({"Aggregation": ["EU", "EU"]}, index=["IT", "FR"]),
        "Activity": grouped(
            ("IT, FR", "A", "AB"),
            ("IT, FR", "B", "AB"),
            ("GB", "A", "GB-total"),
            ("GB", "D", "GB-total"),
        ),
        "Commodity": grouped(("IT, FR", "X", "XY"), ("IT, FR", "Y", "XY")),
    }
    source = database.matrices["baseline"]["S"].copy()
    aggregated = database.aggregate(
        mappings, levels=list(mappings), inplace=False, calc_all=False
    )
    assert aggregated.get_index("Region") == ["EU", "DE", "ES", "GB"]
    assert aggregated.get_index("Activity") == {
        "EU": ["AB"],
        "DE": ["A", "C"],
        "ES": ["A", "C"],
        "GB": ["GB-total"],
    }
    assert aggregated.get_index("Commodity") == {
        "EU": ["XY"],
        "DE": ["X"],
        "ES": ["X", "Z"],
        "GB": ["W"],
    }
    result = aggregated.matrices["baseline"]["S"]
    assert (
        result.loc[("EU", "Activity", "AB"), ("EU", "Commodity", "XY")]
        == source.iloc[:4, :4].to_numpy().sum()
    )
    for name in ("S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"):
        before = database.matrices["baseline"][name]
        after = aggregated.matrices["baseline"][name]
        np.testing.assert_allclose(after.to_numpy().sum(), before.to_numpy().sum())
        if sparse:
            assert all(isinstance(dtype, pd.SparseDtype) for dtype in after.dtypes)
    assert aggregated.meta.region_aggregation_map["GB"] == ["GB"]
    assert aggregated.meta.region_aggregation_map["EU"] == ["IT", "FR"]
    assert aggregated.units["Activity"].index.tolist() == ["AB", "A", "C", "GB-total"]
    pd.testing.assert_frame_equal(database.matrices["baseline"]["S"], source)


def test_units_still_reject_mixing_incompatible_items(database):
    database.units["Commodity"].loc["Y", "unit"] = "kg"
    with pytest.raises(WrongInput, match="different units"):
        database.aggregate(
            {"Commodity": grouped(("IT, FR", "X", "total"), ("IT, FR", "Y", "total"))},
            levels="Commodity",
            calc_all=False,
            inplace=False,
        )


def test_quoted_region_names_and_na_labels_roundtrip(tmp_path):
    regions = ["North, coast", 'A "quoted" region', "NA"]
    database = regional_database(
        {regions[0]: ["A"], regions[1]: ["A"], "NA": ["NA", "None"]},
        {r: ["X"] for r in regions},
    )
    path = tmp_path / "quoted.xlsx"
    database.get_aggregation_excel(path)
    database.read_aggregated_index(path, ignore_nan=True)
    mapping = database.get_index("Activity", "aggregated")
    assert mapping.loc[("NA", "NA"), "Aggregation"] == "NA"
    assert mapping.loc[(regions[1], "A"), "Aggregation"] == "A"
    assert classification_groups({"IT": ["A", "B"], "FR": ["B", "A"], "GB": ["A"]}) == [
        ["IT", "FR"],
        ["GB"],
    ]
    assert format_regions(["IT", "FR"]) == "IT, FR"


def test_workbook_region_preset_preserves_grouped_item_columns(database, tmp_path):
    path = tmp_path / "items.xlsx"
    database.get_aggregation_excel(path, levels="Activity")
    database.aggregate(
        path,
        levels="Activity",
        region_aggregation={"EU": ["IT", "FR"]},
        ignore_nan=True,
        inplace=False,
        calc_all=False,
    )
    assert database.get_index("Region") == ["IT", "FR", "DE", "ES", "GB"]


def test_multiindex_input_and_partial_uniform_mapping_keep_unmapped_nodes(database):
    pairs = pd.MultiIndex.from_tuples([("GB", "D")], names=["Region", "Item"])
    database.read_aggregated_index(
        {"Activity": pd.DataFrame({"Aggregation": ["new-D"]}, index=pairs)},
        levels="Activity",
    )
    assert (
        database.get_index("Activity", "aggregated").loc[("IT", "B"), "Aggregation"]
        == "B"
    )
    uniform = load_test("SUT")
    original = uniform.get_index("Activity")
    result = uniform.aggregate(
        {"Activity": pd.DataFrame({"Aggregation": ["renamed"]}, index=original[:1])},
        levels="Activity",
        inplace=False,
        calc_all=False,
    )
    assert result.get_index("Activity") == ["renamed", *original[1:]]
    assert result.units["Activity"].index.tolist() == ["renamed", *original[1:]]


@pytest.mark.parametrize("sparse", [False, True])
def test_zero_output_cleanup_replaces_sparse_columns_without_assignment(sparse):
    activity = pd.MultiIndex.from_tuples(
        [("GB", "Activity", "A"), ("GB", "Activity", "B")]
    )
    commodity = pd.MultiIndex.from_tuples(
        [("GB", "Commodity", "X"), ("GB", "Commodity", "Y")]
    )
    matrices = {
        "Xa": pd.DataFrame([0.0, 10.0], index=activity, columns=["production"]),
        "Xc": pd.DataFrame([0.0, 10.0], index=commodity, columns=["production"]),
        "U": pd.DataFrame([[1.0, 2.0], [0.0, 3.0]], index=commodity, columns=activity),
        "S": pd.DataFrame([[1.0, 0.0], [0.0, 4.0]], index=activity, columns=commodity),
    }
    if sparse:
        for name in ("U", "S"):
            matrices[name] = matrices[name].astype(pd.SparseDtype(float, 0))
    cleared = _clear_zero_output_sut_flow_overrides(matrices)
    assert len(cleared) == 2
    np.testing.assert_array_equal(matrices["U"].to_numpy(), [[0.0, 2.0], [0.0, 3.0]])
    np.testing.assert_array_equal(matrices["S"].to_numpy(), [[0.0, 0.0], [0.0, 4.0]])
    if sparse:
        assert all(
            isinstance(dtype, pd.SparseDtype)
            for name in ("U", "S")
            for dtype in matrices[name].dtypes
        )


def test_item_harmonization_can_enable_geographic_merger_in_a_second_step(tmp_path):
    database = regional_database(
        {"IT": ["A", "B"], "DE": ["A", "C"]},
        {"IT": ["X"], "DE": ["Y"]},
    )
    mappings = {
        "Activity": grouped(
            ("IT", "A", "All"),
            ("IT", "B", "All"),
            ("DE", "A", "All"),
            ("DE", "C", "All"),
        ),
        "Commodity": grouped(("IT", "X", "Product"), ("DE", "Y", "Product")),
    }
    harmonized = database.aggregate(
        mappings, levels=list(mappings), inplace=False, calc_all=False
    )
    assert harmonized.get_index("Activity") == ["All"]
    assert harmonized.get_index("Commodity") == ["Product"]
    path = tmp_path / "harmonized.xlsx"
    harmonized.get_aggregation_excel(path, levels="Region")
    assert pd.read_excel(path, index_col=0).index.tolist() == ["IT", "DE"]
    merged = harmonized.aggregate(
        None,
        levels="Region",
        region_aggregation={"World": ["IT", "DE"]},
        inplace=False,
        calc_all=False,
    )
    assert merged.get_index("Region") == ["World"]
    assert merged.matrices["baseline"]["S"].shape == (1, 1)


@pytest.mark.parametrize("sparse", [False, True])
def test_regional_consumption_mapping_aggregates_actual_final_demand_columns(sparse):
    database = numerical_database(sparse)
    before = database.matrices["baseline"]["Yc"].to_numpy().sum()
    result = database.aggregate(
        {
            "Consumption category": grouped(
                ("IT", "HH", "Final"), ("DE", "HH", "Final"), ("DE", "GOV", "Final")
            )
        },
        levels="Consumption category",
        calc_all=False,
        inplace=False,
    )
    assert result.get_index("Consumption category") == ["Final"]
    frame = result.matrices["baseline"]["Yc"]
    assert frame.columns.tolist() == [
        ("IT", "Consumption category", "Final"),
        ("DE", "Consumption category", "Final"),
    ]
    np.testing.assert_allclose(frame.to_numpy().sum(), before)
