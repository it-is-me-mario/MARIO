from pathlib import Path
from zipfile import BadZipFile

import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from mario.parsers.wiod import (
    _assert_wiod_file_readable,
    _read_wiod_workbook,
    build_wiod_national_iot_from_frame,
    build_wiod_national_sut_from_frames,
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


def _national_iot_raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            [None, None, None, None, "A01", "C10-C12", "CONS_h", "CONS_np", "CONS_g", "GFCF", "INVEN", "EXP", "GO"],
            [
                "Year",
                "Code",
                "Description",
                "Origin",
                "Agriculture",
                "Manufacturing",
                "Households",
                "NPISH",
                "Government",
                "Gross fixed capital formation",
                "Changes in inventories and valuables",
                "Exports",
                "Total output",
            ],
            [2014, "A01", "Agriculture", "Domestic", 10.0, 1.0, 2.0, 0.0, 0.0, 3.0, 4.0, 5.0, 25.0],
            [2014, "C10-C12", "Manufacturing", "Domestic", 6.0, 7.0, 8.0, 0.0, 0.0, 9.0, 10.0, 11.0, 51.0],
            [2014, "A01", "Agriculture", "Imports", 1.0, 2.0, 3.0, 0.0, 0.0, 4.0, 5.0, 6.0, 21.0],
            [2014, "C10-C12", "Manufacturing", "Imports", 0.5, 1.5, 2.5, 0.0, 0.0, 3.5, 4.5, 5.5, 18.0],
            [2014, "TXSP", "taxes less subsidies on products", "TOT", 1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [2014, "EXP_adj", "Cif/ fob adjustments on exports", "TOT", 3.0, 4.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [2014, "PURR", "Direct purchases abroad by residents", "TOT", 5.0, 6.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [2014, "PURNR", "Purchases on the domestic territory by non-residents ", "TOT", 7.0, 8.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [2014, "VA", "Value added at basic prices", "TOT", 9.0, 10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [2014, "IntTTM", "International Transport Margins", "TOT", 11.0, 12.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ]
    )


def _national_sut_raw_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    supply = pd.DataFrame(
        [
            [None, None, None, "A01", "C10-C12", "DSUP_bas", "IMP", "SUP_bas", "MARG", "TXSP", "SUP_pur"],
            [
                "year",
                "code",
                "desc",
                "Agriculture",
                "Manufacturing",
                "Total domestic supply at basic prices",
                "Imports cif",
                "Total supply at basic prices",
                "Margins",
                "Taxes less subsidies on products",
                "Total supply at purchasers' prices",
            ],
            [2014, "CPA_A01", "Products of agriculture", 10.0, 1.0, 11.0, 2.0, 13.0, 0.0, 0.0, 13.0],
            [2014, "CPA_C10-C12", "Food products", 3.0, 20.0, 23.0, 4.0, 27.0, 0.0, 0.0, 27.0],
        ]
    )
    use = pd.DataFrame(
        [
            [None, None, None, "A01", "C10-C12", "INTC", "CONS_h", "CONS_np", "CONS_g", "CONS", "GFCF", "INVEN", "GCF", "EXP_fob", "FU_bas", "USE_bas", "MARG_TXSP_EXP"],
            [
                "year",
                "code",
                "desc",
                "Agriculture",
                "Manufacturing",
                "Total intermediate consumption",
                "Households",
                "NPISH",
                "Government",
                "Final consumption expenditure",
                "Gross fixed capital formation",
                "Changes in inventories and valuables",
                "Gross capital formation",
                "Exports",
                "Final use at basic prices",
                "Total use at basic prices",
                "Margins and taxes on exports",
            ],
            [2014, "CPA_A01", "Products of agriculture", 1.0, 2.0, 0.0, 10.0, 1.0, 2.0, 13.0, 3.0, 4.0, 7.0, 5.0, 18.0, 18.0, 0.0],
            [2014, "CPA_C10-C12", "Food products", 3.0, 4.0, 0.0, 20.0, 2.0, 3.0, 25.0, 6.0, 7.0, 13.0, 8.0, 33.0, 33.0, 0.0],
            [2014, "TXSP", "Taxes less subsidies on products", 100.0, 101.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [2014, "EXP_adj", "Cif/ fob adjustments on exports", 110.0, 111.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [2014, "PURR", "Direct purchases abroad by residents", 120.0, 121.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [2014, "PURNR", "Purchases on the domestic territory by non-residents ", 130.0, 131.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [2014, "VA", "Value added at basic prices", 140.0, 141.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ]
    )
    return supply, use


def _write_wiod_sea_workbook(path: Path) -> None:
    notes = pd.DataFrame(
        [
            [None, None, None, None, None],
            [None, None, None, None, None],
            [None, None, None, None, None],
            [None, None, None, None, None],
            [None, None, None, None, None],
            [None, None, None, None, None],
            ["Acronym", "Name", None, "Values", "Description"],
            ["ITA", "Italy", None, "GO", "Gross output by industry at current basic prices (in millions of national currency)"],
            ["ITA", "Italy", None, "EMP", "Number of persons engaged (thousands)"],
        ]
    )
    data = pd.DataFrame(
        [
            {"country": "ITA", "variable": "GO", "description": "Agriculture", "code": "A01", 2014: 1000.0},
            {"country": "ITA", "variable": "GO", "description": "Manufacturing", "code": "C10-C12", 2014: 2000.0},
            {"country": "ITA", "variable": "EMP", "description": "Agriculture", "code": "A01", 2014: 10.0},
            {"country": "ITA", "variable": "EMP", "description": "Manufacturing", "code": "C10-C12", 2014: 20.0},
        ]
    )
    with pd.ExcelWriter(path) as writer:
        notes.to_excel(writer, sheet_name="Notes", header=False, index=False)
        data.to_excel(writer, sheet_name="DATA", index=False)


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


def test_detect_wiod_layout_accepts_pyp_and_national_workbooks(tmp_path):
    mrio = tmp_path / "WIOT2014_PYP_Nov16_ROW.xlsb"
    mrio.write_bytes(b"")
    layout = detect_wiod_layout(mrio, table="IOT")
    assert layout.year == 2014
    assert layout.price == "Previous year prices"

    national = tmp_path / "ITA_NIOT_nov16.xlsx"
    national.write_bytes(b"")
    with pytest.raises(WrongInput, match="Please specify year"):
        detect_wiod_layout(national, table="IOT")

    national_layout = detect_wiod_layout(national, table="IOT", year=2014)
    assert national_layout.scope == "National"
    assert national_layout.country == "ITA"


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
    assert set(base) == {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY"}
    assert base["S"].shape == (4, 4)
    assert base["U"].shape == (4, 4)
    assert base["Yc"].shape == (4, 12)
    assert base["Va"].shape == (8, 4)
    assert base["Vc"].shape == (8, 4)
    assert base["VY"].shape == (8, 12)
    assert float(base["S"].iloc[0, 0]) == 10.0
    assert float(base["S"].iloc[1, 0]) == 1.0
    assert float(base["S"].iloc[0, -1]) == 0.0
    assert float(base["U"].iloc[0, 0]) == 1.0
    assert float(base["U"].iloc[-1, -1]) == 114.0
    assert float(base["Yc"].iloc[0, 0]) == 10.0
    assert float(base["Yc"].iloc[-1, -1]) == 118.0
    assert float(base["Va"].iloc[0, 0]) == 100.0
    assert float(base["Va"].iloc[5, -1]) == 251.0
    assert float(base["Va"].iloc[6, 0]) == 21.0
    assert float(base["Va"].iloc[-1, -1]) == 124.0
    assert float(base["Vc"].to_numpy().sum()) == 0.0
    assert float(base["VY"].iloc[6, 0]) == 30.0
    assert float(base["VY"].iloc[-1, -1]) == 128.0
    assert indeces["r"]["main"] == ["ITA", "AUS"]
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
    assert indeces["f"]["main"][-2:] == ["Import from ROW | A01", "Import from ROW | C10-C12"]
    assert layout.notes == (
        "External WIOD commodity origins ROW were removed from the endogenous region set. "
        "Their intermediate uses were reclassified into Va and their final-demand uses into VY.",
    )
    assert units["Activity"].iloc[0, 0] == "millions of US$"


def test_build_wiod_sut_from_frames_supports_legacy_row_region_mode():
    supply, use = _wiod_sut_frames()
    matrices, indeces, units, layout = build_wiod_sut_from_frames(
        supply,
        use,
        year=2014,
        row_mode="legacy_region",
        source_path="intsut14_nov16.xlsb",
    )
    base = matrices["baseline"]

    assert set(base) == {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"}
    assert base["S"].shape == (4, 6)
    assert base["U"].shape == (6, 4)
    assert base["Yc"].shape == (6, 12)
    assert base["Va"].shape == (6, 4)
    assert base["Vc"].shape == (6, 6)
    assert float(base["U"].iloc[5, 3]) == 124.0
    assert float(base["Yc"].iloc[5, -1]) == 128.0
    assert indeces["r"]["main"] == ["ITA", "AUS", "ROW"]
    assert layout.notes == ()
    assert units["Activity"].iloc[0, 0] == "millions of US$"


def test_build_wiod_national_iot_from_frame_aggregates_domestic_and_imports():
    matrices, indeces, units, layout = build_wiod_national_iot_from_frame(
        _national_iot_raw_frame(),
        year=2014,
        country="ITA",
        source_path="ITA_NIOT_nov16.xlsx",
    )
    base = matrices["baseline"]
    assert layout.scope == "National"
    assert base["Z"].shape == (2, 2)
    assert base["Y"].shape == (2, 6)
    assert base["V"].shape == (6, 2)
    assert float(base["Z"].iloc[0, 0]) == 11.0
    assert float(base["Y"].iloc[0, 0]) == 5.0
    assert float(base["V"].iloc[-1, -1]) == 12.0
    assert indeces["r"]["main"] == ["ITA"]
    assert units["Sector"].iloc[0, 0] == "millions of US$"


def test_build_wiod_national_sut_from_frames_returns_split_native_blocks():
    supply, use = _national_sut_raw_frames()
    matrices, indeces, units, layout = build_wiod_national_sut_from_frames(
        supply,
        use,
        year=2014,
        country="ITA",
        source_path="ITA_SUT_nov16.xlsx",
    )
    base = matrices["baseline"]
    assert layout.scope == "National"
    assert base["S"].shape == (2, 2)
    assert base["U"].shape == (2, 2)
    assert base["Yc"].shape == (2, 6)
    assert base["Va"].shape == (5, 2)
    assert float(base["S"].iloc[0, 0]) == 10.0
    assert float(base["U"].iloc[1, 1]) == 4.0
    assert float(base["Yc"].iloc[0, -1]) == 5.0
    assert indeces["r"]["main"] == ["ITA"]
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


def test_public_parse_wiod_supports_national_iot_and_socioeconomic_extensions(monkeypatch, tmp_path):
    workbook = tmp_path / "ITA_NIOT_nov16.xlsx"
    workbook.write_bytes(b"not a real workbook")
    sea = tmp_path / "Socio_Economic_Accounts.xlsx"
    _write_wiod_sea_workbook(sea)

    monkeypatch.setattr(
        "mario.parsers.wiod._read_wiod_xlsx_sheet",
        lambda path, *, sheet_name, header=None: _national_iot_raw_frame(),
    )

    database = mario.parse_wiod(str(workbook), year=2014, add_extensions=str(sea), calc_all=False)

    assert database.table_type == "IOT"
    assert database.Z.shape == (2, 2)
    assert database.E.shape == (2, 2)
    assert database.get_index("k") == [
        "GO | Gross output by industry at current basic prices",
        "EMP | Number of persons engaged",
    ]


def test_public_parse_wiod_supports_national_sut_and_socioeconomic_extensions(monkeypatch, tmp_path):
    workbook = tmp_path / "ITA_SUT_nov16.xlsx"
    workbook.write_bytes(b"not a real workbook")
    sea = tmp_path / "Socio_Economic_Accounts.xlsx"
    _write_wiod_sea_workbook(sea)
    supply, use = _national_sut_raw_frames()

    def _fake_sheet(path, *, sheet_name, header=None):
        if sheet_name == "SUP":
            return supply
        if sheet_name == "USE":
            return use
        raise AssertionError(sheet_name)

    monkeypatch.setattr("mario.parsers.wiod._read_wiod_xlsx_sheet", _fake_sheet)

    database = mario.parse_wiod(str(workbook), table="SUT", year=2014, add_extensions=str(sea), calc_all=False)

    assert database.table_type == "SUT"
    assert database.S.shape == (2, 2)
    assert database.Ea.shape == (2, 2)
    assert database.get_index("k") == [
        "GO | Gross output by industry at current basic prices",
        "EMP | Number of persons engaged",
    ]


def test_assert_wiod_file_readable_reports_timeout_as_local_availability_issue(tmp_path, monkeypatch):
    workbook = tmp_path / "WIOT2014_Nov16_ROW.xlsb"
    workbook.write_bytes(b"dummy")

    def _timeout(self, *args, **kwargs):
        raise TimeoutError("[Errno 60] Operation timed out")

    monkeypatch.setattr(Path, "open", _timeout)

    with pytest.raises(WrongInput, match="available offline"):
        _assert_wiod_file_readable(workbook)


def test_read_wiod_workbook_reports_invalid_xlsb_with_helpful_message(monkeypatch, tmp_path):
    workbook = tmp_path / "WIOT2014_Nov16_ROW.xlsb"
    workbook.write_bytes(b"PK\x03\x04dummy")

    monkeypatch.setattr("mario.parsers.wiod._assert_wiod_file_readable", lambda path: None)
    monkeypatch.setattr("mario.parsers.wiod._require_pyxlsb", lambda: None)

    def _bad_zip(*args, **kwargs):
        raise BadZipFile("File is not a zip file")

    monkeypatch.setattr(pd, "read_excel", _bad_zip)

    with pytest.raises(WrongInput, match="valid WIOD 2016 multiregional workbook"):
        _read_wiod_workbook(workbook, sheet_name="2014")


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
    assert sorted(database["baseline"].keys()) == ["EY", "Ea", "Ec", "S", "U", "VY", "Va", "Vc", "Ya", "Yc"]
    assert database.get_index("Region") == ["ITA", "AUS"]
    assert database.S.shape == (4, 4)
    assert database.U.shape == (4, 4)
    assert database.Y.shape == (8, 12)
    assert database.V.shape == (8, 8)
    assert database.VY.shape == (8, 12)


def test_public_parse_wiod_sut_supports_legacy_row_region_mode(monkeypatch, tmp_path):
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

    database = mario.parse_wiod(
        str(workbook),
        table="SUT",
        row_mode="legacy_region",
        calc_all=False,
    )

    assert database.table_type == "SUT"
    assert database.get_index("Region") == ["ITA", "AUS", "ROW"]
    assert sorted(database["baseline"].keys()) == ["EY", "Ea", "Ec", "S", "U", "Va", "Vc", "Ya", "Yc"]
    assert database.S.shape == (4, 6)
    assert database.U.shape == (6, 4)
    assert database.Y.shape == (10, 12)
    assert database.V.shape == (6, 10)
