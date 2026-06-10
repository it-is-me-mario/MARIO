import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)

import sys
import os
import pytest
import pandas.testing as pdt
import pandas as pd
from scipy import sparse
from tests._paths import REPO_ROOT

from mario.model.conventions import _ENUM, _MASTER_INDEX

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

MAIN_PATH = str(REPO_ROOT)

from mario.api.core_model import CoreModel
from mario.api import Database
from mario.test.mario_test import load_test
from mario.log_exc.exceptions import DataMissing, LackOfInput, WrongInput, NotImplementable
from mario import calc_Z
from mario.compute.sut_formulas import build_sut_c_from_S_Xa
import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)

@pytest.fixture()
def CoreDataIOT():

    return load_test("IOT")

    # return CoreModel(
    #     table = "IOT",
    #     Z = data.Z,
    #     E = data.E,
    #     V = data.V,
    #     Y = data.Y,
    #     EY = data.EY,
    #     units = data.units
    # )


@pytest.fixture()
def CoreDataSUT():

    return load_test("SUT")

    # return CoreModel(
    #     table = "SUT",
    #     Z = data.Z,
    #     E = data.E,
    #     V = data.V,
    #     Y = data.Y,
    #     EY = data.EY,
    #     units = data.units
    # )


def test_clone_scenario(CoreDataIOT):

    CoreDataIOT.clone_scenario(
        scenario = 'baseline',
        name = 'dummy'
    )

    assert set(CoreDataIOT.scenarios) == set(['baseline','dummy'])

    for matrix,value in CoreDataIOT.matrices['dummy'].items():
        pdt.assert_frame_equal(
            value,CoreDataIOT['baseline'][matrix]
        )

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.clone_scenario(
            scenario = 'baseline',
            name = 'dummy'
        )

    assert "already exists" in str(msg.value)

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.clone_scenario(
            scenario = 'another dummy',
            name = 'dummy'
        )

    assert "does not exist" in str(msg.value)


def test_rename_scenario(CoreDataIOT):

    CoreDataIOT.clone_scenario(
        scenario='baseline',
        name='dummy'
    )

    CoreDataIOT.rename_scenario('dummy', 'policy')

    assert set(CoreDataIOT.scenarios) == {'baseline', 'policy'}

    for matrix, value in CoreDataIOT['policy'].items():
        pdt.assert_frame_equal(value, CoreDataIOT['baseline'][matrix])


def test_rename_scenario_rejects_invalid_targets(CoreDataIOT):

    CoreDataIOT.clone_scenario(
        scenario='baseline',
        name='dummy'
    )

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.rename_scenario('missing', 'policy')

    assert 'does not exist' in str(msg.value)

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.rename_scenario('dummy', 'baseline')

    assert 'already exists' in str(msg.value)


def test_rename_baseline_scenario_exposes_public_alias_and_resolves_queries(CoreDataIOT):

    CoreDataIOT.rename_baseline_scenario('reference')

    assert CoreDataIOT.baseline_scenario_name == 'reference'
    assert CoreDataIOT.scenarios == ['reference']

    pdt.assert_frame_equal(
        CoreDataIOT['reference'][_ENUM.Z],
        CoreDataIOT['baseline'][_ENUM.Z],
    )
    pdt.assert_frame_equal(
        CoreDataIOT.query(_ENUM.Z, scenarios='reference'),
        CoreDataIOT.query(_ENUM.Z, scenarios='baseline'),
    )

    data = CoreDataIOT.get_data([_ENUM.Z], scenarios=['reference'], format='dict')
    assert set(data) == {'reference'}


def test_clone_and_rename_scenario_support_public_baseline_alias(CoreDataIOT):

    CoreDataIOT.rename_baseline_scenario('reference')
    CoreDataIOT.clone_scenario('reference', 'dummy')

    assert set(CoreDataIOT.scenarios) == {'reference', 'dummy'}

    CoreDataIOT.rename_scenario('baseline', 'counterfactual')

    assert CoreDataIOT.baseline_scenario_name == 'counterfactual'
    assert set(CoreDataIOT.scenarios) == {'counterfactual', 'dummy'}


def test_rename_baseline_scenario_rejects_existing_scenario_name(CoreDataIOT):

    CoreDataIOT.clone_scenario('baseline', 'dummy')

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.rename_baseline_scenario('dummy')

    assert 'already exists' in str(msg.value)


@pytest.mark.parametrize('scenario_name', ['reference', 'baseline'])
def test_renamed_baseline_scenario_supports_coremodel_accessors(CoreDataIOT, scenario_name):

    CoreDataIOT.rename_baseline_scenario('reference')
    baseline_z = CoreDataIOT['baseline'][_ENUM.Z].copy()

    assert CoreDataIOT.scenarios == ['reference']
    assert _ENUM.Z in CoreDataIOT.list_matrices(scenario=scenario_name)
    assert CoreDataIOT.has_matrix(_ENUM.Z, scenario=scenario_name)
    assert CoreDataIOT.has_block(_ENUM.Z, scenario=scenario_name)

    pdt.assert_frame_equal(
        CoreDataIOT[scenario_name][_ENUM.Z],
        baseline_z,
    )
    pdt.assert_frame_equal(
        CoreDataIOT.get_block(_ENUM.Z, scenario=scenario_name),
        baseline_z,
    )
    pdt.assert_frame_equal(
        CoreDataIOT.get_block_as_pandas(_ENUM.Z, scenario=scenario_name),
        baseline_z,
    )
    pdt.assert_frame_equal(
        CoreDataIOT.query(_ENUM.Z, scenarios=scenario_name),
        baseline_z,
    )

    data = CoreDataIOT.get_data([_ENUM.Z], scenarios=[scenario_name], format='dict')
    assert set(data) == {'reference'}
    pdt.assert_frame_equal(data['reference'][_ENUM.Z], baseline_z)

    explanation = CoreDataIOT.explain(_ENUM.X, scenario=scenario_name)
    assert explanation == CoreDataIOT.explain(_ENUM.X, scenario='baseline')
    assert _ENUM.X in explanation


@pytest.mark.parametrize('scenario_name', ['reference', 'baseline'])
def test_renamed_baseline_scenario_supports_coremodel_mutations(CoreDataIOT, scenario_name):

    CoreDataIOT.rename_baseline_scenario('reference')
    updated_z = CoreDataIOT.get_block_as_pandas(_ENUM.Z, scenario='baseline') + 1

    CoreDataIOT.set_block(_ENUM.Z, updated_z, scenario=scenario_name)

    pdt.assert_frame_equal(
        CoreDataIOT.get_block_as_pandas(_ENUM.Z, scenario='reference'),
        updated_z,
    )

    restored_z = updated_z - 1
    CoreDataIOT.update_scenarios(scenario_name, **{_ENUM.Z: restored_z})

    pdt.assert_frame_equal(
        CoreDataIOT.get_block_as_pandas(_ENUM.Z, scenario='baseline'),
        restored_z,
    )

    CoreDataIOT.calc_all(matrices=[_ENUM.X], scenario=scenario_name)

    pdt.assert_frame_equal(
        CoreDataIOT.get_block_as_pandas(_ENUM.X, scenario='reference'),
        CoreDataIOT.get_block_as_pandas(_ENUM.X, scenario='baseline'),
    )
    pdt.assert_frame_equal(CoreDataIOT.Z, restored_z)

    iterated = list(iter(CoreDataIOT))
    assert iterated[0][0] == 'reference'
    pdt.assert_frame_equal(iterated[0][1][_ENUM.Z], restored_z)


def test_renamed_baseline_scenario_supports_reset_methods(CoreDataIOT):

    CoreDataIOT.rename_baseline_scenario('reference')
    CoreDataIOT.calc_all()
    del CoreDataIOT['baseline'][_ENUM.Z]
    del CoreDataIOT['baseline'][_ENUM.E]

    CoreDataIOT.reset_to_flows('baseline')

    assert set(CoreDataIOT['reference']) == {_ENUM.E, _ENUM.V, _ENUM.Y, _ENUM.Z, _ENUM.EY, _ENUM.VY}

    CoreDataIOT.calc_all(scenario='reference')
    CoreDataIOT.reset_to_coefficients('reference')

    assert set(CoreDataIOT['baseline']) == {_ENUM.e, _ENUM.v, _ENUM.Y, _ENUM.z, _ENUM.EY, _ENUM.VY}


def test_reset_to_flows(CoreDataIOT):

    CoreDataIOT.clone_scenario(
        scenario = 'baseline',
        name = 'dummy'
    )

    # deleting the data to be sure that they will be calculated
    CoreDataIOT.calc_all()
    del CoreDataIOT['baseline'][_ENUM.Z]
    del CoreDataIOT['baseline'][_ENUM.E]

    for ss in CoreDataIOT.scenarios:
        CoreDataIOT.reset_to_flows(ss)

        kept = [*CoreDataIOT[ss]]

        assert set(kept) == {_ENUM.E,_ENUM.V,_ENUM.Y,_ENUM.Z,_ENUM.EY,_ENUM.VY}


    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.reset_to_flows('so dummy')

    assert 'Acceptable scenarios are' in str(msg.value)


def test_reset_to_flows_sut_keeps_split_blocks(CoreDataSUT):

    CoreDataSUT.calc_all([_ENUM.Z, _ENUM.Y, _ENUM.E, _ENUM.V])
    CoreDataSUT.clone_scenario(
        scenario='baseline',
        name='dummy'
    )

    del CoreDataSUT['baseline']['U']
    del CoreDataSUT['baseline']['S']

    for ss in CoreDataSUT.scenarios:
        CoreDataSUT.reset_to_flows(ss)

        kept = [*CoreDataSUT[ss]]

        assert set(kept) == {'U', 'S', 'Ea', 'Ec', 'Va', 'Vc', 'Ya', 'Yc', _ENUM.EY, _ENUM.VY}

    with pytest.raises(WrongInput) as msg:
        CoreDataSUT.reset_to_flows('so dummy')

    assert 'Acceptable scenarios are' in str(msg.value)


def test_reset_to_coefficients(CoreDataIOT):

    CoreDataIOT.clone_scenario(
        scenario='baseline',
        name = 'dummy'
    )

    for ss in CoreDataIOT.scenarios:
        CoreDataIOT.reset_to_coefficients(ss)

        kept = [*CoreDataIOT[ss]]

        assert set(kept) == {_ENUM.e,_ENUM.v,_ENUM.Y,_ENUM.z,_ENUM.EY,_ENUM.VY}

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.reset_to_coefficients('so dummy')

    assert 'Acceptable scenarios are' in str(msg.value)


def test_reset_to_coefficients_sut_keeps_split_blocks(CoreDataSUT):

    CoreDataSUT.clone_scenario(
        scenario='baseline',
        name='dummy'
    )

    for ss in CoreDataSUT.scenarios:
        CoreDataSUT.reset_to_coefficients(ss)

        kept = [*CoreDataSUT[ss]]

        assert set(kept) == {'u', 's', 'ea', 'ec', 'va', 'vc', 'Ya', 'Yc', _ENUM.EY, _ENUM.VY}

    with pytest.raises(WrongInput) as msg:
        CoreDataSUT.reset_to_coefficients('so dummy')

    assert 'Acceptable scenarios are' in str(msg.value)


def test_get_index(CoreDataIOT,CoreDataSUT):

    iot_all_index = {
        'Sector':[
            "Agriculture",
            "Industry",
            "Services",
        ],
        "Region":
        [
            "Reg1",
            "Reg2",
        ],
        "Factor of production":
        [
            "Taxes",
            "Wages",
            "Capital",
        ],
        "Satellite account": [
            "Employment",
            "CO2",
        ],
        "Consumption category":[
            "Final demand"
        ]
    }

    sut_all_index = {
        'Activity':[
            "Manufacturing",
            "Services",
        ],
        'Commodity':[
            "Goods",
            "Services",
        ],
        "Region":
        [
            "Region 1",
            "Region 2",
        ],
        "Factor of production":
        [
            "Taxes",
            "Wages",
            "Capital",
        ],
        # "Satellite account": [
        #     None,  # TODO fix later
        # ],
        "Consumption category":[
            "Final demand"
        ]
    }


    iot_index_all_from_core = CoreDataIOT.get_index('all')

    for k,v in iot_all_index.items():
        assert set(iot_index_all_from_core[k]) == set(v)
        assert set(CoreDataIOT.get_index(k)) == set(v)


    sut_index_all_from_core = CoreDataSUT.get_index('all')

    for k,v in sut_all_index.items():
        assert set(sut_index_all_from_core[k]) == set(v)
        assert set(CoreDataSUT.get_index(k)) == set(v)

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.get_index('dummy')

    assert "is not a valid index" in str(msg.value)

    assert CoreDataIOT.get_index("sector") == CoreDataIOT.get_index("Sector")
    assert CoreDataIOT.get_index("industry") == CoreDataIOT.get_index("Sector")
    assert CoreDataIOT.get_index("industries") == CoreDataIOT.get_index("Sector")
    assert CoreDataIOT.get_index("satellite_account") == CoreDataIOT.get_index("Satellite account")
    assert CoreDataIOT.get_index("satellite_accounts") == CoreDataIOT.get_index("Satellite account")
    assert CoreDataIOT.get_index("k") == CoreDataIOT.get_index("Satellite account")
    assert CoreDataIOT.get_index("consumption_category") == CoreDataIOT.get_index("Consumption category")
    assert CoreDataIOT.get_index("demand_categories") == CoreDataIOT.get_index("Consumption category")
    assert CoreDataIOT.get_index("factor_of_production") == CoreDataIOT.get_index("Factor of production")
    assert CoreDataSUT.get_index("activity") == CoreDataSUT.get_index("Activity")
    assert CoreDataSUT.get_index("c") == CoreDataSUT.get_index("Commodity")
    assert CoreDataSUT.get_index("product") == CoreDataSUT.get_index("Commodity")
    assert CoreDataSUT.get_index("products") == CoreDataSUT.get_index("Commodity")


def test_set_access_via_attributes(CoreDataIOT, CoreDataSUT):

    assert CoreDataIOT.Sector == CoreDataIOT.get_index("Sector")
    assert CoreDataIOT.industry == CoreDataIOT.get_index("Sector")
    assert CoreDataIOT.satellite_account == CoreDataIOT.get_index("Satellite account")
    assert CoreDataIOT.consumption_category == CoreDataIOT.get_index("Consumption category")
    assert CoreDataSUT.Activity == CoreDataSUT.get_index("Activity")
    assert CoreDataSUT.product == CoreDataSUT.get_index("Commodity")
    assert CoreDataSUT.factor_of_production == CoreDataSUT.get_index("Factor of production")


def test_units_accept_set_aliases_for_read_and_write(CoreDataIOT, CoreDataSUT):

    pdt.assert_frame_equal(CoreDataIOT.units["industry"], CoreDataIOT.units["Sector"])
    pdt.assert_frame_equal(CoreDataIOT.units["k"], CoreDataIOT.units["Satellite account"])
    pdt.assert_frame_equal(CoreDataSUT.units["products"], CoreDataSUT.units["Commodity"])
    pdt.assert_frame_equal(CoreDataSUT.units["factor_of_production"], CoreDataSUT.units["Factor of production"])

    updated = CoreDataIOT.units["Sector"].copy()
    updated.iloc[:, 0] = "alias-unit"
    CoreDataIOT.units["industries"] = updated

    pdt.assert_frame_equal(CoreDataIOT.units["Sector"], updated)
    pdt.assert_frame_equal(CoreDataIOT.units["industry"], updated)


def test_string_summary_shows_tech_assumption_for_sut_and_not_iot(CoreDataIOT, CoreDataSUT):

    iot_summary = str(CoreDataIOT)
    sut_summary = str(CoreDataSUT)

    assert "tech_assumption" not in iot_summary
    assert "tech_assumption = industry-based" in sut_summary


def test_change_assumption_resets_all_sut_scenarios_to_flows(CoreDataSUT):

    CoreDataSUT.reset_to_coefficients("baseline")
    CoreDataSUT.clone_scenario("baseline", "dummy")

    assert "u" in CoreDataSUT["baseline"]
    assert _ENUM.Z not in CoreDataSUT["baseline"]

    CoreDataSUT.change_assumption("PT")

    expected_keep = {'U', 'S', 'Ea', 'Ec', 'Va', 'Vc', 'Ya', 'Yc', _ENUM.EY, _ENUM.VY}

    assert CoreDataSUT.tech_assumption == "product-based"
    for scenario in CoreDataSUT.scenarios:
        assert set(CoreDataSUT[scenario]) == expected_keep
        assert "c" not in CoreDataSUT[scenario]
        assert _ENUM.s not in CoreDataSUT[scenario]
        assert _ENUM.Z not in CoreDataSUT[scenario]

    expected_c = build_sut_c_from_S_Xa(CoreDataSUT.S, CoreDataSUT.Xa, tech_assumption="PT")
    pdt.assert_frame_equal(CoreDataSUT.c, expected_c)


def test_change_assumption_is_not_supported_for_iot(CoreDataIOT):

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.change_assumption("PT")

    assert "tech_assumption is only supported for SUT databases." in str(msg.value)


def test_load_test_supports_product_based_sut():

    sut = load_test("SUT", tech_assumption="PT")

    assert sut.tech_assumption == "product-based"
    pdt.assert_frame_equal(
        sut.c,
        build_sut_c_from_S_Xa(sut.S, sut.Xa, tech_assumption="PT"),
    )


def test_scenarios(CoreDataIOT):
    CoreDataIOT.clone_scenario(
        scenario='baseline',
        name = 'dummy'
    )

    assert set(CoreDataIOT.scenarios) == {'baseline','dummy'}


def test_block_access_adapters(CoreDataIOT):

    assert CoreDataIOT.has_matrix(_ENUM.Z)
    assert _ENUM.Z in CoreDataIOT.list_matrices()

    raw = CoreDataIOT.get_block(_ENUM.Z)
    pandas_block = CoreDataIOT.get_block_as_pandas(_ENUM.Z)
    table_block = CoreDataIOT.get_block_as_table(_ENUM.Z, backend="pandas")
    dense_matrix = CoreDataIOT.get_block_as_matrix(_ENUM.Z)
    sparse_matrix = CoreDataIOT.get_block_as_matrix(
        _ENUM.Z,
        backend="scipy",
        prefer_sparse=True,
    )

    pdt.assert_frame_equal(raw, CoreDataIOT["baseline"][_ENUM.Z])
    pdt.assert_frame_equal(pandas_block, CoreDataIOT["baseline"][_ENUM.Z])
    pdt.assert_frame_equal(table_block, CoreDataIOT["baseline"][_ENUM.Z])
    assert dense_matrix.shape == CoreDataIOT.Z.shape
    assert sparse.isspmatrix_csr(sparse_matrix)
    assert sparse_matrix.shape == CoreDataIOT.Z.shape

def test_table_type(CoreDataIOT,CoreDataSUT):

    assert CoreDataIOT.table_type == "IOT"
    assert CoreDataSUT.table_type == 'SUT'

def test_is_multi_region(CoreDataIOT):

    assert CoreDataIOT.is_multi_region

    single_region = load_test('IOT').to_single_region("Reg1",inplace=False)
    assert not single_region.is_multi_region


def _build_three_region_iot_database():
    regions = ["R1", "R2", "R3"]
    sectors = ["s1"]
    factors = ["VA"]
    satellite_accounts = ["CO2"]
    final_demand = ["FD"]

    sector_axis = pd.MultiIndex.from_product(
        [regions, [_MASTER_INDEX["s"]], sectors],
        names=["Region", "Level", "Item"],
    )
    final_demand_axis = pd.MultiIndex.from_product(
        [regions, [_MASTER_INDEX["n"]], final_demand],
        names=["Region", "Level", "Item"],
    )

    Z = pd.DataFrame(
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]],
        index=sector_axis,
        columns=sector_axis,
    )
    Y = pd.DataFrame(
        [[10.0, 20.0, 30.0], [40.0, 50.0, 60.0], [70.0, 80.0, 90.0]],
        index=sector_axis,
        columns=final_demand_axis,
    )
    V = pd.DataFrame([[100.0, 200.0, 300.0]], index=factors, columns=sector_axis)
    E = pd.DataFrame([[1.0, 2.0, 3.0]], index=satellite_accounts, columns=sector_axis)
    EY = pd.DataFrame([[0.0, 0.0, 0.0]], index=satellite_accounts, columns=final_demand_axis)
    VY = pd.DataFrame([[0.0, 0.0, 0.0]], index=factors, columns=final_demand_axis)

    units = {
        _MASTER_INDEX["s"]: pd.DataFrame({"unit": ["USD"]}, index=sectors),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": ["USD"]}, index=factors),
        _MASTER_INDEX["k"]: pd.DataFrame({"unit": ["kg"]}, index=satellite_accounts),
    }

    return Database(
        name="three-region-iot",
        table="IOT",
        Z=Z,
        V=V,
        E=E,
        EY=EY,
        VY=VY,
        Y=Y,
        units=units,
        calc_all=True,
    )


def test_to_region_subset_keeps_selected_regions_explicit_and_externalizes_rest():
    database = _build_three_region_iot_database()

    subset = database.to_region_subset(["R1", "R2"], inplace=False)

    assert subset.is_multi_region
    assert subset.get_index("Region") == ["R1", "R2"]
    assert subset.V.loc["imports", ("R1", _MASTER_INDEX["s"], "s1")] == pytest.approx(7.0)
    assert subset.V.loc["imports", ("R2", _MASTER_INDEX["s"], "s1")] == pytest.approx(8.0)
    assert subset.Y.loc[
        ("R1", _MASTER_INDEX["s"], "s1"),
        ("R1", _MASTER_INDEX["n"], "Final Demand exports"),
    ] == pytest.approx(30.0)
    assert subset.Y.loc[
        ("R2", _MASTER_INDEX["s"], "s1"),
        ("R2", _MASTER_INDEX["n"], "Intermediate exports"),
    ] == pytest.approx(6.0)
    assert subset.Y.loc[
        ("R1", _MASTER_INDEX["s"], "s1"),
        ("R2", _MASTER_INDEX["n"], "Intermediate exports"),
    ] == pytest.approx(0.0)


def test_to_region_subset_by_region_keeps_exogenous_trade_by_region():
    database = _build_three_region_iot_database()

    subset = database.to_region_subset(["R1", "R2"], inplace=False, trade_mode="by_region")

    assert "imports from R3" in subset.get_index(_MASTER_INDEX["f"])
    assert subset.V.loc["imports from R3", ("R1", _MASTER_INDEX["s"], "s1")] == pytest.approx(7.0)
    assert subset.Y.loc[
        ("R1", _MASTER_INDEX["s"], "s1"),
        ("R1", _MASTER_INDEX["n"], "Final Demand exports to R3"),
    ] == pytest.approx(30.0)
    assert subset.Y.loc[
        ("R2", _MASTER_INDEX["s"], "s1"),
        ("R2", _MASTER_INDEX["n"], "Intermediate exports to R3"),
    ] == pytest.approx(6.0)


def test_to_single_region_by_region_explodes_each_excluded_region():
    database = _build_three_region_iot_database()

    single_region = database.to_single_region("R1", inplace=False, trade_mode="by_region")

    assert not single_region.is_multi_region
    assert "imports from R2" in single_region.get_index(_MASTER_INDEX["f"])
    assert "imports from R3" in single_region.get_index(_MASTER_INDEX["f"])
    assert single_region.V.loc["imports from R2", ("R1", _MASTER_INDEX["s"], "s1")] == pytest.approx(4.0)
    assert single_region.V.loc["imports from R3", ("R1", _MASTER_INDEX["s"], "s1")] == pytest.approx(7.0)
    assert single_region.Y.loc[
        ("R1", _MASTER_INDEX["s"], "s1"),
        ("R1", _MASTER_INDEX["n"], "Final Demand exports to R2"),
    ] == pytest.approx(20.0)
    assert single_region.Y.loc[
        ("R1", _MASTER_INDEX["s"], "s1"),
        ("R1", _MASTER_INDEX["n"], "Intermediate exports to R3"),
    ] == pytest.approx(3.0)


def test_to_single_region_aggregate_matches_region_subset_single_region():
    database = _build_three_region_iot_database()

    from_single = database.to_single_region("R1", inplace=False)
    from_subset = database.to_region_subset(["R1"], inplace=False)

    pdt.assert_frame_equal(from_single.Z, from_subset.Z)
    pdt.assert_frame_equal(from_single.V, from_subset.V)
    pdt.assert_frame_equal(from_single.Y, from_subset.Y)
    pdt.assert_frame_equal(from_single.E, from_subset.E)
    pdt.assert_frame_equal(from_single.EY, from_subset.EY)
    pdt.assert_frame_equal(from_single.VY, from_subset.VY)


def test_sets(CoreDataIOT,CoreDataSUT):

    assert set(CoreDataIOT.sets) == {'Sector','Region',"Consumption category","Satellite account","Factor of production"}
    assert set(CoreDataSUT.sets) == {'Activity',"Commodity",'Region',"Consumption category","Satellite account","Factor of production"}

def test_is_hybrid(CoreDataIOT,CoreDataSUT):

    assert not CoreDataIOT.is_hybrid
    assert not CoreDataSUT.is_hybrid

    cpy = CoreDataIOT.copy()
    cpy.units['Sector'].iloc[0,0] = 'dummy'
    assert  cpy.is_hybrid

    cpy = CoreDataIOT.copy()
    cpy.units['Factor of production'].iloc[0,0] = 'dummy'
    assert  cpy.is_hybrid

    cpy = CoreDataSUT.copy()
    cpy.units['Activity'].iloc[0,0] = 'dummy'
    assert  cpy.is_hybrid

    cpy = CoreDataSUT.copy()
    cpy.units['Commodity'].iloc[0,0] = 'dummy'
    assert  cpy.is_hybrid

    cpy = CoreDataSUT.copy()
    cpy.units['Factor of production'].iloc[0,0] = 'dummy'
    assert  cpy.is_hybrid


def _prepend_outer_level(frame: pd.DataFrame, outer_value, outer_name: str) -> pd.DataFrame:
    """Return a copy of frame with one extra outer index level."""
    out = frame.copy()
    if isinstance(out.index, pd.MultiIndex):
        out.index = pd.MultiIndex.from_tuples(
            [(outer_value, *idx) for idx in out.index.tolist()],
            names=[outer_name, *out.index.names],
        )
    else:
        out.index = pd.MultiIndex.from_arrays(
            [[outer_value] * len(out.index), out.index.tolist()],
            names=[outer_name, out.index.name],
        )
    return out


def test_f_ex_iot_supports_filter(CoreDataIOT):

    sat = CoreDataIOT.get_index(_MASTER_INDEX["k"])[0]
    result = CoreDataIOT.f_ex(satellite_accounts=[sat])

    e = CoreDataIOT.query(_ENUM.e)
    w = CoreDataIOT.query("w")
    expected = _prepend_outer_level(w.mul(e.loc[sat], axis=0), sat, _MASTER_INDEX["k"])

    pdt.assert_frame_equal(result, expected)


def test_fa_ex_sut_supports_filter(CoreDataSUT):

    sat = CoreDataSUT.get_index(_MASTER_INDEX["k"])[0]
    result = CoreDataSUT.fa_ex(satellite_accounts=[sat])

    ea = CoreDataSUT.query("ea")
    ec = CoreDataSUT.query("ec")
    waa = CoreDataSUT.query("waa")
    wca = CoreDataSUT.query("wca")
    expected = pd.concat(
        [
            _prepend_outer_level(waa.mul(ea.loc[sat], axis=0), sat, _MASTER_INDEX["k"]),
            _prepend_outer_level(wca.mul(ec.loc[sat], axis=0), sat, _MASTER_INDEX["k"]),
        ],
        axis=0,
    )

    pdt.assert_frame_equal(result, expected)


def test_fc_ex_sut_supports_filter(CoreDataSUT):

    sat = CoreDataSUT.get_index(_MASTER_INDEX["k"])[0]
    result = CoreDataSUT.fc_ex(satellite_accounts=[sat])

    ea = CoreDataSUT.query("ea")
    ec = CoreDataSUT.query("ec")
    s = CoreDataSUT.query("s")
    wcc = CoreDataSUT.query("wcc")
    transfer = s.dot(wcc)
    expected = pd.concat(
        [
            _prepend_outer_level(transfer.mul(ea.loc[sat], axis=0), sat, _MASTER_INDEX["k"]),
            _prepend_outer_level(wcc.mul(ec.loc[sat], axis=0), sat, _MASTER_INDEX["k"]),
        ],
        axis=0,
    )

    pdt.assert_frame_equal(result, expected)


def test_ma_ex_sut_supports_factor_filter(CoreDataSUT):

    factor = CoreDataSUT.get_index(_MASTER_INDEX["f"])[0]
    result = CoreDataSUT.ma_ex(factors=[factor])

    va = CoreDataSUT.query("va")
    vc = CoreDataSUT.query("vc")
    waa = CoreDataSUT.query("waa")
    wca = CoreDataSUT.query("wca")
    expected = pd.concat(
        [
            _prepend_outer_level(waa.mul(va.loc[factor], axis=0), factor, _MASTER_INDEX["f"]),
            _prepend_outer_level(wca.mul(vc.loc[factor], axis=0), factor, _MASTER_INDEX["f"]),
        ],
        axis=0,
    )

    pdt.assert_frame_equal(result, expected)


def test_mc_ex_sut_supports_factor_filter(CoreDataSUT):

    factor = CoreDataSUT.get_index(_MASTER_INDEX["f"])[0]
    result = CoreDataSUT.mc_ex(factors=[factor])

    va = CoreDataSUT.query("va")
    vc = CoreDataSUT.query("vc")
    s = CoreDataSUT.query("s")
    wcc = CoreDataSUT.query("wcc")
    transfer = s.dot(wcc)
    expected = pd.concat(
        [
            _prepend_outer_level(transfer.mul(va.loc[factor], axis=0), factor, _MASTER_INDEX["f"]),
            _prepend_outer_level(wcc.mul(vc.loc[factor], axis=0), factor, _MASTER_INDEX["f"]),
        ],
        axis=0,
    )

    pdt.assert_frame_equal(result, expected)


def test_p_ex_iot_returns_price_contributions(CoreDataIOT):

    result = CoreDataIOT.p_ex()

    v = CoreDataIOT.query(_ENUM.v)
    w = CoreDataIOT.query("w")
    expected = w.mul(v.sum(axis=0), axis=0)

    pdt.assert_frame_equal(result, expected)


def test_pa_ex_sut_returns_activity_side_price_contributions(CoreDataSUT):

    result = CoreDataSUT.pa_ex()

    va = CoreDataSUT.query("va")
    vc = CoreDataSUT.query("vc")
    waa = CoreDataSUT.query("waa")
    wca = CoreDataSUT.query("wca")
    expected = pd.concat(
        [
            waa.mul(va.sum(axis=0), axis=0),
            wca.mul(vc.sum(axis=0), axis=0),
        ],
        axis=0,
    )

    pdt.assert_frame_equal(result, expected)


def test_pc_ex_sut_returns_commodity_side_price_contributions(CoreDataSUT):

    result = CoreDataSUT.pc_ex()

    va = CoreDataSUT.query("va")
    vc = CoreDataSUT.query("vc")
    s = CoreDataSUT.query("s")
    wcc = CoreDataSUT.query("wcc")
    transfer = s.dot(wcc)
    expected = pd.concat(
        [
            transfer.mul(va.sum(axis=0), axis=0),
            wcc.mul(vc.sum(axis=0), axis=0),
        ],
        axis=0,
    )

    pdt.assert_frame_equal(result, expected)


def test_ex_methods_raise_on_unknown_selector(CoreDataIOT):

    with pytest.raises(WrongInput) as msg_f:
        CoreDataIOT.f_ex(satellite_accounts=["__missing__"])
    assert "Unknown satellite accounts" in str(msg_f.value)

    with pytest.raises(WrongInput) as msg_m:
        CoreDataIOT.m_ex(factors=["__missing__"])
    assert "Unknown factors of production" in str(msg_m.value)


def test_ex_methods_raise_on_wrong_table_type(CoreDataIOT, CoreDataSUT):

    with pytest.raises(WrongInput):
        CoreDataSUT.f_ex()

    with pytest.raises(WrongInput):
        CoreDataSUT.m_ex()

    with pytest.raises(WrongInput):
        CoreDataSUT.p_ex()

    with pytest.raises(WrongInput):
        CoreDataIOT.fa_ex()

    with pytest.raises(WrongInput):
        CoreDataIOT.fc_ex()

    with pytest.raises(WrongInput):
        CoreDataIOT.ma_ex()

    with pytest.raises(WrongInput):
        CoreDataIOT.mc_ex()

    with pytest.raises(WrongInput):
        CoreDataIOT.pa_ex()

    with pytest.raises(WrongInput):
        CoreDataIOT.pc_ex()


def test___eq__(CoreDataIOT,CoreDataSUT):

    assert not CoreDataIOT == CoreDataSUT
    assert CoreDataIOT == CoreDataIOT.copy()
    assert CoreDataSUT == CoreDataSUT.copy()

    cpy = CoreDataIOT.copy()
    cpy._indeces['r']['main'].append('dummy')

    assert not CoreDataIOT == cpy


def test_is_balance(CoreDataIOT,CoreDataSUT):

    # test normal balance
    for method in ['coefficients','flows','prices']:
        assert CoreDataIOT.is_balanced(method)
        if method == 'flows': # test database is not balanced with flows
            continue
        assert CoreDataSUT.is_balanced(method)

    # unbalance the data
    cpy_iot = CoreDataIOT.copy()
    getattr(cpy_iot,_ENUM.z).iloc[0,0]+=1000
    getattr(cpy_iot,_ENUM.Z).iloc[0,0]+=1000
    getattr(cpy_iot,_ENUM.p).iloc[0,0]+=1000

    cpy_sut = CoreDataSUT.copy()
    getattr(cpy_sut,_ENUM.z).iloc[0,0]+=1000
    getattr(cpy_sut,_ENUM.Z).iloc[0,0]+=1000
    getattr(cpy_sut,_ENUM.p).iloc[0,0]+=1000

    # for method in ['coefficients','flows','prices']:
    #     assert not CoreDataIOT.is_balanced(method)
    #     assert not CoreDataSUT.is_balanced(method)

    # testing as_dataframe
    assert isinstance(cpy_iot.is_balanced('coefficients',as_dataframe=True),pd.DataFrame)
    assert isinstance(cpy_sut.is_balanced('coefficients',as_dataframe=True),pd.DataFrame)

    # makeing the data hybrid
    cpy_iot = CoreDataIOT.copy()
    cpy_iot.units['Sector'].iloc[0,0]='dummy'

    cpy_sut = CoreDataSUT.copy()
    cpy_sut.units['Activity'].iloc[0,0]='dummy'

    with pytest.raises(NotImplementable) as msg:
        assert not cpy_iot.is_balanced('coefficients')
    assert "hybrid units tables" in str(msg.value)

    with pytest.raises(NotImplementable) as msg:
        assert not cpy_sut.is_balanced('coefficients')
    assert "hybrid units tables" in str(msg.value)

    # testing wrong inputs
    with pytest.raises(WrongInput) as msg:
        assert CoreDataIOT.is_balanced('dummy')

    assert "Acceptable methods are" in str(msg.value)


def test_search(CoreDataIOT):

    assert set(CoreDataIOT.search(
        item = 'Satellite account', search='mp'
    )) == {'Employment'}

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.search('dummy','dummy')

    assert "Acceptable items are" in str(msg.value)

    # test the ignore_case
    assert CoreDataIOT.search(
        item = 'Satellite account', search='employ',ignore_case=False
    ) == []

    assert CoreDataIOT.search(
        item = 'Satellite account', search='employ',ignore_case=True
    ) == ["Employment"]

    assert CoreDataIOT.search("employ") == {"Satellite account": ["Employment"]}
    assert CoreDataIOT.search("mp") == {
        "Satellite account": ["Employment"]
    }
    assert CoreDataIOT.search("satellite_account", "employ") == ["Employment"]
    assert CoreDataIOT.search("industry", "ind") == ["Industry"]
    assert CoreDataIOT.search("demand_categories", "final") == ["Final demand"]



def test__getdir(CoreDataIOT):

    assert (
        'Output/path_test/test_file.xlsx' in
        CoreDataIOT._getdir(None,'path_test','test_file.xlsx')
    )

    assert (
        'test_file.xlsx' ==
        CoreDataIOT._getdir('test_file.xlsx','path_test','test_file.xlsx')
    )


def test_directory(CoreDataIOT, tmp_path):

    path = f'{MAIN_PATH}/Output'

    assert path == CoreDataIOT.directory

    dummy_dir = tmp_path / "dummy"
    CoreDataIOT.directory = str(dummy_dir)

    assert str(dummy_dir) == CoreDataIOT.directory

    # Set impossible path
    with pytest.raises(ValueError) as msg:
        CoreDataIOT.directory = "dummy1/dummy2/dummy3/dummy4"
    
    assert "could not set the directory" in str(msg.value)


def test_cvxpy_exist():

    try:
        import cvxpy
        _cvxpy_here = True
    except ModuleNotFoundError:
        _cvxpy_here = False

    from mario.api.core_model import __cvxpy__

    assert __cvxpy__ == _cvxpy_here

def test_calc_all_failure(CoreDataIOT):
    # testing the cases that recursive process fails

    del CoreDataIOT.matrices['baseline'][_ENUM.Z]

    with pytest.raises(DataMissing) as msg:
        CoreDataIOT.calc_all([_ENUM.z])

    assert "not able to calculate" in str(msg.value)

    # non aceeptable matrix
    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.calc_all(['r'])
    
    assert "not present in acceptable item for calc_all" in str(msg.value)

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.calc_all(scenario='dummy')
    
    assert "Acceptable scenarios are" in str(msg.value)
    
def test_calc_all_overwrite(CoreDataIOT):

    CoreDataIOT.calc_all()
    old_Z = CoreDataIOT.Z

    CoreDataIOT.matrices['baseline'][_ENUM.z].iloc[0,0]+=1

    new_Z = calc_Z(getattr(CoreDataIOT,_ENUM.z),getattr(CoreDataIOT,_ENUM.X))

    CoreDataIOT.calc_all([_ENUM.Z],force_rewrite=False)

    pdt.assert_frame_equal(
        old_Z,getattr(CoreDataIOT,_ENUM.Z)
    )

    # forece rewrite
    CoreDataIOT.calc_all([_ENUM.Z],force_rewrite=True)
    pdt.assert_frame_equal(
        new_Z,getattr(CoreDataIOT,_ENUM.Z)
    )

def test_build_core_from_dfs_missing_data(CoreDataIOT):

    Y =  getattr(CoreDataIOT,_ENUM.Y)
    E =  getattr(CoreDataIOT,_ENUM.E)
    Z =  getattr(CoreDataIOT,_ENUM.Z)
    V =  getattr(CoreDataIOT,_ENUM.V)
    EY = getattr(CoreDataIOT,_ENUM.EY)
    units = CoreDataIOT.units 
    table = CoreDataIOT.table_type

    with pytest.raises(LackOfInput) as msg1:
        CoreModel(Z=Z,E=E,V=V,Y=Y,EY=EY,units=units)

    with pytest.raises(LackOfInput) as msg2:
        CoreModel(Z=Z,E=E,V=V,Y=Y,EY=EY,table=table)

    with pytest.raises(LackOfInput) as msg3:
        CoreModel(Z=Z,E=E,Y=Y,EY=EY,table=table,units=units)

    assert all(
        ["all the data [Y,E,Z,V,EY,units,table] should be given. VY is optional." in str(msg.value) 
        for msg in [msg1,msg2,msg3]
        ]
        )


def test_vy_defaults_to_zero_when_not_materialized(CoreDataIOT):

    CoreDataIOT["baseline"].pop(_ENUM.VY, None)

    expected = pd.DataFrame(
        0.0,
        index=CoreDataIOT.V.index,
        columns=CoreDataIOT.Y.columns,
    )

    pdt.assert_frame_equal(CoreDataIOT.VY, expected)


def test_core_model_init_nots(CoreDataIOT):

    notes = ['dummy note 1',"dummy note 2"]
    io = CoreModel(
        Z=getattr(CoreDataIOT,_ENUM.Z),
        V=getattr(CoreDataIOT,_ENUM.V),
        E=getattr(CoreDataIOT,_ENUM.E),
        EY=getattr(CoreDataIOT,_ENUM.EY),
        Y = getattr(CoreDataIOT,_ENUM.Y),
        units = CoreDataIOT.units,
        table = CoreDataIOT.table_type,
        notes = notes
    )

    for ii,note in enumerate(io.meta._history[-2:]):
        assert  notes[ii] in note


def test_add_note(CoreDataIOT):

    notes = ['dummy 1','dummy 2']

    CoreDataIOT.add_note(notes)

    for ii,note in enumerate(CoreDataIOT.meta._history[-2:]):
        assert notes[ii] in note

def test_update_scenarios(CoreDataIOT):
     # clone scenario 
    CoreDataIOT.clone_scenario(
         'baseline',
         'dummy'
    )

    # Wrong scenario
    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.update_scenarios(scenario='dummy_exist')
    
    assert  "Existing scenarios are" in str(msg.value)

    # passing non pd.DataFrame
    with pytest.raises(WrongInput) as msg:
        matrices= {_ENUM.v: 1}
        CoreDataIOT.update_scenarios('baseline',**matrices)
    
    assert  "items should be DataFrame" in str(msg.value)
    
    new_z = getattr(CoreDataIOT,_ENUM.z) + 1
    matrices = {_ENUM.z :  new_z}

    CoreDataIOT.update_scenarios(scenario='dummy',**matrices)

    pdt.assert_frame_equal(
        CoreDataIOT['dummy'][_ENUM.z],new_z
    )


def test_GDP(CoreDataIOT,CoreDataSUT):
    # iot
    # total
    V = CoreDataIOT['baseline'][_ENUM.V].sum().to_frame()
    GDP= V.groupby(level='Region',sort=False).sum()
    GDP.columns = ['GDP']
    pdt.assert_frame_equal(
        GDP,CoreDataIOT.GDP()
    )
    # Sectoral 
    GDP = V
    GDP.columns = ['GDP']
    GDP.index.names = ['Region',"Level",'Sector']
    GDP = GDP.droplevel("Level")


    pdt.assert_frame_equal(
        GDP,CoreDataIOT.GDP(total=False)
    )

    reg1,reg2 = CoreDataIOT.get_index('Region')

    # share
    reg1_gdp = GDP.loc[reg1]
    reg2_gdp = GDP.loc[reg2]

    reg1_share = reg1_gdp/reg1_gdp.sum().sum()
    reg2_share = reg2_gdp/reg2_gdp.sum().sum()

    GDP.loc[reg1,'Share of sector by region'] = reg1_share.values * 100
    GDP.loc[reg2,'Share of sector by region'] = reg2_share.values * 100

    pdt.assert_frame_equal(
        GDP,CoreDataIOT.GDP(total=False,share=True)
    )

    # exclude items
    # Wrong exclude
    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.GDP(exclude=['dummy'])
    
    assert "is/are not valid" in str(msg.value)

    exclude = CoreDataIOT.get_index("Factor of production")[0:2]
    V = CoreDataIOT.V.drop(exclude)
    assert all([excl not in V.index for excl in exclude])

    GDP = V.sum().to_frame().groupby(level='Region',sort=False).sum()
    GDP.columns = ['GDP']

    pdt.assert_frame_equal(
        GDP,CoreDataIOT.GDP(exclude=exclude)
    )

    # sut
    V = CoreDataSUT.V.loc[:,(slice(None),_MASTER_INDEX["a"],slice(None))]
    GDP = V.sum().to_frame('GDP').droplevel(1)
    GDP.index.names = ['Region','Activity']

    pdt.assert_frame_equal(
        GDP,CoreDataSUT.GDP(total=False)
    )
