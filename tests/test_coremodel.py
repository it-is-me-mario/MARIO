import ssl
import sys
import os
import pytest
import pandas.testing as pdt

sys.path.append(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".."
    )
)

from mario.core.CoreIO import CoreModel
from mario.test.mario_test import load_test
from mario.log_exc.exceptions import (
    WrongInput
)



@pytest.fixture()
def CoreDataIOT():

    data = load_test('IOT')

    return CoreModel(
        table = "IOT",
        Z = data.Z,
        E = data.E,
        V = data.V,
        Y = data.Y,
        EY = data.EY,
        units = data.units
    )    

@pytest.fixture()
def CoreDataSUT():

    data = load_test('SUT')

    return CoreModel(
        table = "SUT",
        Z = data.Z,
        E = data.E,
        V = data.V,
        Y = data.Y,
        EY = data.EY,
        units = data.units
    )    


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


def test_reset_to_flows(CoreDataIOT):

    CoreDataIOT.clone_scenario(
        scenario = 'baseline',
        name = 'dummy'
    )

    for ss in CoreDataIOT.scenarios:
        CoreDataIOT.reset_to_flows(ss)

        kept = [*CoreDataIOT[ss]]

        assert set(kept) == {'E','V','Y','Z','EY'}


    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.reset_to_flows('so dummy')

    assert 'Acceptable scenarios are' in str(msg.value)


def test_reset_to_coefficients(CoreDataIOT):

    CoreDataIOT.clone_scenario(
        scenario='baseline',
        name = 'dummy'
    )

    for ss in CoreDataIOT.scenarios:
        CoreDataIOT.reset_to_coefficients(ss)

        kept = [*CoreDataIOT[ss]]

        assert set(kept) == {'e','v','Y','z','EY'}

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.reset_to_coefficients('so dummy')

    assert 'Acceptable scenarios are' in str(msg.value)


def test_get_index(CoreDataIOT,CoreDataSUT):
    
    iot_all_index = {
        'Sector':[
            "Agriculture",
            "Mining",
            "Manufacturing",
            "Services",
            "Construction",
            "Transport",
        ],
        "Region":
        [
            'Italy',
            "RoW"
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
            "Water Consumption Blue",
            "Energy",
        ],
        "Consumption category":[
            "Final Demand"
        ]
    }
    
    sut_all_index = {
        'Activity':[
            "Agriculture",
            "Mining",
            "Manufacturing",
            "Services",
            "Construction",
            "Transport",
        ],
        'Commodity':[
            "Agriculture",
            "Mining",
            "Manufacturing",
            "Services",
            "Construction",
            "Transport",
        ],
        "Region":
        [
            'Italy',
            "RoW"
        ],
        "Factor of production":
        [
            "Taxes",
            "Wages",
            "Capital",
        ],
        "Satellite account": [
            "None",
        ],
        "Consumption category":[
            "Final Demand"
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

    with pytest.raises(WrongInput) as msg:
        CoreDataIOT.get_index('Sector','aggregated')

    assert "is not a valid level" in str(msg.value)


def test_scenarios(CoreDataIOT):
    CoreDataIOT.clone_scenario(
        scenario='baseline',
        name = 'dummy'
    )

    assert set(CoreDataIOT.scenarios) == {'baseline','dummy'}

def test_table_type(CoreDataIOT,CoreDataSUT):

    assert CoreDataIOT.table_type == "IOT"
    assert CoreDataSUT.table_type == 'SUT'

def test_is_multi_region(CoreDataIOT):

    assert CoreDataIOT.is_multi_region

    single_region = load_test('IOT').to_single_region("Italy",inplace=False)
    assert not single_region.is_multi_region


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
