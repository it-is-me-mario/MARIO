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
from mario.parsers.entrypoints import parse_from_excel
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
        expected = expected.groupby(axis=1, level=list(range(expected.columns.nlevels)), sort=False).sum()
    else:
        expected.columns = pd.Index(
            [item_target if item_target is not None else value for value in columns],
            name=columns.name,
        )
        expected = expected.groupby(axis=1, level=[0], sort=False).sum()
    return expected


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
