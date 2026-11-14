"""Native import blocks preserve the open-economy accounting identities."""

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from tests.ops.test_semantic_import_accounts import iot, dense
from tests.ops.test_sut_region_subset import database as sut


@pytest.mark.parametrize("by", [None, "sector"])
@pytest.mark.parametrize("origins", ["aggregate", "by_region"])
def test_iot_native_imports(iot, by, origins):
    combined = iot.to_single_region("IT", imports_by=by, trade_mode=origins, inplace=False)
    native = combined.to_import_representation("separate", inplace=False)
    assert native.configuration.import_representation == "separate"
    assert "imports" not in native.factors
    assert native.regions == ["IT"]
    assert native.IMP.index.equals(native.IMP_Y.index)
    np.testing.assert_allclose(dense(native.V).sum(axis=0) + dense(native.IMP).sum(axis=0), dense(combined.V).sum(axis=0))
    for name in ("p", "X", "E", "EY", "f"):
        pd.testing.assert_frame_equal(dense(native.query(name)), dense(combined.query(name)))
    np.testing.assert_allclose(dense(native.imp).to_numpy() * native.X.to_numpy().ravel(), dense(native.IMP))
    restored = native.to_import_representation("factor-accounts", inplace=False)
    for name in ("V", "VY", "Y", "Z", "p"):
        pd.testing.assert_frame_equal(dense(restored.query(name)), dense(combined.query(name)))
    native.reset_to_coefficients("baseline")
    native.reset_to_flows("baseline")
    pd.testing.assert_frame_equal(dense(native.IMP), dense(restored.V.loc[restored.V.index.get_level_values(-1) == "imports"]).set_axis(native.IMP.index))


@pytest.mark.parametrize("by", [None, "commodity", "activity"])
@pytest.mark.parametrize("origins", ["aggregate", "by_region"])
def test_sut_native_imports(sut, by, origins):
    combined = sut.to_single_region("IT", imports_by=by, trade_mode=origins, inplace=False)
    native = sut.to_single_region("IT", imports_by=by, trade_mode=origins, import_representation="separate", inplace=False)
    assert native.IMP_a.index.equals(native.IMP_c.index)
    assert native.IMP_a.index.equals(native.IMP_Y.index)
    for factor, imported in (("Va", "IMP_a"), ("Vc", "IMP_c"), ("VY", "IMP_Y")):
        np.testing.assert_allclose(dense(native.query(factor)).sum(axis=0) + dense(native.query(imported)).sum(axis=0), dense(combined.query(factor)).sum(axis=0))
    for name in ("pa", "pc", "f", "X", "Ea", "Ec", "EY"):
        pd.testing.assert_frame_equal(dense(native.query(name)), dense(combined.query(name)))
    assert native.imp.shape == native.IMP.shape
    for suffix, output in (("a", "Xa"), ("c", "Xc")):
        np.testing.assert_allclose(dense(native.query(f"imp_{suffix}")).to_numpy() * native.query(output).to_numpy().ravel(), dense(native.query(f"IMP_{suffix}")))
    native.clone_scenario("baseline", "copy")
    native.reset_to_coefficients("copy")
    native.reset_to_flows("copy")
    restored = native.to_import_representation("factor-accounts", inplace=False)
    for name in ("Va", "Vc", "VY", "p"):
        pd.testing.assert_frame_equal(dense(restored.query(name)), dense(combined.query(name)))
    assert native.configuration.import_representation == "separate"


def test_conversion_errors_are_atomic(iot):
    original = {name: frame.copy() for name, frame in iot.matrices["baseline"].items()}
    with pytest.raises(WrongInput, match="single-region"):
        iot.to_import_representation("separate")
    for name, frame in original.items():
        pd.testing.assert_frame_equal(iot.get_block(name), frame)


@pytest.mark.parametrize("table,by", [("IOT", "sector"), ("SUT", "commodity"), ("IOT", None), ("SUT", None)])
@pytest.mark.parametrize("format,flat", [("parquet", False), ("parquet", True), ("txt", False), ("txt", True), ("excel", False)])
@pytest.mark.parametrize("mode", ["flows", "coefficients"])
def test_native_roundtrip(tmp_path, table, by, format, flat, mode):
    source = mario.load_test(table)
    db = source.to_single_region(
        source.regions[0], imports_by=by, trade_mode="by_region" if by else "aggregate",
        import_representation="separate", inplace=False,
    )
    options = {"flows": mode == "flows", "coefficients": mode == "coefficients"}
    if format == "excel":
        path = tmp_path / "table.xlsx"
        db.to_excel(path=path, **options)
        loaded = mario.parse_from_excel(str(path), table=table, mode=mode, data_sheet=mode)
    else:
        getattr(db, f"to_{format}")(path=tmp_path, flat=flat, **options)
        loaded = getattr(mario, f"parse_from_{format}")(str(tmp_path), table=table, mode=mode, flat=flat)
    assert loaded.configuration == db.configuration
    for name in (("IMP", "IMP_Y", "V", "p") if table == "IOT" else ("IMP_a", "IMP_c", "IMP_Y", "Va", "Vc", "p")):
        expected, actual = dense(db.query(name)), dense(loaded.query(name))
        actual = actual.reindex(index=expected.index, columns=expected.columns)
        np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-10)


@pytest.mark.parametrize("by", [None, "sector"])
def test_native_aggregation_and_balances(iot, by):
    native = iot.to_single_region("IT", imports_by=by, trade_mode="by_region", import_representation="separate", inplace=False)
    combined = native.to_import_representation("factor-accounts", inplace=False)
    mapping = {"Sector": pd.DataFrame({"Aggregation": "energy"}, index=["coal", "wind"])}
    for db in (native, combined):
        assert db.is_balanced("flows", margin=1e-8)
        assert db.is_balanced("coefficients", margin=1e-8)
        db.aggregate(mapping, levels=["Sector"], zero_output_epsilon=None)
    restored = native.to_import_representation("factor-accounts", inplace=False)
    for name in ("V", "VY", "p"):
        pd.testing.assert_frame_equal(dense(restored.query(name)), dense(combined.query(name)))
    if by:
        assert set(native.IMP.index.get_level_values("Sector")) == {"energy"}


@pytest.mark.parametrize("by", ["commodity", "activity"])
def test_sut_native_aggregation(sut, by):
    native = sut.to_single_region("IT", imports_by=by, trade_mode="by_region", import_representation="separate", inplace=False)
    combined = native.to_import_representation("factor-accounts", inplace=False)
    classification = by.title()
    items = list(dict.fromkeys(sut.get_index(classification, flat=True)))
    mapping = {classification: pd.DataFrame({"Aggregation": "combined"}, index=items)}
    for db in (native, combined):
        db.aggregate(mapping, levels=[classification], zero_output_epsilon=None)
    restored = native.to_import_representation("factor-accounts", inplace=False)
    for name in ("Va", "Vc", "VY", "pa", "pc"):
        actual, expected = dense(restored.query(name)), dense(combined.query(name))
        np.testing.assert_allclose(actual.reindex(index=expected.index, columns=expected.columns), expected)
    assert set(native.IMP_a.index.get_level_values(classification)) == {"combined"}


@pytest.mark.parametrize("method", ["A", "B", "C", "D"])
@pytest.mark.parametrize("by", ["commodity", "activity"])
def test_sut_to_iot_preserves_native_imports(method, by):
    source = mario.load_test("SUT")
    native = source.to_single_region(source.regions[0], imports_by=by, import_representation="separate", inplace=False)
    combined = native.to_import_representation("factor-accounts", inplace=False)
    expected = combined.to_iot(method, inplace=False)
    native.to_iot(method)
    assert native.table_type == "IOT"
    assert native.configuration.import_representation == "separate"
    for name in ("Z", "Y", "p"):
        pd.testing.assert_frame_equal(dense(native.query(name)), dense(expected.query(name)))
    restored = native.to_import_representation("factor-accounts", inplace=False)
    pd.testing.assert_frame_equal(dense(restored.V), dense(expected.V))


def test_configuration_tracks_scenario_trade_representation():
    db = mario.load_test("SUT")
    assert db.configuration.trade_representation == "isard"
    db.clone_scenario("baseline", "cm")
    db.to_chenery_moses(scenarios=["cm"])
    assert db.configuration.trade_representation == "isard"
    assert db.get_configuration("cm").trade_representation == "chenery-moses"
    db.clone_scenario("cm", "copy")
    db.rename_scenario("copy", "renamed")
    assert db.get_configuration("renamed").trade_representation == "chenery-moses"


@pytest.mark.parametrize("table,by", [("IOT", None), ("IOT", "sector"), ("SUT", "commodity")])
def test_native_display_and_scenario_copy(table, by):
    source = mario.load_test(table)
    native = source.to_single_region(source.regions[0], imports_by=by, import_representation="separate", inplace=False)
    original_axes = {name: (frame.index.copy(), frame.columns.copy()) for name, frame in native.matrices["baseline"].items()}
    view = native.DataFrame()
    imported = view.index.get_level_values("Import account").notna()
    np.testing.assert_allclose(view.iloc[imported].sum(axis=1).sum(), native.IMP.to_numpy().sum() + native.IMP_Y.to_numpy().sum())
    for name, (rows, columns) in original_axes.items():
        assert native.get_block(name).index.equals(rows)
        assert native.get_block(name).columns.equals(columns)
    native.clone_scenario("baseline", "policy")
    copied = native.build_new_instance("policy")
    assert copied.configuration == native.configuration
    pd.testing.assert_frame_equal(copied.IMP, native.IMP)


def test_native_product_technology_and_internal_state_roundtrip(tmp_path):
    source = mario.load_test("SUT", tech_assumption="PT")
    db = source.to_single_region(source.regions[0], imports_by="commodity", import_representation="separate", inplace=False)
    db.to_parquet(path=tmp_path, coefficients=True, flows=False, flat=True)
    state = mario.parse_from_parquet(str(tmp_path), table="SUT", mode="coefficients", flat=True, model="ModelState")
    from mario.parsers.api import build_database_from_state
    loaded = build_database_from_state(state)
    assert loaded.configuration == db.configuration
    pd.testing.assert_frame_equal(loaded.p, db.p)


def test_native_import_coefficient_updates(iot):
    db = iot.to_single_region("IT", imports_by="sector", import_representation="separate", inplace=False)
    original = db.imp.copy()
    baseline_price = db.p.copy()
    db.clone_scenario("baseline", "policy")
    db.reset_to_coefficients("policy")
    db.update_scenarios("policy", imp=original * 2)
    np.testing.assert_allclose(db.query("IMP", scenarios="policy"), db.IMP * 2)
    assert (db.query("p", scenarios="policy").to_numpy() > baseline_price.to_numpy()).all()
    pd.testing.assert_frame_equal(db.p, baseline_price)


@pytest.mark.parametrize("table,by", [("IOT", "sector"), ("SUT", "commodity"), ("SUT", "activity")])
@pytest.mark.parametrize("origins", ["aggregate", "by_region"])
def test_older_declared_import_layouts_keep_their_detail(table, by, origins):
    source = mario.load_test(table)
    old = source.to_single_region(source.regions[0], imports_by=by, trade_mode=origins, inplace=False)
    old.meta.model_configuration = {}
    native = old.to_import_representation("separate", inplace=False)
    assert native.configuration.imports_by == by
    assert native.configuration.import_origins == origins
    restored = native.to_import_representation("factor-accounts", inplace=False)
    for name in ("V", "VY"):
        pd.testing.assert_frame_equal(restored.query(name), old.query(name))


@pytest.mark.parametrize("table", ["IOT", "SUT"])
@pytest.mark.parametrize("format", ["txt", "parquet"])
def test_native_flat_per_matrix_bundle(tmp_path, table, format):
    source = mario.load_test(table)
    db = source.to_single_region(source.regions[0], import_representation="separate", inplace=False)
    getattr(db, f"to_{format}")(path=tmp_path, flat=True, separate_files=True)
    (tmp_path / "flows" / f"data.{format}").unlink()
    loaded = getattr(mario, f"parse_from_{format}")(str(tmp_path), table=table, mode="flows", flat=True)
    assert loaded.configuration == db.configuration
    np.testing.assert_allclose(loaded.IMP_Y.reindex(index=db.IMP_Y.index, columns=db.IMP_Y.columns), db.IMP_Y)


@pytest.mark.parametrize("table,by", [("IOT", "sector"), ("SUT", "commodity")])
def test_coefficient_only_native_export_and_compute_methods(tmp_path, table, by):
    from mario.compute import resolve
    from mario.compute.types import ResolutionContext

    source = mario.load_test(table)
    db = source.to_single_region(source.regions[0], imports_by=by, import_representation="separate", inplace=False)
    targets = ("im", "p") if table == "IOT" else ("im_a", "im_c", "pa", "pc")
    for name in targets:
        inverse = resolve(name, db.copy(), context=ResolutionContext(compute_method="inverse"))
        solved = resolve(name, db.copy(), context=ResolutionContext(compute_method="solve", linear_solver="scipy"))
        np.testing.assert_allclose(solved, inverse)
    db.reset_to_coefficients("baseline")
    db.to_parquet(path=tmp_path, flows=False, coefficients=True)
    loaded = mario.parse_from_parquet(str(tmp_path), table=table, mode="coefficients")
    loaded.reset_to_coefficients("baseline")
    loaded.to_excel(path=tmp_path / "coefficients.xlsx", flows=False, coefficients=True)
    assert loaded.configuration == db.configuration


@pytest.mark.parametrize("method", ["B", "D"])
def test_sut_conversion_preserves_original_factor_classifiers(method):
    from mario.ops.import_accounts import register_factor_layout

    source = mario.load_test("SUT")
    axis = pd.MultiIndex.from_tuples(
        [(source.regions[0], source.get_index("Activity", flat=True)[0], factor)
         for factor in source.factors],
        names=["Region", "Activity", "Factor of production"],
    )
    for name in ("Va", "Vc", "VY"):
        source.matrices["baseline"][name].index = axis
    register_factor_layout(source, axis)
    native = source.to_single_region(source.regions[0], imports_by="commodity", import_representation="separate", inplace=False)
    expected = native.to_import_representation("factor-accounts", inplace=False).to_iot(method, inplace=False)
    converted = native.to_iot(method, inplace=False)
    restored = converted.to_import_representation("factor-accounts", inplace=False)
    pd.testing.assert_frame_equal(restored.V, expected.V)
