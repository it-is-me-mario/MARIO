"""Exercise public SUT helpers through the same imports shown in the API reference."""

import mario
import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from mario.log_exc.exceptions import WrongInput


@pytest.mark.parametrize("assumption", ["IT", "PT"])
def test_native_sut_helpers_match_database_blocks(assumption):
    db = mario.load_test("SUT", tech_assumption=assumption)
    blocks = db.resolve_many(
        ["U", "S", "Xa", "Xc", "Ya", "Yc", "u", "s", "wcc", "wca",
         "wac", "waa", "bu", "bs", "gcc", "gca", "gac", "gaa", "va", "vc",
         "pa", "pc"]
    )
    calls = {
        "u": (mario.calc_u, ["U", "Xa"]),
        "U": (mario.calc_U, ["u", "Xa"]),
        "s": (mario.calc_s, ["S", "Xc"]),
        "S": (mario.calc_S, ["s", "Xc"]),
        "Xa": (mario.calc_Xa, ["S", "Ya"]),
        "Xc": (mario.calc_Xc, ["U", "Yc"]),
        "wcc": (mario.calc_wcc, ["u", "s"]),
        "wca": (mario.calc_wca, ["u", "s"]),
        "wac": (mario.calc_wac, ["s", "u"]),
        "waa": (mario.calc_waa, ["s", "u"]),
        "bu": (mario.calc_bu, ["Xc", "U"]),
        "bs": (mario.calc_bs, ["Xa", "S"]),
        "gcc": (mario.calc_gcc, ["bu", "bs"]),
        "gca": (mario.calc_gca, ["gcc", "bu"]),
        "gac": (mario.calc_gac, ["gaa", "bs"]),
        "gaa": (mario.calc_gaa, ["bs", "bu"]),
        "pa": (mario.calc_pa, ["va", "vc", "waa", "wca"]),
        "pc": (mario.calc_pc, ["va", "vc", "wac", "wcc"]),
    }
    if assumption == "PT":
        blocks["c"] = db.resolve("c")
        calls["c"] = (mario.calc_c, ["S", "Xa"])

    for target, (function, inputs) in calls.items():
        options = {"Xa": blocks["Xa"], "tech_assumption": assumption} if target in {"s", "S"} else {}
        result = function(*(blocks[name] for name in inputs), **options)
        pdt.assert_frame_equal(result, blocks[target], obj=function.__name__)


def test_public_supply_helpers_select_technology_and_preserve_axes():
    S = pd.DataFrame([[6.0, 1.0], [2.0, 8.0]], index=["a1", "a2"], columns=["c1", "c2"])
    Xa = pd.Series([7.0, 10.0], index=S.index)
    Xc = pd.Series([8.0, 9.0], index=S.columns)

    s_it = mario.calc_s(S, Xc)
    pdt.assert_frame_equal(s_it, S.div(Xc, axis=1))
    pdt.assert_frame_equal(mario.calc_S(s_it, Xc), S)

    expected_c = pd.DataFrame([[6.0 / 7.0, 2.0 / 10.0], [1.0 / 7.0, 8.0 / 10.0]],
                              index=S.columns, columns=S.index)
    c = mario.calc_c(S, Xa)
    pdt.assert_frame_equal(c, expected_c)
    # PT needs activity production only; Xc may be omitted.
    s_pt = mario.calc_s(S, Xa=Xa, tech_assumption="PT")
    pdt.assert_frame_equal(s_pt @ c, pd.DataFrame(np.eye(2), index=S.index, columns=S.index))
    pdt.assert_frame_equal(mario.calc_S(s_pt, Xa=Xa, tech_assumption="product-based"), S)


def test_rectangular_sut_helpers_form_complete_leontief_and_ghosh_inverses():
    activities, commodities = ["a1", "a2"], ["c1", "c2", "c3"]
    U = pd.DataFrame([[2.0, 1.0], [0.0, 4.0], [3.0, 2.0]], index=commodities, columns=activities)
    S = pd.DataFrame([[5.0, 2.0, 3.0], [4.0, 11.0, 4.0]], index=activities, columns=commodities)
    Xa = pd.Series([40.0, 60.0], index=activities)
    Xc = pd.Series([30.0, 40.0, 50.0], index=commodities)
    u, s = mario.calc_u(U, Xa), mario.calc_s(S, Xc)
    pdt.assert_frame_equal(mario.calc_U(u, Xa), U)
    pdt.assert_frame_equal(mario.calc_S(s, Xc), S)
    wcc, wca = mario.calc_wcc(u, s), mario.calc_wca(u, s)
    wac, waa = mario.calc_wac(s, u), mario.calc_waa(s, u)
    for block, rows, columns in [(wcc, commodities, commodities), (wca, commodities, activities),
                                 (wac, activities, commodities), (waa, activities, activities)]:
        assert block.index.tolist() == rows
        assert block.columns.tolist() == columns
    W = np.block([[wcc, wca], [wac, waa]])
    A = np.block([[np.zeros((3, 3)), u], [s, np.zeros((2, 2))]])
    np.testing.assert_allclose(W @ (np.eye(5) - A), np.eye(5), atol=1e-14)

    bu, bs = mario.calc_bu(Xc, U), mario.calc_bs(Xa, S)
    gcc, gaa = mario.calc_gcc(bu, bs), mario.calc_gaa(bs, bu)
    G = np.block([[gcc, mario.calc_gca(gcc, bu)], [mario.calc_gac(gaa, bs), gaa]])
    B = np.block([[np.zeros((3, 3)), bu], [bs, np.zeros((2, 2))]])
    np.testing.assert_allclose(G @ (np.eye(5) - B), np.eye(5), atol=1e-14)

    va = pd.DataFrame([[0.2, 0.3], [0.1, 0.4]], index=["labour", "capital"], columns=activities)
    vc = pd.DataFrame([[0.1, 0.2, 0.3]], index=["taxes"], columns=commodities)
    expected_prices = np.r_[vc.sum(axis=0), va.sum(axis=0)] @ W
    pc, pa = mario.calc_pc(va, vc, wac, wcc), mario.calc_pa(va, vc, waa, wca)
    np.testing.assert_allclose(np.r_[pc.iloc[:, 0], pa.iloc[:, 0]], expected_prices)
    assert pc.index.tolist() == commodities
    assert pa.index.tolist() == activities
    assert pa.columns.tolist() == pc.columns.tolist() == ["price index"]


@pytest.mark.parametrize("helper,axis", [(mario.calc_u, 1), (mario.calc_s, 1),
                                        (mario.calc_bu, 0), (mario.calc_bs, 0)])
def test_coefficient_helpers_keep_zero_production_finite(helper, axis):
    flows = pd.DataFrame([[4.0, 2.0], [6.0, 8.0]], index=["r1", "r2"], columns=["c1", "c2"])
    production = pd.Series([2.0, 0.0], index=flows.columns if axis == 1 else flows.index)
    result = helper(flows, production) if axis == 1 else helper(production, flows)
    expected = pd.DataFrame([[2.0, 0.0], [3.0, 0.0]] if axis == 1 else [[2.0, 1.0], [0.0, 0.0]],
                            index=flows.index, columns=flows.columns)
    pdt.assert_frame_equal(result, expected)


@pytest.mark.parametrize("helper", [mario.calc_s, mario.calc_S])
def test_supply_helpers_reject_incomplete_or_incompatible_inputs(helper):
    supply = pd.DataFrame([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
                          index=["a1", "a2"], columns=["c1", "c2", "c3"])
    with pytest.raises(ValueError, match="Xa is required"):
        helper(supply, tech_assumption="PT")
    with pytest.raises(TypeError, match="Xc must be"):
        helper(supply)
    with pytest.raises(ValueError, match="square"):
        helper(supply, Xa=pd.Series([10.0, 20.0], index=supply.index), tech_assumption="PT")
    with pytest.raises(WrongInput, match="tech_assumption"):
        helper(supply, tech_assumption="unknown")


def test_use_helpers_reject_reordered_production_axes():
    U = pd.DataFrame([[2.0, 4.0]], index=["c1"], columns=["a1", "a2"])
    with pytest.raises(ValueError, match="do not match"):
        mario.calc_u(U, pd.Series([10.0, 20.0], index=["a2", "a1"]))
