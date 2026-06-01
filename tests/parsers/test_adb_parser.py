from pathlib import Path

import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.parsers.adb import (
    build_adb_iot_from_frame,
    build_adb_srio_iot_from_frame,
    detect_adb_layout,
)
from mario.parsers.specs import ADB_FINAL_DEMAND_CODES
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


def _adb_srio_raw_frame(year: int = 2024) -> pd.DataFrame:
    rows: list[list[object]] = []
    rows.append([f"Canada Input-Output Table (4x4), {year}"] + [None] * 13)
    rows.append(["(at current prices, $ million)"] + [None] * 13)
    rows.append([None] * 14)
    rows.append([None] * 14)
    rows.append(
        [
            "Industry",
            "Industry",
            None,
            None,
            "Agriculture, hunting, forestry, and fishing",
            "Manufacturing",
            "Construction",
            "Transport",
            ADB_FINAL_DEMAND_LABELS["F1"],
            ADB_FINAL_DEMAND_LABELS["F2"],
            ADB_FINAL_DEMAND_LABELS["F3"],
            ADB_FINAL_DEMAND_LABELS["F4"],
            ADB_FINAL_DEMAND_LABELS["F5"],
            ADB_FINAL_DEMAND_LABELS["F6"],
            "TOTAL",
        ]
    )
    rows.append([None, None, None, None, "CAN", "CAN", "CAN", "CAN", "CAN", "CAN", "CAN", "CAN", "CAN", "CAN", "CAN"])
    rows.append([None, None, None, None, "c1", "c2", "c3", "c4", "F1", "F2", "F3", "F4", "F5", "F6", None])
    rows.extend(
        [
            [None, "Agriculture, hunting, forestry, and fishing", "CAN", "c1", 10.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 55.0],
            [None, "Manufacturing", "CAN", "c2", 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 155.0],
            [None, "Construction", "CAN", "c3", 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0, 30.0, 255.0],
            [None, "Transport", "CAN", "c4", 31.0, 32.0, 33.0, 34.0, 35.0, 36.0, 37.0, 38.0, 39.0, 40.0, 355.0],
            [None, "Agriculture, hunting, forestry, and fishing", "IMP", "c1", 1.0, 2.0, 3.0, 4.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 85.0],
            [None, "Manufacturing", "IMP", "c2", 5.0, 6.0, 7.0, 8.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 137.0],
            [None, "Construction", "IMP", "c3", 9.0, 10.0, 11.0, 12.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 189.0],
            [None, "Transport", "IMP", "c4", 13.0, 14.0, 15.0, 16.0, 28.0, 29.0, 30.0, 31.0, 32.0, 33.0, 241.0],
            [None, "Total Imports", None, "M", 28.0, 32.0, 36.0, 40.0, 76.0, 80.0, 84.0, 88.0, 92.0, 96.0, 652.0],
            [None, "Intermediate input total", None, "r60", 73.0, 67.0, 72.0, 77.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 289.0],
            [None, "Taxes less subsidies on products", None, "r99", 2.0, 3.0, 4.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 14.0],
            [None, "CIF / FOB adjustments on exports", None, "r61", 0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0],
            [None, "Direct purchases abroad by residents", None, "r62", 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            [None, "Purchases on the domestic territory by non-residents", None, "r63", 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0],
            [None, "Value added at basic prices", None, "r64", 20.0, 21.0, 22.0, 23.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 86.0],
            [None, "International Transport Margins", None, "trs", 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4.0],
            [None, "TOTAL", None, "r69", 124.0, 125.0, 136.0, 147.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 532.0],
        ]
    )
    return pd.DataFrame(rows)


def _write_adb_srio_workbook(path: Path, years=(2023, 2024)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        toc = pd.DataFrame(
            {
                "Sheet Name": [str(year) for year in years],
                "Table Number": [f"Canada Input-Output Table, {year}" for year in years],
            }
        )
        toc.to_excel(writer, sheet_name="Table of Contents", index=False)
        for year in years:
            _adb_srio_raw_frame(year=year).to_excel(
                writer,
                sheet_name=str(year),
                header=False,
                index=False,
            )
    return path


def _write_adb_emissions_workbook(path: Path, *, year: int, regions: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    sector_labels = [
        "Agriculture, hunting, forestry, and fishing",
        "Manufacturing",
    ]
    sector_codes = ["c1", "c2"]
    final_demand_codes = ["F1", "F2", "F3", "F4", "F5"]
    final_demand_labels = [ADB_FINAL_DEMAND_LABELS[code] for code in final_demand_codes]

    width = 3 + len(regions) * (len(sector_labels) + len(final_demand_codes)) + 1

    rows: list[list[object]] = []
    rows.append(["Title:", "Environmentally-Extended Multiregional Input-Output Table (Air Emissions)"] + [None] * (width - 2))
    rows.append(["Year:", year] + [None] * (width - 2))
    rows.append(["Unit:", "Gigagrams of Carbon Dioxide equivalent (Gg of CO2e)"] + [None] * (width - 2))
    rows.append([None] * width)
    rows.append(
        [
            "Main IPCC Sector",
            "GHG Sector",
            None,
            *(sector_labels * len(regions)),
            *(final_demand_labels * len(regions)),
            "TOTAL",
        ]
    )
    rows.append(
        [
            None,
            None,
            None,
            *sum([[region] * len(sector_labels) for region in regions], []),
            *sum([[region] * len(final_demand_codes) for region in regions], []),
            None,
        ]
    )
    rows.append(
        [
            None,
            None,
            None,
            *(sector_codes * len(regions)),
            *(final_demand_codes * len(regions)),
            None,
        ]
    )

    def _row_values(start: int) -> list[float]:
        sector_values = list(range(start, start + len(regions) * len(sector_labels)))
        final_demand_values = list(
            range(start + 100, start + 100 + len(regions) * len(final_demand_codes))
        )
        return [*sector_values, *final_demand_values, float(sum(sector_values) + sum(final_demand_values))]

    rows.append(["Energy production", "CO2", None, *_row_values(1)])
    rows.append(["Road transport", "CH4", None, *_row_values(11)])
    rows.append(["Total by substance", "GHG", None, *_row_values(21)])

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name=str(year), header=False, index=False)
        pd.DataFrame({"Notes": ["mock"]}).to_excel(writer, sheet_name="Notes", index=False)
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
    assert indeces["n"]["main"] == [ADB_FINAL_DEMAND_LABELS[code] for code in ADB_FINAL_DEMAND_CODES[:5]]
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
    assert indeces["n"]["main"] == [ADB_FINAL_DEMAND_LABELS[code] for code in ADB_FINAL_DEMAND_CODES[:5]]


def test_build_adb_srio_iot_from_frame_supports_yearly_single_region_layout():
    matrices, indeces, units, layout = build_adb_srio_iot_from_frame(
        _adb_srio_raw_frame(year=2024),
        year=2024,
        source_path="CAN IOT 2000, 2007-2024.xlsx",
        sheet_name="2024",
    )
    base = matrices["baseline"]

    assert layout.workbook_type == "SRIO"
    assert layout.domestic_region == "CAN"
    assert base["Z"].shape == (4, 4)
    assert base["Y"].shape == (4, 6)
    assert base["V"].shape == (7, 4)
    assert indeces["r"]["main"] == ["CAN"]
    assert indeces["n"]["main"] == list(ADB_FINAL_DEMAND_LABELS.values())
    assert list(base["V"].index)[-1] == "imports"
    assert units["Factor of production"].loc["imports", "unit"] == "millions of US$"


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


def test_parse_adb_iot_can_add_air_emissions_extensions_and_record_warnings(tmp_path):
    workbook = _write_adb_workbook(
        tmp_path / "74 economies" / "ADB-MRIO-2024-August 2025.xlsx",
        extra_code_row=False,
        economies_text=75,
    )
    emissions = _write_adb_emissions_workbook(
        tmp_path / "2023 EE-MRIOT (Air Emissions).xlsx",
        year=2023,
        regions=["AAA"],
    )

    database = mario.parse_adb(
        str(workbook),
        add_extensions=str(emissions),
        calc_all=False,
    )

    assert list(database.E.index) == [
        "CO2 | Energy production",
        "CH4 | Road transport",
        "GHG | Total by substance",
    ]
    assert database.E.shape == (3, 4)
    assert database.EY.shape == (3, 10)
    assert database.units["Satellite account"].iloc[0, 0] == "Gigagrams of Carbon Dioxide equivalent (Gg of CO2e)"
    assert float(database.E.iloc[0, 0]) == 1.0
    assert float(database.E.iloc[0, 1]) == 2.0
    assert float(database.E.iloc[0, 2]) == 0.0
    assert float(database.EY.iloc[0, 0]) == 101.0
    assert float(database.EY.iloc[0, 4]) == 105.0
    assert float(database.EY.iloc[0, 5]) == 0.0
    assert any("does not match the economic table year" in note for note in database.meta._history)
    assert any("does not cover database regions" in note for note in database.meta._history)


def test_parse_adb_supports_srio_extensions_when_region_is_covered(tmp_path):
    workbook = _write_adb_srio_workbook(tmp_path / "CAN IOT 2000, 2007-2024.xlsx")
    emissions = _write_adb_emissions_workbook(
        tmp_path / "2024 EE-MRIOT (Air Emissions).xlsx",
        year=2024,
        regions=["CAN", "RoW"],
    )

    database = mario.parse_adb(
        str(workbook),
        year=2024,
        add_extensions=str(emissions),
        calc_all=False,
    )

    assert database.get_index("Region") == ["CAN"]
    assert list(database.E.index) == [
        "CO2 | Energy production",
        "CH4 | Road transport",
        "GHG | Total by substance",
    ]
    assert database.E.shape == (3, 4)
    assert database.EY.shape == (3, 6)
    assert float(database.E.iloc[0, 0]) == 1.0
    assert float(database.EY.iloc[0, 0]) == 101.0
    assert float(database.EY.iloc[0, 4]) == 105.0
    assert float(database.EY.iloc[0, 5]) == 0.0
    assert not any("does not cover database regions" in note for note in database.meta._history)


def test_detect_adb_layout_requires_year_for_srio_workbooks(tmp_path):
    workbook = _write_adb_srio_workbook(tmp_path / "CAN IOT 2000, 2007-2024.xlsx")

    with pytest.raises(WrongInput, match="requires year"):
        detect_adb_layout(workbook)

    layout = detect_adb_layout(workbook, year=2024)
    assert layout.workbook_type == "SRIO"
    assert layout.sheet_name == "2024"
    assert layout.domestic_region == "CAN"


def test_public_parse_adb_supports_srio_workbooks_when_year_is_given(tmp_path):
    workbook = _write_adb_srio_workbook(tmp_path / "CAN IOT 2000, 2007-2024.xlsx")

    database = mario.parse_adb(str(workbook), year=2024, calc_all=False)

    assert database.table_type == "IOT"
    assert database.meta.year == 2024
    assert database.meta.name == "ADB SRIO Canada 2024"
    assert database.get_index("Region") == ["CAN"]
    assert database.get_index("Consumption category") == list(ADB_FINAL_DEMAND_LABELS.values())
    assert "imports" in database.get_index("Factor of production")
    assert database.Z.shape == (4, 4)
    assert database.Y.shape == (4, 6)
    assert database.V.shape == (7, 4)
