from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.parsers.ceads import parse_ceads_iot


def _ceads_fixture_workbook(path: Path, *, year: int) -> Path:
    """Write one compact CEADS-like workbook fixture."""
    provinces = ["Alpha", "Beta"]
    sectors = [("01", "Agriculture"), ("02", "Manufacturing")]
    fd = [
        ("FU101", "Rural household consumption"),
        ("FU102", "Urban household consumption"),
        ("FU103", "Government consumption"),
        ("FU201", "Fixed capital formation"),
        ("FU202", "Changes in inventories"),
    ]

    n_rows = len(provinces) * len(sectors)
    total_cols = 24
    table = pd.DataFrame("", index=range(19), columns=range(total_cols), dtype=object)
    table.iat[0, 0] = f"Test CEADS MRIO {year}"

    # Main Z block headers
    col = 3
    for province in provinces:
        table.iat[1, col] = province
        for code, label in sectors:
            table.iat[2, col] = label
            table.iat[3, col] = code
            col += 1
    table.iat[2, 7] = "Total intermediate use"

    # Final demand headers
    fd_start = 8
    col = fd_start
    for province in provinces:
        table.iat[1, col] = province
        for code, label in fd:
            table.iat[2, col] = label
            table.iat[3, col] = code
            col += 1
    table.iat[2, 18] = "Export"
    table.iat[3, 18] = "EX"
    table.iat[2, 19] = "Total Final Use"
    table.iat[3, 19] = "TFU"
    table.iat[2, 20] = "Errors"
    table.iat[3, 20] = "ERR"
    table.iat[2, 21] = "Gross Output"
    table.iat[3, 21] = "GO"
    table.iat[2, 22] = "Proportion of errors in gross output (less than 5%)"
    table.iat[2, 23] = "Gross Output Check"

    z = np.array(
        [
            [1.0, 2.0, 3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0],
            [9.0, 10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0, 16.0],
        ]
    )
    y_domestic = np.array(
        [
            [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0],
            [201.0, 202.0, 203.0, 204.0, 205.0, 206.0, 207.0, 208.0, 209.0, 210.0],
            [301.0, 302.0, 303.0, 304.0, 305.0, 306.0, 307.0, 308.0, 309.0, 310.0],
            [401.0, 402.0, 403.0, 404.0, 405.0, 406.0, 407.0, 408.0, 409.0, 410.0],
        ]
    )
    exports = [1000.0, 2000.0, 3000.0, 4000.0]

    row = 4
    for province in provinces:
        table.iat[row, 0] = province
        for code, label in sectors:
            table.iat[row, 1] = label
            table.iat[row, 2] = code
            table.iloc[row, 3:7] = z[row - 4, :]
            table.iloc[row, 8:18] = y_domestic[row - 4, :]
            table.iat[row, 18] = exports[row - 4]
            row += 1

    footer_rows = {
        8: ("IM", "Imports", [10.0, 20.0, 30.0, 40.0]),
        9: ("TII", "Total Intermediate Input", [0.0, 0.0, 0.0, 0.0]),
        10: ("VA001", "Conpensation of employees", [1.1, 1.2, 1.3, 1.4]),
        11: ("VA002", "Net taxes on production", [2.1, 2.2, 2.3, 2.4]),
        12: ("VA003", "Depreciation on the fixed capital", [3.1, 3.2, 3.3, 3.4]),
        13: ("VA004", "Operationg surplus", [4.1, 4.2, 4.3, 4.4]),
        14: ("TVA", "Total Value Added", [0.0, 0.0, 0.0, 0.0]),
        15: ("TI", "Total Input", [0.0, 0.0, 0.0, 0.0]),
        16: ("", "Gross Input", [0.0, 0.0, 0.0, 0.0]),
        18: ("", "CO2 (Mt)", [0.5, 0.6, 0.7, 0.8]),
    }
    for row, (code, label, values) in footer_rows.items():
        table.iat[row, 1] = label
        table.iat[row, 2] = code
        table.iloc[row, 3:7] = values

    sector_meta = pd.DataFrame(
        {
            "No.": [1, 2],
            "行业": ["农业", "制造业"],
            "Sector": [label for _, label in sectors],
        }
    )
    province_meta = pd.DataFrame(
        {
            "Order": [1, 2],
            "省份": ["甲", "乙"],
            "Province": provinces,
        }
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"A": ["placeholder"]}).to_excel(writer, sheet_name="Note", index=False)
        sector_meta.to_excel(writer, sheet_name="Sector ", index=False)
        province_meta.to_excel(writer, sheet_name="Province", index=False)
        pd.DataFrame({"A": ["placeholder"]}).to_excel(writer, sheet_name=f"Table_{year}", index=False)
        table.to_excel(writer, sheet_name=f"Table_{year}_English Version", header=False, index=False)

    return path


def test_parse_ceads_iot_returns_expected_blocks(tmp_path):
    workbook = _ceads_fixture_workbook(tmp_path / "MRIO 2018.xlsx", year=2018)

    matrices, indeces, units, layout = parse_ceads_iot(workbook)
    base = matrices["baseline"]

    assert layout.workbook_format == "ceads_provincial_workbook"
    assert layout.year == 2018
    assert set(base) == {"Z", "Y", "V", "E", "EY"}
    assert base["Z"].shape == (4, 4)
    assert base["Y"].shape == (4, 12)
    assert base["V"].shape == (5, 4)
    assert base["E"].shape == (1, 4)
    assert base["EY"].shape == (1, 12)
    assert indeces["r"]["main"] == ["Alpha", "Beta"]
    assert indeces["s"]["main"] == ["Agriculture", "Manufacturing"]
    assert indeces["n"]["main"] == [
        "Rural household consumption",
        "Urban household consumption",
        "Government consumption",
        "Fixed capital formation",
        "Changes in inventories",
        "Exports",
    ]
    assert indeces["f"]["main"] == [
        "Imports",
        "Compensation of employees",
        "Net taxes on production",
        "Depreciation of fixed capital",
        "Operating surplus",
    ]
    assert indeces["k"]["main"] == ["CO2"]
    assert units["Sector"].loc["Agriculture", "unit"] == "ten thousand yuan"
    assert units["Satellite account"].loc["CO2", "unit"] == "Mt"

    np.testing.assert_allclose(
        base["Z"].to_numpy(),
        np.array(
            [
                [1.0, 2.0, 3.0, 4.0],
                [5.0, 6.0, 7.0, 8.0],
                [9.0, 10.0, 11.0, 12.0],
                [13.0, 14.0, 15.0, 16.0],
            ]
        ),
    )
    np.testing.assert_allclose(base["V"].loc["Imports"].to_numpy(), np.array([10.0, 20.0, 30.0, 40.0]))
    np.testing.assert_allclose(base["E"].loc["CO2"].to_numpy(), np.array([0.5, 0.6, 0.7, 0.8]))

    export_cols = [column for column in base["Y"].columns if column[-1] == "Exports"]
    assert len(export_cols) == 2
    np.testing.assert_allclose(base["Y"][export_cols[0]].to_numpy(), np.array([1000.0, 2000.0, 0.0, 0.0]))
    np.testing.assert_allclose(base["Y"][export_cols[1]].to_numpy(), np.array([0.0, 0.0, 3000.0, 4000.0]))


def test_public_parse_ceads_returns_database(tmp_path):
    workbook = _ceads_fixture_workbook(tmp_path / "MRIO 2018.xlsx", year=2018)

    database = mario.parse_ceads(str(workbook), calc_all=False)

    assert database.table_type == "IOT"
    assert sorted(database["baseline"].keys()) == ["E", "EY", "V", "Y", "Z"]
    assert database.meta.year == 2018
    assert "CEADS" in database.meta.source


def test_parse_ceads_directory_selection_and_validation(tmp_path):
    _ceads_fixture_workbook(tmp_path / "MRIO 2018.xlsx", year=2018)
    _ceads_fixture_workbook(tmp_path / "MRIO 2020.xlsx", year=2020)

    database = mario.parse_ceads(str(tmp_path), year=2020, calc_all=False)
    assert database.meta.year == 2020

    with pytest.raises(WrongInput):
        mario.parse_ceads(str(tmp_path), calc_all=False)

    with pytest.raises(WrongInput):
        mario.parse_ceads(str(tmp_path), format="legacy", year=2018, calc_all=False)

    with pytest.raises(NotImplementable):
        mario.parse_ceads(str(tmp_path), table="SUT", year=2018, calc_all=False)
