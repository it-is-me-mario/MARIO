"""Mathematical Engine Tests"""


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

def test_calc_X(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['X'],calc_X(IOT_table['Z'],IOT_table['Y'])
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

def test_calc_y(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['y'],calc_y(IOT_table['Y'])
    )

    assert calc_y(IOT_table['y']).sum().sum() == 1

def test_calc_b(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['b'],calc_b(IOT_table['X'],IOT_table['Z'])
    )

def test_calc_g(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['g'],calc_g(IOT_table['b'])
    )

def test_calc_f(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['f'],calc_f(IOT_table['e'],IOT_table['w'])
    )

def test_calc_F(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['F'],calc_F(IOT_table['f'],IOT_table['Y'])
    )

def test_calc_m(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['m'],calc_m(IOT_table['v'],IOT_table['w'])
    )

def test_calcM(IOT_table):
    pdt.assert_frame_equal(
        IOT_table['M'],calc_M(IOT_table['m'],IOT_table['Y'])
    )

