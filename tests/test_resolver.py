import pandas.testing as pdt
import pytest

from mario.compute.catalog import COMPUTE_CATALOG
from mario.compute.graph import build_dependency_graph, render_dependency_graph
from mario.compute.planner import build_plan
from mario.compute.resolver import explain, resolve
from mario.compute.types import AxisSpec, FormulaStrategy, MatrixKey, MatrixSpec, MatrixStatus, StrategyKind
from mario.model.enums import TableKind
from mario.model.labels import INDEX_LABELS, ITEM_LABEL
from mario.compute.primitives import calc_w, calc_z
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
    assert "z" in iot["baseline"]
    assert "w" in iot["baseline"]


def test_build_plan_prefers_extract_for_materialized_sut_source():
    sut = load_test("SUT")
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
    assert {"wcc", "wca", "wac", "waa", "w"}.issubset(set(sut["baseline"]))


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
