import pandas as pd
import pandas.testing as pdt
import pytest

from mario.api import Database
from mario.model.conventions import _MASTER_INDEX


def _build_ghg_database():
    regions = ["R1"]
    sectors = ["s1", "s2"]
    final_demand = ["fd"]
    factors = ["Labor"]
    satellite_accounts = [
        "CO2 - combustion - air",
        "CH4 - combustion - air",
        "N2O - combustion - air",
        "Employment",
    ]

    sector_axis = pd.MultiIndex.from_product(
        [regions, [_MASTER_INDEX["s"]], sectors],
        names=["Region", "Level", "Item"],
    )
    final_demand_axis = pd.MultiIndex.from_product(
        [regions, [_MASTER_INDEX["n"]], final_demand],
        names=["Region", "Level", "Item"],
    )

    Z = pd.DataFrame(
        [[1.0, 0.0], [0.0, 1.0]],
        index=sector_axis,
        columns=sector_axis,
    )
    Y = pd.DataFrame(
        [[10.0], [20.0]],
        index=sector_axis,
        columns=final_demand_axis,
    )
    V = pd.DataFrame([[1.0, 1.0]], index=factors, columns=sector_axis)
    E = pd.DataFrame(
        [[1.0, 2.0], [3.0, 4.0], [0.5, 1.5], [9.0, 9.0]],
        index=satellite_accounts,
        columns=sector_axis,
    )
    EY = pd.DataFrame(
        [[5.0], [6.0], [7.0], [0.0]],
        index=satellite_accounts,
        columns=final_demand_axis,
    )
    VY = pd.DataFrame([[0.0]], index=factors, columns=final_demand_axis)

    units = {
        _MASTER_INDEX["s"]: pd.DataFrame({"unit": ["EUR", "EUR"]}, index=sectors),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": ["EUR"]}, index=factors),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": ["kg", "kg", "kg", "hours"]},
            index=satellite_accounts,
        ),
    }

    database = Database(
        name="ghg-fixture",
        table="IOT",
        Z=Z,
        V=V,
        E=E,
        EY=EY,
        VY=VY,
        Y=Y,
        units=units,
        calc_all=True,
    )
    database.meta.source = "exiobase monetary fixture"

    return database


def test_calc_ghg_adds_weighted_row_to_E_and_EY():
    database = _build_ghg_database()

    result = database.calc_ghg(profile="exiobase_monetary")

    label = "GHG AR6 GWP-100"
    assert result is None
    assert label in database.get_index("Satellite account")
    assert database.units["Satellite account"].loc[label, "unit"] == "kg"
    assert label in database.e.index

    expected_e = (
        database.E.loc["CO2 - combustion - air"]
        + database.E.loc["CH4 - combustion - air"] * 29.8
        + database.E.loc["N2O - combustion - air"] * 273
    )
    expected_ey = (
        database.EY.loc["CO2 - combustion - air"]
        + database.EY.loc["CH4 - combustion - air"] * 29.8
        + database.EY.loc["N2O - combustion - air"] * 273
    )

    pdt.assert_series_equal(database.E.loc[label], expected_e, check_names=False)
    pdt.assert_series_equal(database.EY.loc[label], expected_ey, check_names=False)


def test_calc_ghg_default_label_encodes_report_and_horizon():
    database = _build_ghg_database()

    database.calc_ghg(profile="exiobase_monetary", ipcc_report="ar5", time_horizon=100)

    assert "GHG AR5 GWP-100" in database.get_index("Satellite account")


def test_calc_ghg_custom_gwp_default_label_is_plain_ghg():
    database = _build_ghg_database()

    database.calc_ghg(
        gwp={"CO2 - combustion - air": 1},
        ipcc_report="AR6",
        time_horizon=100,
    )

    assert "GHG" in database.get_index("Satellite account")
    assert "GHG AR6 GWP-100" not in database.get_index("Satellite account")


def test_calc_ghg_requires_consistent_source_units():
    database = _build_ghg_database()
    database.units["Satellite account"].loc["CH4 - combustion - air", "unit"] = "ton"

    with pytest.raises(ValueError, match="share the same unit"):
        database.calc_ghg(profile="exiobase_monetary")


def test_calc_ghg_resolves_requested_ipcc_report():
    database = _build_ghg_database()

    database.calc_ghg(
        profile="exiobase_monetary",
        time_horizon=100,
        ipcc_report="AR4",
    )

    label = "GHG AR4 GWP-100"
    expected_e = (
        database.E.loc["CO2 - combustion - air"]
        + database.E.loc["CH4 - combustion - air"] * 25
        + database.E.loc["N2O - combustion - air"] * 298
    )
    expected_ey = (
        database.EY.loc["CO2 - combustion - air"]
        + database.EY.loc["CH4 - combustion - air"] * 25
        + database.EY.loc["N2O - combustion - air"] * 298
    )

    pdt.assert_series_equal(database.E.loc[label], expected_e, check_names=False)
    pdt.assert_series_equal(database.EY.loc[label], expected_ey, check_names=False)


def test_calc_ghg_custom_gwp_ignores_profile_resolution_arguments():
    database = _build_ghg_database()

    database.calc_ghg(
        gwp={
            "CO2 - combustion - air": 1,
            "CH4 - combustion - air": 10,
            "N2O - combustion - air": 20,
        },
        time_horizon=20,
        ipcc_report="AR4",
    )

    expected_e = (
        database.E.loc["CO2 - combustion - air"]
        + database.E.loc["CH4 - combustion - air"] * 10
        + database.E.loc["N2O - combustion - air"] * 20
    )
    expected_ey = (
        database.EY.loc["CO2 - combustion - air"]
        + database.EY.loc["CH4 - combustion - air"] * 10
        + database.EY.loc["N2O - combustion - air"] * 20
    )

    pdt.assert_series_equal(database.E.loc["GHG"], expected_e, check_names=False)
    pdt.assert_series_equal(database.EY.loc["GHG"], expected_ey, check_names=False)
