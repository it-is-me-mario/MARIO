"""User workflows on transformed supply-use and input-output tables."""

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import NotImplementable
from mario.ops.workbook_specs import SHOCK_FLAT_COLUMNS
from tests.api.test_regional_indexes import regional_database
from tests.ops.test_addsector import _configure_split_workbook
from tests.ops.test_semantic_import_accounts import dense, iot as three_region_iot


@pytest.fixture
def isard():
    """Balanced monetary SUT with secondary production and asymmetric bilateral trade."""
    db = regional_database(
        {r: ["Manufacturing", "Services"] for r in ("IT", "DE")},
        {r: ["Goods", "Services"] for r in ("IT", "DE")},
    )
    for level in ("Activity", "Commodity"):
        db.units[level].loc[:, "unit"] = "EUR"
    values = {
        "S": [[54, 6, 0, 0], [9, 51, 0, 0], [0, 0, 65, 5], [0, 0, 8, 52]],
        "U": [[10, 6, 4, 3], [3, 12, 1, 4], [8, 3, 14, 7], [4, 5, 6, 9]],
        "Yc": [[28, 12], [19, 18], [8, 33], [9, 24]],
        "Va": [[35, 34, 45, 37]],
        "Ea": [[6, 12, 21, 3]],
        "EY": [[2, 5]],
    }
    for name in ("S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "VY", "EY"):
        frame = db.query(name)
        db.set_block(
            name,
            pd.DataFrame(
                values.get(name, 0.0),
                index=frame.index,
                columns=frame.columns,
                dtype=float,
            ),
        )
    return db


@pytest.fixture(params=["isard", "chenery-moses"])
def multiregional_sut(isard, request):
    db = (
        isard.to_chenery_moses(inplace=False)
        if request.param == "chenery-moses"
        else isard
    )
    assert db.configuration.trade_representation == request.param
    return db


def test_bilateral_trade_after_commodity_aggregation(multiregional_sut):
    db = multiregional_sut
    mapping = pd.DataFrame(
        {"Aggregation": ["Products", "Products"]}, index=["Goods", "Services"]
    )
    aggregated = db.aggregate(
        {"Commodity": mapping}, levels=["Commodity"], inplace=False
    )
    # Directly from U and Yc in the source: each origin sells to domestic and foreign buyers.
    expected = pd.DataFrame(
        [[78.0, 42.0], [37.0, 93.0]], index=["IT", "DE"], columns=["IT", "DE"]
    )
    trades = aggregated.calc_trades("Products")
    pd.testing.assert_frame_equal(trades, expected, check_like=True, check_names=False)


@pytest.mark.parametrize(
    "representation,resolution,by",
    [
        ("factor-accounts", "aggregate", None),
        ("factor-accounts", "by_region", "activity"),
        ("separate", "by_region", "commodity"),
    ],
)
@pytest.mark.parametrize("file_format", ["excel", "parquet"])
def test_single_region_accounts_survive_export(
    tmp_path, multiregional_sut, representation, resolution, by, file_format
):
    db = multiregional_sut
    local = db.to_single_region(
        "IT",
        trade_resolution=resolution,
        imports_by=by,
        import_representation=representation,
        inplace=False,
    )
    if file_format == "excel":
        path = tmp_path / "national.xlsx"
        local.to_excel(path=path, flows=True, coefficients=False)
        loaded = mario.parse_from_excel(
            str(path), table="SUT", mode="flows", data_sheet="flows"
        )
    else:
        local.to_parquet(path=tmp_path, flows=True, coefficients=False)
        loaded = mario.parse_from_parquet(str(tmp_path), table="SUT", mode="flows")
    assert loaded.regions == ["IT"]
    assert loaded.configuration == local.configuration
    assert loaded.is_balanced("flows", margin=1e-9)

    # Compare both storage layouts in native import blocks.
    native = (
        loaded
        if representation == "separate"
        else loaded.to_import_representation("separate", inplace=False)
    )
    if db.is_isard():
        # German intermediate inputs to each Italian industry and final purchases by Italian HH.
        expected_a, expected_c, expected_final = [12.0, 8.0], [0.0, 0.0], 17.0
    else:
        # In Chenery-Moses, foreign deliveries enter the two Italian commodity markets in S.
        expected_a, expected_c, expected_final = [0.0, 0.0], [19.0, 18.0], 0.0
    activity_imports = native.IMP_a.sum(axis=0).xs("IT", level=0).droplevel(0)
    commodity_imports = native.IMP_c.sum(axis=0).xs("IT", level=0).droplevel(0)
    np.testing.assert_allclose(
        activity_imports.loc[["Manufacturing", "Services"]], expected_a
    )
    np.testing.assert_allclose(commodity_imports.loc[["Goods", "Services"]], expected_c)
    hh = ("IT", "Consumption category", "HH")
    assert native.IMP_Y.loc[:, hh].sum() == pytest.approx(expected_final)
    exports = (
        native.Ya.drop(columns=[hh]).sum().sum()
        + native.Yc.drop(columns=[hh]).sum().sum()
    )
    assert exports == pytest.approx(42.0)


@pytest.mark.parametrize("method", list("ABCD"))
def test_single_region_conversion_preserves_external_and_domestic_accounts(
    multiregional_sut, method
):
    sut = multiregional_sut
    local = sut.to_single_region(
        "IT",
        trade_resolution="by_region",
        imports_by="commodity",
        import_representation="separate",
        inplace=False,
    )
    if sut.is_chenerymoses() and method in ("A", "C"):
        # Supply-side exports become activity final demand when the border is drawn.
        exports = local.Ya.copy()
        assert exports.to_numpy().sum() == pytest.approx(42.0)
        with pytest.raises(NotImplementable, match="zero activity final demand"):
            local.to_iot(method)
        assert local.table_type == "SUT"
        pd.testing.assert_frame_equal(local.Ya, exports)
        return

    iot = local.to_iot(method, inplace=False)
    assert iot.regions == ["IT"]
    assert iot.configuration.import_representation == "separate"
    assert iot.is_balanced("flows", margin=1e-9)
    assert iot.IMP.to_numpy().sum() + iot.IMP_Y.to_numpy().sum() == pytest.approx(37.0)
    assert iot.V.to_numpy().sum() + iot.VY.to_numpy().sum() == pytest.approx(69.0)
    assert iot.E.to_numpy().sum() + iot.EY.to_numpy().sum() == pytest.approx(20.0)


def write_demand_shock(path, supplier, buyer, amount):
    region, level, item = supplier
    destination, _, category = buyer
    row = {
        SHOCK_FLAT_COLUMNS["region_from"]: region,
        SHOCK_FLAT_COLUMNS[level.lower() + "_from"]: item,
        SHOCK_FLAT_COLUMNS["region_to"]: destination,
        SHOCK_FLAT_COLUMNS["category_to"]: category,
        SHOCK_FLAT_COLUMNS["type"]: "Update",
        SHOCK_FLAT_COLUMNS["value"]: amount,
    }
    sheet = "Yc" if level == "Commodity" else "Y"
    pd.DataFrame([row]).to_excel(path, sheet_name=sheet, index=False)


def test_shocked_sut_scenario_becomes_product_iot(tmp_path, multiregional_sut):
    sut = multiregional_sut
    buyer = ("IT", "Consumption category", "HH")
    commodity = ("IT", "Commodity", "Goods")
    base_y = sut.Yc.copy()
    supply = sut.S
    use = sut.U.loc[supply.columns, supply.index]
    g = supply.sum(axis=1)
    q = use.sum(axis=1) + base_y.sum(axis=1)
    # Eliminate activities in the industry-technology Leontief system.
    coefficients = use.div(g, axis="columns") @ supply.div(q, axis="columns")
    change = pd.Series(0.0, index=q.index)
    change.loc[commodity] = 5.0
    expected_output = q + np.linalg.solve(
        np.eye(len(q)) - coefficients.to_numpy(), change
    )
    path = tmp_path / "commodity_demand.xlsx"
    write_demand_shock(path, commodity, buyer, base_y.at[commodity, buyer] + 5)
    sut.shock_calc(str(path), Yc=True, scenario="policy")
    # to_iot consumes the baseline. Select the policy scenario before converting it.
    transformed = sut.build_new_instance("policy").to_iot("B", inplace=False)
    sectors = pd.MultiIndex.from_tuples(
        [(region, "Sector", item) for region, _, item in q.index], names=q.index.names
    )
    expected_y = base_y.copy()
    expected_y.at[commodity, buyer] += 5
    pd.testing.assert_frame_equal(
        transformed.Y, expected_y.set_axis(sectors), check_like=True
    )
    np.testing.assert_allclose(transformed.X.loc[sectors].iloc[:, 0], expected_output)
    pd.testing.assert_frame_equal(sut.Yc, base_y)


@pytest.mark.parametrize("method", list("ABCD"))
def test_sut_to_iot_demand_shock_and_export(tmp_path, multiregional_sut, method):
    sut = multiregional_sut
    iot = sut.to_iot(method, inplace=False)
    product_table = method in ("A", "B")
    sector = "Goods" if product_table else "Manufacturing"
    output = (
        sut.U.sum(axis=1) + sut.Yc.sum(axis=1)
        if product_table
        else sut.S.sum(axis=1) + sut.Ya.sum(axis=1)
    )
    output.index = pd.MultiIndex.from_tuples(
        [(region, "Sector", item) for region, _, item in output.index],
        names=output.index.names,
    )
    baseline_y = iot.Y.copy()
    baseline_x = iot.X.copy()
    pd.testing.assert_series_equal(
        baseline_x.iloc[:, 0], output, check_names=False, check_like=True
    )
    supplier, buyer = ("DE", "Sector", sector), ("IT", "Consumption category", "HH")
    expected_y = baseline_y.copy()
    expected_y.loc[supplier, buyer] += 5.0
    labels = baseline_y.index
    z = iot.Z.loc[labels, labels].div(output.loc[labels], axis="columns")
    expected_x = np.linalg.solve(
        np.eye(len(labels)) - z.to_numpy(), expected_y.sum(axis=1)
    )

    path = tmp_path / "demand.xlsx"
    write_demand_shock(path, supplier, buyer, expected_y.loc[supplier, buyer])
    iot.shock_calc(str(path), Y=True, scenario="policy")
    pd.testing.assert_frame_equal(iot.Y, baseline_y)
    pd.testing.assert_frame_equal(iot.X, baseline_x)
    pd.testing.assert_frame_equal(
        iot.query("Y", scenarios="policy"), expected_y, check_like=True
    )
    np.testing.assert_allclose(
        iot.query("X", scenarios="policy").loc[labels].iloc[:, 0], expected_x
    )
    iot.to_parquet(path=tmp_path, scenario="policy", flows=True, coefficients=False)
    loaded = mario.parse_from_parquet(str(tmp_path), table="IOT", mode="flows")
    pd.testing.assert_frame_equal(loaded.Y, expected_y, check_like=True)
    np.testing.assert_allclose(loaded.X.loc[labels].iloc[:, 0], expected_x)


@pytest.mark.parametrize("representation", ["factor-accounts", "separate"])
def test_single_region_iot_shock_preserves_imports_by_partner(
    three_region_iot, tmp_path, representation
):
    source = three_region_iot
    # Compile the reference from the original three-region flows before extraction.
    transactions = dense(source.Z)
    demand = dense(source.Y)
    domestic = transactions.loc["IT", "IT"].to_numpy().sum()
    output = transactions.loc["IT"].to_numpy().sum() + demand.loc["IT"].to_numpy().sum()
    expected_output = output + 5 / (1 - domestic / output)
    hh = ("IT", "Consumption category", "HH")
    node = ("IT", "Sector", "Energy")
    local = source.to_single_region(
        "IT",
        trade_resolution="by_region",
        imports_by="sector",
        import_representation=representation,
        inplace=False,
    )
    mapping = pd.DataFrame(
        {"Aggregation": ["Energy", "Energy"]}, index=["coal", "wind"]
    )
    local.aggregate({"Sector": mapping}, levels=["Sector"])
    assert local.regions == ["IT"]
    assert local.Y.at[node, hh] == pytest.approx(demand.loc["IT", hh].sum())
    path = tmp_path / "demand.xlsx"
    write_demand_shock(path, node, hh, local.Y.at[node, hh] + 5)
    local.shock_calc(str(path), Y=True, scenario="policy")
    assert local.query("X", scenarios="policy").loc[node].item() == pytest.approx(
        expected_output
    )
    if representation == "separate":
        intermediate = local.query("IMP", scenarios="policy")
        final = local.query("IMP_Y", scenarios="policy")
    else:
        intermediate = local.query("V", scenarios="policy").xs(
            "imports", level="Factor of production"
        )
        final = local.query("VY", scenarios="policy").xs(
            "imports", level="Factor of production"
        )
    assert set(intermediate.index.get_level_values("Region")) == {"DE", "FR"}
    for partner in ("DE", "FR"):
        original = transactions.loc[partner, "IT"].to_numpy().sum()
        assert intermediate.xs(partner, level="Region").loc[
            :, node
        ].sum() == pytest.approx(original * expected_output / output)
        assert final.xs(partner, level="Region").loc[:, hh].sum() == pytest.approx(
            demand.loc[partner, hh].sum()
        )


def test_sut_emission_shock_preserves_native_imports(tmp_path, multiregional_sut):
    sut = multiregional_sut.to_single_region(
        "IT", imports_by="commodity", trade_resolution="by_region",
        import_representation="separate", inplace=False,
    )
    before = {name: sut.query(name).copy() for name in ("IMP_a", "IMP_c", "IMP_Y")}
    coefficient = sut.query("ea")
    indicator, buyer = coefficient.index[0], coefficient.columns[0]
    value = coefficient.at[indicator, buyer] * .5
    path = tmp_path / "emissions.xlsx"
    pd.DataFrame([{
        SHOCK_FLAT_COLUMNS["satellite_from"]: indicator,
        SHOCK_FLAT_COLUMNS["region_to"]: buyer[0],
        SHOCK_FLAT_COLUMNS["activity_to"]: buyer[-1],
        SHOCK_FLAT_COLUMNS["type"]: "Update",
        SHOCK_FLAT_COLUMNS["value"]: value,
    }]).to_excel(path, sheet_name="ea", index=False)
    sut.shock_calc(str(path), ea=True, scenario="corrected_emissions")
    assert sut.query("ea", scenarios="corrected_emissions").at[indicator, buyer] == pytest.approx(value)
    for name, expected in before.items():
        pd.testing.assert_frame_equal(sut.query(name, scenarios="corrected_emissions"), expected)
        pd.testing.assert_frame_equal(sut.query(name), expected)


def test_sut_to_iot_split_then_reaggregate(tmp_path, multiregional_sut):
    pytest.importorskip("cvxlab")
    iot = multiregional_sut.to_iot("B", inplace=False)
    child = "Specialised goods"
    path = tmp_path / "split.xlsx"
    iot.get_add_sectors_excel(items=[child], regions=["IT"], path=path)
    setup = _configure_split_workbook(iot, path, new_sector=child, quantity=2.0)
    split = iot.add_sectors(
        io=path, split=True, cvxlab_path=tmp_path, solver="CLARABEL", inplace=False
    )
    assert split.X.loc[("IT", "Sector", child)].item() == pytest.approx(2.0, abs=1e-4)
    mapping = pd.DataFrame(
        {
            "Aggregation": [
                setup["parent_sector"] if s == child else s for s in split.sectors
            ]
        },
        index=split.sectors,
    )
    restored = split.aggregate({"Sector": mapping}, levels=["Sector"], inplace=False)
    for name in ("Z", "Y", "V", "X"):
        # The split workbook permits relative deviations of 1e-5 on the restored flows.
        # The model bounds the original by (1 ± eps) times the optimized value.
        expected = iot.query(name).sort_index().sort_index(axis=1)
        actual = restored.query(name).sort_index().sort_index(axis=1)
        pd.testing.assert_index_equal(actual.index, expected.index)
        pd.testing.assert_index_equal(actual.columns, expected.columns)
        np.testing.assert_allclose(actual, expected, rtol=1e-5 / (1 - 1e-5), atol=1e-6)
