import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)


import sys
import os
from numpy import eye
import pytest
import pandas.testing as pdt
import pandas as pd
from pymrio import Extension,IOSystem
import warnings
warnings.simplefilter(action='ignore')

from mario.tools.constants import _ENUM

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

MAIN_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK_PATH = f"{MAIN_PATH}/tests/mocks"

from mario.core.CoreIO import CoreModel
from mario.core.AttrData import Database
from mario.test.mario_test import load_test
from mario.log_exc.exceptions import (
    WrongInput, 
    NotImplementable,
    DataMissing
)
from mario import parse_from_excel


@pytest.fixture()
def CoreDataIOT():

    return load_test("IOT")


@pytest.fixture()
def CoreDataSUT():

    return load_test("SUT")


@pytest.fixture()
def transformated():
    return parse_from_excel(f"{MOCK_PATH}/isard_to_chennery.xlsx",table="SUT",mode="flows")


def test_is_isard(CoreDataIOT,CoreDataSUT):

    # for our load_test SUT model should:
    assert CoreDataSUT.is_isard()


    # for IOT the method is not implementable
    with pytest.raises(NotImplementable) as msg:
        CoreDataIOT.is_isard()

    assert "This test is implementable only on SUT tables" in str(msg.value)

    # for single region table, cannot be implemented
    CoreDataSUT.to_single_region("Italy")

    with pytest.raises(NotImplementable) as msg:
        CoreDataSUT.is_isard()

    assert "This test is not implementable on single-region tables" in str(msg.value)  




def test_is_chenerymoses(CoreDataIOT,CoreDataSUT):

    assert not CoreDataSUT.is_chenerymoses()

    # for IOT the method is not implementable
    with pytest.raises(NotImplementable) as msg:
        CoreDataIOT.is_chenerymoses()

    assert "This test is implementable only on SUT tables" in str(msg.value)

    # for single region table, cannot be implemented
    CoreDataSUT.to_single_region("Italy")

    with pytest.raises(NotImplementable) as msg:
        CoreDataSUT.is_chenerymoses()

    assert "This test is not implementable on single-region tables" in str(msg.value)  



def test_to_chenery_moses(CoreDataSUT,transformated):

    # test inplace= False
    new = CoreDataSUT.to_chenery_moses(inplace=False)

    print(new["baseline"][_ENUM.Z].sort_index().sort_index(axis=1))
    print(transformated["baseline"][_ENUM.Z].sort_index().sort_index(axis=1))
    pdt.assert_frame_equal(
        new["baseline"][_ENUM.Z].sort_index().sort_index(axis=1),
        transformated["baseline"][_ENUM.Z].sort_index().sort_index(axis=1)
        )

    with pytest.raises(AssertionError):
        pdt.assert_frame_equal(
            new["baseline"][_ENUM.Z].sort_index().sort_index(axis=1), 
            CoreDataSUT["baseline"][_ENUM.Z].sort_index().sort_index(axis=1)
            )
        
    # a scenario which is alreayd chennery
    CoreDataSUT.matrices["dummy"] = new["baseline"]

    with pytest.raises(NotImplementable) as msg:
        CoreDataSUT.to_chenery_moses(scenarios=["dummy"])

    assert "scenario dummy is already in Chenery-Moses format" in str(msg.value)
        
