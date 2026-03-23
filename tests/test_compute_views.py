import pandas.testing as pdt

from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.views import (
    concat_sut_E,
    concat_sut_V,
    concat_sut_X,
    concat_sut_Y,
    concat_sut_Z,
    concat_sut_e,
    concat_sut_f,
    concat_sut_m,
    concat_sut_p,
    concat_sut_v,
    concat_sut_w,
    concat_sut_z,
    extract_Ea_from_E,
    extract_Ec_from_E,
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


def test_sut_ordering_matches_database_unified_layout():
    sut = load_test("SUT")
    ordering = SUTUnifiedOrderingPolicy.from_blocks(Z=sut.Z, Y=sut.Y)

    pdt.assert_index_equal(ordering.activity_index, sut.S.index)
    pdt.assert_index_equal(ordering.commodity_index, sut.U.index)
    pdt.assert_index_equal(ordering.unified_index, sut.Z.index)
    pdt.assert_index_equal(ordering.final_demand_columns, sut.Y.columns)


def test_sut_concat_and_extract_match_database_flows():
    sut = load_test("SUT")
    ordering = SUTUnifiedOrderingPolicy.from_blocks(U=sut.U, S=sut.S, Y=sut.Y, X=sut.X, V=sut.V, E=sut.E)

    pdt.assert_frame_equal(concat_sut_Z(sut.U, sut.S, ordering), sut.Z)
    pdt.assert_frame_equal(extract_U_from_Z(sut.Z, ordering), sut.U)
    pdt.assert_frame_equal(extract_S_from_Z(sut.Z, ordering), sut.S)

    Ya = extract_Ya_from_Y(sut.Y, ordering)
    Yc = extract_Yc_from_Y(sut.Y, ordering)
    pdt.assert_frame_equal(concat_sut_Y(Ya, Yc, ordering), sut.Y)

    Xa = extract_Xa_from_X(sut.X, ordering)
    Xc = extract_Xc_from_X(sut.X, ordering)
    pdt.assert_frame_equal(concat_sut_X(Xa, Xc, ordering), sut.X)

    Va = extract_Va_from_V(sut.V, ordering)
    Vc = extract_Vc_from_V(sut.V, ordering)
    pdt.assert_frame_equal(concat_sut_V(Va, Vc, ordering), sut.V)

    Ea = extract_Ea_from_E(sut.E, ordering)
    Ec = extract_Ec_from_E(sut.E, ordering)
    pdt.assert_frame_equal(concat_sut_E(Ea, Ec, ordering), sut.E)


def test_sut_concat_and_extract_match_database_coefficients_and_views():
    sut = load_test("SUT")
    sut.calc_all([_ENUM.z, _ENUM.u, _ENUM.s, _ENUM.w, _ENUM.v, _ENUM.e, _ENUM.p, _ENUM.m, _ENUM.f])
    ordering = SUTUnifiedOrderingPolicy.from_blocks(z=sut.z, w=sut.w, Y=sut.Y)

    pdt.assert_frame_equal(concat_sut_z(sut.u, sut.s, ordering), sut.z)
    pdt.assert_frame_equal(extract_u_from_z(sut.z, ordering), sut.u)
    pdt.assert_frame_equal(extract_s_from_z(sut.z, ordering), sut.s)

    wcc = extract_wcc_from_w(sut.w, ordering)
    wca = extract_wca_from_w(sut.w, ordering)
    wac = extract_wac_from_w(sut.w, ordering)
    waa = extract_waa_from_w(sut.w, ordering)
    pdt.assert_frame_equal(concat_sut_w(wcc, wca, wac, waa, ordering), sut.w)

    va = extract_va_from_v(sut.v, ordering)
    vc = extract_vc_from_v(sut.v, ordering)
    pdt.assert_frame_equal(concat_sut_v(va, vc, ordering), sut.v)

    ea = extract_ea_from_e(sut.e, ordering)
    ec = extract_ec_from_e(sut.e, ordering)
    pdt.assert_frame_equal(concat_sut_e(ea, ec, ordering), sut.e)

    ma = extract_ma_from_m(sut.m, ordering)
    mc = extract_mc_from_m(sut.m, ordering)
    pdt.assert_frame_equal(concat_sut_m(ma, mc, ordering), sut.m)

    fa = extract_fa_from_f(sut.f, ordering)
    fc = extract_fc_from_f(sut.f, ordering)
    pdt.assert_frame_equal(concat_sut_f(fa, fc, ordering), sut.f)

    pa = extract_pa_from_p(sut.p, ordering)
    pc = extract_pc_from_p(sut.p, ordering)
    pdt.assert_frame_equal(concat_sut_p(pa, pc, ordering), sut.p)
