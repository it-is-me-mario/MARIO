import os

import pandas as pd
import pandas.testing as pdt
import pytest
from pymrio import IOSystem

from mario.ops import (
    aggregate_database,
    build_new_instance_from_scenario,
    export_database_to_pymrio,
    transform_sut_to_iot,
    transform_to_chenery_moses,
)
from mario.test.mario_test import load_test
from mario.model.conventions import _ENUM
from mario.parsers.api import build_database_from_state, build_parser_state
from mario.parsers.entrypoints import parse_from_excel
from mario.parsers.matrix_layouts import sut_block_specs_for_matrix_layouts
from mario.views import build_database_frame


MAIN_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK_PATH = f"{MAIN_PATH}/tests/mocks"


def _write_iot_layout_workbook(path):
    flows = pd.DataFrame(
        [
            [None, None, None, "r1", "r1", "r2", "r2", None, None],
            [None, None, None, "s1", "s2", "s1", "s2", "hh", "investment"],
            ["r1", "s1", None, 20, 15, 4, 5, 15, 25],
            ["r1", "s2", None, 10, 54, 5, 5, 20, 45],
            ["r2", "s1", None, 5, 5, 18, 11, 15, 30],
            ["r2", "s2", None, 3, 5, 9, 41, 35, 30],
            ["r1", "s1", "taxes", 10, 5, 2, 1, 0, 0],
            ["r1", "s1", "capital", 18, 4, 1, 1, 0, 0],
            ["r1", "s2", "taxes", 1, 21, 4, 2, 0, 0],
            ["r1", "s2", "capital", 5, 15, 2, 3, 0, 0],
            ["r2", "s1", "taxes", 2, 0, 12, 7, 0, 0],
            ["r2", "s1", "capital", 1, 0, 8, 10, 0, 0],
            ["r2", "s2", "taxes", 3, 2, 2, 32, 0, 0],
            ["r2", "s2", "capital", 2, 4, 6, 18, 0, 0],
            ["r1", "CO2", None, 10, 5, 20, 10, 4, 0],
            ["r2", "CO2", None, 23, 6, 5, 2, 1, 2],
        ]
    )
    units = pd.DataFrame(
        [
            [None, None, "unit"],
            ["Sector", "s1", "EUR"],
            ["Sector", "s2", "EUR"],
            ["Factor of production", "taxes", "EUR"],
            ["Factor of production", "capital", "EUR"],
            ["Satellite account", "CO2", "ton"],
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        flows.to_excel(writer, sheet_name="flows", header=False, index=False)
        units.to_excel(writer, sheet_name="units", header=False, index=False)


def _aggregate_expected_standard_axis(frame, *, region_target=None, item_target=None):
    expected = frame.copy()
    columns = expected.columns
    if isinstance(columns, pd.MultiIndex):
        arrays = []
        for level in range(columns.nlevels):
            values = list(columns.get_level_values(level))
            if level == 0 and region_target is not None:
                values = [region_target] * len(values)
            elif level == columns.nlevels - 1 and item_target is not None:
                values = [item_target] * len(values)
            arrays.append(values)
        expected.columns = pd.MultiIndex.from_arrays(arrays, names=columns.names)
        expected = expected.T.groupby(
            level=list(range(expected.columns.nlevels)),
            sort=False,
        ).sum().T
    else:
        expected.columns = pd.Index(
            [item_target if item_target is not None else value for value in columns],
            name=columns.name,
        )
        expected = expected.T.groupby(level=[0], sort=False).sum().T
    return expected


def _build_custom_sut_database():
    productive = pd.MultiIndex.from_tuples(
        [
            ("r1", "Activity", "a1"),
            ("r1", "Activity", "a2"),
            ("r1", "Commodity", "c1"),
            ("r1", "Commodity", "c2"),
        ],
        names=["Region", "Level", "Item"],
    )
    final_demand = pd.MultiIndex.from_tuples(
        [("r1", "Consumption category", "hh")],
        names=["Region", "Level", "Item"],
    )
    factors = pd.MultiIndex.from_tuples(
        [
            ("r1", "a1", "taxes"),
            ("r1", "a1", "capital"),
            ("r1", "a2", "taxes"),
            ("r1", "a2", "capital"),
        ],
        names=["Region", "Activity", "Factor of production"],
    )
    satellites = pd.MultiIndex.from_tuples(
        [("r1", "a1", "CO2"), ("r1", "a2", "CO2")],
        names=["Region", "Activity", "Satellite account"],
    )

    blocks = {
        "Z": pd.DataFrame(
            [
                [0.0, 0.0, 40.0, 10.0],
                [0.0, 0.0, 20.0, 30.0],
                [5.0, 7.0, 0.0, 0.0],
                [3.0, 9.0, 0.0, 0.0],
            ],
            index=productive,
            columns=productive,
        ),
        "Y": pd.DataFrame(
            [[0.0], [0.0], [50.0], [60.0]],
            index=productive,
            columns=final_demand,
        ),
        "V": pd.DataFrame(
            [
                [4.0, 0.0, 0.0, 0.0],
                [6.0, 0.0, 0.0, 0.0],
                [0.0, 5.0, 0.0, 0.0],
                [0.0, 8.0, 0.0, 0.0],
            ],
            index=factors,
            columns=productive,
        ),
        "E": pd.DataFrame(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 2.0, 0.0, 0.0],
            ],
            index=satellites,
            columns=productive,
        ),
        "EY": pd.DataFrame([[0.5], [1.5]], index=satellites, columns=final_demand),
        "VY": pd.DataFrame([[0.0], [0.0], [0.0], [0.0]], index=factors, columns=final_demand),
    }
    indexes = {
        "r": {"main": ["r1"]},
        "n": {"main": ["hh"]},
        "a": {"main": ["a1", "a2"]},
        "c": {"main": ["c1", "c2"]},
        "s": {"main": ["a1", "a2", "c1", "c2"]},
        "f": {"main": ["taxes", "capital"]},
        "k": {"main": ["CO2"]},
    }
    units = {
        "Activity": pd.DataFrame({"unit": ["EUR", "EUR"]}, index=pd.Index(["a1", "a2"], name="Item")),
        "Commodity": pd.DataFrame({"unit": ["EUR", "EUR"]}, index=pd.Index(["c1", "c2"], name="Item")),
        "Factor of production": pd.DataFrame({"unit": ["EUR", "EUR"]}, index=pd.Index(["taxes", "capital"], name="Item")),
        "Satellite account": pd.DataFrame({"unit": ["ton"]}, index=pd.Index(["CO2"], name="Item")),
    }
    state = build_parser_state(
        table="SUT",
        matrices={"baseline": blocks},
        indexes=indexes,
        units=units,
        parser_name="tests",
        mode="flows",
        name="custom SUT",
    )
    state.metadata.extra["block_specs"] = sut_block_specs_for_matrix_layouts(
        {"V": ("Region", "Activity"), "E": ("Region", "Activity")}
    )
    return build_database_from_state(state, calc_all=False)


def test_build_new_instance_from_scenario_returns_baseline_clone():
    database = load_test("IOT")
    database.calc_all([_ENUM.X])
    database.clone_scenario("baseline", "policy")

    instance = build_new_instance_from_scenario(database, "policy")

    assert instance.scenarios == ["baseline"]
    for matrix, value in instance["baseline"].items():
        database.calc_all([matrix], scenario="policy")
        pdt.assert_frame_equal(database["policy"][matrix].round(0), value.round(0))


def test_transform_wrappers_match_database_results():
    sut = load_test("SUT")
    chenery = transform_to_chenery_moses(sut, inplace=False)
    iot = transform_sut_to_iot(load_test("SUT"), "A", inplace=False)

    assert chenery.table_type == "SUT"
    assert iot.table_type == "IOT"
    assert chenery.scenarios == ["baseline"]
    assert iot.scenarios == ["baseline"]


def test_transform_sut_to_iot_preserves_custom_extension_and_factor_rows():
    sut = _build_custom_sut_database()

    iot = transform_sut_to_iot(sut, "C", inplace=False)

    assert iot.table_type == "IOT"
    assert iot.V.index.names == ["Region", "Activity", "Factor of production"]
    assert iot.E.index.names == ["Region", "Activity", "Satellite account"]
    assert tuple(axis.id for axis in iot.get_block_spec("V").row_axes) == (
        "Region",
        "Activity",
        "Factor of production",
    )
    assert tuple(axis.id for axis in iot.get_block_spec("V").col_axes) == (
        "Region",
        "Sector",
    )
    assert tuple(axis.id for axis in iot.get_block_spec("E").row_axes) == (
        "Region",
        "Activity",
        "Satellite account",
    )
    assert tuple(axis.id for axis in iot.get_block_spec("E").col_axes) == (
        "Region",
        "Sector",
    )


def test_aggregate_database_wrapper_returns_aggregated_copy():
    database = parse_from_excel(
        path=f"{MOCK_PATH}/IOT_aggregation.xlsx",
        table="IOT",
        mode="flows",
    )

    aggregated = aggregate_database(
        database,
        io=f"{MOCK_PATH}/IOT_aggregation.xlsx",
        levels="Region",
        inplace=False,
    )

    assert aggregated is not database
    assert len(aggregated.get_index("Region")) <= len(database.get_index("Region"))


def test_aggregate_database_supports_custom_matrix_layouts(tmp_path):
    path = tmp_path / "layout_iot.xlsx"
    _write_iot_layout_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"V": ("Region", "Sector"), "E": "Region", "EY": "Region"},
        calc_all=False,
    )

    mappings = {
        "Region": pd.DataFrame({"Aggregation": ["world", "world"]}, index=["r1", "r2"]),
        "Sector": pd.DataFrame({"Aggregation": ["sec", "sec"]}, index=["s1", "s2"]),
    }
    aggregated = aggregate_database(
        database,
        io=mappings,
        levels=["Region", "Sector"],
        inplace=False,
        calc_all=False,
    )

    assert aggregated.get_index("Region") == ["world"]
    assert aggregated.get_index("Sector") == ["sec"]
    assert aggregated.E.index.names == ["Region", "Satellite account"]
    assert aggregated.V.index.names == ["Region", "Sector", "Factor of production"]
    assert tuple(axis.id for axis in aggregated.get_block_spec("E").row_axes) == (
        "Region",
        "Satellite account",
    )
    assert tuple(axis.id for axis in aggregated.get_block_spec("V").row_axes) == (
        "Region",
        "Sector",
        "Factor of production",
    )

    expected_e = database.E.copy()
    expected_e.index = pd.MultiIndex.from_arrays(
        [
            ["world"] * len(expected_e.index),
            expected_e.index.get_level_values(1),
        ],
        names=expected_e.index.names,
    )
    expected_e = expected_e.groupby(level=[0, 1], sort=False).sum()
    expected_e = _aggregate_expected_standard_axis(
        expected_e,
        region_target="world",
        item_target="sec",
    )

    expected_v = database.V.copy()
    expected_v.index = pd.MultiIndex.from_arrays(
        [
            ["world"] * len(expected_v.index),
            ["sec"] * len(expected_v.index),
            expected_v.index.get_level_values(2),
        ],
        names=expected_v.index.names,
    )
    expected_v = expected_v.groupby(level=[0, 1, 2], sort=False).sum()
    expected_v = _aggregate_expected_standard_axis(
        expected_v,
        region_target="world",
        item_target="sec",
    )

    pdt.assert_frame_equal(aggregated.E, expected_e)
    pdt.assert_frame_equal(aggregated.V, expected_v)


def test_aggregate_database_supports_custom_sut_matrix_layouts():
    database = _build_custom_sut_database()

    mappings = {
        "Region": pd.DataFrame({"Aggregation": ["world"]}, index=["r1"]),
        "Activity": pd.DataFrame({"Aggregation": ["act", "act"]}, index=["a1", "a2"]),
        "Commodity": pd.DataFrame({"Aggregation": ["com", "com"]}, index=["c1", "c2"]),
    }
    aggregated = aggregate_database(
        database,
        io=mappings,
        levels=["Region", "Activity", "Commodity"],
        inplace=False,
        calc_all=False,
    )

    assert aggregated.get_index("Region") == ["world"]
    assert aggregated.get_index("Activity") == ["act"]
    assert aggregated.get_index("Commodity") == ["com"]
    assert aggregated.V.index.names == ["Region", "Activity", "Factor of production"]
    assert aggregated.E.index.names == ["Region", "Activity", "Satellite account"]
    assert tuple(axis.id for axis in aggregated.get_block_spec("V").row_axes) == (
        "Region",
        "Activity",
        "Factor of production",
    )
    assert tuple(axis.id for axis in aggregated.get_block_spec("E").row_axes) == (
        "Region",
        "Activity",
        "Satellite account",
    )


def test_aggregate_database_preserves_zero_output_sut_coefficients_with_epsilon(caplog):
    database = _build_custom_sut_database()
    database.clone_scenario("baseline", "policy")
    database.calc_all(
        [_ENUM.z, _ENUM.e, _ENUM.v, _ENUM.X, _ENUM.Z, _ENUM.V, _ENUM.E],
        scenario="policy",
    )

    target = ("r1", "Activity", "a1")
    policy = database.matrices["policy"]
    assert float(policy[_ENUM.z].loc[:, target].abs().sum()) > 0.0

    policy[_ENUM.X].loc[target, :] = 0.0
    policy[_ENUM.Z].loc[target, :] = 0.0
    policy[_ENUM.Z].loc[:, target] = 0.0
    policy[_ENUM.V].loc[:, target] = 0.0
    policy[_ENUM.E].loc[:, target] = 0.0
    if _ENUM.Y not in policy:
        policy[_ENUM.Y] = database.query([_ENUM.Y], scenarios=["policy"])
    policy[_ENUM.Y].loc[target, :] = 0.0

    mapping = {
        "Region": pd.DataFrame({"Aggregation": ["world"]}, index=["r1"]),
    }

    without_epsilon = database.copy().aggregate(
        io=mapping,
        levels=["Region"],
        inplace=False,
        zero_output_epsilon=None,
    )

    with caplog.at_level("WARNING"):
        with_epsilon = database.copy().aggregate(
            io=mapping,
            levels=["Region"],
            inplace=False,
        )

    aggregated_target = ("world", "Activity", "a1")
    without_epsilon_z = without_epsilon.query([_ENUM.z], scenarios=["policy"])
    with_epsilon_z = with_epsilon.query([_ENUM.z], scenarios=["policy"])
    assert float(without_epsilon_z.loc[:, aggregated_target].abs().sum()) == 0.0
    assert float(with_epsilon_z.loc[:, aggregated_target].abs().sum()) > 0.0
    assert any("zero_output_epsilon" in record.message for record in caplog.records)


def test_export_to_pymrio_and_tabular_view_work_from_new_modules():
    iot = load_test("IOT")
    sut = load_test("SUT")

    io = export_database_to_pymrio(
        iot,
        satellite_account="Extensions",
        factor_of_production="Value_added",
    )
    frame = build_database_frame(sut)

    assert isinstance(io, IOSystem)
    pdt.assert_frame_equal(frame, sut.DataFrame())
