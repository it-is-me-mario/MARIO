import pandas as pd
import pytest

from mario import parse_eurostat
from mario.log_exc.exceptions import NotImplementable
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.eurostat_sdmx import build_eurostat_sut_from_frames
from mario.parsers.specs import (
    EUROSTAT_SATELLITE_PLACEHOLDER,
    EUROSTAT_SUT_ACTIVITY_LABELS,
    EUROSTAT_SUT_COMMODITY_LABELS,
)


def _supply_frame():
    return pd.DataFrame(
        [
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP15(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_impv": "A01",
                "prd_amo": "CPA_A01",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 100.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP15(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_impv": "A02",
                "prd_amo": "CPA_A02",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 200.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP15(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_impv": "P7",
                "prd_amo": "CPA_A01",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 5.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
        ]
    )


def _use_frame():
    return pd.DataFrame(
        [
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP16(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_use": "A01",
                "prd_ava": "CPA_A01",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 10.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP16(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_use": "A02",
                "prd_ava": "CPA_A02",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 20.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP16(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_use": "A01",
                "prd_ava": "D1",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 30.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP16(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_use": "A01",
                "prd_ava": "D11",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 31.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP16(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_use": "A01",
                "prd_ava": "D29X39",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 32.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP16(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_use": "A01",
                "prd_ava": "P51C",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 33.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP16(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_use": "A01",
                "prd_ava": "B2A3N",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 34.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP16(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_use": "P3",
                "prd_ava": "CPA_A01",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 40.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP16(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_use": "P5",
                "prd_ava": "CPA_A01",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 50.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP16(1.0)",
                "LAST UPDATE": "22/03/26 23:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "ind_use": "P6",
                "prd_ava": "CPA_A01",
                "geo": "IT",
                "TIME_PERIOD": 2017,
                "OBS_VALUE": 60.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
        ]
    )


def test_build_eurostat_sut_from_frames_returns_split_native_payload():
    matrices, indexes, units, layout = build_eurostat_sut_from_frames(
        _supply_frame(),
        _use_frame(),
        country="IT",
        year=2017,
        unit="MIO_EUR",
    )

    baseline = matrices["baseline"]
    activity_1 = EUROSTAT_SUT_ACTIVITY_LABELS["A01"]
    commodity_1 = EUROSTAT_SUT_COMMODITY_LABELS["CPA_A01"]

    assert layout.dataset_name == "Eurostat SUT IT 2017"
    assert set(baseline) == {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"}
    assert indexes["r"]["main"] == ["IT"]
    assert len(indexes["a"]["main"]) == 65
    assert len(indexes["c"]["main"]) == 65
    assert indexes["k"]["main"] == [EUROSTAT_SATELLITE_PLACEHOLDER]
    assert baseline["S"].loc[("IT", _MASTER_INDEX["a"], activity_1), ("IT", _MASTER_INDEX["c"], commodity_1)] == 100.0
    assert baseline["U"].loc[("IT", _MASTER_INDEX["c"], commodity_1), ("IT", _MASTER_INDEX["a"], activity_1)] == 10.0
    assert baseline["Yc"].loc[("IT", _MASTER_INDEX["c"], commodity_1), ("IT", _MASTER_INDEX["n"], "Final consumption expenditure")] == 40.0
    assert baseline["Va"].loc["Compensation of employees", ("IT", _MASTER_INDEX["a"], activity_1)] == 30.0
    assert baseline["Vc"].loc["Imports of goods and services", ("IT", _MASTER_INDEX["c"], commodity_1)] == 5.0
    assert baseline["Ea"].shape == (1, 65)
    assert units[_MASTER_INDEX["f"]].loc["Imports of goods and services", "unit"] == "MIO_EUR"


def test_parse_eurostat_uses_sdmx_backend(monkeypatch):
    supply_csv = _supply_frame().to_csv(index=False)
    use_csv = _use_frame().to_csv(index=False)

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    def fake_get(url, params=None, timeout=None):
        if "NAIO_10_CP15" in url:
            return FakeResponse(supply_csv)
        if "NAIO_10_CP16" in url:
            return FakeResponse(use_csv)
        raise AssertionError(url)

    monkeypatch.setattr("mario.parsers.eurostat_sdmx.requests.get", fake_get)

    database = parse_eurostat("IT", 2017, table="SUT", calc_all=False)

    assert database.table_type == "SUT"
    assert database.meta.year == 2017
    assert database.meta.price == "Current prices"
    assert "Z" not in database["baseline"]
    assert {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"} <= set(database["baseline"])
    assert database.get_index(_MASTER_INDEX["r"]) == ["IT"]
    assert database.get_index(_MASTER_INDEX["k"]) == [EUROSTAT_SATELLITE_PLACEHOLDER]


def test_parse_eurostat_iot_is_not_implemented_yet():
    with pytest.raises(NotImplementable):
        parse_eurostat("IT", 2017, table="IOT", calc_all=False)
