"""Mathematical Engine Tests"""

#%%import pandas as pd
import numpy as np
import pytest
import pandas.testing as pdt

import os
import sys

sys.path.append(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".."
    )
)

from mario.test.mario_test import load_dummy
from mario.tools.iomath import (
    calc_X,
    calc_Z,
    calc_w,
    calc_g,
    calc_X_from_w,
    calc_X_from_z,
    calc_E,
    calc_V,
    calc_e,
    calc_v,
    calc_z,
    calc_b,
    calc_F,
    calc_f,
    calc_f_dis,
    calc_m,
    calc_M,
    calc_y,
    calc_p,
)

@pytest.fixture()
def IOT_table():
    """ A dictionary with dummy test data from an excel file
    """
    return load_dummy('IOT_dummy')



def test_calc_X_from_z(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['X'],calc_X_from_z(IOT_table['z'],IOT_table['Y'])
    )

def test_calc_X_from_w(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['X'],calc_X_from_w(IOT_table['w'],IOT_table['Y'])
    )

def test_calc_w(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['w'],calc_w(IOT_table['z'])
    )

def test_calc_z(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['z'],calc_z(IOT_table['Z'],IOT_table['X'])
    )

def test_calc_Z(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['Z'],calc_Z(IOT_table['z'],IOT_table['X']),
    )

def test_calc_v(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['v'],calc_v(IOT_table['V'],IOT_table['X'])
    )

def test_calc_V(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['V'],calc_V(IOT_table['v'],IOT_table['X'])
    )

def test_calc_e(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['e'],calc_e(IOT_table['E'],IOT_table['X'])
    )

def test_calc_E(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['E'],calc_E(IOT_table['e'],IOT_table['X'])
    )

def test_calc_p(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['p'],calc_p(IOT_table['v'],IOT_table['w'])
    )
