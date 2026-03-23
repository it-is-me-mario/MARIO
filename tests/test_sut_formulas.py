import pandas.testing as pdt

from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.sut_formulas import (
    build_sut_Ea_from_ea_Xa,
    build_sut_Ec_from_ec_Xc,
    build_sut_Fc_from_fc_Yc,
    build_sut_Mc_from_mc_Yc,
    build_sut_S_from_s_Xc,
    build_sut_U_from_u_Xa,
    build_sut_Va_from_va_Xa,
    build_sut_Vc_from_vc_Xc,
    build_sut_Xa_from_S_Ya,
    build_sut_Xa_from_s_Xc,
    build_sut_Xc_from_U_Yc,
    build_sut_Xc_from_wcc_Yc,
    build_sut_ea_from_Ea_Xa,
    build_sut_ec_from_Ec_Xc,
    build_sut_fa_from_ea_waa,
    build_sut_fc_from_ea_s_wcc,
    build_sut_ma_from_va_waa,
    build_sut_mc_from_va_s_wcc,
    build_sut_pa_from_va,
    build_sut_pc_from_vc,
    build_sut_s_from_S_Xc,
    build_sut_u_from_U_Xa,
    build_sut_va_from_Va_Xa,
    build_sut_vc_from_Vc_Xc,
    build_sut_waa_from_s_u,
    build_sut_wac_from_s_u,
    build_sut_wca_from_u_s,
    build_sut_wcc_from_u_s,
)
from mario.compute.views import (
    extract_Ea_from_E,
    extract_Ec_from_E,
    extract_Fc_from_F,
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
    sut.calc_all([_ENUM.z, _ENUM.u, _ENUM.s, _ENUM.w, _ENUM.v, _ENUM.e, _ENUM.p, _ENUM.m, _ENUM.f])
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

    pdt.assert_frame_equal(wcc, extract_wcc_from_w(sut.w, ordering))
    pdt.assert_frame_equal(wca, extract_wca_from_w(sut.w, ordering))
    pdt.assert_frame_equal(wac, extract_wac_from_w(sut.w, ordering))
    pdt.assert_frame_equal(waa, extract_waa_from_w(sut.w, ordering))
    pdt.assert_frame_equal(build_sut_Xc_from_wcc_Yc(wcc, Yc), Xc)

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

    ma = build_sut_ma_from_va_waa(va, waa)
    mc = build_sut_mc_from_va_s_wcc(va, sut.s, wcc)
    fa = build_sut_fa_from_ea_waa(ea, waa)
    fc = build_sut_fc_from_ea_s_wcc(ea, sut.s, wcc)

    pdt.assert_frame_equal(ma, extract_ma_from_m(sut.m, ordering))
    pdt.assert_frame_equal(mc, extract_mc_from_m(sut.m, ordering))
    pdt.assert_frame_equal(fa, extract_fa_from_f(sut.f, ordering))
    pdt.assert_frame_equal(fc, extract_fc_from_f(sut.f, ordering))
    pdt.assert_frame_equal(build_sut_pa_from_va(va, vc, waa, wca), extract_pa_from_p(sut.p, ordering))
    pdt.assert_frame_equal(build_sut_pc_from_vc(va, vc, wac, wcc), extract_pc_from_p(sut.p, ordering))


def test_sut_split_flow_formulas_match_database_views_when_final_demand_is_commodity_side():
    sut = load_test("SUT")
    sut.calc_all([_ENUM.z, _ENUM.u, _ENUM.s, _ENUM.w, _ENUM.v, _ENUM.e, _ENUM.m, _ENUM.f, _ENUM.M, _ENUM.F])
    ordering = SUTUnifiedOrderingPolicy.from_blocks(Z=sut.Z, Y=sut.Y)

    Xc = extract_Xc_from_X(sut.X, ordering)
    Xa = extract_Xa_from_X(sut.X, ordering)
    Yc = extract_Yc_from_Y(sut.Y, ordering)
    Va = extract_Va_from_V(sut.V, ordering)
    Ea = extract_Ea_from_E(sut.E, ordering)

    va = build_sut_va_from_Va_Xa(Va, Xa)
    ea = build_sut_ea_from_Ea_Xa(Ea, Xa)
    wcc = build_sut_wcc_from_u_s(sut.u, sut.s)
    waa = build_sut_waa_from_s_u(sut.s, sut.u)
    mc = build_sut_mc_from_va_s_wcc(va, sut.s, wcc)
    fc = build_sut_fc_from_ea_s_wcc(ea, sut.s, wcc)

    pdt.assert_frame_equal(build_sut_Xc_from_wcc_Yc(wcc, Yc), Xc)
    pdt.assert_frame_equal(build_sut_Mc_from_mc_Yc(mc, Yc), extract_Mc_from_M(sut.M, ordering))
    pdt.assert_frame_equal(build_sut_Fc_from_fc_Yc(fc, Yc), extract_Fc_from_F(sut.F, ordering))
    pdt.assert_frame_equal(build_sut_fa_from_ea_waa(ea, waa), extract_fa_from_f(sut.f, ordering))
