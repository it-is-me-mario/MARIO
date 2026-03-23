import pandas.testing as pdt

from mario.compute.ghosh_formulas import build_iot_b_from_X_Z, build_iot_g_from_b
from mario.compute.iot_formulas import (
    build_iot_E_from_e_X,
    build_iot_F_from_f_Y,
    build_iot_M_from_m_Y,
    build_iot_V_from_v_X,
    build_iot_X_from_Z_Y,
    build_iot_X_from_w_Y,
    build_iot_Z_from_z_X,
    build_iot_e_from_E_X,
    build_iot_f_from_e_w,
    build_iot_m_from_v_w,
    build_iot_p_from_v_w,
    build_iot_v_from_V_X,
    build_iot_w_from_z,
    build_iot_z_from_Z_X,
)
from mario.compute.primitives import (
    calc_E,
    calc_F,
    calc_M,
    calc_V,
    calc_X,
    calc_X_from_w,
    calc_Z,
    calc_b,
    calc_e,
    calc_f,
    calc_g,
    calc_m,
    calc_p,
    calc_v,
    calc_w,
    calc_z,
)
from mario.test.mario_test import load_dummy
from mario.model.conventions import _ENUM


def test_new_iot_formulas_match_public_primitives():
    data = load_dummy("IOT_dummy")

    comparisons = [
        (build_iot_Z_from_z_X(data[_ENUM.z], data[_ENUM.X]), calc_Z(data[_ENUM.z], data[_ENUM.X])),
        (build_iot_z_from_Z_X(data[_ENUM.Z], data[_ENUM.X]), calc_z(data[_ENUM.Z], data[_ENUM.X])),
        (build_iot_w_from_z(data[_ENUM.z]), calc_w(data[_ENUM.z])),
        (build_iot_X_from_Z_Y(data[_ENUM.Z], data[_ENUM.Y]), calc_X(data[_ENUM.Z], data[_ENUM.Y])),
        (build_iot_X_from_w_Y(data[_ENUM.w], data[_ENUM.Y]), calc_X_from_w(data[_ENUM.w], data[_ENUM.Y])),
        (build_iot_V_from_v_X(data[_ENUM.v], data[_ENUM.X]), calc_V(data[_ENUM.v], data[_ENUM.X])),
        (build_iot_v_from_V_X(data[_ENUM.V], data[_ENUM.X]), calc_v(data[_ENUM.V], data[_ENUM.X])),
        (build_iot_E_from_e_X(data[_ENUM.e], data[_ENUM.X]), calc_E(data[_ENUM.e], data[_ENUM.X])),
        (build_iot_e_from_E_X(data[_ENUM.E], data[_ENUM.X]), calc_e(data[_ENUM.E], data[_ENUM.X])),
        (build_iot_m_from_v_w(data[_ENUM.v], data[_ENUM.w]), calc_m(data[_ENUM.v], data[_ENUM.w])),
        (build_iot_M_from_m_Y(data[_ENUM.m], data[_ENUM.Y]), calc_M(data[_ENUM.m], data[_ENUM.Y])),
        (build_iot_f_from_e_w(data[_ENUM.e], data[_ENUM.w]), calc_f(data[_ENUM.e], data[_ENUM.w])),
        (build_iot_F_from_f_Y(data[_ENUM.f], data[_ENUM.Y]), calc_F(data[_ENUM.f], data[_ENUM.Y])),
        (build_iot_p_from_v_w(data[_ENUM.v], data[_ENUM.w]), calc_p(data[_ENUM.v], data[_ENUM.w])),
        (build_iot_b_from_X_Z(data[_ENUM.X], data[_ENUM.Z]), calc_b(data[_ENUM.X], data[_ENUM.Z])),
        (build_iot_g_from_b(data[_ENUM.b]), calc_g(data[_ENUM.b])),
    ]

    for new_result, public_result in comparisons:
        pdt.assert_frame_equal(new_result, public_result)
