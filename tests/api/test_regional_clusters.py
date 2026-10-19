"""Regional cluster definitions and their expansion into real matrix nodes."""

import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from mario.ops.shocks import (
    _apply_shock,
    _fd_axis_key,
    _io_axis_key,
    check_replace_clusters,
)
from mario.ops.workbook_specs import SHOCK_COLUMNS
from mario.utils import check_clusters
from tests.api.test_regional_indexes import regional_database


@pytest.fixture
def regional():
    return regional_database(
        {"IT": ["A1", "A2"], "DE": ["A1", "A3"]},
        {"IT": ["C1"], "DE": ["C2", "C3"]},
        {"IT": ["HH"], "DE": ["HH", "GOV"]},
    )


def test_explicit_clusters_keep_regions_aliases_and_omitted_regions(regional):
    payload = {
        "activities": {"selected": {"IT": ["A2"], "DE": ["A3"]}},
        "commodities": {"italian": {"IT": ["C1"]}},
    }
    regional.set_clusters(payload)
    expected = {"Activity": payload["activities"], "Commodity": payload["commodities"]}
    assert regional.clusters == expected
    assert (
        regional.available_clusters["Activity"]["selected"]
        == expected["Activity"]["selected"]
    )
    assert regional.available_clusters["Commodity"]["italian"] == {"IT": ["C1"]}
    assert regional.available_clusters["Commodity"]["all"] == regional.get_index(
        "Commodity"
    )
    payload["activities"]["selected"]["IT"].append("changed")
    returned = regional.clusters
    returned["Activity"]["selected"]["DE"].clear()
    assert regional.clusters["Activity"]["selected"] == {"IT": ["A2"], "DE": ["A3"]}


def test_list_shorthand_is_intersected_with_each_region(regional):
    regional.set_clusters(
        {
            "Activity": {"picked": ["A1", "A2"]},
            "Consumption category": {"government": "GOV"},
        }
    )
    assert regional.clusters == {
        "Activity": {"picked": {"IT": ["A1", "A2"], "DE": ["A1"]}},
        "Consumption category": {"government": {"IT": [], "DE": ["GOV"]}},
    }


@pytest.mark.parametrize(
    "members",
    [
        {"IT": ["A3"]},
        {"missing": ["A1"]},
        {"DE": ["missing"]},
        ["A1", "missing"],
        ["IT"],
        {"IT": {"nested": ["A1"]}},
        None,
    ],
)
def test_invalid_regional_clusters_are_rejected_atomically(regional, members):
    regional.set_clusters({"Region": {"kept": ["IT"]}})
    before = regional.clusters
    with pytest.raises(WrongInput):
        regional.set_clusters({"Activity": {"invalid": members}})
    assert regional.clusters == before


def test_uniform_sets_require_lists_and_keep_legacy_arguments(regional):
    regional.set_clusters(r={"countries": ["IT", "DE"]})
    assert regional.clusters == {"Region": {"countries": ["IT", "DE"]}}
    with pytest.raises(WrongInput):
        regional.set_clusters({"Region": {"invalid": {"IT": ["IT"]}}})


def test_add_cluster_and_explicit_override_preserve_regional_definitions(regional):
    regional.set_clusters({"Region": {"kept": ["IT"]}})
    regional.add_cluster("activities", "picked", {"DE": ["A3"]})
    assert regional.clusters["Region"] == {"kept": ["IT"]}
    assert regional.clusters["Activity"]["picked"] == {"DE": ["A3"]}
    resolved = regional._resolved_clusters({"Activity": {"picked": {"IT": ["A2"]}}})
    assert resolved["Activity"]["picked"] == {"IT": ["A2"]}
    assert regional.clusters["Activity"]["picked"] == {"DE": ["A3"]}
    regional.clear_clusters()
    assert regional.clusters == {}


def test_check_clusters_validates_region_item_pairs(regional):
    indexes = regional.get_index("all")
    check_clusters(indexes, "SUT", {"Activity": {"ok": {"IT": ["A2"]}}})
    with pytest.raises(WrongInput, match="region 'DE'"):
        check_clusters(indexes, "SUT", {"Activity": {"bad": {"DE": ["A2"]}}})


def test_selectors_expand_only_actual_pairs_and_allow_empty_clusters(regional):
    domain = regional.get_index("Activity")
    axis = regional.matrices["baseline"]["U"].columns
    clusters = {"picked": {"IT": ["A2"], "DE": ["A3"]}, "empty": {"IT": []}}
    selected = check_replace_clusters("picked", domain, clusters)
    assert _io_axis_key(axis, ["IT", "DE"], MI["a"], selected) == [
        ("IT", MI["a"], "A2"),
        ("DE", MI["a"], "A3"),
    ]
    assert (
        _io_axis_key(
            axis, "DE", MI["a"], check_replace_clusters("empty", domain, clusters)
        )
        == []
    )
    literal = check_replace_clusters("A2", domain, clusters)
    with pytest.raises(WrongInput, match="selected regions"):
        _io_axis_key(axis, "DE", MI["a"], literal)
    assert _io_axis_key(axis, ["IT", "DE"], MI["a"], literal) == [("IT", MI["a"], "A2")]
    with pytest.raises(WrongInput):
        check_replace_clusters("IT", domain, clusters)


def test_final_demand_selection_supports_two_level_axes(regional):
    axis = regional.matrices["baseline"]["Yc"].columns.droplevel(1)
    assert _fd_axis_key(axis, ["IT", "DE"], {"DE": ["GOV"]}) == [("DE", "GOV")]


def numerical_database(sparse):
    database = regional_database(
        {"IT": ["A1", "A2"], "DE": ["A1", "A3"]},
        {"IT": ["C1"], "DE": ["C2", "C3"]},
        {"IT": ["HH"], "DE": ["HH", "GOV"]},
    )
    for name, value in {
        "S": 10,
        "U": 1,
        "Ya": 0.1,
        "Yc": 5,
        "Va": 2,
        "Vc": 1,
        "Ea": 3,
        "Ec": 1,
        "EY": 0.2,
    }.items():
        source = database.matrices["baseline"][name]
        frame = pd.DataFrame(float(value), index=source.index, columns=source.columns)
        if sparse:
            frame = frame.astype(pd.SparseDtype(float, 0))
        database.matrices["baseline"][name] = frame
    return database


@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("kind", ["Percentage", "Absolute", "Update"])
def test_public_u_shocks_respect_regional_clusters_and_keep_baseline(sparse, kind):
    database = numerical_database(sparse)
    before = database.query("u")
    flow = database.query("U")
    output = database.query("Xa")
    definitions = {
        "Commodity": {"picked": {"IT": ["C1"], "DE": ["C3"]}},
        "Activity": {"picked": {"IT": ["A2"], "DE": ["A1"]}},
    }
    database.set_clusters(definitions)
    sheet = pd.DataFrame(
        [("all", "picked", "all", "picked", kind, 0.2)],
        columns=[
            "Region_from",
            "Commodity_from",
            "Region_to",
            "Activity_to",
            "type",
            "value",
        ],
    )
    database.shock_calc({"u": sheet}, u=True, scenario="probe")
    expected = before.sparse.to_dense() if sparse else before.copy()
    rows = [("IT", MI["c"], "C1"), ("DE", MI["c"], "C3")]
    cols = [("IT", MI["a"], "A2"), ("DE", MI["a"], "A1")]
    if kind == "Percentage":
        expected.loc[rows, cols] *= 1.2
    elif kind == "Update":
        expected.loc[rows, cols] = 0.2
    else:
        expected.loc[rows, cols] = (flow.loc[rows, cols].to_numpy() + 0.2) / output.loc[
            cols, "production"
        ].to_numpy()
    result = database.query("u", scenarios="probe")
    assert result.index.equals(before.index) and result.columns.equals(before.columns)
    if sparse:
        assert all(isinstance(dtype, pd.SparseDtype) for dtype in result.dtypes)
    np.testing.assert_allclose(result.to_numpy(), expected.to_numpy())
    pd.testing.assert_frame_equal(database.query("u"), before)


@pytest.mark.parametrize("sparse", [False, True])
def test_final_demand_and_extension_shocks_select_region_specific_members(sparse):
    database = numerical_database(sparse)
    before = database.query("Yc")
    clusters = {
        "Commodity": {"chosen": {"DE": ["C3"]}},
        "Consumption category": {"chosen": {"IT": ["HH"], "DE": ["GOV"]}},
    }
    sheet = pd.DataFrame(
        [("all", "chosen", "all", "chosen", "Update", 4)],
        columns=[
            "Region_from",
            "Commodity_from",
            "Region_to",
            "Consumption category_to",
            "type",
            "value",
        ],
    )
    database.shock_calc({"Yc": sheet}, Yc=True, scenario="demand", clusters=clusters)
    expected = before.sparse.to_dense() if sparse else before.copy()
    expected.loc[
        [("DE", MI["c"], "C3")], [("IT", MI["n"], "HH"), ("DE", MI["n"], "GOV")]
    ] = 4
    np.testing.assert_allclose(
        database.query("Yc", scenarios="demand").to_numpy(), expected.to_numpy()
    )
    ea = database.query("ea")
    sheet = pd.DataFrame(
        [("CO2", "all", "picked", "Update", 0.2)],
        columns=["Satellite account_from", "Region_to", "Activity_to", "type", "value"],
    )
    database.shock_calc(
        {"ea": sheet},
        ea=True,
        scenario="extension",
        clusters={"Activity": {"picked": {"IT": ["A2"]}}},
    )
    expected_ea = ea.sparse.to_dense() if sparse else ea.copy()
    expected_ea.loc["CO2", ("IT", MI["a"], "A2")] = 0.2
    np.testing.assert_allclose(
        database.query("ea", scenarios="extension").to_numpy(), expected_ea.to_numpy()
    )


def test_regional_template_keeps_definitions_and_does_not_densify_blocks(
    tmp_path, monkeypatch
):
    database = numerical_database(True)
    database.set_clusters({"Activity": {"picked": {"IT": ["A2"]}}})
    before = database.clusters
    database.calc_all(["u", "s", "va", "vc", "ea", "ec"])
    original = pd.DataFrame.to_numpy

    def checked(frame, *args, **kwargs):
        if any(isinstance(dtype, pd.SparseDtype) for dtype in frame.dtypes):
            raise AssertionError("Template generation must not densify sparse blocks.")
        return original(frame, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pd.DataFrame, "to_numpy", checked)
        database.get_shock_excel(path=str(tmp_path / "regional.xlsx"), num_shock=2)
    with pd.ExcelFile(tmp_path / "regional.xlsx") as workbook:
        assert {"u", "s", "Yc", "ea", "vc", "ec"}.issubset(workbook.sheet_names)
        menus = workbook.parse("indeces", header=None)
        assert set(menus.iloc[:, 1].dropna()) == {"A1", "A2", "A3", "all", "picked"}
    assert database.clusters == before


def test_regional_shock_rejects_a_literal_code_in_the_wrong_region():
    database = numerical_database(True)
    sheet = pd.DataFrame(
        [("DE", "C1", "IT", "A1", "Update", 0.2)],
        columns=[
            "Region_from",
            "Commodity_from",
            "Region_to",
            "Activity_to",
            "type",
            "value",
        ],
    )
    with pytest.raises(WrongInput, match="selected regions"):
        database.shock_calc({"u": sheet}, u=True, scenario="invalid")
    assert "invalid" not in database.scenarios


def test_invalid_shock_clusters_do_not_leave_a_base_scenario():
    database = numerical_database(True)
    with pytest.raises(WrongInput):
        database.shock_calc(
            {},
            u=True,
            scenario="invalid",
            clusters={"Activity": {"bad": {"IT": ["A3"]}}},
        )
    assert getattr(database, "_shock_base_scenario", None) is None


@pytest.mark.parametrize("sparse", [False, True])
def test_legacy_sut_shock_workbook_expands_regional_clusters(sparse):
    database = numerical_database(sparse)
    before = database.query("u")
    sheet = pd.DataFrame(
        {
            SHOCK_COLUMNS["r_reg"]: ["all"],
            SHOCK_COLUMNS["r_lev"]: [MI["c"]],
            SHOCK_COLUMNS["r_sec"]: ["picked"],
            SHOCK_COLUMNS["c_reg"]: ["all"],
            SHOCK_COLUMNS["c_lev"]: [MI["a"]],
            SHOCK_COLUMNS["c_sec"]: ["picked"],
            SHOCK_COLUMNS["type"]: ["Update"],
            SHOCK_COLUMNS["value"]: [0.2],
        }
    )
    database.shock_calc(
        {"z": sheet},
        z=True,
        scenario="legacy",
        clusters={
            "Commodity": {"picked": {"DE": ["C2"]}},
            "Activity": {"picked": {"IT": ["A2"]}},
        },
    )
    expected = before.sparse.to_dense() if sparse else before.copy()
    expected.loc[("DE", MI["c"], "C2"), ("IT", MI["a"], "A2")] = 0.2
    np.testing.assert_allclose(
        database.query("u", scenarios="legacy").to_numpy(), expected.to_numpy()
    )


def test_absolute_shock_aligns_output_values_by_node_instead_of_position():
    columns = pd.MultiIndex.from_tuples([("IT", MI["a"], "A"), ("DE", MI["a"], "A")])
    coefficients = pd.DataFrame([[0.1, 0.1]], index=["CO2"], columns=columns)
    flows = pd.DataFrame([[1.0, 10.0]], index=coefficients.index, columns=columns)
    output = pd.DataFrame(
        {"production": [100.0, 10.0]},
        index=pd.MultiIndex.from_tuples([("DE", "A"), ("IT", "A")]),
    )
    result = _apply_shock(
        coefficients,
        ["CO2"],
        columns.tolist(),
        "Absolute",
        1.0,
        flow=flows,
        output=output,
        output_key=output.index.tolist(),
    )
    np.testing.assert_allclose(result.to_numpy(), [[0.2, 0.11]])
