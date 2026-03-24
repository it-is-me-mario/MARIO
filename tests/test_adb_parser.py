from pathlib import Path

import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.parsers.adb import build_adb_iot_from_frame, detect_adb_layout
from mario.parsers.specs import ADB_FINAL_DEMAND_LABELS


def _adb_raw_frame(*, extra_code_row: bool, economies_text: int) -> pd.DataFrame:
    rows: list[list[object]] = []
    rows.append(["Multiregional Input-Output Table 2024"] + [None] * 18)
    rows.append([f"{economies_text} economies, at current prices (industry by industry)"] + [None] * 18)
    rows.append(["In millions of US$"] + [None] * 18)
    rows.append([None] * 19)

    if extra_code_row:
        rows.append(
            [None, None, None, None, "0001", "0002", "0001", "0002", "1001", "1002", "1003", "1004", "1005", "1001", "1002", "1003", "1004", "1005", None]
        )

    rows.append(
        [
            None,
            None,
            None,
            None,
            "Agriculture, hunting, forestry, and fishing",
            "Manufacturing",
            "Agriculture, hunting, forestry, and fishing",
            "Manufacturing",
            ADB_FINAL_DEMAND_LABELS["F1"],
            ADB_FINAL_DEMAND_LABELS["F2"],
            ADB_FINAL_DEMAND_LABELS["F3"],
            ADB_FINAL_DEMAND_LABELS["F4"],
            ADB_FINAL_DEMAND_LABELS["F5"],
            ADB_FINAL_DEMAND_LABELS["F1"],
            ADB_FINAL_DEMAND_LABELS["F2"],
            ADB_FINAL_DEMAND_LABELS["F3"],
            ADB_FINAL_DEMAND_LABELS["F4"],
            ADB_FINAL_DEMAND_LABELS["F5"],
            "TOTAL",
        ]
    )
    rows.append([None, None, None, None, "AAA", "AAA", "BBB", "BBB", "AAA", "AAA", "AAA", "AAA", "AAA", "BBB", "BBB", "BBB", "BBB", "BBB", "ToT"])
    rows.append([None, None, None, None, "c1", "c2", "c1", "c2", "F1", "F2", "F3", "F4", "F5", "F1", "F2", "F3", "F4", "F5", None])

    rows.extend(
        [
            [None, "Agriculture, hunting, forestry, and fishing", "AAA", "c1", 10.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 14.0, 15.0, 16.0, 17.0, 18.0, 126.0],
            [None, "Manufacturing", "AAA", "c2", 11.0, 12.0, 13.0, 14.0, 24.0, 25.0, 26.0, 27.0, 28.0, 34.0, 35.0, 36.0, 37.0, 38.0, 360.0],
            [None, "Agriculture, hunting, forestry, and fishing", "BBB", "c1", 21.0, 22.0, 23.0, 24.0, 44.0, 45.0, 46.0, 47.0, 48.0, 54.0, 55.0, 56.0, 57.0, 58.0, 600.0],
            [None, "Manufacturing", "BBB", "c2", 31.0, 32.0, 33.0, 34.0, 64.0, 65.0, 66.0, 67.0, 68.0, 74.0, 75.0, 76.0, 77.0, 78.0, 840.0],
            [None, "Intermediate input total", "TOT", "r60", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [None, "Taxes less subsidies on products", "TOT", "r99", 1.0, 2.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [None, "CIF / FOB adjustments", "TOT", "r61", 5.0, 6.0, 7.0, 8.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [None, "Direct purchases abroad by residents", "TOT", "r62", 9.0, 10.0, 11.0, 12.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [None, "Purchases on the domestic territory by non-residents", "TOT", "r63", 13.0, 14.0, 15.0, 16.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [None, "Value added at basic prices", "TOT", "r64", 17.0, 18.0, 19.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [None, "International Transport Margins", "TOT", "trs", 21.0, 22.0, 23.0, 24.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [None, "TOTAL", "TOT", "r69", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ]
    )
    return pd.DataFrame(rows)


def _write_adb_workbook(path: Path, *, extra_code_row: bool, economies_text: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        _adb_raw_frame(extra_code_row=extra_code_row, economies_text=economies_text).to_excel(
            writer,
            sheet_name="ADB MRIO 2024",
            header=False,
            index=False,
        )
        pd.DataFrame({"Code": ["AAA", "BBB"], "Country": ["Alpha", "Beta"]}).to_excel(
            writer,
            sheet_name="Legend",
            index=False,
        )
    return path


def test_build_adb_iot_from_frame_supports_modern_layout():
    matrices, indeces, units, layout = build_adb_iot_from_frame(
        _adb_raw_frame(extra_code_row=False, economies_text=75),
        year=2024,
        source_path="ADB-MRIO-2024-August 2025.xlsx",
        variant=74,
        economies=75,
    )
    base = matrices["baseline"]

    assert layout.variant == 74
    assert layout.economies == 75
    assert base["Z"].shape == (4, 4)
    assert base["Y"].shape == (4, 10)
    assert base["V"].shape == (6, 4)
    assert base["E"].shape == (1, 4)
    assert base["EY"].shape == (1, 10)
    assert indeces["r"]["main"] == ["AAA", "BBB"]
    assert indeces["s"]["main"] == [
        "Agriculture, hunting, forestry, and fishing",
        "Manufacturing",
    ]
    assert indeces["n"]["main"] == list(ADB_FINAL_DEMAND_LABELS.values())
    assert list(base["V"].index) == [
        "Taxes less subsidies on products",
        "CIF / FOB adjustments",
        "Direct purchases abroad by residents",
        "Purchases on the domestic territory by non-residents",
        "Value added at basic prices",
        "International Transport Margins",
    ]
    assert units["Sector"].iloc[0, 0] == "millions of US$"


def test_build_adb_iot_from_frame_supports_legacy_lac_layout():
    matrices, indeces, _, layout = build_adb_iot_from_frame(
        _adb_raw_frame(extra_code_row=True, economies_text=71),
        year=2017,
        source_path="ADB-MRIO-LAC-2017_Mar2022-2.xlsx",
        variant=71,
        economies=71,
    )

    assert layout.year == 2017
    assert layout.variant == 71
    assert matrices["baseline"]["Z"].shape == (4, 4)
    assert matrices["baseline"]["Y"].shape == (4, 10)
    assert indeces["n"]["main"] == list(ADB_FINAL_DEMAND_LABELS.values())


def test_detect_adb_layout_requires_disambiguation_for_multiple_same_year_variants(tmp_path):
    _write_adb_workbook(
        tmp_path / "72 economies" / "ADB-MRIO72-2024_August 2025.xlsx",
        extra_code_row=False,
        economies_text=73,
    )
    _write_adb_workbook(
        tmp_path / "74 economies" / "ADB-MRIO-2024-August 2025.xlsx",
        extra_code_row=False,
        economies_text=75,
    )

    with pytest.raises(WrongInput):
        detect_adb_layout(tmp_path, year=2024)

    layout = detect_adb_layout(tmp_path, year=2024, economies=74)
    assert layout.variant == 74


def test_public_parse_adb_returns_database_and_validates_table(tmp_path):
    workbook = _write_adb_workbook(
        tmp_path / "74 economies" / "ADB-MRIO-2024-August 2025.xlsx",
        extra_code_row=False,
        economies_text=75,
    )

    database = mario.parse_adb(str(workbook), calc_all=False)

    assert database.table_type == "IOT"
    assert database.meta.year == 2024
    assert database.meta.name == "ADB MRIO 2024 (74 economies)"
    assert "kidb.adb.org" in database.meta.source
    assert database.Z.shape == (4, 4)
    assert database.Y.shape == (4, 10)
    assert database.V.shape == (6, 4)
    assert database.E.shape == (1, 4)

    with pytest.raises(NotImplementable):
        mario.parse_adb(str(workbook), table="SUT", calc_all=False)
