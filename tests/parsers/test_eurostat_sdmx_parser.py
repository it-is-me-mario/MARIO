import pandas as pd
import pytest

from mario import Database, parse_eurostat
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.eurostat_sdmx import (
    build_eurostat_iot_from_frame,
    build_eurostat_sut_from_frames,
)
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


def _iot_product_frame():
    return pd.DataFrame(
        [
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP1700(1.0)",
                "LAST UPDATE": "16/03/26 11:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "prd_use": "CPA_A01",
                "prd_ava": "CPA_A01",
                "geo": "IT",
                "TIME_PERIOD": 2015,
                "OBS_VALUE": 10.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP1700(1.0)",
                "LAST UPDATE": "16/03/26 11:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "prd_use": "CPA_A02",
                "prd_ava": "CPA_A02",
                "geo": "IT",
                "TIME_PERIOD": 2015,
                "OBS_VALUE": 20.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP1700(1.0)",
                "LAST UPDATE": "16/03/26 11:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "prd_use": "P3",
                "prd_ava": "CPA_A01",
                "geo": "IT",
                "TIME_PERIOD": 2015,
                "OBS_VALUE": 40.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP1700(1.0)",
                "LAST UPDATE": "16/03/26 11:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "prd_use": "P5",
                "prd_ava": "CPA_A01",
                "geo": "IT",
                "TIME_PERIOD": 2015,
                "OBS_VALUE": 50.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP1700(1.0)",
                "LAST UPDATE": "16/03/26 11:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "prd_use": "P6",
                "prd_ava": "CPA_A01",
                "geo": "IT",
                "TIME_PERIOD": 2015,
                "OBS_VALUE": 60.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP1700(1.0)",
                "LAST UPDATE": "16/03/26 11:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "prd_use": "CPA_A01",
                "prd_ava": "D1",
                "geo": "IT",
                "TIME_PERIOD": 2015,
                "OBS_VALUE": 30.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP1700(1.0)",
                "LAST UPDATE": "16/03/26 11:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "prd_use": "CPA_A01",
                "prd_ava": "D11",
                "geo": "IT",
                "TIME_PERIOD": 2015,
                "OBS_VALUE": 31.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP1700(1.0)",
                "LAST UPDATE": "16/03/26 11:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "prd_use": "CPA_A01",
                "prd_ava": "D29X39",
                "geo": "IT",
                "TIME_PERIOD": 2015,
                "OBS_VALUE": 32.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP1700(1.0)",
                "LAST UPDATE": "16/03/26 11:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "prd_use": "CPA_A01",
                "prd_ava": "P51C",
                "geo": "IT",
                "TIME_PERIOD": 2015,
                "OBS_VALUE": 33.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP1700(1.0)",
                "LAST UPDATE": "16/03/26 11:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "prd_use": "CPA_A01",
                "prd_ava": "B2A3N",
                "geo": "IT",
                "TIME_PERIOD": 2015,
                "OBS_VALUE": 34.0,
                "OBS_FLAG": None,
                "CONF_STATUS": None,
            },
            {
                "DATAFLOW": "ESTAT:NAIO_10_CP1700(1.0)",
                "LAST UPDATE": "16/03/26 11:00:00",
                "freq": "A",
                "unit": "MIO_EUR",
                "stk_flow": "TOTAL",
                "prd_use": "CPA_A01",
                "prd_ava": "P7",
                "geo": "IT",
                "TIME_PERIOD": 2015,
                "OBS_VALUE": 5.0,
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


def test_build_eurostat_iot_from_frame_returns_canonical_payload():
    matrices, indexes, units, layout = build_eurostat_iot_from_frame(
        _iot_product_frame(),
        country="IT",
        year=2015,
        unit="MIO_EUR",
        mode="product",
    )

    baseline = matrices["baseline"]
    sector_1 = EUROSTAT_SUT_COMMODITY_LABELS["CPA_A01"]

    assert layout.dataset_name == "Eurostat IOT IT 2015 product"
    assert set(baseline) == {"Z", "Y", "V", "E", "EY"}
    assert indexes["r"]["main"] == ["IT"]
    assert len(indexes["s"]["main"]) == 65
    assert indexes["k"]["main"] == [EUROSTAT_SATELLITE_PLACEHOLDER]
    assert baseline["Z"].loc[("IT", _MASTER_INDEX["s"], sector_1), ("IT", _MASTER_INDEX["s"], sector_1)] == 10.0
    assert baseline["Y"].loc[("IT", _MASTER_INDEX["s"], sector_1), ("IT", _MASTER_INDEX["n"], "Final consumption expenditure")] == 40.0
    assert baseline["V"].loc["Compensation of employees", ("IT", _MASTER_INDEX["s"], sector_1)] == 30.0
    assert baseline["V"].loc["Imports of goods and services", ("IT", _MASTER_INDEX["s"], sector_1)] == 5.0
    assert units[_MASTER_INDEX["s"]].loc[sector_1, "unit"] == "MIO_EUR"


def test_parse_eurostat_iot_uses_sdmx_backend(monkeypatch):
    iot_csv = _iot_product_frame().to_csv(index=False)

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    def fake_get(url, params=None, timeout=None):
        if "NAIO_10_CP1700" in url:
            return FakeResponse(iot_csv)
        raise AssertionError(url)

    monkeypatch.setattr("mario.parsers.eurostat_sdmx.requests.get", fake_get)

    database = parse_eurostat("IT", 2015, table="IOT", calc_all=False)

    assert database.table_type == "IOT"
    assert database.meta.year == 2015
    assert database.meta.price == "Current prices"
    assert set(database["baseline"]) == {"E", "EY", "V", "Y", "Z"}
    assert database.get_index(_MASTER_INDEX["r"]) == ["IT"]
    assert database.get_index(_MASTER_INDEX["k"]) == [EUROSTAT_SATELLITE_PLACEHOLDER]


def test_parse_eurostat_rejects_unknown_iot_mode():
    with pytest.raises(WrongInput):
        parse_eurostat("IT", 2015, table="IOT", iot_mode="unknown", calc_all=False)


def test_parse_eurostat_uses_local_raw_files_when_path_is_provided(tmp_path, monkeypatch):
    supply_path = tmp_path / "NAIO_10_CP15_IT_2017_MIO_EUR.csv"
    use_path = tmp_path / "NAIO_10_CP16_IT_2017_MIO_EUR.csv"
    _supply_frame().to_csv(supply_path, index=False)
    _use_frame().to_csv(use_path, index=False)

    def fail_get(*args, **kwargs):
        raise AssertionError("network should not be used when local Eurostat files exist")

    monkeypatch.setattr("mario.parsers.eurostat_sdmx.requests.get", fail_get)

    database = parse_eurostat(
        "IT",
        2017,
        table="SUT",
        path=tmp_path,
        calc_all=False,
    )

    assert database.table_type == "SUT"
    assert database.meta.year == 2017
    assert database.get_index(_MASTER_INDEX["r"]) == ["IT"]


@pytest.mark.parametrize("mode", ["product", "industry"])
@pytest.mark.parametrize("aggregate", [False, True])
def test_eurostat_iot_named_sector_heatmap_and_aggregation(mode, aggregate):
    raw = _iot_product_frame()
    if mode == "industry":
        raw = raw.rename(columns={"prd_ava": "ind_ava", "prd_use": "ind_use"})
        for column in ("ind_ava", "ind_use"):
            raw[column] = raw[column].str.removeprefix("CPA_")
    matrices, indexes, units, _ = build_eurostat_iot_from_frame(
        raw, country="IT", year=2015, unit="MIO_EUR", mode=mode,
    )
    database = Database(table="IOT", init_by_parsers={
        "matrices": matrices, "_indeces": indexes, "units": units,
    }, calc_all=False)
    total = database.Z.to_numpy().sum()
    if aggregate:
        sectors = database.sectors
        labels = ["Primary" if i < 2 else "Other" for i in range(len(sectors))]
        mapping = pd.DataFrame({"Aggregation": labels}, index=sectors)
        expected = [[
            database.Z.loc[
                database.Z.index.get_level_values(2).map(mapping.Aggregation) == row,
                database.Z.columns.get_level_values(2).map(mapping.Aggregation) == column,
            ].to_numpy().sum()
            for column in ("Primary", "Other")
        ] for row in ("Primary", "Other")]
        database.aggregate({"Sector": mapping}, levels="Sector")
        assert database.Z.shape == (2, 2)
        pd.testing.assert_frame_equal(
            database.Z, pd.DataFrame(expected, index=database.Z.index, columns=database.Z.columns),
        )
    assert database.Z.to_numpy().sum() == pytest.approx(total)
    figure = database.plot(
        matrix="Z", preset="heatmap", x="Sector_to", color="Sector_from",
        heatmap_y="Sector_from",
        category_orders={"Sector_from": database.sectors, "Sector_to": database.sectors},
        path=False,
    )
    assert list(figure.data[0].x) == database.sectors
    assert list(figure.data[0].y) == database.sectors
    assert figure.data[0].z.shape == database.Z.shape


def test_eurostat_sut_aggregation_reduces_both_productive_axes():
    matrices, indexes, units, _ = build_eurostat_sut_from_frames(
        _supply_frame(), _use_frame(), country="IT", year=2017, unit="MIO_EUR",
    )
    database = Database(table="SUT", init_by_parsers={
        "matrices": matrices, "_indeces": indexes, "units": units,
    }, calc_all=False)
    totals = {name: database.query(name).to_numpy().sum() for name in ("S", "U", "Yc", "Va")}
    levels = ["Activity", "Commodity"]
    mapping = {
        level: pd.DataFrame({"Aggregation": "All " + level}, index=database.get_index(level))
        for level in levels
    }
    database.aggregate(mapping, levels=levels)
    assert database.S.shape == (1, 1)
    assert database.U.shape == (1, 1)
    for name, total in totals.items():
        assert database.query(name).to_numpy().sum() == pytest.approx(total)
