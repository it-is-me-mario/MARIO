import mario

import numpy as np
import pandas as pd
import pandas.testing as pdt
from scipy import sparse

from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.sut_formulas import (
    build_sut_c_from_S_Xa,
    build_sut_c_from_s,
    build_sut_Ea_from_ea_Xa,
    build_sut_Ec_from_ec_Xc,
    build_sut_Fa_from_fa_s_Yc,
    build_sut_Fc_from_fc_Yc,
    build_sut_Ma_from_ma_s_Yc,
    build_sut_Mc_from_mc_Yc,
    build_sut_S_from_c_Xa,
    build_sut_S_from_s_Xc,
    build_sut_U_from_u_Xa,
    build_sut_Va_from_va_Xa,
    build_sut_Vc_from_vc_Xc,
    build_sut_Xa_from_S_Ya,
    build_sut_Xa_from_s_Xc,
    build_sut_Xc_from_U_Yc,
    build_sut_Xc_from_u_s_Yc,
    build_sut_Xc_from_wcc_Yc,
    build_sut_bs_from_Xa_S,
    build_sut_bu_from_Xc_U,
    build_sut_ea_from_Ea_Xa,
    build_sut_ec_from_Ec_Xc,
    build_sut_fa_from_ea_s_u,
    build_sut_fa_from_ea_waa,
    build_sut_fc_from_ea_s_u,
    build_sut_fc_from_ea_s_wcc,
    build_sut_gaa_from_bs_bu,
    build_sut_gac_from_gaa_bs,
    build_sut_gca_from_gcc_bu,
    build_sut_gcc_from_bu_bs,
    build_sut_ma_from_va_s_u,
    build_sut_ma_from_va_waa,
    build_sut_mc_from_va_s_u,
    build_sut_mc_from_va_s_wcc,
    build_sut_pa_from_v_s_u,
    build_sut_pa_from_va,
    build_sut_pc_from_v_s_u,
    build_sut_pc_from_vc,
    build_sut_s_from_S_Xc,
    build_sut_s_from_c,
    build_sut_u_from_U_Xa,
    build_sut_va_from_Va_Xa,
    build_sut_vc_from_Vc_Xc,
    build_sut_waa_from_s_u,
    build_sut_waa_from_s_u_solve,
    build_sut_wac_from_waa_s,
    build_sut_wac_from_s_u_solve,
    build_sut_wac_from_s_u,
    build_sut_wca_from_wcc_u,
    build_sut_wca_from_u_s_solve,
    build_sut_wca_from_u_s,
    build_sut_wcc_from_u_s,
    build_sut_wcc_from_u_s_solve,
)
from mario.compute.views import (
    extract_Ea_from_E,
    extract_Ec_from_E,
    extract_Fa_from_F,
    extract_Fc_from_F,
    extract_Ma_from_M,
    extract_Mc_from_M,
    extract_S_from_Z,
    extract_U_from_Z,
    extract_Va_from_V,
    extract_Vc_from_V,
    extract_Xa_from_X,
    extract_Xc_from_X,
    extract_Ya_from_Y,
    extract_Yc_from_Y,
    extract_ea_from_e,
    extract_ec_from_e,
    extract_fa_from_f,
    extract_fc_from_f,
    extract_ma_from_m,
    extract_mc_from_m,
    extract_pa_from_p,
    extract_pc_from_p,
    extract_s_from_z,
    extract_u_from_z,
    extract_waa_from_w,
    extract_wac_from_w,
    extract_wca_from_w,
    extract_wcc_from_w,
    extract_va_from_v,
    extract_vc_from_v,
)
from mario.test.mario_test import load_test
from mario.model.conventions import _ENUM


def test_sut_split_formulas_match_database_views():
    sut = load_test("SUT")
    sut.calc_all(
        [
            _ENUM.z,
            _ENUM.u,
            _ENUM.s,
            _ENUM.w,
            "bu",
            "bs",
            "gcc",
            "gca",
            "gac",
            "gaa",
            _ENUM.v,
            _ENUM.e,
            _ENUM.p,
            _ENUM.m,
            _ENUM.f,
        ]
    )
    ordering = SUTUnifiedOrderingPolicy.from_blocks(Z=sut.Z, Y=sut.Y, V=sut.V, E=sut.E)

    U = extract_U_from_Z(sut.Z, ordering)
    S = extract_S_from_Z(sut.Z, ordering)
    Xa = extract_Xa_from_X(sut.X, ordering)
    Xc = extract_Xc_from_X(sut.X, ordering)
    Ya = extract_Ya_from_Y(sut.Y, ordering)
    Yc = extract_Yc_from_Y(sut.Y, ordering)
    Va = extract_Va_from_V(sut.V, ordering)
    Vc = extract_Vc_from_V(sut.V, ordering)
    Ea = extract_Ea_from_E(sut.E, ordering)
    Ec = extract_Ec_from_E(sut.E, ordering)

    pdt.assert_frame_equal(build_sut_u_from_U_Xa(U, Xa), extract_u_from_z(sut.z, ordering))
    pdt.assert_frame_equal(build_sut_s_from_S_Xc(S, Xc), extract_s_from_z(sut.z, ordering))
    pdt.assert_frame_equal(build_sut_U_from_u_Xa(sut.u, Xa), U)
    pdt.assert_frame_equal(build_sut_S_from_s_Xc(sut.s, Xc), S)
    pdt.assert_frame_equal(build_sut_Xa_from_S_Ya(S, Ya), Xa)
    pdt.assert_frame_equal(build_sut_Xa_from_s_Xc(sut.s, Xc), Xa)
    pdt.assert_frame_equal(build_sut_Xc_from_U_Yc(U, Yc), Xc)

    wcc = build_sut_wcc_from_u_s(sut.u, sut.s)
    wca = build_sut_wca_from_u_s(sut.u, sut.s)
    wac = build_sut_wac_from_s_u(sut.s, sut.u)
    waa = build_sut_waa_from_s_u(sut.s, sut.u)
    wcc_solve = build_sut_wcc_from_u_s_solve(sut.u, sut.s)
    wca_solve = build_sut_wca_from_u_s_solve(sut.u, sut.s)
    wac_solve = build_sut_wac_from_s_u_solve(sut.s, sut.u)
    waa_solve = build_sut_waa_from_s_u_solve(sut.s, sut.u)

    pdt.assert_frame_equal(wcc, extract_wcc_from_w(sut.w, ordering))
    pdt.assert_frame_equal(wca, extract_wca_from_w(sut.w, ordering))
    pdt.assert_frame_equal(wac, extract_wac_from_w(sut.w, ordering))
    pdt.assert_frame_equal(waa, extract_waa_from_w(sut.w, ordering))
    pdt.assert_frame_equal(wcc_solve, wcc)
    pdt.assert_frame_equal(wca_solve, wca)
    pdt.assert_frame_equal(wac_solve, wac)
    pdt.assert_frame_equal(waa_solve, waa)
    pdt.assert_frame_equal(build_sut_wca_from_wcc_u(wcc_solve, sut.u), wca)
    pdt.assert_frame_equal(build_sut_wac_from_waa_s(waa_solve, sut.s), wac)
    pdt.assert_frame_equal(build_sut_Xc_from_wcc_Yc(wcc, Yc), Xc)
    pdt.assert_frame_equal(build_sut_Xc_from_u_s_Yc(sut.u, sut.s, Yc), Xc)

    bu = build_sut_bu_from_Xc_U(Xc, U)
    bs = build_sut_bs_from_Xa_S(Xa, S)
    gcc = build_sut_gcc_from_bu_bs(bu, bs)
    gca = build_sut_gca_from_gcc_bu(gcc, bu)
    gaa = build_sut_gaa_from_bs_bu(bs, bu)
    gac = build_sut_gac_from_gaa_bs(gaa, bs)

    pdt.assert_frame_equal(bu, sut.query("bu"))
    pdt.assert_frame_equal(bs, sut.query("bs"))
    pdt.assert_frame_equal(gcc, sut.query("gcc"))
    pdt.assert_frame_equal(gca, sut.query("gca"))
    pdt.assert_frame_equal(gac, sut.query("gac"))
    pdt.assert_frame_equal(gaa, sut.query("gaa"))

    va = build_sut_va_from_Va_Xa(Va, Xa)
    vc = build_sut_vc_from_Vc_Xc(Vc, Xc)
    ea = build_sut_ea_from_Ea_Xa(Ea, Xa)
    ec = build_sut_ec_from_Ec_Xc(Ec, Xc)

    pdt.assert_frame_equal(va, extract_va_from_v(sut.v, ordering))
    pdt.assert_frame_equal(vc, extract_vc_from_v(sut.v, ordering))
    pdt.assert_frame_equal(ea, extract_ea_from_e(sut.e, ordering))
    pdt.assert_frame_equal(ec, extract_ec_from_e(sut.e, ordering))
    pdt.assert_frame_equal(build_sut_Va_from_va_Xa(va, Xa), Va)
    pdt.assert_frame_equal(build_sut_Vc_from_vc_Xc(vc, Xc), Vc)
    pdt.assert_frame_equal(build_sut_Ea_from_ea_Xa(ea, Xa), Ea)
    pdt.assert_frame_equal(build_sut_Ec_from_ec_Xc(ec, Xc), Ec)

    ma = build_sut_ma_from_va_waa(va, waa, vc, sut.u)
    mc = build_sut_mc_from_va_s_wcc(va, sut.s, wcc, vc)
    fa = build_sut_fa_from_ea_waa(ea, waa, ec, sut.u)
    fc = build_sut_fc_from_ea_s_wcc(ea, sut.s, wcc, ec)
    ma_solve = build_sut_ma_from_va_s_u(va, sut.s, sut.u, vc)
    mc_solve = build_sut_mc_from_va_s_u(va, sut.s, sut.u, vc)
    fa_solve = build_sut_fa_from_ea_s_u(ea, sut.s, sut.u, ec)
    fc_solve = build_sut_fc_from_ea_s_u(ea, sut.s, sut.u, ec)

    pdt.assert_frame_equal(ma, extract_ma_from_m(sut.m, ordering))
    pdt.assert_frame_equal(mc, extract_mc_from_m(sut.m, ordering))
    pdt.assert_frame_equal(fa, extract_fa_from_f(sut.f, ordering))
    pdt.assert_frame_equal(fc, extract_fc_from_f(sut.f, ordering))
    pdt.assert_frame_equal(ma_solve, ma)
    pdt.assert_frame_equal(mc_solve, mc)
    pdt.assert_frame_equal(fa_solve, fa)
    pdt.assert_frame_equal(fc_solve, fc)
    pdt.assert_frame_equal(build_sut_pa_from_va(va, vc, waa, wca), extract_pa_from_p(sut.p, ordering))
    pdt.assert_frame_equal(build_sut_pc_from_vc(va, vc, wac, wcc), extract_pc_from_p(sut.p, ordering))
    pdt.assert_frame_equal(build_sut_pa_from_v_s_u(va, vc, sut.s, sut.u), extract_pa_from_p(sut.p, ordering))
    pdt.assert_frame_equal(build_sut_pc_from_v_s_u(va, vc, sut.s, sut.u), extract_pc_from_p(sut.p, ordering))


def test_sut_split_flow_formulas_match_database_views_when_final_demand_is_commodity_side():
    sut = load_test("SUT")
    sut.calc_all([_ENUM.z, _ENUM.u, _ENUM.s, _ENUM.w, _ENUM.v, _ENUM.e, _ENUM.m, _ENUM.f, _ENUM.M, _ENUM.F])
    ordering = SUTUnifiedOrderingPolicy.from_blocks(Z=sut.Z, Y=sut.Y)

    Xc = extract_Xc_from_X(sut.X, ordering)
    Xa = extract_Xa_from_X(sut.X, ordering)
    Yc = extract_Yc_from_Y(sut.Y, ordering)
    Va = extract_Va_from_V(sut.V, ordering)
    Vc = extract_Vc_from_V(sut.V, ordering)
    Ea = extract_Ea_from_E(sut.E, ordering)
    Ec = extract_Ec_from_E(sut.E, ordering)

    va = build_sut_va_from_Va_Xa(Va, Xa)
    vc = build_sut_vc_from_Vc_Xc(Vc, Xc)
    ea = build_sut_ea_from_Ea_Xa(Ea, Xa)
    ec = build_sut_ec_from_Ec_Xc(Ec, Xc)
    wcc = build_sut_wcc_from_u_s(sut.u, sut.s)
    waa = build_sut_waa_from_s_u(sut.s, sut.u)
    ma = build_sut_ma_from_va_waa(va, waa, vc, sut.u)
    mc = build_sut_mc_from_va_s_wcc(va, sut.s, wcc, vc)
    fa = build_sut_fa_from_ea_waa(ea, waa, ec, sut.u)
    fc = build_sut_fc_from_ea_s_wcc(ea, sut.s, wcc, ec)

    pdt.assert_frame_equal(build_sut_Xc_from_wcc_Yc(wcc, Yc), Xc)
    pdt.assert_frame_equal(build_sut_Xc_from_u_s_Yc(sut.u, sut.s, Yc), Xc)
    pdt.assert_frame_equal(build_sut_Ma_from_ma_s_Yc(ma, sut.s, Yc), extract_Ma_from_M(sut.M, ordering))
    pdt.assert_frame_equal(build_sut_Mc_from_mc_Yc(mc, Yc), extract_Mc_from_M(sut.M, ordering))
    pdt.assert_frame_equal(build_sut_Fa_from_fa_s_Yc(fa, sut.s, Yc), extract_Fa_from_F(sut.F, ordering))
    pdt.assert_frame_equal(build_sut_Fc_from_fc_Yc(fc, Yc), extract_Fc_from_F(sut.F, ordering))
    pdt.assert_frame_equal(build_sut_fa_from_ea_waa(ea, waa, ec, sut.u), extract_fa_from_f(sut.f, ordering))
    pdt.assert_frame_equal(build_sut_mc_from_va_s_u(va, sut.s, sut.u, vc), mc)
    pdt.assert_frame_equal(build_sut_fc_from_ea_s_u(ea, sut.s, sut.u, ec), fc)
    pdt.assert_frame_equal(build_sut_fa_from_ea_s_u(ea, sut.s, sut.u, ec), extract_fa_from_f(sut.f, ordering))


def test_public_sut_calc_wrappers_match_split_builders():
    sut = load_test("SUT")
    sut.calc_all([_ENUM.z, _ENUM.u, _ENUM.s, _ENUM.w, _ENUM.v, _ENUM.e, _ENUM.m, _ENUM.f, _ENUM.M, _ENUM.F])
    ordering = SUTUnifiedOrderingPolicy.from_blocks(Z=sut.Z, Y=sut.Y)

    Xc = extract_Xc_from_X(sut.X, ordering)
    Xa = extract_Xa_from_X(sut.X, ordering)
    Yc = extract_Yc_from_Y(sut.Y, ordering)
    Va = extract_Va_from_V(sut.V, ordering)
    Vc = extract_Vc_from_V(sut.V, ordering)
    Ea = extract_Ea_from_E(sut.E, ordering)
    Ec = extract_Ec_from_E(sut.E, ordering)
    va = extract_va_from_v(sut.v, ordering)
    vc = extract_vc_from_v(sut.v, ordering)
    ea = extract_ea_from_e(sut.e, ordering)
    ec = extract_ec_from_e(sut.e, ordering)
    waa = build_sut_waa_from_s_u(sut.s, sut.u)
    wcc = build_sut_wcc_from_u_s(sut.u, sut.s)
    ma = extract_ma_from_m(sut.m, ordering)
    mc = extract_mc_from_m(sut.m, ordering)
    fa = extract_fa_from_f(sut.f, ordering)
    fc = extract_fc_from_f(sut.f, ordering)

    pdt.assert_frame_equal(mario.calc_Va(va, Xa), Va)
    pdt.assert_frame_equal(mario.calc_Vc(vc, Xc), Vc)
    pdt.assert_frame_equal(mario.calc_va(Va, Xa), va)
    pdt.assert_frame_equal(mario.calc_vc(Vc, Xc), vc)
    pdt.assert_frame_equal(mario.calc_Ea(ea, Xa), Ea)
    pdt.assert_frame_equal(mario.calc_Ec(ec, Xc), Ec)
    pdt.assert_frame_equal(mario.calc_ea(Ea, Xa), ea)
    pdt.assert_frame_equal(mario.calc_ec(Ec, Xc), ec)
    pdt.assert_frame_equal(mario.calc_ma(va, waa, vc=vc, u=sut.u), ma)
    pdt.assert_frame_equal(mario.calc_mc(va, sut.s, wcc, vc=vc), mc)
    pdt.assert_frame_equal(mario.calc_Ma(ma, sut.s, Yc), extract_Ma_from_M(sut.M, ordering))
    pdt.assert_frame_equal(mario.calc_Mc(mc, Yc), extract_Mc_from_M(sut.M, ordering))
    pdt.assert_frame_equal(mario.calc_fa(ea, waa, ec=ec, u=sut.u), fa)
    pdt.assert_frame_equal(mario.calc_fc(ea, sut.s, wcc, ec=ec), fc)
    pdt.assert_frame_equal(mario.calc_Fa(fa, sut.s, Yc), extract_Fa_from_F(sut.F, ordering))
    pdt.assert_frame_equal(mario.calc_Fc(fc, Yc), extract_Fc_from_F(sut.F, ordering))


def test_sut_multiplier_formulas_include_commodity_side_direct_coefficients():
    va = pd.DataFrame(
        [[1.0, 0.0], [0.0, 2.0]],
        index=["f1", "f2"],
        columns=["a1", "a2"],
    )
    vc = pd.DataFrame(
        [[3.0, 0.0], [0.0, 4.0]],
        index=va.index,
        columns=["c1", "c2"],
    )
    ea = pd.DataFrame(
        [[5.0, 0.0], [0.0, 6.0]],
        index=["k1", "k2"],
        columns=va.columns,
    )
    ec = pd.DataFrame(
        [[7.0, 0.0], [0.0, 8.0]],
        index=ea.index,
        columns=vc.columns,
    )
    s = pd.DataFrame(
        [[0.2, 0.1], [0.3, 0.2]],
        index=va.columns,
        columns=vc.columns,
    )
    u = pd.DataFrame(
        [[0.1, 0.05], [0.02, 0.1]],
        index=vc.columns,
        columns=va.columns,
    )

    waa = build_sut_waa_from_s_u(s, u)
    wcc = build_sut_wcc_from_u_s(u, s)

    expected_ma = pd.DataFrame(
        (va.to_numpy() + vc.to_numpy() @ u.to_numpy()) @ waa.to_numpy(),
        index=va.index,
        columns=waa.columns,
    )
    expected_mc = pd.DataFrame(
        (va.to_numpy() @ s.to_numpy() + vc.to_numpy()) @ wcc.to_numpy(),
        index=va.index,
        columns=wcc.columns,
    )
    expected_fa = pd.DataFrame(
        (ea.to_numpy() + ec.to_numpy() @ u.to_numpy()) @ waa.to_numpy(),
        index=ea.index,
        columns=waa.columns,
    )
    expected_fc = pd.DataFrame(
        (ea.to_numpy() @ s.to_numpy() + ec.to_numpy()) @ wcc.to_numpy(),
        index=ea.index,
        columns=wcc.columns,
    )

    pdt.assert_frame_equal(build_sut_ma_from_va_waa(va, waa, vc, u), expected_ma)
    pdt.assert_frame_equal(build_sut_mc_from_va_s_wcc(va, s, wcc, vc), expected_mc)
    pdt.assert_frame_equal(build_sut_fa_from_ea_waa(ea, waa, ec, u), expected_fa)
    pdt.assert_frame_equal(build_sut_fc_from_ea_s_wcc(ea, s, wcc, ec), expected_fc)
    pdt.assert_frame_equal(build_sut_ma_from_va_s_u(va, s, u, vc), expected_ma)
    pdt.assert_frame_equal(build_sut_mc_from_va_s_u(va, s, u, vc), expected_mc)
    pdt.assert_frame_equal(build_sut_fa_from_ea_s_u(ea, s, u, ec), expected_fa)
    pdt.assert_frame_equal(build_sut_fc_from_ea_s_u(ea, s, u, ec), expected_fc)


def test_sut_satellite_multiplier_formulas_handle_pandas_sparse_float32_inputs():
    ea_values = np.array([[1, 0], [0, 2]], dtype=np.float32)
    s_values = np.array([[1, 3], [2, 4]], dtype=np.float32)
    wcc_values = np.array([[1, 2], [0, 1]], dtype=np.float32)
    waa_values = np.array([[1, 1], [0, 1]], dtype=np.float32)
    ea = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(ea_values),
        index=["k1", "k2"],
        columns=["a1", "a2"],
    )
    s = pd.DataFrame(
        s_values,
        index=["a1", "a2"],
        columns=["c1", "c2"],
    )
    wcc = pd.DataFrame(
        wcc_values,
        index=["c1", "c2"],
        columns=["c1", "c2"],
    )
    waa = pd.DataFrame(
        waa_values,
        index=["a1", "a2"],
        columns=["a1", "a2"],
    )

    expected_fc = pd.DataFrame(
        ea_values.astype(float) @ s_values.astype(float) @ wcc_values.astype(float),
        index=ea.index,
        columns=wcc.columns,
    )
    expected_fa = pd.DataFrame(
        ea_values.astype(float) @ waa_values.astype(float),
        index=ea.index,
        columns=waa.columns,
    )

    pdt.assert_frame_equal(build_sut_fc_from_ea_s_wcc(ea, s, wcc), expected_fc)
    pdt.assert_frame_equal(build_sut_fa_from_ea_waa(ea, waa), expected_fa)


def test_sut_price_formulas_handle_pandas_sparse_float32_inputs():
    va_values = np.array([[1, 0], [0, 2]], dtype=np.float32)
    vc_values = np.array([[3, 0], [0, 4]], dtype=np.float32)
    wac_values = np.array([[1, 2], [0, 1]], dtype=np.float32)
    wcc_values = np.array([[2, 0], [1, 1]], dtype=np.float32)
    waa_values = np.array([[1, 0], [3, 1]], dtype=np.float32)
    wca_values = np.array([[1, 1], [0, 2]], dtype=np.float32)
    va = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(va_values),
        index=["f1", "f2"],
        columns=["a1", "a2"],
    )
    vc = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(vc_values),
        index=["f1", "f2"],
        columns=["c1", "c2"],
    )
    wac = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(wac_values),
        index=["a1", "a2"],
        columns=["c1", "c2"],
    )
    wcc = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(wcc_values),
        index=["c1", "c2"],
        columns=["c1", "c2"],
    )
    waa = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(waa_values),
        index=["a1", "a2"],
        columns=["a1", "a2"],
    )
    wca = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(wca_values),
        index=["c1", "c2"],
        columns=["a1", "a2"],
    )

    expected_pc = pd.DataFrame(
        (
            wac_values.astype(float).T @ va_values.astype(float).sum(axis=0)
            + wcc_values.astype(float).T @ vc_values.astype(float).sum(axis=0)
        ).reshape(-1, 1),
        index=wcc.columns,
        columns=["price index"],
    )
    expected_pa = pd.DataFrame(
        (
            waa_values.astype(float).T @ va_values.astype(float).sum(axis=0)
            + wca_values.astype(float).T @ vc_values.astype(float).sum(axis=0)
        ).reshape(-1, 1),
        index=waa.columns,
        columns=["price index"],
    )

    pdt.assert_frame_equal(build_sut_pc_from_vc(va, vc, wac, wcc), expected_pc)
    pdt.assert_frame_equal(build_sut_pa_from_va(va, vc, waa, wca), expected_pa)


def test_product_based_sut_c_s_and_S_formulas_roundtrip():
    S = pd.DataFrame(
        [[6.0, 1.0], [2.0, 8.0]],
        index=["a1", "a2"],
        columns=["c1", "c2"],
    )
    Xa = pd.DataFrame([7.0, 10.0], index=["a1", "a2"], columns=["production"])
    Xc = pd.DataFrame([8.0, 9.0], index=["c1", "c2"], columns=["production"])

    c = build_sut_c_from_S_Xa(S, Xa, tech_assumption="PT")
    expected_c = pd.DataFrame(
        [[6.0 / 7.0, 2.0 / 10.0], [1.0 / 7.0, 8.0 / 10.0]],
        index=["c1", "c2"],
        columns=["a1", "a2"],
    )
    pdt.assert_frame_equal(c, expected_c)

    s = build_sut_s_from_c(c, tech_assumption="product-based")
    pdt.assert_frame_equal(s, build_sut_s_from_S_Xc(S, Xc, Xa=Xa, tech_assumption="PT"))

    rebuilt_c = build_sut_c_from_s(s, tech_assumption="product-based")
    rebuilt_S = build_sut_S_from_c_Xa(c, Xa, tech_assumption="PT")
    pdt.assert_frame_equal(rebuilt_c, c)
    pdt.assert_frame_equal(rebuilt_S, S)
    pdt.assert_frame_equal(
        build_sut_S_from_s_Xc(s, Xc, Xa=Xa, tech_assumption="product-based"),
        S,
    )


def test_sut_production_formulas_handle_pandas_sparse_float32_inputs():
    S = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(np.array([[1, 0], [0, 2]], dtype=np.float32)),
        index=["a1", "a2"],
        columns=["c1", "c2"],
    )
    U = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(np.array([[3, 0], [0, 4]], dtype=np.float32)),
        index=["c1", "c2"],
        columns=["a1", "a2"],
    )
    Ya = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(np.array([[5, 0], [0, 6]], dtype=np.float32)),
        index=["a1", "a2"],
        columns=["n1", "n2"],
    )
    Yc = pd.DataFrame.sparse.from_spmatrix(
        sparse.csr_matrix(np.array([[7, 0], [0, 8]], dtype=np.float32)),
        index=["c1", "c2"],
        columns=["n1", "n2"],
    )

    expected_xa = pd.DataFrame({"production": [6.0, 8.0]}, index=["a1", "a2"])
    expected_xc = pd.DataFrame({"production": [10.0, 12.0]}, index=["c1", "c2"])
    expected_xa.columns = pd.Index(["production"], name="Item")
    expected_xc.columns = pd.Index(["production"], name="Item")

    pdt.assert_frame_equal(build_sut_Xa_from_S_Ya(S, Ya), expected_xa)
    pdt.assert_frame_equal(build_sut_Xc_from_U_Yc(U, Yc), expected_xc)
