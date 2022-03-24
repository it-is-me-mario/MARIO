"""Tests for Database class"""


import sys
import os
import pytest
import pandas.testing as pdt
import pandas as pd

sys.path.append(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".."
    )
)

MAIN_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from mario.core.CoreIO import CoreModel
from mario.core.AttrData import Database
from mario.test.mario_test import load_test
from mario.log_exc.exceptions import (
    WrongInput,
    NotImplementable
)



@pytest.fixture()
def CoreDataIOT():

    return load_test('IOT')

@pytest.fixture()
def CoreDataSUT():

    return load_test('SUT')


def test_build_new_instance(CoreDataIOT):

    CoreDataIOT.calc_all(matrices=['X'])
    CoreDataIOT.clone_scenario(
        'baseline',
        'dummy'
    )

    dummy = CoreDataIOT.build_new_instance(
        'dummy'
    )

    assert dummy.scenarios == ['baseline']

    for k,v in dummy['baseline'].items():
        CoreDataIOT.calc_all([k],scenario='dummy')
        pdt.assert_frame_equal(
            CoreDataIOT['dummy'][k].round(0),v.round(0)
        )
 
def test_to_iot(CoreDataSUT,CoreDataIOT):

    assert CoreDataSUT.copy().to_iot('A',inplace=True) is None
    assert isinstance(CoreDataSUT.copy().to_iot('A',inplace=False),Database)

    for method in ['A','B','C','D']:
        CoreDataSUT.copy().to_iot(method)

    CoreDataSUT.clone_scenario(
        'baseline',
        'dummy'
    )
    cpy = CoreDataSUT.to_iot('A',False)

    assert CoreDataSUT.table_type == 'SUT'
    assert cpy.table_type == 'IOT'
    assert cpy.scenarios == ['baseline']

    assert cpy.sets == CoreDataIOT.sets

    for index in ['Satellite account','Factor of production','Consumption category']:
        assert set(cpy.get_index(index)) == set(CoreDataSUT.get_index(index))

    assert cpy.units.keys() == CoreDataIOT.units.keys()

def test_get_aggregation_excel(CoreDataIOT,CoreDataSUT):
    path = f'{CoreDataIOT.directory}/agg.xlsx'

    for db in [CoreDataIOT,CoreDataSUT]:
        for level in db.sets:
            db.get_aggregation_excel(path,levels=level)
            file = pd.ExcelFile(path)
            assert file.sheet_names == [level]
            pdt.assert_index_equal(
                file.parse(sheet_name=level,index_col=0).index,
                pd.Index(db.get_index(level)),
            )

        db.get_aggregation_excel(path,levels = 'all')
        file = pd.ExcelFile(path)
        assert set(file.sheet_names) == set(db.sets)

        with pytest.raises(WrongInput) as msg:
            db.get_aggregation_excel(path,levels='dummy')
        
        assert  "acceptable level/s" in str(msg.value)

