from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.parsers.bea import parse_bea_sut


def _write_bea_summary_workbooks(root: Path, *, year: int = 2024) -> tuple[Path, Path]:
    """Write one compact BEA summary-like supply/use pair."""
    supply = pd.DataFrame("", index=range(10), columns=range(14), dtype=object)
    supply.iat[3, 0] = year
    supply.iloc[5, 2:14] = [
        "111A",
        "222B",
        "T007",
        "MCIF",
        "MADJ",
        "TRADE",
        "TRANS",
        "MDTY",
        "TOP",
        "SUB",
        "T015",
        "T016",
    ]
    supply.iloc[6, 2:14] = [
        "Farms",
        "Factories",
        "Total Commodity Output",
        "Imports",
        "CIF/FOB Adjustments on Imports",
        "Trade margins",
        "Transport margins",
        "Import duties",
        "Tax on products",
        "Subsidies",
        "Total tax less subsidies on products",
        "Total product supply (purchaser prices)",
    ]
    supply.iat[7, 0] = "111A"
    supply.iat[7, 1] = "Farms"
    supply.iloc[7, 2:14] = [10, 20, 30, 1, 2, 3, 4, 5, 6, 7, 0, 0]
    supply.iat[8, 0] = "222B"
    supply.iat[8, 1] = "Factories"
    supply.iloc[8, 2:14] = [40, 50, 90, 8, 9, 10, 11, 12, 13, 14, 0, 0]
    supply.iat[9, 0] = "T017"
    supply.iat[9, 1] = "Total industry supply"

    use = pd.DataFrame("", index=range(15), columns=range(8), dtype=object)
    use.iat[3, 0] = year
    use.iloc[5, 2:8] = ["111A", "222B", "T001", "F010", "F040", "T019"]
    use.iloc[6, 2:8] = [
        "Farms",
        "Factories",
        "Total Intermediate",
        "Personal consumption expenditures",
        "Exports of goods and services",
        "Total use of products",
    ]
    use.iat[7, 0] = "111A"
    use.iat[7, 1] = "Farms"
    use.iloc[7, 2:8] = [100, 200, 300, 400, 500, 0]
    use.iat[8, 0] = "222B"
    use.iat[8, 1] = "Factories"
    use.iloc[8, 2:8] = [600, 700, 1300, 800, 900, 0]
    use.iat[9, 0] = "T005"
    use.iat[9, 1] = "Total Intermediate"
    use.iat[10, 0] = "V001"
    use.iat[10, 1] = "Compensation of employees"
    use.iloc[10, 2:4] = [11, 12]
    use.iat[11, 0] = "T00OTOP"
    use.iat[11, 1] = "Other taxes on production"
    use.iloc[11, 2:4] = [13, 14]
    use.iat[12, 0] = "T00OSUB"
    use.iat[12, 1] = "Less: Other subsidies on production"
    use.iloc[12, 2:4] = [1, 2]
    use.iat[13, 0] = "V003"
    use.iat[13, 1] = "Gross operating surplus"
    use.iloc[13, 2:4] = [15, 16]
    use.iat[14, 0] = "T018"
    use.iat[14, 1] = "Total industry output"

    supply_path = root / "Supply_Summary.xlsx"
    use_path = root / "Use_Summary.xlsx"
    with pd.ExcelWriter(supply_path, engine="openpyxl") as writer:
        supply.to_excel(writer, sheet_name=str(year), header=False, index=False)
    with pd.ExcelWriter(use_path, engine="openpyxl") as writer:
        use.to_excel(writer, sheet_name=str(year), header=False, index=False)
    return supply_path, use_path


def _write_bea_detail_workbooks(root: Path, *, year: int = 2017) -> tuple[Path, Path]:
    """Write one compact BEA detail-like supply/use pair."""
    supply = pd.DataFrame("", index=range(9), columns=range(10), dtype=object)
    supply.iat[2, 0] = "Bureau of Economic Analysis"
    supply.iloc[4, 0:10] = [
        "Commodities/Industries",
        "",
        "Oilseed farming",
        "Paper mills",
        "Total Commodity Output",
        "Imports",
        "CIF/FOB Adjustments on Imports",
        "Trade margins",
        "Tax on products",
        "Total product supply (purchaser prices)",
    ]
    supply.iloc[5, 0:10] = ["Code", "Commodity Description", "111100", "322100", "T007", "MCIF", "MADJ", "TRADE", "TOP", "T016"]
    supply.iat[6, 0] = "111100"
    supply.iat[6, 1] = "Oilseed farming"
    supply.iloc[6, 2:10] = [10, 20, 30, 1, 2, 3, 4, 0]
    supply.iat[7, 0] = "322100"
    supply.iat[7, 1] = "Paper mills"
    supply.iloc[7, 2:10] = [40, 50, 90, 8, 9, 10, 11, 0]
    supply.iat[8, 0] = "T017"
    supply.iat[8, 1] = "Total industry supply"

    use = pd.DataFrame("", index=range(13), columns=range(7), dtype=object)
    use.iloc[4, 0:7] = [
        "Commodities/Industries",
        "",
        "Oilseed farming",
        "Paper mills",
        "Total intermediate",
        "Personal consumption expenditures",
        "Total use of products",
    ]
    use.iloc[5, 0:7] = ["Code", "Commodity Description", "111100", "322100", "T001", "F01000", "T019"]
    use.iat[6, 0] = "111100"
    use.iat[6, 1] = "Oilseed farming"
    use.iloc[6, 2:7] = [100, 200, 300, 400, 0]
    use.iat[7, 0] = "322100"
    use.iat[7, 1] = "Paper mills"
    use.iloc[7, 2:7] = [600, 700, 1300, 800, 0]
    use.iat[8, 0] = "T005"
    use.iat[8, 1] = "Total intermediate inputs"
    use.iat[9, 0] = "V00100"
    use.iat[9, 1] = "Compensation of employees"
    use.iloc[9, 2:4] = [21, 22]
    use.iat[10, 0] = "T00OTOP"
    use.iat[10, 1] = "Other taxes on production"
    use.iloc[10, 2:4] = [23, 24]
    use.iat[11, 0] = "V00300"
    use.iat[11, 1] = "Gross operating surplus"
    use.iloc[11, 2:4] = [25, 26]
    use.iat[12, 0] = "T018"
    use.iat[12, 1] = "Total industry output"

    supply_path = root / "Supply_Detail.xlsx"
    use_path = root / "Use_SUT_Detail.xlsx"
    with pd.ExcelWriter(supply_path, engine="openpyxl") as writer:
        supply.to_excel(writer, sheet_name=str(year), header=False, index=False)
    with pd.ExcelWriter(use_path, engine="openpyxl") as writer:
        use.to_excel(writer, sheet_name=str(year), header=False, index=False)
    return supply_path, use_path


def _write_bea_summary_zip(path: Path, *, year: int = 2024) -> Path:
    """Write one zip bundle containing the BEA summary fixture pair."""
    root = path.parent / f"{path.stem}_source"
    root.mkdir()
    supply_path, use_path = _write_bea_summary_workbooks(root, year=year)
    with ZipFile(path, "w") as archive:
        archive.write(supply_path, supply_path.name)
        archive.write(use_path, use_path.name)
    return path


def test_parse_bea_sut_summary_blocks(tmp_path):
    _write_bea_summary_workbooks(tmp_path, year=2024)

    matrices, indeces, units, layout = parse_bea_sut(tmp_path, year=2024, level="summary")
    base = matrices["baseline"]

    assert layout.level == "summary"
    assert layout.year == 2024
    assert set(base) == {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"}
    assert base["S"].shape == (2, 2)
    assert base["U"].shape == (2, 2)
    assert base["Yc"].shape == (2, 2)
    assert base["Va"].shape == (11, 2)
    assert base["Vc"].shape == (11, 2)
    assert indeces["r"]["main"] == ["USA"]
    assert indeces["a"]["main"] == ["Farms", "Factories"]
    assert indeces["c"]["main"] == ["Farms", "Factories"]
    assert indeces["n"]["main"] == [
        "Personal consumption expenditures",
        "Exports of goods and services",
    ]
    assert indeces["f"]["main"] == [
        "Compensation of employees",
        "Other taxes on production",
        "Less: Other subsidies on production",
        "Gross operating surplus",
        "Imports",
        "CIF/FOB adjustments on imports",
        "Trade margins",
        "Transport margins",
        "Import duties",
        "Tax on products",
        "Subsidies",
    ]
    assert units["Activity"].loc["Farms", "unit"] == "Millions of current dollars"

    np.testing.assert_allclose(base["S"].to_numpy(), np.array([[10.0, 40.0], [20.0, 50.0]]))
    np.testing.assert_allclose(base["U"].to_numpy(), np.array([[100.0, 200.0], [600.0, 700.0]]))
    np.testing.assert_allclose(base["Yc"].to_numpy(), np.array([[400.0, 500.0], [800.0, 900.0]]))
    np.testing.assert_allclose(base["Va"].loc["Compensation of employees"].to_numpy(), np.array([11.0, 12.0]))
    np.testing.assert_allclose(base["Vc"].loc["Imports"].to_numpy(), np.array([1.0, 8.0]))
    np.testing.assert_allclose(base["Vc"].loc["Tax on products"].to_numpy(), np.array([6.0, 13.0]))


def test_public_parse_bea_accepts_zip_bundle(tmp_path):
    bundle = _write_bea_summary_zip(tmp_path / "SUPPLY-USE.zip", year=2024)

    database = mario.parse_bea(str(bundle), year=2024, level="summary", calc_all=False)

    assert database.table_type == "SUT"
    assert database.meta.year == 2024
    assert "BEA" in database.meta.source
    assert sorted(database["baseline"].keys()) == ["EY", "Ea", "Ec", "S", "U", "Va", "Vc", "Ya", "Yc"]


def test_parse_bea_detail_from_workbook_path(tmp_path):
    supply_path, _ = _write_bea_detail_workbooks(tmp_path, year=2017)

    database = mario.parse_bea(str(supply_path), year=2017, level="detail", calc_all=False)

    assert database.meta.year == 2017
    assert database["baseline"]["S"].shape == (2, 2)
    assert database["baseline"]["Yc"].shape == (2, 1)
    np.testing.assert_allclose(
        database["baseline"]["Va"].loc["Compensation of employees"].to_numpy(),
        np.array([21.0, 22.0]),
    )


def test_parse_bea_validation(tmp_path):
    _write_bea_summary_workbooks(tmp_path, year=2024)

    with pytest.raises(NotImplementable):
        mario.parse_bea(str(tmp_path), year=2024, table="IOT", calc_all=False)

    with pytest.raises(WrongInput):
        mario.parse_bea(str(tmp_path), year=2024, level="legacy", calc_all=False)

    with pytest.raises(WrongInput):
        mario.parse_bea(str(tmp_path), year=2017, level="summary", calc_all=False)
