import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)

from mario.tools.sectoradd import get_corresponding_keys,matrix_concat,fill_matrix
from mario.tools.constants import _MASTER_INDEX,_ADD_SECTOR_SHEETS
from mario.tools.database_builder import MatrixBuilder
import pandas.testing as pdt
import pandas as pd
import pytest
from mario import load_test
from mario.tools.constants import _ENUM,_MASTER_INDEX

@pytest.fixture()
def CoreDataIOT():
    return load_test("IOT")

def test_get_corresponding_keys():

    # case 1, Sector
    item = _MASTER_INDEX["s"]

    keys,counter_item = get_corresponding_keys(item)

    assert counter_item == _MASTER_INDEX["s"]
    assert set(keys) == set([key for key in _ADD_SECTOR_SHEETS.keys() if key not in ["of"]])

    # case 2, Activity
    item = _MASTER_INDEX["a"]

    keys,counter_item = get_corresponding_keys(item)

    assert counter_item == _MASTER_INDEX["c"]
    assert set(keys) == set([key for key in _ADD_SECTOR_SHEETS.keys() if key not in ["sf","it"]])

    # case 3, Commodity
    item = _MASTER_INDEX["c"]

    keys,counter_item = get_corresponding_keys(item)

    assert counter_item == _MASTER_INDEX["a"]
    assert set(keys) == set([key for key in _ADD_SECTOR_SHEETS.keys() if key not in ["sf","if"]])


def test_matrix_concat():

    # Test should be global for SUT and IOT

    set_1 = MatrixBuilder(
        "IOT",
        {
            _MASTER_INDEX.s : ["sector 1"],
            _MASTER_INDEX.k : ["CO2"],
            _MASTER_INDEX.n : ["FD"],
            _MASTER_INDEX.f : ["VA"],
            _MASTER_INDEX.r : ["reg 1","reg 2"]
        }
    )

    set_2 = MatrixBuilder(
        "IOT",
        {
            _MASTER_INDEX.s : ["sector 2"],
            _MASTER_INDEX.k : ["CO2"],
            _MASTER_INDEX.n : ["FD"],
            _MASTER_INDEX.f : ["VA"],
            _MASTER_INDEX.r : ["reg 1","reg 2"]
        }
    )

    data = dict(
        Y = set_1.Y,
        z = set_1.Z,
        e = set_1.E,
        v = set_1.V,
        EY = set_1.EY,
    )

    empty_matrices = dict(
        Y = set_2.Y,
        z = set_2.Z,
        e = set_2.E,
        v = set_2.V,
        EY = set_2.EY,
    )

    matrix_concat(data,empty_matrices)

    Y_index = pd.MultiIndex.from_product(
        [["reg 1","reg 2"],[_MASTER_INDEX["s"]],["sector 1","sector 2"]]
    ).sort_values()

    pdt.assert_index_equal(Y_index,data["Y"].index)
    pdt.assert_index_equal(Y_index,data["z"].index)
    pdt.assert_index_equal(Y_index,data["z"].columns)
    pdt.assert_index_equal(Y_index,data["v"].columns)
    pdt.assert_index_equal(Y_index,data["e"].columns)

def test_fill_matrix(CoreDataIOT):
    
    # Empty matrix
    

    empty_df = MatrixBuilder(
        "IOT",
        {
            _MASTER_INDEX.s : CoreDataIOT.get_index(_MASTER_INDEX.s) + ["new_sector"],
            _MASTER_INDEX.k : CoreDataIOT.get_index(_MASTER_INDEX.k),
            _MASTER_INDEX.n : CoreDataIOT.get_index(_MASTER_INDEX.n),
            _MASTER_INDEX.f : CoreDataIOT.get_index(_MASTER_INDEX.f),
            _MASTER_INDEX.r : CoreDataIOT.get_index(_MASTER_INDEX.r),
        }
    )

    user_df = getattr(CoreDataIOT,_ENUM.Z)
    output = fill_matrix(empty_df.Z,user_df)
    output.index.names = user_df.index.names
    output.columns.names = user_df.columns.names

    pdt.assert_frame_equal(
        user_df.sort_index(axis=0).sort_index(axis=1),
        output.drop(
            labels=["new_sector"],axis=0,level=-1
            ).drop(
                labels=["new_sector"],axis=1,level=-1
                ).sort_index(axis=0).sort_index(axis=1),
                
    )

    
