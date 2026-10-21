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


@pytest.mark.parametrize("table", ["IOT", "SUT"])
@pytest.mark.parametrize("sparse_backed", [False, True])
@pytest.mark.parametrize("coefficients_only", [False, True])
def test_calc_ghg_updates_cached_blocks_without_computing_or_deleting_scenarios(
    table, sparse_backed, coefficients_only, monkeypatch,
):
    import numpy as np
    import mario
    from mario.compute.catalog import get_matrix_spec, available_matrix_names
    from mario.compute.helpers import dense_values
    from mario.compute.types import ComputeOptions

    db = mario.load_test(table)
    if sparse_backed:
        for name, frame in list(db.matrices["baseline"].items()):
            db.set_block(name, frame.astype(pd.SparseDtype(float, 0)))
    db.calc_all(
        ["e", "f", "F"] if table == "IOT" else ["ea", "ec", "fa", "fc", "Fa", "Fc", "E", "e", "f", "F"],
        compute_options=ComputeOptions(backend_override="sparse_direct"),
    )
    if coefficients_only:
        db.reset_to_coefficients("baseline")
    environmental = {
        name for name in available_matrix_names(table)
        if get_matrix_spec(table, name).axes.rows == ("Satellite account",)
    }
    db.clone_scenario("baseline", "policy")
    for name in set(db.matrices["policy"]) & environmental:
        db.matrices["policy"][name] = db.matrices["policy"][name] * 2
    before = {s: dict(blocks) for s, blocks in db.matrices.items()}
    units_before = db.units["Satellite account"].copy()

    def forbidden(*args, **kwargs):
        raise AssertionError("calc_ghg must not resolve matrices or reconstruct the database")

    monkeypatch.setattr(db, "calc_all", forbidden)
    monkeypatch.setattr(db, "query", forbidden)
    monkeypatch.setattr(db, "add_extensions", forbidden)
    monkeypatch.setattr("mario.compute.resolver.Resolver.resolve", forbidden)
    db.calc_ghg(gwp={"CO2": 2.0})

    assert db.scenarios == ["baseline", "policy"]
    assert db.get_index("Satellite account") == ["Employment", "CO2", "GHG"]
    pdt.assert_frame_equal(db.units["Satellite account"].loc[units_before.index], units_before)
    assert db.units["Satellite account"].loc["GHG", "unit"] == units_before.loc["CO2", "unit"]
    for scenario, blocks in before.items():
        assert blocks.keys() == db.matrices[scenario].keys()
        for name, old in blocks.items():
            actual = db.get_block(name, scenario=scenario)
            if name in environmental:
                pdt.assert_frame_equal(actual.loc[old.index], old)
                assert actual.columns.equals(old.columns)
                assert actual.index.name == old.index.name
                np.testing.assert_allclose(dense_values(actual.loc["GHG"]), dense_values(old.loc["CO2"]) * 2)
                if all(isinstance(t, pd.SparseDtype) and t.fill_value == 0 for t in old.dtypes):
                    assert all(isinstance(t, pd.SparseDtype) and t.fill_value == 0 for t in actual.dtypes)
            else:
                assert actual is old


@pytest.mark.parametrize("inplace", [False, True])
def test_calc_ghg_native_regional_sut_uses_only_stored_satellites(inplace, monkeypatch):
    import numpy as np
    from tests.api.test_trade_content_loading import regional_model
    from mario.compute.helpers import dense_values

    db = regional_model(True)
    for name in ["Ea", "Ec", "EY"]:
        frame = db.get_block(name)
        ch4 = frame * .2
        ch4.index = pd.Index(["CH4"], name=frame.index.name)
        db.set_block(name, pd.concat([frame, ch4]))
    db._indeces["k"]["main"].append("CH4")
    db.units["Satellite account"] = pd.DataFrame({"unit": ["kg", "kg"]}, index=["CO2", "CH4"])
    before = dict(db.matrices["baseline"])
    before_indices = db.get_index("all")

    def forbidden(*args, **kwargs):
        raise AssertionError("Characterization must not ask the resolver for missing matrices")

    monkeypatch.setattr("mario.compute.resolver.Resolver.resolve", forbidden)
    result = db.calc_ghg(gwp={"CO2": 1., "CH4": 10.}, inplace=inplace)
    target = db if inplace else result
    assert set(target.matrices["baseline"]) == set(before)
    for name in ["Ea", "Ec", "EY"]:
        actual = target.get_block(name)
        expected = dense_values(before[name].loc["CO2"]) * 3
        np.testing.assert_allclose(dense_values(actual.loc["GHG"]), expected)
        assert all(isinstance(t, pd.SparseDtype) and t.fill_value == 0 for t in actual.dtypes)
    for name in ["Activity", "Commodity", "Consumption category", "Region"]:
        assert target.get_index(name) == before_indices[name]
    assert not {"E", "e", "Z", "z", "V", "v", "Y", "f", "fc"}.intersection(target["baseline"])
    if not inplace:
        assert "GHG" not in db.get_index("Satellite account")
        assert all(db.get_block(name) is frame for name, frame in before.items())
        modified = target.Ea.sparse.to_dense()
        modified.iloc[0, 0] = -999
        target.set_block("Ea", modified)
        pdt.assert_frame_equal(db.Ea, before["Ea"])


def test_calc_ghg_cached_multiplier_matches_later_resolution_from_characterized_flows():
    import mario
    from mario.compute.types import ComputeOptions

    db = mario.load_test("SUT")
    options = ComputeOptions(backend_override="sparse_direct")
    reference = db.resolve("fc", compute_options=options).loc["CO2"] * 2
    db.calc_ghg(gwp={"CO2": 2.})
    pdt.assert_series_equal(db.fc.loc["GHG"], reference, check_names=False)
    cached = db.fc.copy()
    db.matrices["baseline"].pop("fc")
    rebuilt = db.resolve("fc", compute_options=options)
    pdt.assert_frame_equal(rebuilt, cached)


@pytest.mark.parametrize("sparse_backed", [False, True])
@pytest.mark.parametrize("co2_gwp", [0., 1.])
def test_calc_ghg_preserves_partial_nan_and_zero_gwp_semantics(sparse_backed, co2_gwp):
    import numpy as np

    db = _build_ghg_database()
    fc = db.E.copy()
    fc.loc["CO2 - combustion - air", fc.columns[0]] = np.nan
    fc.attrs["mario_partial"] = {"undefined_nodes": [fc.columns[0]]}
    if sparse_backed:
        fc = fc.astype(pd.SparseDtype(float, 0))
    db.set_block("f", fc)
    before = fc.copy()
    db.calc_ghg(gwp={"CO2 - combustion - air": co2_gwp, "CH4 - combustion - air": 10.})
    assert db.f.attrs == before.attrs
    if co2_gwp:
        assert pd.isna(db.f.loc["GHG", fc.columns[0]])
    else:
        assert db.f.loc["GHG", fc.columns[0]] == 30.
    pdt.assert_frame_equal(db.f.loc[before.index], before)


def test_calc_ghg_invalidates_custom_totals_transitively_but_preserves_economic_results():
    from mario.compute import sum_operator

    db = _build_ghg_database()
    db.register_operator(sum_operator(name="satellite_total", source="E", over="rows"))
    db.register_operator(sum_operator(name="grand_total", source="satellite_total"))
    db.register_operator(sum_operator(name="economic_total", source="Y"))
    db.resolve_many(["satellite_total", "grand_total", "economic_total"])
    independent = db.get_block("economic_total")
    db.calc_ghg(gwp={"CO2 - combustion - air": 1.})
    assert not db.has_matrix("satellite_total") and not db.has_matrix("grand_total")
    assert db.get_block("economic_total") is independent
    result = db.resolve("satellite_total")
    pdt.assert_series_equal(result.iloc[0], db.E.sum(axis=0), check_names=False)


@pytest.mark.parametrize("failure", ["missing_account", "bad_block", "duplicate_label", "bad_factor", "mixed_units"])
def test_calc_ghg_validation_is_atomic_across_scenarios(failure):
    import numpy as np
    from copy import deepcopy

    db = _build_ghg_database()
    db.clone_scenario("baseline", "policy")
    gwp = {"CO2 - combustion - air": 1., "CH4 - combustion - air": 10.}
    if failure == "missing_account":
        db.matrices["policy"]["EY"] = db.get_block("EY", scenario="policy").drop("CH4 - combustion - air")
    elif failure == "bad_block":
        db.matrices["policy"]["EY"] = np.zeros_like(db.EY)
    elif failure == "duplicate_label":
        db.matrices["policy"]["EY"] = pd.concat([db.EY, db.EY.iloc[[0]].rename(index={db.EY.index[0]: "GHG"})])
    elif failure == "bad_factor":
        gwp["CH4 - combustion - air"] = float("nan")
    else:
        db.units["Satellite account"].loc["CH4 - combustion - air", "unit"] = "tonnes"
    before = {s: dict(blocks) for s, blocks in db.matrices.items()}
    indexes, units, history = deepcopy(db._indeces), deepcopy(db.units), list(db.meta._history)
    with pytest.raises(ValueError):
        db.calc_ghg(gwp=gwp)
    assert db._indeces == indexes
    assert db.meta._history == history
    for name in units:
        pdt.assert_frame_equal(db.units[name], units[name])
    for scenario, blocks in before.items():
        assert blocks.keys() == db.matrices[scenario].keys()
        assert all(db.get_block(name, scenario=scenario) is frame for name, frame in blocks.items())


def test_calc_ghg_prefix_profile_weights_all_matching_subsources_and_allows_zero_columns():
    from mario.ops.ghg import GHG_PROFILES, register_ghg_profile

    db = _build_ghg_database()
    db.set_block("EY", db.EY.iloc[:, :0])
    register_ghg_profile("test_prefix", match="fixture", gwp={"CO2": 1., "CH4": 10.}, match_mode="prefix")
    try:
        db.calc_ghg(profile="test_prefix")
    finally:
        GHG_PROFILES.pop("test_prefix")
    assert db.E.loc["GHG AR6 GWP-100"].tolist() == pytest.approx([31., 42.])
    assert db.EY.shape == (5, 0)


@pytest.mark.parametrize("profile", [None, "bonsai"])
@pytest.mark.parametrize("report,methane_fossil,methane_biogenic,nitrous_oxide", [
    ("AR6", 29.8, 27.0, 273),
    ("AR5", 30, 28, 265),
    ("AR4", 25, 25, 298),
])
def test_bonsai_profile_uses_n2o_and_distinct_methane_factors_without_biogenic_co2(
    tmp_path, monkeypatch, bonsai_without_umfpack,
    profile, report, methane_fossil, methane_biogenic, nitrous_oxide,
):
    import mario
    from mario.compute.helpers import dense_values
    from tests.parsers.test_bonsai_parser import _bundle

    path = _bundle(tmp_path / "Balanced")
    gases = [
        ("fossil-co2", "Carbon dioxide, fossil", "Air", 2., 1.),
        ("biogenic-co2", "Carbon dioxide, non-fossil", "Air", 1000., 500.),
        ("fossil-ch4", "Methane, fossil", "Air", 3., 2.),
        ("biogenic-ch4", "Methane, non-fossil", "Air", 5., 3.),
        ("n2o", "Dinitrogen monoxide", "Air", 7., 4.),
        ("nox", "Nitrogen oxides", "Air", 10000., 20000.),
        ("co2-uptake", "Carbon dioxide, in air", "", 1000000., 2000000.),
        ("fossil-co2", "Carbon dioxide, fossil", "Water", 999999., 888888.),
    ]
    if report == "AR6":
        gases.append(("Accelerated CO2, Air", "Accelerated CO2, Air", "Air", 11., 13.))
    rows = [
        (substance, region, activity, compartment, "tonnes", value, name)
        for substance, name, compartment, emission, direct in gases
        for region, activity, value in [("AT", "A_FARM", emission), ("DE", "consumer", direct)]
    ]
    pd.DataFrame(rows, columns=[
        "Exio substance", "Exio country code", "Exio act code", "Exio compartment",
        "unit", "Value", "substance_name",
    ]).to_csv(path / "all_elementary_flows_AB_and_BB.csv", index=False)
    db = mario.parse_bonsai(path, name="User-selected name")
    before = dict(db.matrices["baseline"])

    def forbidden(*args, **kwargs):
        pytest.fail("The built-in BONSAI profile must not calculate missing economic blocks")

    monkeypatch.setattr("mario.compute.resolver.Resolver.resolve", forbidden)
    db.calc_ghg(profile=profile, ipcc_report=report)

    label = f"GHG {report} GWP-100"
    ea = dense_values(db.get_block("Ea").loc[label])
    ey = dense_values(db.get_block("EY").loc[label])
    accelerated_factor = 0.00772 if report == "AR6" else 0
    assert ea.sum() == pytest.approx(2 + 3 * methane_fossil + 5 * methane_biogenic + 7 * nitrous_oxide + 11 * accelerated_factor)
    assert ey.sum() == pytest.approx(1 + 2 * methane_fossil + 3 * methane_biogenic + 4 * nitrous_oxide + 13 * accelerated_factor)
    assert not dense_values(db.get_block("Ec").loc[label]).any()
    assert db.units["Satellite account"].loc[label, "unit"] == "tonnes"
    assert "Carbon dioxide, non-fossil | Air" in db.get_index("Satellite account")
    for name, frame in before.items():
        if name not in ("Ea", "Ec", "EY"):
            assert db.get_block(name) is frame
    assert set(db.matrices["baseline"]) == set(before)


@pytest.mark.parametrize("legacy", [False, True])
def test_bonsai_profile_accepts_identity_suffixes_and_older_full_labels(legacy):
    db = _build_ghg_database()
    labels = {
        "CO2 - combustion - air": "Carbon dioxide, fossil | Air",
        "CH4 - combustion - air": "Methane, non-fossil | Air",
        "N2O - combustion - air": "Dinitrogen monoxide | Air",
    }
    labels = {key: value + (" | kg | native-id" if legacy else " | native-id") for key, value in labels.items()}
    for name, matrix in list(db.matrices["baseline"].items()):
        if isinstance(matrix, pd.DataFrame):
            db.matrices["baseline"][name] = matrix.rename(index=labels)
    db.units["Satellite account"] = db.units["Satellite account"].rename(index=labels)
    db._indeces["k"]["main"] = [labels.get(label, label) for label in db.get_index("Satellite account")]
    db.meta.source = "BONSAI"

    db.calc_ghg()

    expected = db.E.loc[labels["CO2 - combustion - air"]] + 27 * db.E.loc[labels["CH4 - combustion - air"]] + 273 * db.E.loc[labels["N2O - combustion - air"]]
    pdt.assert_series_equal(db.E.loc["GHG AR6 GWP-100"], expected, check_names=False)


@pytest.mark.parametrize("sparse_backed", [False, True])
@pytest.mark.parametrize("suffix", ["", " | native-id", " | kg | native-id"])
def test_bonsai_default_characterizes_accelerated_co2_in_flows_and_cached_multipliers(
    sparse_backed, suffix,
):
    from mario.compute.helpers import dense_values
    from mario.compute.types import ComputeOptions

    db = _build_ghg_database()
    db.calc_all(["f", "F"], compute_options=ComputeOptions(backend_override="sparse_direct"))
    accelerated = "Accelerated CO2, Air | Air" + suffix
    labels = {
        "CO2 - combustion - air": "Carbon dioxide, fossil | Air",
        "CH4 - combustion - air": "Methane, fossil | Air",
        "N2O - combustion - air": "Dinitrogen monoxide | Air",
        "Employment": accelerated,
    }
    db.meta.source = "BONSAI"
    db.units["Satellite account"].loc["Employment", "unit"] = "kg"
    db.units["Satellite account"] = db.units["Satellite account"].rename(index=labels)
    db._indeces["k"]["main"] = [labels[x] for x in db.get_index("Satellite account")]
    for name, frame in list(db.matrices["baseline"].items()):
        frame = frame.rename(index=labels)
        if sparse_backed:
            frame = frame.astype(pd.SparseDtype(float, 0))
        db.set_block(name, frame)
    before = dict(db.matrices["baseline"])
    db.calc_ghg()
    for name in ["E", "EY", "e", "f", "F"]:
        original = before[name]
        expected = (
            original.loc[labels["CO2 - combustion - air"]]
            + 29.8 * original.loc[labels["CH4 - combustion - air"]]
            + 273 * original.loc[labels["N2O - combustion - air"]]
            + 0.00772 * original.loc[accelerated]
        )
        assert dense_values(db.get_block(name).loc["GHG AR6 GWP-100"]) == pytest.approx(dense_values(expected))
        pdt.assert_frame_equal(db.get_block(name).loc[original.index], original)


@pytest.mark.parametrize("report", ["AR4", "AR5"])
def test_bonsai_accelerated_co2_factor_is_not_reused_for_other_reports(report):
    db = _build_ghg_database()
    label = "Accelerated CO2, Air | Air"
    for name, frame in list(db.matrices["baseline"].items()):
        db.set_block(name, frame.rename(index={"Employment": label}))
    db._indeces["k"]["main"][-1] = label
    db.units["Satellite account"] = db.units["Satellite account"].rename(index={"Employment": label})
    db.units["Satellite account"].loc[label, "unit"] = "kg"
    before = dict(db.matrices["baseline"])
    with pytest.raises(ValueError, match="not available for 'Accelerated CO2"):
        db.calc_ghg(profile="bonsai", ipcc_report=report)
    assert all(db.get_block(name) is frame for name, frame in before.items())
    assert f"GHG {report} GWP-100" not in db.get_index("Satellite account")
