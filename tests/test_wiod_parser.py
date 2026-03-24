from pathlib import Path

import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from mario.parsers.wiod import (
    build_wiod_iot_from_frame,
    build_wiod_sut_from_frames,
    detect_wiod_layout,
)


def _raw_wiod_frame() -> pd.DataFrame:
    rows: list[list[object]] = []
    rows.append(["Intercountry Input-Output Table"] + [None] * 14)
    rows.append(["43 countries, in current prices"] + [None] * 14)
    rows.append(
        [
            "(industry-by-industry)",
            None,
            None,
            None,
            "A01",
            "C10-C12",
            "A01",
            "C10-C12",
            "CONS_h",
            "CONS_np",
            "CONS_g",
            "GFCF",
            "INVEN",
            "CONS_h",
            "GO",
        ]
    )
    rows.append(
        [
            "(millions of US$)",
            None,
            None,
            None,
            "Agriculture",
            "Manufacturing",
            "Agriculture",
            "Manufacturing",
            "Households",
            "NPISH",
            "Government",
            "Gross fixed capital formation",
            "Changes in inventories and valuables",
            "Households",
            "Total output",
        ]
    )
    rows.append(
        [
            None,
            None,
            None,
            None,
            "ITA",
            "ITA",
            "ROW",
            "ROW",
            "ITA",
            "ITA",
            "ITA",
            "ITA",
            "ITA",
            "ROW",
            "TOT",
        ]
    )
    rows.append([None, None, None, None, "c1", "c2", "c1", "c2", "c57", "c58", "c59", "c60", "c61", "c57", "c62"])
    rows.extend(
        [
            ["A01", "Agriculture", "ITA", "r1", 10.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 55.0],
            ["C10-C12", "Manufacturing", "ITA", "r2", 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 155.0],
            ["A01", "Agriculture", "ROW", "r3", 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0, 30.0, 255.0],
            ["C10-C12", "Manufacturing", "ROW", "r4", 31.0, 32.0, 33.0, 34.0, 35.0, 36.0, 37.0, 38.0, 39.0, 40.0, 355.0],
            ["II_fob", "Total intermediate consumption", "TOT", "r65", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ["TXSP", "taxes less subsidies on products", "TOT", "r66", 1.0, 2.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ["EXP_adj", "Cif/ fob adjustments on exports", "TOT", "r67", 5.0, 6.0, 7.0, 8.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ["PURR", "Direct purchases abroad by residents", "TOT", "r68", 9.0, 10.0, 11.0, 12.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ["PURNR", "Purchases on the domestic territory by non-residents ", "TOT", "r69", 13.0, 14.0, 15.0, 16.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ["VA", "Value added at basic prices", "TOT", "r70", 17.0, 18.0, 19.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ["IntTTM", "International Transport Margins", "TOT", "r71", 21.0, 22.0, 23.0, 24.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ["GO", "Output at basic prices", "TOT", "r73", 100.0, 200.0, 300.0, 400.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ]
    )
    return pd.DataFrame(rows)


def _wiod_sut_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    supply = pd.DataFrame(
        [
            ["ITA", "ITA", "CPA_A01", 10.0, 1.0, 11.0, 2.0, 13.0, 0.0, 0.0, 0.0],
            ["ITA", "ITA", "CPA_C10-C12", 3.0, 20.0, 23.0, 4.0, 27.0, 0.0, 0.0, 0.0],
            ["ITA", "ITA", "GO", 13.0, 21.0, 34.0, 6.0, 40.0, 0.0, 0.0, 0.0],
            ["ITA", "ITA", "IMP_adj", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ["ITA", "ITA", "PURR", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ["ITA", "ITA", "GO_adj", 13.0, 21.0, 34.0, 6.0, 40.0, 0.0, 0.0, 0.0],
            ["AUS", "AUS", "CPA_A01", 30.0, 4.0, 34.0, 5.0, 39.0, 0.0, 0.0, 0.0],
            ["AUS", "AUS", "CPA_C10-C12", 6.0, 40.0, 46.0, 7.0, 53.0, 0.0, 0.0, 0.0],
            ["AUS", "AUS", "GO", 36.0, 44.0, 80.0, 12.0, 92.0, 0.0, 0.0, 0.0],
            ["AUS", "AUS", "IMP_adj", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ["AUS", "AUS", "PURR", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ["AUS", "AUS", "GO_adj", 36.0, 44.0, 80.0, 12.0, 92.0, 0.0, 0.0, 0.0],
        ],
        columns=[
            "REP",
            "PAR",
            "CPA",
            "A01",
            "C10-C12",
            "DSUP_bas",
            "IMP",
            "SUP_bas",
            "ExpTTM",
            "ReEXP",
            "IntTTM",
        ],
    )

    use_rows: list[list[object]] = []
    for rep, offset in [("ITA", 0.0), ("AUS", 100.0)]:
        for par, par_offset in [("ITA", 0.0), ("AUS", 10.0), ("ROW", 20.0)]:
            use_rows.append(
                [
                    rep,
                    par,
                    "CPA_A01",
                    1.0 + offset + par_offset,
                    2.0 + offset + par_offset,
                    0.0,
                    10.0 + offset + par_offset,
                    1.0,
                    2.0,
                    13.0 + offset + par_offset,
                    3.0,
                    4.0,
                    7.0,
                    5.0 + offset + par_offset,
                    0.0,
                    18.0 + offset + par_offset,
                    0.0,
                    0.0,
                ]
            )
            use_rows.append(
                [
                    rep,
                    par,
                    "CPA_C10-C12",
                    3.0 + offset + par_offset,
                    4.0 + offset + par_offset,
                    0.0,
                    20.0 + offset + par_offset,
                    2.0,
                    3.0,
                    25.0 + offset + par_offset,
                    6.0,
                    7.0,
                    13.0,
                    8.0 + offset + par_offset,
                    0.0,
                    33.0 + offset + par_offset,
                    0.0,
                    0.0,
                ]
            )

        for factor, a01, c10 in [
            ("TXSP", 100.0 + offset, 101.0 + offset),
            ("EXP_adj", 110.0 + offset, 111.0 + offset),
            ("PURR", 120.0 + offset, 121.0 + offset),
            ("PURNR", 130.0 + offset, 131.0 + offset),
            ("VA", 140.0 + offset, 141.0 + offset),
            ("IntTTM", 150.0 + offset, 151.0 + offset),
        ]:
            use_rows.append(
                [
                    rep,
                    "ZZZ",
                    factor,
                    a01,
                    c10,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ]
            )

    use = pd.DataFrame(
        use_rows,
        columns=[
            "REP",
            "PAR",
            "CPA",
            "A01",
            "C10-C12",
            "INTC",
            "CONS_h",
            "CONS_np",
            "CONS_g",
            "CONS",
            "GFCF",
            "INVEN",
            "GCF",
            "EXP",
            "FU_bas",
            "USE_bas",
            "ReEXP",
            "IntTTM",
        ],
    )
    return supply, use


def test_build_wiod_iot_from_frame_returns_canonical_blocks():
    matrices, indeces, units, layout = build_wiod_iot_from_frame(
        _raw_wiod_frame(),
        year=2014,
        source_path="WIOT2014_Nov16_ROW.xlsb",
    )
    base = matrices["baseline"]

    assert layout.year == 2014
    assert set(base) == {"Z", "Y", "V", "E", "EY"}
    assert base["Z"].shape == (4, 4)
    assert base["Y"].shape == (4, 6)
    assert base["V"].shape == (6, 4)
    assert float(base["Z"].iloc[0, 0]) == 10.0
    assert float(base["Z"].iloc[3, 3]) == 34.0
    assert float(base["Y"].iloc[0, 0]) == 4.0
    assert float(base["Y"].iloc[0, 5]) == 9.0
    assert float(base["V"].iloc[0, 0]) == 1.0
    assert float(base["V"].iloc[-1, -1]) == 24.0
    assert indeces["r"]["main"] == ["ITA", "ROW"]
    assert indeces["s"]["main"] == ["Agriculture", "Manufacturing"]
    assert indeces["n"]["main"] == [
        "Households",
        "NPISH",
        "Government",
        "Gross fixed capital formation",
        "Changes in inventories and valuables",
    ]
    assert indeces["f"]["main"] == [
        "taxes less subsidies on products",
        "Cif/ fob adjustments on exports",
        "Direct purchases abroad by residents",
        "Purchases on the domestic territory by non-residents ",
        "Value added at basic prices",
        "International Transport Margins",
    ]
    assert units["Sector"].iloc[0, 0] == "millions of US$"


def test_detect_wiod_layout_requires_year_for_multiple_files(tmp_path):
    (tmp_path / "WIOT2013_Nov16_ROW.xlsb").write_bytes(b"")
    (tmp_path / "WIOT2014_Nov16_ROW.xlsb").write_bytes(b"")

    with pytest.raises(WrongInput):
        detect_wiod_layout(tmp_path)

    layout = detect_wiod_layout(tmp_path, year=2014)
    assert layout.year == 2014
    assert layout.data_path.name == "WIOT2014_Nov16_ROW.xlsb"


def test_detect_wiod_sut_layout_accepts_multiregional_workbook(tmp_path):
    workbook = tmp_path / "intsut14_nov16.xlsb"
    workbook.write_bytes(b"")

    layout = detect_wiod_layout(workbook, table="SUT")
    assert layout.year == 2014
    assert layout.sheet_names == ("SUP", "USE")


def test_build_wiod_sut_from_frames_returns_split_native_blocks():
    supply, use = _wiod_sut_frames()
    matrices, indeces, units, layout = build_wiod_sut_from_frames(
        supply,
        use,
        year=2014,
        source_path="intsut14_nov16.xlsb",
    )
    base = matrices["baseline"]

    assert layout.year == 2014
    assert set(base) == {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"}
    assert base["S"].shape == (4, 6)
    assert base["U"].shape == (6, 4)
    assert base["Yc"].shape == (6, 12)
    assert base["Va"].shape == (6, 4)
    assert base["Vc"].shape == (6, 6)
    assert float(base["S"].iloc[0, 0]) == 10.0
    assert float(base["S"].iloc[1, 0]) == 1.0
    assert float(base["S"].iloc[0, 4]) == 0.0
    assert float(base["U"].iloc[0, 0]) == 1.0
    assert float(base["U"].iloc[5, 3]) == 124.0
    assert float(base["Yc"].iloc[0, 0]) == 10.0
    assert float(base["Yc"].iloc[5, -1]) == 128.0
    assert float(base["Va"].iloc[0, 0]) == 100.0
    assert float(base["Va"].iloc[-1, -1]) == 251.0
    assert float(base["Vc"].to_numpy().sum()) == 0.0
    assert indeces["r"]["main"] == ["ITA", "AUS", "ROW"]
    assert indeces["a"]["main"] == ["A01", "C10-C12"]
    assert indeces["c"]["main"] == ["A01", "C10-C12"]
    assert indeces["n"]["main"] == [
        "Households",
        "NPISH",
        "Government",
        "Gross fixed capital formation",
        "Changes in inventories and valuables",
        "Exports",
    ]
    assert units["Activity"].iloc[0, 0] == "millions of US$"


def test_public_parse_wiod_returns_database(monkeypatch, tmp_path):
    workbook = tmp_path / "WIOT2014_Nov16_ROW.xlsb"
    workbook.write_bytes(b"not a real workbook")

    monkeypatch.setattr("mario.parsers.wiod._read_wiod_workbook", lambda path, *, sheet_name: _raw_wiod_frame())

    database = mario.parse_wiod(str(workbook), calc_all=False)

    assert database.table_type == "IOT"
    assert sorted(database["baseline"].keys()) == ["E", "EY", "V", "Y", "Z"]
    assert database.Z.shape == (4, 4)
    assert database.Y.shape == (4, 6)
    assert database.V.shape == (6, 4)
    assert "WIOD 2016" in mario.parse_wiod.__doc__

    with pytest.raises(WrongInput):
        mario.parse_wiod(str(workbook), table="BAD", calc_all=False)


def test_public_parse_wiod_sut_returns_database(monkeypatch, tmp_path):
    workbook = tmp_path / "intsut14_nov16.xlsb"
    workbook.write_bytes(b"not a real workbook")
    supply, use = _wiod_sut_frames()

    def _fake_sheet(path, *, sheet_name):
        if sheet_name == "SUP":
            return supply
        if sheet_name == "USE":
            return use
        raise AssertionError(sheet_name)

    monkeypatch.setattr("mario.parsers.wiod._read_wiod_table_sheet", _fake_sheet)

    database = mario.parse_wiod(str(workbook), table="SUT", calc_all=False)

    assert database.table_type == "SUT"
    assert sorted(database["baseline"].keys()) == ["EY", "Ea", "Ec", "S", "U", "Va", "Vc", "Ya", "Yc"]
    assert database.S.shape == (4, 6)
    assert database.U.shape == (6, 4)
    assert database.Y.shape == (10, 12)
    assert database.V.shape == (6, 10)
