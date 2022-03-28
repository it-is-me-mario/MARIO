import sys
import os
import pytest
import pandas.testing as pdt
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

MAIN_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from mario.core.CoreIO import CoreModel
from mario.test.mario_test import load_test
from mario.log_exc.exceptions import WrongInput, NotImplementable


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


# def test_clone_scenario(CoreDataIOT):

#     CoreDataIOT.clone_scenario(
#         scenario = 'baseline',
#         name = 'dummy'
#     )

#     assert set(CoreDataIOT.scenarios) == set(['baseline','dummy'])

#     for matrix,value in CoreDataIOT.matrices['dummy'].items():
#         pdt.assert_frame_equal(
#             value,CoreDataIOT['baseline'][matrix]
#         )

#     with pytest.raises(WrongInput) as msg:
#         CoreDataIOT.clone_scenario(
#             scenario = 'baseline',
#             name = 'dummy'
#         )

#     assert "already exists" in str(msg.value)

#     with pytest.raises(WrongInput) as msg:
#         CoreDataIOT.clone_scenario(
#             scenario = 'another dummy',
#             name = 'dummy'
#         )

#     assert "does not exist" in str(msg.value)


# def test_reset_to_flows(CoreDataIOT):

#     CoreDataIOT.clone_scenario(
#         scenario = 'baseline',
#         name = 'dummy'
#     )

#     for ss in CoreDataIOT.scenarios:
#         CoreDataIOT.reset_to_flows(ss)

#         kept = [*CoreDataIOT[ss]]

#         assert set(kept) == {'E','V','Y','Z','EY'}


#     with pytest.raises(WrongInput) as msg:
#         CoreDataIOT.reset_to_flows('so dummy')

#     assert 'Acceptable scenarios are' in str(msg.value)


# def test_reset_to_coefficients(CoreDataIOT):

#     CoreDataIOT.clone_scenario(
#         scenario='baseline',
#         name = 'dummy'
#     )

#     for ss in CoreDataIOT.scenarios:
#         CoreDataIOT.reset_to_coefficients(ss)

#         kept = [*CoreDataIOT[ss]]

#         assert set(kept) == {'e','v','Y','z','EY'}

#     with pytest.raises(WrongInput) as msg:
#         CoreDataIOT.reset_to_coefficients('so dummy')

#     assert 'Acceptable scenarios are' in str(msg.value)


# def test_get_index(CoreDataIOT,CoreDataSUT):

#     iot_all_index = {
#         'Sector':[
#             "Agriculture",
#             "Mining",
#             "Manufacturing",
#             "Services",
#             "Construction",
#             "Transport",
#         ],
#         "Region":
#         [
#             'Italy',
#             "RoW"
#         ],
#         "Factor of production":
#         [
#             "Taxes",
#             "Wages",
#             "Capital",
#         ],
#         "Satellite account": [
#             "Employment",
#             "CO2",
#             "Water Consumption Blue",
#             "Energy",
#         ],
#         "Consumption category":[
#             "Final Demand"
#         ]
#     }

#     sut_all_index = {
#         'Activity':[
#             "Agriculture",
#             "Mining",
#             "Manufacturing",
#             "Services",
#             "Construction",
#             "Transport",
#         ],
#         'Commodity':[
#             "Agriculture",
#             "Mining",
#             "Manufacturing",
#             "Services",
#             "Construction",
#             "Transport",
#         ],
#         "Region":
#         [
#             'Italy',
#             "RoW"
#         ],
#         "Factor of production":
#         [
#             "Taxes",
#             "Wages",
#             "Capital",
#         ],
#         "Satellite account": [
#             "None",
#         ],
#         "Consumption category":[
#             "Final Demand"
#         ]
#     }


#     iot_index_all_from_core = CoreDataIOT.get_index('all')

#     for k,v in iot_all_index.items():
#         assert set(iot_index_all_from_core[k]) == set(v)
#         assert set(CoreDataIOT.get_index(k)) == set(v)


#     sut_index_all_from_core = CoreDataSUT.get_index('all')

#     for k,v in sut_all_index.items():
#         assert set(sut_index_all_from_core[k]) == set(v)
#         assert set(CoreDataSUT.get_index(k)) == set(v)

#     with pytest.raises(WrongInput) as msg:
#         CoreDataIOT.get_index('dummy')

#     assert "is not a valid index" in str(msg.value)

#     with pytest.raises(WrongInput) as msg:
#         CoreDataIOT.get_index('Sector','aggregated')

#     assert "is not a valid level" in str(msg.value)


# def test_scenarios(CoreDataIOT):
#     CoreDataIOT.clone_scenario(
#         scenario='baseline',
#         name = 'dummy'
#     )

#     assert set(CoreDataIOT.scenarios) == {'baseline','dummy'}

# def test_table_type(CoreDataIOT,CoreDataSUT):

#     assert CoreDataIOT.table_type == "IOT"
#     assert CoreDataSUT.table_type == 'SUT'

# def test_is_multi_region(CoreDataIOT):

#     assert CoreDataIOT.is_multi_region

#     single_region = load_test('IOT').to_single_region("Italy",inplace=False)
#     assert not single_region.is_multi_region


# def test_sets(CoreDataIOT,CoreDataSUT):

#     assert set(CoreDataIOT.sets) == {'Sector','Region',"Consumption category","Satellite account","Factor of production"}
#     assert set(CoreDataSUT.sets) == {'Activity',"Commodity",'Region',"Consumption category","Satellite account","Factor of production"}

# def test_is_hybrid(CoreDataIOT,CoreDataSUT):

#     assert not CoreDataIOT.is_hybrid
#     assert not CoreDataSUT.is_hybrid

#     cpy = CoreDataIOT.copy()
#     cpy.units['Sector'].iloc[0,0] = 'dummy'
#     assert  cpy.is_hybrid

#     cpy = CoreDataIOT.copy()
#     cpy.units['Factor of production'].iloc[0,0] = 'dummy'
#     assert  cpy.is_hybrid

#     cpy = CoreDataSUT.copy()
#     cpy.units['Activity'].iloc[0,0] = 'dummy'
#     assert  cpy.is_hybrid

#     cpy = CoreDataSUT.copy()
#     cpy.units['Commodity'].iloc[0,0] = 'dummy'
#     assert  cpy.is_hybrid

#     cpy = CoreDataSUT.copy()
#     cpy.units['Factor of production'].iloc[0,0] = 'dummy'
#     assert  cpy.is_hybrid


# def test___eq__(CoreDataIOT,CoreDataSUT):

#     assert not CoreDataIOT == CoreDataSUT
#     assert CoreDataIOT == CoreDataIOT.copy()
#     assert CoreDataSUT == CoreDataSUT.copy()

#     cpy = CoreDataIOT.copy()
#     cpy._indeces['r']['main'].append('dummy')

#     assert not CoreDataIOT == cpy


# def test_is_balance(CoreDataIOT,CoreDataSUT):

#     # test normal balance
#     for method in ['coefficients','flows','prices']:
#         assert CoreDataIOT.is_balanced(method)
#         if method == 'flows': # test database is not balanced with flows
#             continue
#         assert CoreDataSUT.is_balanced(method)

#     # unbalance the data
#     cpy_iot = CoreDataIOT.copy()
#     cpy_iot.z.iloc[0,0]+=1000
#     cpy_iot.Z.iloc[0,0]+=1000
#     cpy_iot.p.iloc[0,0]+=1000

#     cpy_sut = CoreDataSUT.copy()
#     cpy_sut.z.iloc[0,0]+=1000
#     cpy_sut.Z.iloc[0,0]+=1000
#     cpy_sut.p.iloc[0,0]+=1000

#     # for method in ['coefficients','flows','prices']:
#     #     assert not CoreDataIOT.is_balanced(method)
#     #     assert not CoreDataSUT.is_balanced(method)

#     # testing as_dataframe
#     assert isinstance(cpy_iot.is_balanced('coefficients',as_dataframe=True),pd.DataFrame)
#     assert isinstance(cpy_sut.is_balanced('coefficients',as_dataframe=True),pd.DataFrame)

#     # makeing the data hybrid
#     cpy_iot = CoreDataIOT.copy()
#     cpy_iot.units['Sector'].iloc[0,0]='dummy'

#     cpy_sut = CoreDataSUT.copy()
#     cpy_sut.units['Activity'].iloc[0,0]='dummy'

#     with pytest.raises(NotImplementable) as msg:
#         assert not cpy_iot.is_balanced('coefficients')
#     assert "hybrid units tables" in str(msg.value)

#     with pytest.raises(NotImplementable) as msg:
#         assert not cpy_sut.is_balanced('coefficients')
#     assert "hybrid units tables" in str(msg.value)

#     # testing wrong inputs
#     with pytest.raises(WrongInput) as msg:
#         assert CoreDataIOT.is_balanced('dummy')

#     assert "Acceptable methods are" in str(msg.value)


# def test_search(CoreDataIOT):

#     assert set(CoreDataIOT.search(
#         item = 'Satellite account', search='mp'
#     )) == {'Employment', 'Water Consumption Blue'}

#     with pytest.raises(WrongInput) as msg:
#         CoreDataIOT.search('dummy','dummy')

#     assert "Acceptable items are" in str(msg.value)

# def test__getdir(CoreDataIOT):

#     assert (
#         'Output/path_test/test_file.xlsx' in
#         CoreDataIOT._getdir(None,'path_test','test_file.xlsx')
#     )

#     assert (
#         'test_file.xlsx' ==
#         CoreDataIOT._getdir('test_file.xlsx','path_test','test_file.xlsx')
#     )

# def test_directory(CoreDataIOT):

#     path = f'{MAIN_PATH}/Output'

#     assert path == CoreDataIOT.directory

#     CoreDataIOT.directory = 'dummy'

#     assert 'dummy' == CoreDataIOT.directory
