import numpy as np
import pandas as pd
import pandas.testing as pdt
from scipy import sparse

from mario.compute.iot_formulas import (
    build_iot_b_from_X_Z,
    build_iot_E_from_e_X,
    build_iot_F_from_f_Y,
    build_iot_g_from_b,
    build_iot_M_from_m_Y,
    build_iot_V_from_v_X,
    build_iot_X_from_z_Y,
    build_iot_X_from_Z_Y,
    build_iot_X_from_w_Y,
    build_iot_Z_from_z_X,
    build_iot_e_from_E_X,
    build_iot_f_from_e_z,
    build_iot_f_from_e_w,
    build_iot_m_from_v_z,
    build_iot_m_from_v_w,
    build_iot_p_from_v_z,
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
    calc_X_from_z,
    calc_X_from_w,
    calc_Z,
    calc_b,
    calc_e,
    calc_f,
    calc_f_from_z,
    calc_g,
    calc_m,
    calc_m_from_z,
    calc_p,
    calc_p_from_z,
    calc_v,
    calc_w,
    calc_z,
)
from mario.test.mario_test import load_dummy
from mario.model.conventions import _ENUM


def test_new_iot_formulas_match_public_primitives():
    data = load_dummy("IOT")

    comparisons = [
        (build_iot_Z_from_z_X(data[_ENUM.z], data[_ENUM.X]), calc_Z(data[_ENUM.z], data[_ENUM.X])),
        (build_iot_z_from_Z_X(data[_ENUM.Z], data[_ENUM.X]), calc_z(data[_ENUM.Z], data[_ENUM.X])),
        (build_iot_w_from_z(data[_ENUM.z]), calc_w(data[_ENUM.z])),
        (build_iot_X_from_Z_Y(data[_ENUM.Z], data[_ENUM.Y]), calc_X(data[_ENUM.Z], data[_ENUM.Y])),
        (build_iot_X_from_z_Y(data[_ENUM.z], data[_ENUM.Y]), calc_X_from_z(data[_ENUM.z], data[_ENUM.Y])),
        (build_iot_X_from_w_Y(data[_ENUM.w], data[_ENUM.Y]), calc_X_from_w(data[_ENUM.w], data[_ENUM.Y])),
        (build_iot_V_from_v_X(data[_ENUM.v], data[_ENUM.X]), calc_V(data[_ENUM.v], data[_ENUM.X])),
        (build_iot_v_from_V_X(data[_ENUM.V], data[_ENUM.X]), calc_v(data[_ENUM.V], data[_ENUM.X])),
        (build_iot_E_from_e_X(data[_ENUM.e], data[_ENUM.X]), calc_E(data[_ENUM.e], data[_ENUM.X])),
        (build_iot_e_from_E_X(data[_ENUM.E], data[_ENUM.X]), calc_e(data[_ENUM.E], data[_ENUM.X])),
        (build_iot_m_from_v_z(data[_ENUM.v], data[_ENUM.z]), calc_m_from_z(data[_ENUM.v], data[_ENUM.z])),
        (build_iot_m_from_v_w(data[_ENUM.v], data[_ENUM.w]), calc_m(data[_ENUM.v], data[_ENUM.w])),
        (build_iot_M_from_m_Y(data[_ENUM.m], data[_ENUM.Y]), calc_M(data[_ENUM.m], data[_ENUM.Y])),
        (build_iot_f_from_e_z(data[_ENUM.e], data[_ENUM.z]), calc_f_from_z(data[_ENUM.e], data[_ENUM.z])),
        (build_iot_f_from_e_w(data[_ENUM.e], data[_ENUM.w]), calc_f(data[_ENUM.e], data[_ENUM.w])),
        (build_iot_F_from_f_Y(data[_ENUM.f], data[_ENUM.Y]), calc_F(data[_ENUM.f], data[_ENUM.Y])),
        (build_iot_p_from_v_z(data[_ENUM.v], data[_ENUM.z]), calc_p_from_z(data[_ENUM.v], data[_ENUM.z])),
        (build_iot_p_from_v_w(data[_ENUM.v], data[_ENUM.w]), calc_p(data[_ENUM.v], data[_ENUM.w])),
        (build_iot_b_from_X_Z(data[_ENUM.X], data[_ENUM.Z]), calc_b(data[_ENUM.X], data[_ENUM.Z])),
        (build_iot_g_from_b(data[_ENUM.b]), calc_g(data[_ENUM.b])),
    ]

    for new_result, public_result in comparisons:
        pdt.assert_frame_equal(new_result, public_result)


def test_direct_solve_iot_formulas_match_inverse_based_results():
    data = load_dummy("IOT")

    pdt.assert_frame_equal(
        build_iot_X_from_z_Y(data[_ENUM.z], data[_ENUM.Y]),
        build_iot_X_from_w_Y(data[_ENUM.w], data[_ENUM.Y]),
    )
    pdt.assert_frame_equal(
        build_iot_m_from_v_z(data[_ENUM.v], data[_ENUM.z]),
        build_iot_m_from_v_w(data[_ENUM.v], data[_ENUM.w]),
    )
    pdt.assert_frame_equal(
        build_iot_f_from_e_z(data[_ENUM.e], data[_ENUM.z]),
        build_iot_f_from_e_w(data[_ENUM.e], data[_ENUM.w]),
    )
    pdt.assert_frame_equal(
        build_iot_p_from_v_z(data[_ENUM.v], data[_ENUM.z]),
        build_iot_p_from_v_w(data[_ENUM.v], data[_ENUM.w]),
    )


def test_iot_production_formulas_handle_pandas_sparse_float32_inputs():
    Z = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(np.array([[1, 0], [0, 2]], dtype=np.float32)),
        index=["s1", "s2"],
        columns=["s1", "s2"],
    )
    Y = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(np.array([[3, 0], [0, 4]], dtype=np.float32)),
        index=["s1", "s2"],
        columns=["n1", "n2"],
    )

    expected = pd.DataFrame({"production": [4.0, 6.0]}, index=["s1", "s2"])

    pdt.assert_frame_equal(build_iot_X_from_Z_Y(Z, Y), expected)


def test_iot_multiplier_and_price_formulas_handle_pandas_sparse_float32_inputs():
    v = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(np.array([[1, 0], [0, 2]], dtype=np.float32)),
        index=["f1", "f2"],
        columns=["s1", "s2"],
    )
    e = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(np.array([[3, 0], [0, 4]], dtype=np.float32)),
        index=["k1", "k2"],
        columns=["s1", "s2"],
    )
    w = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(np.array([[1, 2], [0, 1]], dtype=np.float32)),
        index=["s1", "s2"],
        columns=["s1", "s2"],
    )

    expected_m = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(v.to_numpy(dtype=float) @ w.to_numpy(dtype=float)),
        index=v.index,
        columns=w.columns,
    )
    expected_f = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(e.to_numpy(dtype=float) @ w.to_numpy(dtype=float)),
        index=e.index,
        columns=w.columns,
    )
    expected_p = pd.DataFrame(
        (w.to_numpy(dtype=float).T @ v.to_numpy(dtype=float).sum(axis=0)).reshape(-1, 1),
        index=w.columns,
        columns=["price index"],
    )

    pdt.assert_frame_equal(build_iot_m_from_v_w(v, w), expected_m, check_dtype=False)
    pdt.assert_frame_equal(build_iot_f_from_e_w(e, w), expected_f, check_dtype=False)
    pdt.assert_frame_equal(build_iot_p_from_v_w(v, w), expected_p)
