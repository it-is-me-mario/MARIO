
import pytest
import pandas.testing as pdt
import numpy.testing as npt
import os
import sys

import pandas as pd
import numpy as np


sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mario.tools import utilities as ut
from mario import load_test
from mario.tools.constants import _INDEX_NAMES
@pytest.fixture()
def CoreDataIOT():

    return load_test("IOT")


@pytest.fixture()
def CoreDataSUT():

    return load_test("SUT")

def test_slicer(CoreDataIOT,CoreDataSUT):

    sl = ut.slicer(matrix='E',axis=1,Region=['Italy'],Item=['Transport',"Manufacturing"])

    pdt.assert_frame_equal(
        CoreDataIOT.E.loc[:,sl],
        CoreDataIOT.E.loc[:,(["Italy"],slice(None),['Transport',"Manufacturing"])]
    )

    sl = ut.slicer(
        matrix = 'Z',
        axis = 0,
        Region = ["Italy"],
        Level = "Activity",
        Item = ["Transport","Manufacturing"]
    )

    pdt.assert_frame_equal(
        CoreDataSUT.Z.loc[sl,sl],
        CoreDataSUT.Z.loc[(["Italy"],"Activity",["Transport","Manufacturing"]),(["Italy"],"Activity",["Transport","Manufacturing"])]
    )

    assert "dummy" == ut.slicer(matrix='E',axis=0,Item="dummy")

    with pytest.raises(ValueError) as msg:
        ut.slicer(matrix='E',axis=0,Region='dummy')
    
    assert "acceptable levels are" in str(msg.value)

def test_sort_frames():
    # Sorting only on the second level of index
    unsorted_index = pd.MultiIndex.from_product(
        [["reg1","reg2"],["level2","level1"]]
    )
    sorted_index = pd.MultiIndex.from_arrays(
        [["reg1","reg2","reg1","reg2"],["level1","level1","level2","level2"]]
    )

    unsorted_frame = pd.DataFrame(0,index=unsorted_index,columns=unsorted_index)
    
    matrices = ['e','V','Z']

    _dict = {k:unsorted_frame for k in matrices}

    ut.sort_frames(_dict)

    for k,v in _dict.items():
    
        pdt.assert_index_equal(
          v.columns , sorted_index  
        )
        # exceptions for ['e','v','E','V','EY'], sorting only on cols
        if k in ['e','V']:
            pdt.assert_index_equal(
                v.index, unsorted_index
            )
        else:
            pdt.assert_index_equal(
                v.columns, sorted_index
            )

def test_delete_duplicates():

    assert ut.delete_duplicates(['a','a','b','a']) == ['a','b']
    assert ut.delete_duplicates(pd.Index(['a','c','b','c','a'])) == ['a','c','b']


def test_return_index():

    index   = pd.Index(['row1','row2'])
    columns = pd.MultiIndex.from_product([['reg1','reg2'],['Sector'],["sec1","sec2"]])

    df = pd.DataFrame(index=index,columns=columns)

    assert ut.return_index(df=df,item='index',multi_index=False,del_duplicate=False) == ['row1','row2'] 
    assert ut.return_index(df=df,item='columns',multi_index=True,del_duplicate=False,level=0) == ['reg1','reg1','reg2','reg2'] 
    assert ut.return_index(df=df,item='columns',multi_index=True,del_duplicate=True,level=0) == ['reg1','reg2'] 


def test_multiindex_contain():
    file = 'dummy'
    outer_index = pd.MultiIndex.from_product([['reg1','reg2'],['sec'],['sec1','sec2']])

    # Full correct case
    inner_index = pd.MultiIndex.from_product([['reg1','reg2'],['sec'],['sec1','sec2']])
    output = ut.multiindex_contain(
        inner_index= inner_index,
        outer_index= outer_index,
        file = file
    )

    assert output["passed"]
    assert output["differences"] == {i:[] for i in range(inner_index.nlevels)}

    # adding extra info to the inner level not outer -> extra data should not be impactful and will pass
    inner_index = pd.MultiIndex.from_product([['reg1','reg2','reg3'],['sec','pec'],['sec1','sec2','sec3']])
    output = ut.multiindex_contain(
        inner_index= inner_index,
        outer_index= outer_index,
        file = file
    )
    assert output["passed"]
    assert output["differences"] == {i:[] for i in range(inner_index.nlevels)}

    # Removing/mistaking the minimum info
    inner_index = pd.MultiIndex.from_product([['reg1','reg3'],['pec'],['sec1','sec3']])
    output = ut.multiindex_contain(
        inner_index= inner_index,
        outer_index= outer_index,
        file = file
    )
    assert not output["passed"]
    assert output["differences"] == {
        0 : ['reg2'], # is missed
        1 : ['sec'], # is missed
        2 : ['sec2'], # is missed
    }

    # Checking not all the levels -> mistake only in second level
    inner_index = pd.MultiIndex.from_product([['reg1','reg2'],['pec'],['sec1','sec2']])

    #checking only second level
    output = ut.multiindex_contain(
        inner_index= inner_index,
        outer_index= outer_index,
        file = file,
        check_levels = [1]
    )
    assert not output["passed"]
    assert output["differences"] == {
        1 : ['sec'], # is missed
    } 

    # checking all the levels except the second level
    output = ut.multiindex_contain(
        inner_index= inner_index,
        outer_index= outer_index,
        file = file,
        check_levels = [0,2]
    )
    assert output["passed"]
    assert output["differences"] == {i:[] for i in [0,2]} 

def test_rename_index():

    index = pd.Index(['r1','r2'])
    columns = pd.MultiIndex.from_tuples([('c1','c2','c3')])

    _dict = {i:pd.DataFrame(index=index,columns=columns) for i in list('ab')}

    ut.rename_index(_dict)

    for df in _dict.values():
        assert tuple(df.columns.names) ==  _INDEX_NAMES["3levels"]
        assert df.index.name ==  _INDEX_NAMES["1level"]

def test_to_single_index():
    index = pd.Index(['r1','r2'])
    df = pd.Series(dtype=float,index=index)
    pdt.assert_index_equal(
        ut.to_single_index(df).index, index
    )

    multi_index = pd.MultiIndex.from_tuples([('r1','r2')])
    df = pd.Series(dtype=float,index=multi_index)

    assert list(ut.to_single_index(df).index) == ['r1, r2']


def test_pymrio_styling():

    df = pd.DataFrame(
        0,
        index = pd.Index(['item1','item2']),
        columns = pd.MultiIndex.from_product([['reg1','reg2'],['Sector'],['sec1','sec2']]) 
    )

    df = ut.pymrio_styling(
        df = df,
        keep_index = [0],
        keep_columns= [0,-1],
        index_name = "index",
        columns_name = ["col1","col2"]
    )

    index = pd.Index(["item1","item2"],name="index")
    columns = pd.MultiIndex.from_product([['reg1','reg2'],['sec1','sec2']],names=['col1','col2'])

    pdt.assert_index_equal(
        df.index,index
    )
    pdt.assert_index_equal(
        df.columns,columns
    )
