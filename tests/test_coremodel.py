import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)

import sys
import os
import pytest
import pandas.testing as pdt
import pandas as pd

from mario.tools.constants import _ENUM, _MASTER_INDEX

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

MAIN_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from mario.core.CoreIO import CoreModel
from mario.test.mario_test import load_test
from mario.log_exc.exceptions import DataMissing, LackOfInput, WrongInput, NotImplementable
from mario import calc_Z
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

        assert set(kept) == {_ENUM.E,_ENUM.V,_ENUM.Y,_ENUM.Z,_ENUM.EY}


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

        assert set(kept) == {_ENUM.e,_ENUM.v,_ENUM.Y,_ENUM.z,_ENUM.EY}

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
        # "Satellite account": [
        #     None,  # TODO fix later
        # ],
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
    )) == {'Employment', 'Water Consumption Blue'}

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



def test__getdir(CoreDataIOT):

    assert (
        'Output/path_test/test_file.xlsx' in
        CoreDataIOT._getdir(None,'path_test','test_file.xlsx')
    )

    assert (
        'test_file.xlsx' ==
        CoreDataIOT._getdir('test_file.xlsx','path_test','test_file.xlsx')
    )


def test_directory(CoreDataIOT):

    path = f'{MAIN_PATH}/Output'

    assert path == CoreDataIOT.directory

    CoreDataIOT.directory = 'dummy'

    assert 'dummy' == CoreDataIOT.directory

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

    from mario.core.CoreIO import __cvxpy__

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
        ["all the data [Y,E,Z,V,EY,units,table] should be given." in str(msg.value) 
        for msg in [msg1,msg2,msg3]
        ]
        )


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