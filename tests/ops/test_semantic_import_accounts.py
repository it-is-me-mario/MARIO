"""Sector/commodity mappings must also aggregate the import row dimensions."""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

import mario
from mario import Database


def dense(frame):
    return frame.sparse.to_dense() if all(
        isinstance(dtype, pd.SparseDtype) for dtype in frame.dtypes
    ) else frame.copy()


@pytest.fixture(params=[False, True], ids=["dense", "sparse"])
def iot(request):
    axis = pd.MultiIndex.from_product(
        [["IT", "DE", "FR"], ["Sector"], ["coal", "wind"]],
        names=["Region", "Level", "Item"],
    )
    fd = pd.MultiIndex.from_product(
        [["IT", "DE", "FR"], ["Consumption category"], ["HH", "GOV"]],
        names=axis.names,
    )
    z = np.arange(36, dtype=float).reshape(6, 6) / 10 + 1
    y = np.arange(36, dtype=float).reshape(6, 6) + 20
    residual = z.sum(axis=1) + y.sum(axis=1) - z.sum(axis=0)
    factors = ["Wages", "Capital"]
    source = {
        "Z": pd.DataFrame(z, index=axis, columns=axis),
        "Y": pd.DataFrame(y, index=axis, columns=fd),
        "V": pd.DataFrame([residual * .6, residual * .4], index=factors, columns=axis),
        "E": pd.DataFrame(np.arange(6, dtype=float)[None, :] + 1, index=["CO2"], columns=axis),
        "VY": pd.DataFrame(np.arange(12, dtype=float).reshape(2, 6) / 10, index=factors, columns=fd),
        "EY": pd.DataFrame(np.arange(6, dtype=float)[None, :] / 10, index=["CO2"], columns=fd),
    }
    db = Database(
        table="IOT", calc_all=False,
        **source,
        units={
            "Sector": pd.DataFrame({"unit": "EUR"}, index=["coal", "wind"]),
            "Factor of production": pd.DataFrame({"unit": "EUR"}, index=factors),
            "Satellite account": pd.DataFrame({"unit": "kg"}, index=["CO2"]),
        },
    )
    if request.param:
        db.matrices["baseline"] = {
            name: frame.astype(pd.SparseDtype(float, 0))
            for name, frame in db.matrices["baseline"].items()
        }
    return db


@pytest.mark.parametrize("partners", [False, True])
def test_iot_import_cells_and_empty_sector_factors(iot, partners):
    original = {name: dense(iot.query(name)) for name in ("Z", "Y", "V", "VY", "E", "EY")}
    result = iot.to_single_region(
        "IT", imports_by="sector", trade_resolution="by_region" if partners else "aggregate", inplace=False,
    )
    expected = {name: {} for name in ("V", "VY")}
    for target, source in (("V", "Z"), ("VY", "Y")):
        for supplier in original[source].index:
            if supplier[0] == "IT":
                continue
            row = (supplier[0], supplier[-1], "imports") if partners else (supplier[-1], "imports")
            for buyer in original[source].columns:
                if buyer[0] == "IT":
                    key = (row, buyer)
                    expected[target][key] = expected[target].get(key, 0) + original[source].loc[supplier, buyer]
        frame = dense(result.query(target))
        for (row, col), amount in expected[target].items():
            assert frame.loc[row, col] == pytest.approx(amount)
        for factor in ("Wages", "Capital"):
            actual = frame.xs(factor, level="Factor of production")
            assert actual.index.get_level_values("Sector").isna().all()
            expected_columns = original[target].columns[original[target].columns.get_level_values(0) == "IT"]
            np.testing.assert_allclose(actual.loc[:, expected_columns].sum(axis=0), original[target].loc[factor, expected_columns])
    assert result.factors == ["Wages", "Capital", "imports"]
    assert result.regions == ["IT"]
    if partners:
        imports = result.V.xs("imports", level="Factor of production")
        assert set(imports.index.get_level_values("Region")) == {"DE", "FR"}
    else:
        assert "Region" not in result.V.index.names
    for name in ("v", "m", "M"):
        assert result.query(name).index.equals(result.V.index)
        assert tuple(axis.id for axis in result.get_block_spec(name).row_axes) == tuple(result.V.index.names)


def aggregate_reference(frame, set_name, new_label):
    result = dense(frame)
    for side in ("index", "columns"):
        axis = getattr(result, side)
        if not isinstance(axis, pd.MultiIndex):
            continue
        values = []
        for entry in axis:
            entry = list(entry)
            if "Level" in axis.names:
                if entry[1] == set_name:
                    entry[2] = new_label
            elif set_name in axis.names:
                position = axis.names.index(set_name)
                if pd.notna(entry[position]):
                    entry[position] = new_label
            values.append(tuple(entry))
        setattr(result, side, pd.MultiIndex.from_tuples(values, names=axis.names))
    result = result.groupby(level=list(range(result.index.nlevels)), sort=False, dropna=False).sum()
    result = result.T.groupby(level=list(range(result.columns.nlevels)), sort=False, dropna=False).sum().T
    # groupby stores NaN as a level member; canonical MultiIndexes use -1
    # missing codes. Normalize the independent reference before label alignment.
    for side in ("index", "columns"):
        axis = getattr(result, side)
        if isinstance(axis, pd.MultiIndex):
            setattr(result, side, pd.MultiIndex.from_tuples(list(axis), names=axis.names))
    return result


@pytest.mark.parametrize("partners", [False, True])
def test_iot_sector_aggregation_applies_to_v_and_vy_without_factor_mapping(iot, partners):
    result = iot.to_single_region(
        "IT", trade_resolution="by_region_and_sector" if partners else "by_sector", inplace=False,
    )
    source = {name: result.query(name).copy() for name in ("Z", "Y", "V", "VY", "E", "EY")}
    result.query("m")
    result.aggregate(
        {"Sector": pd.DataFrame({"Aggregation": "electricity"}, index=["coal", "wind"])},
        levels=["Sector"], zero_output_epsilon=None,
    )
    for name, frame in source.items():
        expected = aggregate_reference(frame, "Sector", "electricity")
        actual = dense(result.query(name)).reindex(index=expected.index, columns=expected.columns)
        np.testing.assert_allclose(actual, expected)
    assert set(result.V.index.get_level_values("Sector").dropna()) == {"electricity"}
    assert result.m.index.equals(result.V.index)
    assert result.factors == ["Wages", "Capital", "imports"]
    if partners:
        assert len(result.V.xs("imports", level="Factor of production")) == 2
    else:
        assert len(result.V.xs("imports", level="Factor of production")) == 1


@pytest.mark.parametrize("table,classification", [("IOT", "sector"), ("SUT", "commodity"), ("SUT", "activity")])
@pytest.mark.parametrize("partners", [False, True])
def test_empty_classification_levels_survive_excel_and_aggregation(table, classification, partners, tmp_path):
    db = mario.load_test(table)
    db.to_single_region(
        db.regions[0], imports_by=classification,
        trade_resolution="by_region" if partners else "aggregate",
    )
    prefix = tuple(axis.id for axis in db.get_block_spec("V").row_axes[:-1])
    path = tmp_path / f"{table}-{classification}-{partners}.xlsx"
    db.to_excel(path=str(path), flows=True, coefficients=False)
    restored = mario.parse_from_excel(
        str(path), table=table, mode="flows", matrix_layouts={"V": prefix},
    )
    names = ("V", "VY") if table == "IOT" else ("Va", "Vc", "VY")
    for name in names:
        pd.testing.assert_frame_equal(dense(restored.query(name)), dense(db.query(name)), check_names=False)
    set_name = classification.title()
    items = restored.get_index(set_name)
    before = {name: restored.query(name).copy() for name in names}
    restored.aggregate(
        {set_name: pd.DataFrame({"Aggregation": "combined"}, index=items)},
        levels=[set_name], zero_output_epsilon=None,
    )
    for name in names:
        expected = aggregate_reference(before[name], set_name, "combined")
        actual = dense(restored.query(name)).reindex(index=expected.index, columns=expected.columns)
        np.testing.assert_allclose(actual, expected)


def test_iot_sparse_extraction_never_densifies_source(iot):
    if not isinstance(iot.Z.dtypes.iloc[0], pd.SparseDtype):
        pytest.skip("Sparse-path guard")
    with patch.object(pd.DataFrame, "to_numpy", side_effect=AssertionError("dense frame")):
        result = iot.to_single_region("IT", imports_by="sector", inplace=False)
    assert all(isinstance(dtype, pd.SparseDtype) for dtype in result.VY.dtypes)


def test_source_region_aggregation_does_not_add_endogenous_regions(iot):
    result = iot.to_single_region("IT", imports_by="sector", trade_resolution="by_region", inplace=False)
    before = result.VY.xs("imports", level="Factor of production").sum(axis=0)
    result.aggregate(io=None, levels=["Region"], region_aggregation="continent", zero_output_epsilon=None)
    assert result.regions == ["Europe"]
    assert set(result.V.index.get_level_values("Region")) == {"Europe"}
    assert result.meta.region_aggregation_map == {"Europe": ["IT"]}
    np.testing.assert_allclose(result.VY.xs("imports", level="Factor of production").sum(axis=0), before)


@pytest.mark.parametrize("imports_by", ["commodity", "activity"])
def test_native_sut_coefficients_and_multipliers_keep_the_import_layout(imports_by):
    db = mario.load_test("SUT")
    db.to_single_region(db.regions[0], imports_by=imports_by)
    axis = db.query("Va").index
    for name in ("va", "vc", "ma", "mc", "Ma", "Mc"):
        assert db.query(name).index.equals(axis)
        assert tuple(item.id for item in db.get_block_spec(name).row_axes) == tuple(axis.names)


@pytest.mark.parametrize("regional", [False, True])
def test_existing_activity_factor_layout_can_add_commodity_imports(regional, tmp_path):
    from mario.ops.import_accounts import register_factor_layout

    db = mario.load_test("SUT")
    region, activity = db.regions[0], db.get_index("Activity")[0]
    prefix = ["Region", "Activity"] if regional else ["Activity"]
    for name in ("Va", "Vc", "VY"):
        frame = db.query(name)
        values = [(region, activity, factor) if regional else (activity, factor) for factor in frame.index]
        frame.index = pd.MultiIndex.from_tuples(values, names=prefix + ["Factor of production"])
        db.matrices["baseline"][name] = frame
    register_factor_layout(db, db.query("Va").index)
    db.to_single_region(region, imports_by="commodity", trade_resolution="aggregate")
    expected_names = prefix + ["Commodity", "Factor of production"]
    assert list(db.query("Va").index.names) == expected_names
    assert db.query("Va").index.get_level_values("Commodity")[
        db.query("Va").index.get_level_values("Factor of production") != "imports"
    ].isna().all()
    path = tmp_path / "combined-sut-layout.xlsx"
    db.to_excel(path=str(path), flows=True, coefficients=False)
    restored = mario.parse_from_excel(
        str(path), table="SUT", mode="flows", matrix_layouts={"V": tuple(expected_names[:-1])},
    )
    for name in ("Va", "Vc", "VY"):
        pd.testing.assert_frame_equal(restored.query(name), db.query(name), check_names=False)


@pytest.mark.parametrize("table,classification", [("IOT", "sector"), ("SUT", "commodity"), ("SUT", "activity")])
@pytest.mark.parametrize("partners", [False, True])
def test_dataframe_view_preserves_empty_dimensions_values_and_live_matrices(table, classification, partners):
    db = mario.load_test(table)
    db.to_single_region(db.regions[0], imports_by=classification,
                        trade_resolution="by_region" if partners else "aggregate")
    names = ["Z", "Y", "V", "E", "EY", "VY"]
    original = {name: db.query(name).copy() for name in names}
    # Direct final-demand account ordering need not match productive accounts.
    for name in ("VY", "EY"):
        db.matrices["baseline"][name] = db.matrices["baseline"][name].iloc[::-1, ::-1]
    frame = db.DataFrame()
    assert classification.title() in frame.index.names
    ordinary = frame.index.get_level_values("Factor of production").isin(["Taxes", "Wages", "Capital"])
    assert frame.index.get_level_values(classification.title())[ordinary].isna().all()
    assert frame.shape == (sum(len(original[name]) for name in ("Z", "V", "E")),
                           original["Z"].shape[1] + original["Y"].shape[1])
    assert frame.to_numpy().sum() == pytest.approx(sum(dense(value).to_numpy().sum() for value in original.values()))
    for row in original["VY"].index:
        fields = dict(zip(original["VY"].index.names, row))
        target_row = tuple(fields.get(name) for name in frame.index.names)
        for col in original["VY"].columns:
            fields = {"Region": col[0], "Consumption category": col[-1]}
            target_col = tuple(fields.get(name) for name in frame.columns.names)
            assert frame.loc[target_row, target_col] == pytest.approx(original["VY"].loc[row, col])
    for name, value in original.items():
        expected = value.iloc[::-1, ::-1] if name in ("VY", "EY") else value
        pd.testing.assert_frame_equal(db.query(name), expected)


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_legacy_dataframe_view_does_not_change_model_indexes(table):
    db = mario.load_test(table)
    original = {name: db.query(name).copy() for name in ("Z", "Y", "V", "E", "EY", "VY")}
    db.DataFrame()
    for name, frame in original.items():
        pd.testing.assert_frame_equal(db.query(name), frame)
