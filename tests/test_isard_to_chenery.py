import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)


import sys
import os
from numpy import eye
import pytest
import pandas.testing as pdt
import pandas as pd
import numpy as np
from pymrio import Extension,IOSystem
import warnings
warnings.simplefilter(action='ignore')

from mario.model.conventions import _ENUM

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

MAIN_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK_PATH = f"{MAIN_PATH}/tests/mocks"

from mario.api.core_model import CoreModel
from mario.api.database import Database
from mario.test.mario_test import load_test
from mario.log_exc.exceptions import (
    WrongInput, 
    NotImplementable,
    DataMissing
)


@pytest.fixture()
def CoreDataIOT():

    return load_test("IOT")


@pytest.fixture()
def CoreDataSUT():

    return load_test("SUT")

def _sut_block(frame, row_region, col_region):
    return frame.loc[
        (row_region, slice(None), slice(None)),
        (col_region, slice(None), slice(None)),
    ]


def _collapse_rows(block):
    collapsed = block.groupby(level=[1, 2]).sum()
    collapsed.index.names = block.index.names[1:]
    return collapsed


def test_is_isard(CoreDataIOT,CoreDataSUT):

    # for our load_test SUT model should:
    assert CoreDataSUT.is_isard()


    # for IOT the method is not implementable
    with pytest.raises(NotImplementable) as msg:
        CoreDataIOT.is_isard()

    assert "This test is implementable only on SUT tables" in str(msg.value)

    # for single region table, cannot be implemented
    CoreDataSUT.to_single_region(CoreDataSUT.get_index("Region")[0])

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
    CoreDataSUT.to_single_region(CoreDataSUT.get_index("Region")[0])

    with pytest.raises(NotImplementable) as msg:
        CoreDataSUT.is_chenerymoses()

    assert "This test is not implementable on single-region tables" in str(msg.value)  



def test_to_chenery_moses(CoreDataSUT):

    new = CoreDataSUT.to_chenery_moses(inplace=False)
    regions = CoreDataSUT.get_index("Region")
    original_u = CoreDataSUT.U.copy()
    original_s = CoreDataSUT.S.copy()
    original_yc = CoreDataSUT.Yc.copy()
    original_coeff = CoreDataSUT.query("s")

    assert new.table_type == "SUT"
    assert not new.is_isard()
    assert new.is_chenerymoses()

    with pytest.raises(AssertionError):
        pdt.assert_frame_equal(new.U, original_u)

    with pytest.raises(AssertionError):
        pdt.assert_frame_equal(new.S, original_s)

    pdt.assert_frame_equal(CoreDataSUT.U, original_u)
    pdt.assert_frame_equal(CoreDataSUT.S, original_s)
    pdt.assert_frame_equal(CoreDataSUT.Yc, original_yc)

    for destination in regions:
        expected_u = _collapse_rows(CoreDataSUT.U.loc[:, (destination, slice(None), slice(None))])
        actual_u = _sut_block(new.U, destination, destination).copy()
        actual_u.index = actual_u.index.droplevel(0)
        pdt.assert_frame_equal(actual_u, expected_u)

        expected_yc = _collapse_rows(CoreDataSUT.Yc.loc[:, (destination, slice(None), slice(None))])
        actual_yc = _sut_block(new.Yc, destination, destination).copy()
        actual_yc.index = actual_yc.index.droplevel(0)
        pdt.assert_frame_equal(actual_yc, expected_yc)

    for origin in regions:
        for destination in regions:
            block_u = _sut_block(new.U, origin, destination)
            block_yc = _sut_block(new.Yc, origin, destination)

            if origin != destination:
                assert np.allclose(block_u.to_numpy(), 0.0)
                assert np.allclose(block_yc.to_numpy(), 0.0)

                imports = (
                    _sut_block(CoreDataSUT.U, origin, destination).sum(axis=1)
                    + _sut_block(CoreDataSUT.Yc, origin, destination).sum(axis=1)
                ).to_numpy()

                expected_s = (
                    _sut_block(original_coeff, origin, origin).to_numpy()
                    @ np.diag(imports)
                )
                actual_s = _sut_block(new.S, origin, destination).to_numpy()
                assert np.allclose(actual_s, expected_s)

        offdiag_exports = 0
        for destination in regions:
            if origin == destination:
                continue
            offdiag_exports = offdiag_exports + _sut_block(new.S, origin, destination).to_numpy()

        expected_domestic_supply = _sut_block(original_s, origin, origin).to_numpy() - offdiag_exports
        actual_domestic_supply = _sut_block(new.S, origin, origin).to_numpy()
        assert np.allclose(actual_domestic_supply, expected_domestic_supply)

    CoreDataSUT.matrices["dummy"] = new["baseline"]

    with pytest.raises(NotImplementable) as msg:
        CoreDataSUT.to_chenery_moses(scenarios=["dummy"])

    assert "scenario dummy is already in Chenery-Moses format" in str(msg.value)
        
