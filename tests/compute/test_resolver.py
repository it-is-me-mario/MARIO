import numpy as np
import pandas.testing as pdt
import pytest

from mario.compute.catalog import COMPUTE_CATALOG
from mario.compute.graph import build_dependency_graph, render_dependency_graph
from mario.compute.planner import build_plan
from mario.compute.resolver import explain, resolve
from mario.compute.runtime import choose_linear_strategy
from mario.compute.types import AxisSpec, FormulaStrategy, MatrixKey, MatrixSpec, MatrixStatus, ResolutionContext, StrategyKind
from mario.model.enums import TableKind
from mario.model.labels import INDEX_LABELS, ITEM_LABEL
from mario.compute.primitives import calc_w, calc_z
from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.sut_formulas import (
    build_sut_ea_from_Ea_Xa,
    build_sut_ec_from_Ec_Xc,
    build_sut_fc_from_ea_s_wcc,
    build_sut_pa_from_va,
    build_sut_va_from_Va_Xa,
    build_sut_vc_from_Vc_Xc,
    build_sut_wca_from_u_s,
    build_sut_wcc_from_u_s,
    build_sut_waa_from_s_u,
)
from mario.compute.views import (
    extract_Ea_from_E,
    extract_Ec_from_E,
    extract_Va_from_V,
    extract_Vc_from_V,
    extract_Xa_from_X,
    extract_Xc_from_X,
)
from mario.test.mario_test import load_test
from mario.model.conventions import _ENUM


def test_build_plan_iot_resolves_dependency_order():
    iot = load_test("IOT")
    plan = build_plan("w", iot)

    assert [step.key.name for step in plan] == ["X", "z", "w"]
    assert [step.strategy_kind for step in plan] == [
        StrategyKind.FORMULA,
        StrategyKind.FORMULA,
        StrategyKind.FORMULA,
    ]


def test_resolve_iot_materializes_expected_result():
    iot = load_test("IOT")
    assert "z" not in iot["baseline"]
    assert "w" not in iot["baseline"]

    resolved = resolve("w", iot)
    expected = calc_w(calc_z(iot.Z, iot.X))

    pdt.assert_frame_equal(resolved, expected)
    assert "z" not in iot["baseline"]
    assert "w" in iot["baseline"]


def test_resolve_iot_solve_context_materializes_w_via_linear_solve(monkeypatch):
    iot = load_test("IOT")
    expected = calc_w(calc_z(iot.Z, iot.X))

    def _boom(*args, **kwargs):
        raise AssertionError("safe_inverse should not be called under solve context")

    monkeypatch.setattr("mario.compute.iot_formulas.safe_inverse", _boom)

    resolved = resolve("w", iot, context=ResolutionContext(compute_method="solve", linear_solver="scipy"))

    pdt.assert_frame_equal(resolved, expected)
    assert "w" in iot["baseline"]


def test_resolve_iot_solve_context_avoids_materializing_w_for_f():
    iot = load_test("IOT")

    resolved = resolve("f", iot, context=ResolutionContext(compute_method="solve", linear_solver="scipy"))
    expected = iot.e.dot(calc_w(calc_z(iot.Z, iot.X)))

    pdt.assert_frame_equal(resolved, expected)
    assert "f" in iot["baseline"]
    assert "w" not in iot["baseline"]


def test_resolve_iot_auto_context_can_prefer_solve_when_memory_budget_is_tight(monkeypatch):
    iot = load_test("IOT")
    monkeypatch.setattr("mario.compute.runtime.physical_memory_bytes", lambda: 1)

    resolved = resolve("f", iot, context=ResolutionContext(compute_method="auto", linear_solver="scipy"))
    expected = iot.e.dot(calc_w(calc_z(iot.Z, iot.X)))

    pdt.assert_frame_equal(resolved, expected)
    assert "w" not in iot["baseline"]


def test_resolve_iot_iterative_linear_strategy_avoids_sparse_direct_factorization(monkeypatch):
    iot = load_test("IOT")

    def _boom(*args, **kwargs):
        raise AssertionError("factorized should not be called under iterative strategy")

    monkeypatch.setattr("scipy.sparse.linalg.factorized", _boom)

    resolved = resolve(
        "f",
        iot,
        context=ResolutionContext(
            compute_method="solve",
            linear_solver="scipy",
            linear_strategy="iterative",
        ),
    )
    expected = iot.e.dot(calc_w(calc_z(iot.Z, iot.X)))

    pdt.assert_frame_equal(resolved, expected)
    assert "w" not in iot["baseline"]


def test_resolve_iot_direct_linear_strategy_falls_back_to_iterative_when_factorization_fails(monkeypatch):
    iot = load_test("IOT")

    def _boom(*args, **kwargs):
        raise RuntimeError("Factor is exactly singular")

    monkeypatch.setattr("scipy.sparse.linalg.factorized", _boom)

    resolved = resolve(
        "f",
        iot,
        context=ResolutionContext(
            compute_method="solve",
            linear_solver="scipy",
            linear_strategy="direct",
        ),
    )
    expected = iot.e.dot(calc_w(calc_z(iot.Z, iot.X)))

    pdt.assert_frame_equal(resolved, expected)
    assert "w" not in iot["baseline"]


def test_resolve_iot_iterative_then_direct_failure_falls_back_to_least_squares(monkeypatch):
    iot = load_test("IOT")

    def _nonconvergent(*args, **kwargs):
        vector = np.asarray(args[1], dtype=float)
        return np.zeros_like(vector), 1

    def _boom(*args, **kwargs):
        raise RuntimeError("Factor is exactly singular")

    monkeypatch.setattr("scipy.sparse.linalg.lgmres", _nonconvergent)
    monkeypatch.setattr("scipy.sparse.linalg.factorized", _boom)

    resolved = resolve(
        "f",
        iot,
        context=ResolutionContext(
            compute_method="solve",
            linear_solver="scipy",
            linear_strategy="iterative",
        ),
    )
    expected = iot.e.dot(calc_w(calc_z(iot.Z, iot.X)))

    pdt.assert_frame_equal(resolved, expected)
    assert "w" not in iot["baseline"]


def test_resolve_sut_solve_context_avoids_materializing_w_quadrants_for_fc():
    sut = load_test("SUT")
    ordering = SUTUnifiedOrderingPolicy.from_blocks(Z=sut.Z, Y=sut.Y, E=sut.E)
    Xa = extract_Xa_from_X(sut.X, ordering)
    Xc = extract_Xc_from_X(sut.X, ordering)
    Ea = extract_Ea_from_E(sut.E, ordering)
    Ec = extract_Ec_from_E(sut.E, ordering)
    ea = build_sut_ea_from_Ea_Xa(Ea, Xa)
    ec = build_sut_ec_from_Ec_Xc(Ec, Xc)
    expected = build_sut_fc_from_ea_s_wcc(ea, sut.s, build_sut_wcc_from_u_s(sut.u, sut.s), ec)

    resolved = resolve("fc", sut, context=ResolutionContext(compute_method="solve", linear_solver="scipy"))

    pdt.assert_frame_equal(resolved, expected)
    assert "fc" in sut["baseline"]
    assert "wcc" not in sut["baseline"]
    assert "waa" not in sut["baseline"]


def test_resolve_sut_iterative_linear_strategy_avoids_sparse_direct_factorization(monkeypatch):
    sut = load_test("SUT")
    ordering = SUTUnifiedOrderingPolicy.from_blocks(Z=sut.Z, Y=sut.Y, E=sut.E)
    Xa = extract_Xa_from_X(sut.X, ordering)
    Xc = extract_Xc_from_X(sut.X, ordering)
    Ea = extract_Ea_from_E(sut.E, ordering)
    Ec = extract_Ec_from_E(sut.E, ordering)
    ea = build_sut_ea_from_Ea_Xa(Ea, Xa)
    ec = build_sut_ec_from_Ec_Xc(Ec, Xc)
    expected = build_sut_fc_from_ea_s_wcc(ea, sut.s, build_sut_wcc_from_u_s(sut.u, sut.s), ec)

    def _boom(*args, **kwargs):
        raise AssertionError("factorized should not be called under iterative strategy")

    monkeypatch.setattr("scipy.sparse.linalg.factorized", _boom)

    resolved = resolve(
        "fc",
        sut,
        context=ResolutionContext(
            compute_method="solve",
            linear_solver="scipy",
            linear_strategy="iterative",
        ),
    )

    pdt.assert_frame_equal(resolved, expected)
    assert "wcc" not in sut["baseline"]
    assert "waa" not in sut["baseline"]


def test_resolve_sut_iterative_then_direct_failure_falls_back_to_least_squares(monkeypatch):
    sut = load_test("SUT")
    ordering = SUTUnifiedOrderingPolicy.from_blocks(Z=sut.Z, Y=sut.Y, E=sut.E)
    Xa = extract_Xa_from_X(sut.X, ordering)
    Xc = extract_Xc_from_X(sut.X, ordering)
    Ea = extract_Ea_from_E(sut.E, ordering)
    Ec = extract_Ec_from_E(sut.E, ordering)
    ea = build_sut_ea_from_Ea_Xa(Ea, Xa)
    ec = build_sut_ec_from_Ec_Xc(Ec, Xc)
    expected = build_sut_fc_from_ea_s_wcc(ea, sut.s, build_sut_wcc_from_u_s(sut.u, sut.s), ec)

    def _nonconvergent(*args, **kwargs):
        vector = np.asarray(args[1], dtype=float)
        return np.zeros_like(vector), 1

    def _boom(*args, **kwargs):
        raise RuntimeError("Factor is exactly singular")

    monkeypatch.setattr("scipy.sparse.linalg.lgmres", _nonconvergent)
    monkeypatch.setattr("scipy.sparse.linalg.factorized", _boom)

    resolved = resolve(
        "fc",
        sut,
        context=ResolutionContext(
            compute_method="solve",
            linear_solver="scipy",
            linear_strategy="iterative",
        ),
    )

    pdt.assert_frame_equal(resolved, expected)
    assert "wcc" not in sut["baseline"]
    assert "waa" not in sut["baseline"]


def test_resolve_sut_direct_linear_strategy_falls_back_to_iterative_when_factorization_fails(monkeypatch):
    sut = load_test("SUT")
    ordering = SUTUnifiedOrderingPolicy.from_blocks(Z=sut.Z, Y=sut.Y, E=sut.E)
    Xa = extract_Xa_from_X(sut.X, ordering)
    Xc = extract_Xc_from_X(sut.X, ordering)
    Ea = extract_Ea_from_E(sut.E, ordering)
    Ec = extract_Ec_from_E(sut.E, ordering)
    ea = build_sut_ea_from_Ea_Xa(Ea, Xa)
    ec = build_sut_ec_from_Ec_Xc(Ec, Xc)
    expected = build_sut_fc_from_ea_s_wcc(ea, sut.s, build_sut_wcc_from_u_s(sut.u, sut.s), ec)

    def _boom(*args, **kwargs):
        raise RuntimeError("Factor is exactly singular")

    monkeypatch.setattr("scipy.sparse.linalg.factorized", _boom)

    resolved = resolve(
        "fc",
        sut,
        context=ResolutionContext(
            compute_method="solve",
            linear_solver="scipy",
            linear_strategy="direct",
        ),
    )

    pdt.assert_frame_equal(resolved, expected)
    assert "wcc" not in sut["baseline"]
    assert "waa" not in sut["baseline"]


def test_choose_linear_strategy_auto_prefers_iterative_for_huge_system_with_seven_rhs(monkeypatch):
    monkeypatch.setattr("mario.compute.runtime.physical_memory_bytes", lambda: 1)
    chosen = choose_linear_strategy(size=32585, rhs_count=7, context=ResolutionContext(linear_strategy="auto"))
    assert chosen == "iterative"


def test_resolve_sut_solve_context_avoids_materializing_w_quadrants_for_pa():
    sut = load_test("SUT")
    ordering = SUTUnifiedOrderingPolicy.from_blocks(Z=sut.Z, Y=sut.Y, V=sut.V)
    Xa = extract_Xa_from_X(sut.X, ordering)
    Xc = extract_Xc_from_X(sut.X, ordering)
    Va = extract_Va_from_V(sut.V, ordering)
    Vc = extract_Vc_from_V(sut.V, ordering)
    va = build_sut_va_from_Va_Xa(Va, Xa)
    vc = build_sut_vc_from_Vc_Xc(Vc, Xc)
    expected = build_sut_pa_from_va(
        va,
        vc,
        build_sut_waa_from_s_u(sut.s, sut.u),
        build_sut_wca_from_u_s(sut.u, sut.s),
    )

    resolved = resolve("pa", sut, context=ResolutionContext(compute_method="solve", linear_solver="scipy"))

    pdt.assert_frame_equal(resolved, expected)
    assert "pa" in sut["baseline"]
    assert "wcc" not in sut["baseline"]
    assert "waa" not in sut["baseline"]


def test_build_plan_prefers_extract_for_materialized_sut_source():
    sut = load_test("SUT")
    sut["baseline"]["Z"] = sut.Z.copy()
    sut["baseline"].pop("U", None)
    assert "U" not in sut["baseline"]

    plan = build_plan("U", sut)

    assert len(plan) == 1
    assert plan[0].key.name == "U"
    assert plan[0].strategy_kind == StrategyKind.EXTRACT

    resolved = resolve("U", sut)
    pdt.assert_frame_equal(resolved, sut.Z.loc[:, :].loc[(slice(None), INDEX_LABELS["c"], slice(None)), (slice(None), INDEX_LABELS["a"], slice(None))])


def test_build_plan_resolves_sut_unified_w_through_quadrants():
    sut = load_test("SUT")

    plan = build_plan("w", sut)

    assert plan[-1].key.name == "w"
    assert plan[-1].strategy_kind == StrategyKind.CONCAT
    assert {"wcc", "wca", "wac", "waa"}.issubset({step.key.name for step in plan})

    resolved = resolve("w", sut)
    expected = calc_w(calc_z(sut.Z, sut.X))
    pdt.assert_frame_equal(resolved, expected)
    assert "w" in sut["baseline"]
    assert "wcc" not in sut["baseline"]
    assert "wca" not in sut["baseline"]
    assert "wac" not in sut["baseline"]
    assert "waa" not in sut["baseline"]


def test_resolve_sut_solve_context_materializes_w_via_linear_solve(monkeypatch):
    sut = load_test("SUT")
    expected = calc_w(calc_z(sut.Z, sut.X))

    def _boom(*args, **kwargs):
        raise AssertionError("safe_inverse should not be called under solve context")

    monkeypatch.setattr("mario.compute.sut_formulas.safe_inverse", _boom)

    resolved = resolve("w", sut, context=ResolutionContext(compute_method="solve", linear_solver="scipy"))

    pdt.assert_frame_equal(resolved, expected)
    assert "w" in sut["baseline"]
    assert "wcc" not in sut["baseline"]
    assert "wca" not in sut["baseline"]
    assert "wac" not in sut["baseline"]
    assert "waa" not in sut["baseline"]


def test_explain_plans_sut_formula_resolution():
    sut = load_test("SUT")
    text = explain("w", sut)

    assert "concat from wcc, wca, wac, waa" in text
    assert "formula build_sut_wcc_from_u_s" in text
    assert "formula build_sut_u_from_U_Xa" in text
    assert "formula build_sut_s_from_S_Xc" in text
    assert "not implemented" not in text


def test_dependency_graph_reports_cycles(monkeypatch):
    row_axis = (INDEX_LABELS["r"], INDEX_LABELS["s"], ITEM_LABEL)
    cyclic_a = MatrixSpec(
        key=MatrixKey(TableKind.IOT, "TEMP_A"),
        status=MatrixStatus.ADD,
        axes=AxisSpec(row_axis, row_axis),
        strategies=(
            FormulaStrategy(
                inputs=("TEMP_B",),
                function="build_iot_w_from_z",
                spreadsheet_expr="TEMP_A = TEMP_B",
            ),
        ),
    )
    cyclic_b = MatrixSpec(
        key=MatrixKey(TableKind.IOT, "TEMP_B"),
        status=MatrixStatus.ADD,
        axes=AxisSpec(row_axis, row_axis),
        strategies=(
            FormulaStrategy(
                inputs=("TEMP_A",),
                function="build_iot_w_from_z",
                spreadsheet_expr="TEMP_B = TEMP_A",
            ),
        ),
    )

    monkeypatch.setitem(COMPUTE_CATALOG[TableKind.IOT], "TEMP_A", cyclic_a)
    monkeypatch.setitem(COMPUTE_CATALOG[TableKind.IOT], "TEMP_B", cyclic_b)

    dataset = {"__table_kind__": "IOT", "baseline": {}}
    graph = build_dependency_graph("TEMP_A", dataset)
    rendered = render_dependency_graph(graph)

    assert "cycle" in rendered
    assert "TEMP_A -> TEMP_B -> TEMP_A" in rendered
