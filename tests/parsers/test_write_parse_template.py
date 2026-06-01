import warnings

import mario
import numpy as np
import pandas as pd
import pytest
from mario.log_exc.exceptions import WrongInput


def test_write_parse_template_iot_flat_roundtrip(tmp_path):
    path = tmp_path / "custom_iot_template.xlsx"

    mario.write_parse_template(
        str(path),
        table="IOT",
        sets={
            "regions": ["Italy", "France"],
            "sectors": ["Agriculture", "Industry"],
            "final demand": ["Households", "Government"],
            "factors": ["Labor", "Capital"],
            "satellites": ["CO2"],
        },
        units={
            "sectors": "M EUR",
            "factors": "M EUR",
            "satellites": "kt",
        },
    )

    database = mario.parse_from_excel(
        str(path),
        table="IOT",
        mode="flows",
        calc_all=False,
    )

    assert database.table_type == "IOT"
    assert database.Z.index.names == ["Region", "Sector"]
    assert database.Y.columns.names == ["Region", "Consumption category"]
    assert set(database.Z.index.get_level_values("Region").unique()) == {"Italy", "France"}
    assert tuple(database.Z.index.get_level_values("Sector").unique()) == ("Agriculture", "Industry")
    assert set(database.Y.columns.get_level_values("Consumption category").unique()) == {
        "Households",
        "Government",
    }
    assert tuple(database.units["Sector"].index) == ("Agriculture", "Industry")
    assert tuple(database.units["Sector"].iloc[:, 0]) == ("M EUR", "M EUR")
    assert tuple(database.units["Factor of production"].index) == ("Labor", "Capital")
    assert tuple(database.units["Satellite account"].index) == ("CO2",)
    assert np.allclose(database.Z.to_numpy(), 0)
    assert np.allclose(database.Y.to_numpy(), 0)
    assert np.allclose(database.V.to_numpy(), 0)
    assert np.allclose(database.E.to_numpy(), 0)


def test_write_parse_template_sut_flat_roundtrip(tmp_path):
    path = tmp_path / "custom_sut_template.xlsx"

    mario.write_parse_template(
        str(path),
        table="SUT",
        sets={
            "regions": ["Italy"],
            "activities": ["Activity 1", "Activity 2"],
            "commodities": ["Commodity 1", "Commodity 2"],
            "final demand": ["Households"],
            "factors": ["Labor"],
            "satellites": ["CO2"],
        },
        units={
            "activities": "M EUR",
            "commodities": "M EUR",
            "factors": "M EUR",
            "satellites": "kt",
        },
    )

    database = mario.parse_from_excel(
        str(path),
        table="SUT",
        mode="flows",
        calc_all=False,
    )

    assert database.table_type == "SUT"
    assert database.Z.index.names == ["Region", "Level", "Item"]
    assert tuple(database.Z.index.get_level_values("Level").unique()) == ("Activity", "Commodity")
    assert tuple(database.Y.columns.get_level_values("Item")) == ("Households",)
    assert tuple(database.units["Activity"].index) == ("Activity 1", "Activity 2")
    assert tuple(database.units["Commodity"].index) == ("Commodity 1", "Commodity 2")
    assert tuple(database.units["Factor of production"].index) == ("Labor",)
    assert tuple(database.units["Satellite account"].index) == ("CO2",)
    assert np.allclose(database.Z.to_numpy(), 0)
    assert np.allclose(database.Y.to_numpy(), 0)
    assert np.allclose(database.V.to_numpy(), 0)
    assert np.allclose(database.E.to_numpy(), 0)


def test_write_parse_template_matrix_format_roundtrip(tmp_path):
    path = tmp_path / "custom_iot_matrix_template.xlsx"

    mario.write_parse_template(
        str(path),
        table="IOT",
        format="matrix",
        sets={
            "regions": ["Italy"],
            "sectors": ["Agriculture"],
            "final demand": ["Households"],
            "factors": ["Labor"],
            "satellites": ["CO2"],
        },
        units={
            "sectors": "M EUR",
            "factors": "M EUR",
            "satellites": "kt",
        },
    )

    database = mario.parse_from_excel(
        str(path),
        table="IOT",
        mode="flows",
        calc_all=False,
    )

    assert database.table_type == "IOT"
    assert database.Z.index.names == ["Region", "Level", "Item"]
    assert tuple(database.Z.index.get_level_values("Item").unique()) == ("Agriculture",)
    assert tuple(database.Y.columns.get_level_values("Item").unique()) == ("Households",)
    assert tuple(database.units["Sector"].iloc[:, 0]) == ("M EUR",)
    assert np.allclose(database.Z.to_numpy(), 0)


def test_write_parse_template_accepts_definition_workbook(tmp_path):
    definition_path = tmp_path / "custom_iot_definition.xlsx"
    workbook_path = tmp_path / "custom_iot_from_definition.xlsx"

    mario.write_template_definition(
        str(definition_path),
        table="IOT",
    )

    definition = pd.read_excel(definition_path, sheet_name="definition", header=[0, 1])
    definition = definition.loc[
        :,
        ~definition.columns.get_level_values(0).map(str).str.startswith("Unnamed:"),
    ]
    definition.loc[0, ("Region", "value")] = "Italy"
    definition.loc[1, ("Region", "value")] = "France"
    definition.loc[0, ("Sector", "value")] = "Agriculture"
    definition.loc[0, ("Sector", "unit")] = "M EUR"
    definition.loc[1, ("Sector", "value")] = "Industry"
    definition.loc[1, ("Sector", "unit")] = "M EUR"
    definition.loc[0, ("Final demand", "value")] = "Households"
    definition.loc[1, ("Final demand", "value")] = "Government"
    definition.loc[0, ("Factor of production", "value")] = "Labor"
    definition.loc[0, ("Factor of production", "unit")] = "M EUR"
    definition.loc[1, ("Factor of production", "value")] = "Capital"
    definition.loc[1, ("Factor of production", "unit")] = "M EUR"
    definition.loc[0, ("Satellite account", "value")] = "CO2"
    definition.loc[0, ("Satellite account", "unit")] = "kt"

    with pd.ExcelWriter(definition_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        definition.to_excel(writer, sheet_name="definition")

    mario.write_parse_template(
        str(workbook_path),
        table="IOT",
        definition=str(definition_path),
    )

    database = mario.parse_from_excel(
        str(workbook_path),
        table="IOT",
        mode="flows",
        calc_all=False,
    )

    assert set(database.Z.index.get_level_values("Region").unique()) == {"Italy", "France"}
    assert tuple(database.units["Sector"].index) == ("Agriculture", "Industry")
    assert tuple(database.units["Factor of production"].index) == ("Labor", "Capital")
    assert tuple(database.units["Satellite account"].index) == ("CO2",)


def test_write_parse_template_rejects_definition_plus_sets(tmp_path):
    definition_path = tmp_path / "custom_iot_definition.xlsx"
    mario.write_template_definition(str(definition_path), table="IOT")

    with pytest.raises(WrongInput):
        mario.write_parse_template(
            str(tmp_path / "invalid.xlsx"),
            table="IOT",
            definition=str(definition_path),
            sets={"regions": ["Italy"]},
            units={"sectors": "M EUR"},
        )


def test_datatemplate_emits_deprecation_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        template = mario.DataTemplate("IOT")

    assert template._table == "IOT"
    assert any(
        isinstance(item.message, DeprecationWarning)
        or item.category is DeprecationWarning
        for item in caught
    )
