import pandas as pd
import pandas.testing as pdt
import pytest

from mario.api import Database
from mario.model.conventions import _MASTER_INDEX
from mario.settings.settings import download_settings, upload_settings


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


@pytest.mark.parametrize("inplace", [True, False])
@pytest.mark.parametrize("canonical,alias", [("E", "R"), ("EY", "Ry"), ("F", "Re")])
def test_calc_ghg_and_plot_accept_renamed_flow_and_coefficient_matrices(inplace, canonical, alias):
    original = download_settings(None)
    custom = download_settings(None)
    custom["nomenclature"].update({
        "E": "R", "EY": "Ry", "e": "rho", "F": "Re",
        "V": "Primary inputs", "v": "Primary coefficients",
    })
    try:
        upload_settings(custom)
        database = _build_ghg_database()
        name = database.R.index.name
        result = database.calc_ghg(profile="exiobase_monetary", inplace=inplace)
        target = database if inplace else result

        assert target.R.index.name == name
        assert target.Ry.index.name == name
        assert target.R.loc["GHG AR6 GWP-100"].tolist() == pytest.approx([226.9, 530.7])
        assert "GHG AR6 GWP-100" in target.rho.index
        assert {"E", "EY"} <= set(target["baseline"])
        if not inplace:
            assert "GHG AR6 GWP-100" not in database.R.index

        plotted = []
        for matrix in (canonical, alias):
            figure, values = target.plot(
                matrix=matrix, x="Item_to", color="Region",
                filters={"Item_from": ["GHG AR6 GWP-100"]},
                show_totals=True, path=False, return_data=True,
            )
            totals = [trace for trace in figure.data if trace.type == "scatter"]
            assert sum(totals[0].customdata) == pytest.approx(values.Value.sum())
            assert values.Value.sum() == pytest.approx(target.query(canonical).loc["GHG AR6 GWP-100"].sum())
            plotted.append(values)
        pdt.assert_frame_equal(plotted[0], plotted[1])
    finally:
        upload_settings(original)


@pytest.mark.parametrize("inplace", [True, False])
@pytest.mark.parametrize("index_name", ["Item", "Satellite account"])
def test_calc_ghg_preserves_axes_and_plot_filters(inplace, index_name):
    database = _build_ghg_database()
    database.E.index.name = index_name
    database.EY.index.name = index_name
    unit_name = database.units["Satellite account"].index.name
    sector_names = database.E.columns.names
    final_names = database.EY.columns.names

    result = database.calc_ghg(profile="exiobase_monetary", inplace=inplace)
    result = database if inplace else result

    assert result.E.index.name == index_name
    assert result.EY.index.name == index_name
    assert result.units["Satellite account"].index.name == unit_name
    assert result.E.columns.names == sector_names
    assert result.EY.columns.names == final_names
    if not inplace:
        assert "GHG AR6 GWP-100" not in database.E.index

    account_column = "Item_from" if index_name == "Item" else index_name
    sector_column = "Item_to" if index_name == "Item" else "Item"
    _, plotted = result.plot(
        matrix="E", x=sector_column, color="Region",
        filters={"Region": ["R1"], account_column: ["GHG AR6 GWP-100"]},
        path=False, return_data=True,
    )
    assert plotted[sector_column].tolist() == ["s1", "s2"]
    assert plotted.Value.tolist() == pytest.approx([226.9, 530.7])


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
