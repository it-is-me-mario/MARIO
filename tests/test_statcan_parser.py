import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.parsers.statcan_wds import (
    build_statcan_iot_from_frame,
    build_statcan_sut_from_frame,
)


def _statcan_sut_frame() -> pd.DataFrame:
    rows = [
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Supply and use": "Supply",
            "Valuation": "Basic price",
            "Industry": "Crop and animal production [BS11A]",
            "Product": "Grains and other crop products [M111B]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v1",
            "COORDINATE": "1",
            "VALUE": 10.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Supply and use": "Supply",
            "Valuation": "Basic price",
            "Industry": "Manufacturing [BS3A0]",
            "Product": "Food and non-alcoholic beverages [M31C0]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v2",
            "COORDINATE": "2",
            "VALUE": 20.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Supply and use": "Use",
            "Valuation": "Basic price",
            "Industry": "Crop and animal production [BS11A]",
            "Product": "Grains and other crop products [M111B]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v3",
            "COORDINATE": "3",
            "VALUE": 1.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Supply and use": "Use",
            "Valuation": "Basic price",
            "Industry": "Manufacturing [BS3A0]",
            "Product": "Food and non-alcoholic beverages [M31C0]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v4",
            "COORDINATE": "4",
            "VALUE": 2.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Supply and use": "Use",
            "Valuation": "Basic price",
            "Industry": "Household final consumption expenditure [PEC00]",
            "Product": "Grains and other crop products [M111B]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v5",
            "COORDINATE": "5",
            "VALUE": 3.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Supply and use": "Use",
            "Valuation": "Basic price",
            "Industry": "International exports [INTEX]",
            "Product": "Food and non-alcoholic beverages [M31C0]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v6",
            "COORDINATE": "6",
            "VALUE": 4.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Supply and use": "Use",
            "Valuation": "Basic price",
            "Industry": "Crop and animal production [BS11A]",
            "Product": "Wages and salaries [P5000]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v7",
            "COORDINATE": "7",
            "VALUE": 5.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Supply and use": "Use",
            "Valuation": "Basic price",
            "Industry": "Manufacturing [BS3A0]",
            "Product": "Gross operating surplus [P8000]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v8",
            "COORDINATE": "8",
            "VALUE": 6.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Supply and use": "Use",
            "Valuation": "Purchaser price",
            "Industry": "International imports [INTIM]",
            "Product": "Grains and other crop products [M111B]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v9",
            "COORDINATE": "9",
            "VALUE": 7.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
    ]
    return pd.DataFrame(rows)


def _statcan_iot_frame() -> pd.DataFrame:
    rows = [
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Valuation": "Basic price",
            "Supply": "Crop and animal production [BS11A]",
            "Use": "Crop and animal production [BS11A]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v1",
            "COORDINATE": "1",
            "VALUE": 10.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Valuation": "Basic price",
            "Supply": "Manufacturing [BS3A0]",
            "Use": "Manufacturing [BS3A0]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v2",
            "COORDINATE": "2",
            "VALUE": 20.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Valuation": "Basic price",
            "Supply": "Crop and animal production [BS11A]",
            "Use": "Household final consumption expenditure [PEC00]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v3",
            "COORDINATE": "3",
            "VALUE": 30.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Valuation": "Basic price",
            "Supply": "Manufacturing [BS3A0]",
            "Use": "International exports to United States [INTEXUS]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v4",
            "COORDINATE": "4",
            "VALUE": 40.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Valuation": "Basic price",
            "Supply": "Wages and salaries [P5000]",
            "Use": "Crop and animal production [BS11A]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v5",
            "COORDINATE": "5",
            "VALUE": 50.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
        {
            "REF_DATE": 2023,
            "GEO": "Canada",
            "DGUID": "2016A000011124",
            "Valuation": "Basic price",
            "Supply": "Gross operating surplus [P8000]",
            "Use": "Manufacturing [BS3A0]",
            "UOM": "Dollars",
            "UOM_ID": 81,
            "SCALAR_FACTOR": "millions",
            "SCALAR_ID": 6,
            "VECTOR": "v6",
            "COORDINATE": "6",
            "VALUE": 60.0,
            "STATUS": "",
            "SYMBOL": "",
            "TERMINATED": "",
            "DECIMALS": 1,
        },
    ]
    return pd.DataFrame(rows)


def test_build_statcan_sut_from_frame_returns_split_native_blocks():
    matrices, indeces, units, layout = build_statcan_sut_from_frame(
        _statcan_sut_frame(),
        year=2023,
        geo="Canada",
        level="summary",
        csv_url="https://example.test/statcan.csv",
    )
    base = matrices["baseline"]

    assert layout.pid == "36100438"
    assert set(base) == {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"}
    assert base["S"].shape == (2, 2)
    assert base["U"].shape == (2, 2)
    assert base["Yc"].shape == (2, 2)
    assert base["Va"].shape == (3, 2)
    assert base["Vc"].shape == (3, 2)
    assert indeces["a"]["main"] == [
        "Crop and animal production [BS11A]",
        "Manufacturing [BS3A0]",
    ]
    assert indeces["n"]["main"] == [
        "Household final consumption expenditure [PEC00]",
        "International exports [INTEX]",
    ]
    assert float(base["S"].iloc[0, 0]) == 10.0
    assert float(base["U"].iloc[1, 1]) == 2.0
    assert float(base["Yc"].iloc[0, 0]) == 3.0
    assert float(base["Yc"].iloc[1, 1]) == 4.0
    assert float(base["Va"].loc["Wages and salaries [P5000]"].iloc[0]) == 5.0
    assert float(base["Va"].loc["Gross operating surplus [P8000]"].iloc[1]) == 6.0
    assert float(base["Vc"].loc["International imports [INTIM]"].iloc[0]) == 7.0
    assert units["Activity"].iloc[0, 0] == "millions Dollars"


def test_build_statcan_iot_from_frame_returns_canonical_iot_blocks():
    matrices, indeces, units, layout = build_statcan_iot_from_frame(
        _statcan_iot_frame(),
        year=2023,
        geo="Canada",
        level="summary",
        valuation="basic",
        csv_url="https://example.test/statcan.csv",
    )
    base = matrices["baseline"]

    assert layout.pid == "36100084"
    assert set(base) == {"Z", "Y", "V", "E", "EY"}
    assert base["Z"].shape == (2, 2)
    assert base["Y"].shape == (2, 2)
    assert base["V"].shape == (2, 2)
    assert float(base["Z"].iloc[0, 0]) == 10.0
    assert float(base["Y"].iloc[0, 0]) == 30.0
    assert float(base["Y"].iloc[1, 1]) == 40.0
    assert float(base["V"].loc["Wages and salaries [P5000]"].iloc[0]) == 50.0
    assert float(base["V"].loc["Gross operating surplus [P8000]"].iloc[1]) == 60.0
    assert units["Sector"].iloc[0, 0] == "millions Dollars"
    assert indeces["n"]["main"] == [
        "Household final consumption expenditure [PEC00]",
        "International exports to United States [INTEXUS]",
    ]


def test_public_parse_statcan_builds_database_from_wds_backend(monkeypatch):
    frame = _statcan_sut_frame()

    def fake_download(pid, *, timeout=60, session=None):
        assert pid == "36100438"
        return frame.copy(), "https://example.test/statcan.csv"

    monkeypatch.setattr("mario.parsers.statcan_wds._download_statcan_csv_table", fake_download)

    database = mario.parse_statcan(2023, table="SUT", level="summary", geo="Canada", calc_all=False)

    assert database.table_type == "SUT"
    assert sorted(database["baseline"].keys()) == ["EY", "Ea", "Ec", "S", "U", "Va", "Vc", "Ya", "Yc"]
    assert database.Z.shape == (4, 4)
    assert "Statistics Canada WDS full-table API" in database.meta.source


def test_public_parse_statcan_validates_sut_valuation_and_available_geo(monkeypatch):
    frame = _statcan_sut_frame()
    monkeypatch.setattr(
        "mario.parsers.statcan_wds._download_statcan_csv_table",
        lambda pid, *, timeout=60, session=None: (frame.copy(), "https://example.test/statcan.csv"),
    )

    with pytest.raises(NotImplementable):
        mario.parse_statcan(2023, table="SUT", valuation="purchaser", calc_all=False)

    with pytest.raises(WrongInput):
        mario.parse_statcan(2023, table="SUT", geo="Ontario", calc_all=False)

