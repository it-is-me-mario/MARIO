"""Mathematical Engine Tests"""

import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)

import pytest
import pandas.testing as pdt
import numpy.testing as npt
import os
import sys

import pandas as pd
import numpy as np

from mario.tools.constants import _ENUM


sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

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
    X_inverse,
    calc_all_shock,
)


@pytest.fixture()
def IOT_table():
    """ A dictionary with dummy test data from an excel file
    """
    return load_dummy("IOT_dummy")


def test_calc_all_shock(IOT_table):

    output = calc_all_shock(
        z = IOT_table[_ENUM.z],
        v = IOT_table[_ENUM.v],
        Y = IOT_table[_ENUM.Y],
        e = IOT_table[_ENUM.e]
    )

    for k,v in output.items():
        pdt.assert_frame_equal(
            IOT_table[k],v
        )


# def test_X_inverse():
#     x_array = np.array([1,2,3,0,0,1])
#     x_inv = np.array([1,1/2,1/3,0,0,1])
#     x_series = pd.Series(x_array,dtype=float)
#     x_frame = pd.DataFrame(x_array)

#     assert npt.assert_array_equal(x_inv,X_inverse(x_array))
#     assert npt.assert_array_equal(x_inv,X_inverse(x_series))
#     assert npt.assert_array_equal(x_inv,X_inverse(x_frame))


def test_calc_X_from_z(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.X],calc_X_from_z(IOT_table[_ENUM.z],IOT_table[_ENUM.Y])
    )

def test_calc_X_from_w(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.X],calc_X_from_w(IOT_table[_ENUM.w],IOT_table[_ENUM.Y])
    )

def test_calc_X(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.X],calc_X(IOT_table[_ENUM.Z],IOT_table[_ENUM.Y])
    )

def test_calc_w(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.w],calc_w(IOT_table[_ENUM.z])
    )

def test_calc_z(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.z],calc_z(IOT_table[_ENUM.Z],IOT_table[_ENUM.X])
    )

def test_calc_Z(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.Z],calc_Z(IOT_table[_ENUM.z],IOT_table[_ENUM.X]),
    )

def test_calc_v(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.v],calc_v(IOT_table[_ENUM.V],IOT_table[_ENUM.X])
    )

def test_calc_V(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.V],calc_V(IOT_table[_ENUM.v],IOT_table[_ENUM.X])
    )

def test_calc_e(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.e],calc_e(IOT_table[_ENUM.E],IOT_table[_ENUM.X])
    )

def test_calc_E(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.E],calc_E(IOT_table[_ENUM.e],IOT_table[_ENUM.X])
    )

def test_calc_p(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.p],calc_p(IOT_table[_ENUM.v],IOT_table[_ENUM.w])
    )

def test_calc_y(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.y],calc_y(IOT_table[_ENUM.Y])
    )

    assert calc_y(IOT_table[_ENUM.y]).sum().sum() == 1

def test_calc_b(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.b],calc_b(IOT_table[_ENUM.X],IOT_table[_ENUM.Z])
    )

def test_calc_g(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.g],calc_g(IOT_table[_ENUM.b])
    )

def test_calc_f(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.f],calc_f(IOT_table[_ENUM.e],IOT_table[_ENUM.w])
    )

def test_calc_F(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.F],calc_F(IOT_table[_ENUM.f],IOT_table[_ENUM.Y])
    )

def test_calc_m(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.m],calc_m(IOT_table[_ENUM.v],IOT_table[_ENUM.w])
    )

def test_calcM(IOT_table):
    pdt.assert_frame_equal(
        IOT_table[_ENUM.M],calc_M(IOT_table[_ENUM.m],IOT_table[_ENUM.Y])
    )
