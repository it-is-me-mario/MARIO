import os

import pandas.testing as pdt
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
