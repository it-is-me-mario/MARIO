from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.parsers.useeio import parse_useeio_sut


def _write_useeio_workbook(path: Path, *, demand_year: int = 2022) -> Path:
    """Write one compact USEEIO-like workbook fixture."""
    commodity_ids = ["A11/US", "A22/US", "Used/US"]
    activity_ids = ["A11/US", "A22/US"]
    final_demand_ids = ["F010/US", "F040/US"]
    factor_ids = ["V001/US", "V002/US"]
    flow_ids = ["CO2/emission/air/kg", "Water/resource/m3"]

    V = pd.DataFrame(
        [[10.0, 1.0, 0.0], [2.0, 20.0, 3.0]],
        index=activity_ids,
        columns=commodity_ids,
    )
    U = pd.DataFrame(
        [
            [1.0, 2.0, 7.0, 8.0],
            [3.0, 4.0, 9.0, 10.0],
            [5.0, 6.0, 11.0, 12.0],
            [13.0, 14.0, 0.0, 0.0],
            [15.0, 16.0, 0.0, 0.0],
        ],
        index=commodity_ids + factor_ids,
        columns=activity_ids + final_demand_ids,
    )
    B = pd.DataFrame(
        [[0.1, 0.2, 0.3], [1.0, 2.0, 3.0]],
        index=flow_ids,
        columns=commodity_ids,
    )
    q = pd.Series([100.0, 200.0, 300.0], index=commodity_ids, name="q")
    x = pd.Series([110.0, 220.0], index=activity_ids, name="x")

    commodities_meta = pd.DataFrame(
        {
            "Index": [0, 1, 2],
            "ID": commodity_ids,
            "Name": ["Commodity 1", "Commodity 2", "Used commodity"],
            "Code": ["A11", "A22", "Used"],
            "Location": ["US", "US", "US"],
            "Category": ["Test", "Test", "Test"],
            "Description": ["", "", ""],
            "Unit": ["USD", "USD", "USD"],
        }
    )
    final_demand_meta = pd.DataFrame(
        {
            "Index": [0, 1],
            "ID": final_demand_ids,
            "Name": ["Households", "Exports"],
            "Code": ["F010", "F040"],
            "Location": ["US", "US"],
            "Description": ["", ""],
        }
    )
    value_added_meta = pd.DataFrame(
        {
            "Index": [0, 1],
            "ID": factor_ids,
            "Name": ["Compensation", "Taxes net of subsidies"],
            "Code": ["V001", "V002"],
            "Location": ["US", "US"],
            "Description": ["", ""],
        }
    )
    flows = pd.DataFrame(
        {
            "Index": [0, 1],
            "ID": flow_ids,
            "Flowable": ["CO2", "Water"],
            "Context": ["emission/air", "resource"],
            "Unit": ["kg", "m3"],
            "UUID": ["", ""],
        }
    )
    demands = pd.DataFrame(
        {
            "ID": [
                f"{demand_year}_US_Production_Complete",
                f"{demand_year}_US_Consumption_Complete",
            ],
            "Year": [demand_year, demand_year],
            "Type": ["Production", "Consumption"],
            "System": ["Complete", "Complete"],
            "Location": ["US", "US"],
        }
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        V.to_excel(writer, sheet_name="V", index_label="")
        U.to_excel(writer, sheet_name="U", index_label="")
        B.to_excel(writer, sheet_name="B", index_label="")
        q.to_frame().to_excel(writer, sheet_name="q", index_label="")
        x.to_frame().to_excel(writer, sheet_name="x", index_label="")
        commodities_meta.to_excel(writer, sheet_name="commodities_meta", index=False)
        final_demand_meta.to_excel(writer, sheet_name="final_demand_meta", index=False)
        value_added_meta.to_excel(writer, sheet_name="value_added_meta", index=False)
        flows.to_excel(writer, sheet_name="flows", index=False)
        demands.to_excel(writer, sheet_name="demands", index=False)

    return path


def test_parse_useeio_sut_returns_split_native_blocks(tmp_path):
    workbook = _write_useeio_workbook(tmp_path / "USEEIOv2.5-yellowthroat-22.xlsx")

    matrices, indeces, units, layout = parse_useeio_sut(workbook)
    base = matrices["baseline"]

    assert layout.workbook_format == "v2.5_workbook"
    assert layout.workbook_version == "2.5"
    assert layout.model_alias == "yellowthroat"
    assert layout.release_year == 2022
    assert layout.io_year == 2022
    assert set(base) == {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"}
    assert base["S"].shape == (2, 3)
    assert base["U"].shape == (3, 2)
    assert base["Yc"].shape == (3, 2)
    assert base["Va"].shape == (2, 2)
    assert base["Ec"].shape == (2, 3)
    assert np.allclose(base["Ea"].to_numpy(), 0.0)
    assert np.allclose(base["Vc"].to_numpy(), 0.0)
    assert np.allclose(base["EY"].to_numpy(), 0.0)
    assert indeces["r"]["main"] == ["US"]
    assert indeces["a"]["main"] == ["Commodity 1", "Commodity 2"]
    assert indeces["c"]["main"] == ["Commodity 1", "Commodity 2", "Used commodity"]
    assert indeces["n"]["main"] == ["Households", "Exports"]
    assert indeces["f"]["main"] == ["Compensation", "Taxes net of subsidies"]
    assert indeces["k"]["main"] == ["CO2/emission/air/kg", "Water/resource/m3"]
    assert units["Satellite account"].loc["CO2/emission/air/kg", "unit"] == "kg"

    np.testing.assert_allclose(base["S"].to_numpy(), np.array([[10.0, 1.0, 0.0], [2.0, 20.0, 3.0]]))
    np.testing.assert_allclose(base["U"].to_numpy(), np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]))
    np.testing.assert_allclose(base["Yc"].to_numpy(), np.array([[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]))
    np.testing.assert_allclose(base["Va"].to_numpy(), np.array([[13.0, 14.0], [15.0, 16.0]]))
    np.testing.assert_allclose(
        base["Ec"].to_numpy(),
        np.array([[10.0, 40.0, 90.0], [100.0, 400.0, 900.0]]),
    )


def test_public_parse_useeio_returns_database(tmp_path):
    workbook = _write_useeio_workbook(tmp_path / "USEEIOv2.5-yellowthroat-22.xlsx")

    database = mario.parse_useeio(str(workbook), calc_all=False)

    assert database.table_type == "SUT"
    assert sorted(database["baseline"].keys()) == ["EY", "Ea", "Ec", "S", "U", "Va", "Vc", "Ya", "Yc"]
    assert database.meta.year == 2022
    assert "USEEIO" in database.meta.source
    assert database.meta.price == "Model-year USD"


def test_parse_useeio_directory_selects_alias_and_release_year(tmp_path):
    _write_useeio_workbook(tmp_path / "USEEIOv2.5-yellowthroat-22.xlsx", demand_year=2022)
    _write_useeio_workbook(tmp_path / "USEEIOv2.5-waxwing-22.xlsx", demand_year=2022)
    _write_useeio_workbook(tmp_path / "USEEIOv2.5-yellowthroat-21.xlsx", demand_year=2021)

    database = mario.parse_useeio(
        str(tmp_path),
        model_alias="yellowthroat",
        release_year=2022,
        calc_all=False,
    )

    assert database.meta.name == "USEEIO v2.5 yellowthroat 2022"
    assert database.meta.year == 2022


def test_parse_useeio_directory_with_many_workbooks_requires_selector(tmp_path):
    _write_useeio_workbook(tmp_path / "USEEIOv2.5-yellowthroat-22.xlsx")
    _write_useeio_workbook(tmp_path / "USEEIOv2.5-waxwing-22.xlsx")

    with pytest.raises(WrongInput, match="model_alias"):
        mario.parse_useeio(str(tmp_path), calc_all=False)


def test_parse_useeio_validates_format_and_table(tmp_path):
    workbook = _write_useeio_workbook(tmp_path / "USEEIOv2.5-yellowthroat-22.xlsx")

    with pytest.raises(WrongInput):
        mario.parse_useeio(str(workbook), format="legacy", calc_all=False)

    with pytest.raises(NotImplementable):
        mario.parse_useeio(str(workbook), table="IOT", calc_all=False)
