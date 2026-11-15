"""Exercise CVXLab's real workbook generation through the public MARIO API."""

from copy import deepcopy
from pathlib import Path
import sqlite3

import numpy as np
from openpyxl import load_workbook
from openpyxl.comments import Comment
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from mario.ops import cvxlab_export


pytest.importorskip("cvxlab")


SUT_AXES = {
    "S": ["Region_from", "Activity_from", "Region_to", "Commodity_to"],
    "U": ["Region_from", "Commodity_from", "Region_to", "Activity_to"],
    "Yc": ["Region_from", "Commodity_from", "Region_to", "Consumption category_to"],
    "Va": ["Factor of production_from", "Region_to", "Activity_to"],
    "VY": ["Factor of production_from", "Region_to", "Consumption category_to"],
    "Ea": ["Satellite account_from", "Region_to", "Activity_to"],
    "EY": ["Satellite account_from", "Region_to", "Consumption category_to"],
    "IMP_a": ["Commodity_from", "Region_to", "Activity_to"],
    "IMP_c": ["Commodity_from", "Region_to", "Commodity_to"],
    "IMP_Y": ["Commodity_from", "Region_to", "Consumption category_to"],
}


def make_settings(path, axes=SUT_AXES, *, scenarios=False, extra=True, copies=True, attributes=False):
    """Create a small executable CVXLab model with one input per MARIO matrix."""
    sources = list(dict.fromkeys(field for fields in axes.values() for field in fields))
    if scenarios:
        sources.append("Scenario")
    set_map = {source: source.replace(" ", "_").lower() for source in sources}
    sets = []
    for source, target in set_map.items():
        origin = source.removesuffix("_to") + "_from"
        sets.append({
            "set_key": target,
            "description": source,
            "copy_from": set_map.get(origin) if copies and source.endswith("_to") else None,
            "split_problem": True if source == "Scenario" else None,
            "filters": "annotation: [selected, other]" if attributes and source.startswith("Activity_") else None,
        })
    matrix_map = {matrix: f"DATA_{matrix}" for matrix in axes}
    variables = []
    for matrix, fields in axes.items():
        row = {"table_key": matrix_map[matrix], "type": "exogenous",
               "coordinates": ", ".join([set_map[field] for field in fields] + (["scenario"] if scenarios else [])),
               "variables_info": f"parameter_{matrix}"}
        row[set_map[fields[0]]] = "dim: rows"
        if len(fields) > 1:
            row[set_map[fields[-1]]] = "dim: cols"
        variables.append(row)
    first = next(iter(set_map.values()))
    variables.append({"table_key": "OUTPUT", "type": "endogenous",
                      "coordinates": first + (", scenario" if scenarios else ""),
                      "variables_info": "decision", first: "dim: rows"})
    if extra:
        sets.append({"set_key": "manual", "description": "Additional user data"})
        variables.append({"table_key": "EXTRA", "type": "exogenous",
                          "coordinates": "manual" + (", scenario" if scenarios else ""),
                          "variables_info": "manual_parameter", "manual": "dim: rows"})
    problem = pd.DataFrame([{"objective": "Minimize(sum(decision))", "expressions": "decision >= 0",
                             "description": "Workbook transfer example"}])
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(sets).to_excel(writer, sheet_name="structure_sets", index=False)
        pd.DataFrame(variables).to_excel(writer, sheet_name="structure_variables", index=False)
        problem.to_excel(writer, sheet_name="problem", index=False)
    return {"sets": set_map, "matrices": matrix_map}


@pytest.fixture
def source():
    db = mario.load_test("SUT")
    return db.to_single_region(db.regions[0], imports_by="commodity", import_representation="separate", inplace=False)


def assert_matrix_values(path, db, matrix, fields, mapping, *, scenario="baseline"):
    table = pd.read_excel(path, sheet_name=mapping["matrices"][matrix], dtype=object)
    if "scenario_Name" in table:
        table = table.loc[table["scenario_Name"] == scenario]
    frame = db.query(matrix, scenarios=scenario)
    row_axis = frame.index.tolist()
    col_axis = frame.columns.tolist()
    if not isinstance(frame.index, pd.MultiIndex):
        row_axis = [(label,) for label in row_axis]
    if not isinstance(frame.columns, pd.MultiIndex):
        col_axis = [(label,) for label in col_axis]
    observed = table.set_index([mapping["sets"][field] + "_Name" for field in fields])["values"]
    values = frame.to_numpy()
    for i, row in enumerate(row_axis):
        for j, column in enumerate(col_axis):
            # Public productive axes contain a constant Level between region and item.
            labels = [str(value) for value in (*row, *column)
                      if value not in {"Activity", "Commodity", "Sector", "Consumption category"}]
            key = tuple(labels)
            assert float(observed.loc[key]) == pytest.approx(values[i, j])


def test_sut_native_inputs_and_partial_completion(tmp_path, source):
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings)
    original_mapping = deepcopy(mapping)
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert mapping == original_mapping
    assert report["pending_sets"] == ["manual"]
    assert report["unmapped_tables"] == ["EXTRA"]
    assert report["pending_matrices"] == {}
    assert report["unmatched_coordinates"] == {}
    for matrix, fields in SUT_AXES.items():
        assert report["written_cells"][mapping["matrices"][matrix]] == source.query(matrix).size
        assert_matrix_values(report["input_files"][0], source, matrix, fields, mapping)
    sets = pd.read_excel(report["sets_file"], sheet_name=None)
    assert "_set_ACTIVITY_TO" not in sets  # copy_from uses the source sheet.
    assert "imports" not in sets["_set_FACTOR_OF_PRODUCTION_FROM"].iloc[:, 0].tolist()
    assert pd.read_excel(report["input_files"][0], sheet_name="EXTRA").empty


def test_existing_attributes_values_and_extra_sheets_survive(tmp_path, source):
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings, attributes=True)
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    book = load_workbook(report["sets_file"])
    sheet = book["_set_ACTIVITY_FROM"]
    sheet.cell(2, 2, "Keep this attribute")
    sheet.cell(2, 2).comment = Comment("User note", "User")
    book["_set_MANUAL"].cell(2, 1, "manual item")
    book.create_sheet("notes").cell(1, 1, "Keep this sheet")
    book.save(report["sets_file"])
    book = load_workbook(report["input_files"][0])
    sheet = book["EXTRA"]
    sheet.append([1, "manual item", 123.0])
    book.create_sheet("user_data").cell(1, 1, "Keep input notes")
    book.save(report["input_files"][0])
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert report["pending_sets"] == []
    book = load_workbook(report["sets_file"])
    assert book["_set_ACTIVITY_FROM"].cell(2, 2).value == "Keep this attribute"
    assert book["_set_ACTIVITY_FROM"].cell(2, 2).comment.text == "User note"
    assert book["notes"].cell(1, 1).value == "Keep this sheet"
    book = load_workbook(report["input_files"][0])
    assert book["EXTRA"].cell(2, 3).value == 123.0
    assert book["user_data"].cell(1, 1).value == "Keep input notes"


def test_multiple_scenarios_and_retry_updates(tmp_path, source):
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings, scenarios=True, extra=False)
    source.clone_scenario("baseline", "policy")
    source.matrices["policy"]["U"] = source.U.copy() * 2
    source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping,
                             scenarios=["baseline", "policy"])
    assert not report["pending_sets"]
    for scenario in ("baseline", "policy"):
        assert_matrix_values(report["input_files"][0], source, "U", SUT_AXES["U"], mapping, scenario=scenario)
    source.matrices["policy"]["U"] *= 2
    source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping, scenarios="policy")
    for scenario in ("baseline", "policy"):
        assert_matrix_values(report["input_files"][0], source, "U", SUT_AXES["U"], mapping, scenario=scenario)


@pytest.mark.parametrize("detail", [None, "sector"])
def test_iot_and_total_imports(tmp_path, detail):
    db = mario.load_test("IOT")
    db.to_single_region(db.regions[0], imports_by=detail, import_representation="separate")
    imported = (["Sector_from"] if detail else [])
    axes = {
        "Z": ["Region_from", "Sector_from", "Region_to", "Sector_to"],
        "IMP": [*imported, "Region_to", "Sector_to"],
        "IMP_Y": [*imported, "Region_to", "Consumption category_to"],
    }
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings, axes, extra=False)
    report = db.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert not report["unmatched_coordinates"]
    for matrix in axes:
        assert report["written_cells"][mapping["matrices"][matrix]] == db.query(matrix).size


def test_validation_is_transactional(tmp_path, source):
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings)
    target = tmp_path / "model"
    source.to_cvxlab(model_settings=settings, path=target, mapping=mapping)
    before = {path: path.read_bytes() for path in target.rglob("*.xlsx")}
    invalid = deepcopy(mapping)
    invalid["sets"].pop("Activity_from")
    with pytest.raises(WrongInput, match="requires a set mapping"):
        source.to_cvxlab(model_settings=settings, path=target, mapping=invalid)
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("existing", [False, True])
def test_file_commit_rolls_back(tmp_path, source, monkeypatch, existing):
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings)
    target = tmp_path / "model"
    if existing:
        source.to_cvxlab(model_settings=settings, path=target, mapping=mapping)
    before = {path: path.read_bytes() for path in target.rglob("*.xlsx")}
    replace = cvxlab_export.os.replace
    failed = False

    def fail_once(source_path, destination):
        nonlocal failed
        if Path(destination) == target / "sets.xlsx" and not failed:
            failed = True
            raise OSError("Injected file update failure")
        return replace(source_path, destination)

    monkeypatch.setattr(cvxlab_export.os, "replace", fail_once)
    with pytest.raises(OSError, match="Injected"):
        source.to_cvxlab(model_settings=settings, path=target, mapping=mapping)
    assert failed
    assert {path: path.read_bytes() for path in target.rglob("*.xlsx")} == before


def test_missing_coordinate_is_reported_for_a_mapped_table(tmp_path, source):
    settings = tmp_path / "settings.xlsx"
    axes = {"S": [*SUT_AXES["S"], "Sector_to"]}
    mapping = make_settings(settings, axes, extra=False)
    mapping["sets"].pop("Sector_to")
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert report["pending_sets"] == ["sector_to"]
    assert report["pending_matrices"] == {"S": ["sector_to"]}
    book = load_workbook(report["sets_file"])
    book["_set_SECTOR_TO"].cell(2, 1, "Additional coordinate")
    book.save(report["sets_file"])
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert not report["pending_sets"]
    assert not report["pending_matrices"]
    assert report["written_cells"]["DATA_S"] == source.S.size


def test_cvxlab_loads_the_generated_workbooks(tmp_path, source, monkeypatch):
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings, extra=False)
    original = settings.read_bytes()
    def reject_prompt(*args, **kwargs):
        pytest.fail("MARIO workbook export requested interactive confirmation")

    monkeypatch.setattr("builtins.input", reject_prompt)
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert settings.read_bytes() == original
    bridge = cvxlab_export.cvxlab_bridge
    # CVXLab's constructor asks whether to erase an existing sets workbook.
    with monkeypatch.context() as context:
        context.setattr("builtins.input", lambda *args: "n")
        model = bridge._build_cvxlab_model(main_dir_path=tmp_path, model_dir_name="model",
                                          input_data_files_type="xlsx", import_custom=False)
    bridge._call_model_method(model, "load_model_coordinates", "_load_model_coordinates")
    model.core.database.create_blank_sqlite_database()
    model.core.database.load_sets_to_sqlite_database()
    model.core.database.generate_blank_sqlite_data_tables()
    model.core.database.sets_data_to_sql_data_tables()
    model.core.database.load_data_input_files_to_database(
        table_key_list=list(mapping["matrices"].values()), force_overwrite=True,
    )
    database_path = report["path"] / bridge.cl.Defaults.ConfigFiles.SQLITE_DATABASE_FILE
    with sqlite3.connect(database_path) as connection:
        actual = pd.read_sql_query('SELECT * FROM "DATA_IMP_a"', connection)
    assert len(actual) == source.IMP_a.size
    np.testing.assert_allclose(np.sort(actual["values"].to_numpy(dtype=float)),
                               np.sort(source.IMP_a.to_numpy().ravel()))


def test_bare_set_mapping_to_both_directions(tmp_path, source):
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings, extra=False)
    mapping["sets"].pop("Activity_from")
    mapping["sets"].pop("Activity_to")
    mapping["sets"]["Activity"] = ["activity_from", "activity_to"]
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert not report["pending_sets"]
    assert not report["unmatched_coordinates"]


def test_multiple_scenarios_require_a_mapping(tmp_path, source):
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings, extra=False)
    source.clone_scenario("baseline", "policy")
    with pytest.raises(WrongInput, match="Scenario"):
        source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping,
                         scenarios=["baseline", "policy"])
    assert not (tmp_path / "model").exists()


def test_concurrent_exports_are_rejected(tmp_path, source):
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings, extra=False)
    (tmp_path / ".model.mario-cvxlab-lock").mkdir()
    with pytest.raises(WrongInput, match="Another MARIO CVXLab export"):
        source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert not (tmp_path / "model").exists()


def test_optional_dependency_error(tmp_path, source, monkeypatch):
    monkeypatch.setattr(cvxlab_export.cvxlab_bridge, "cl", None)
    with pytest.raises(ImportError, match="optional 'cvxlab'"):
        source.to_cvxlab(model_settings=tmp_path / "settings.xlsx", path=tmp_path / "model", mapping={})


def test_filtered_attributes_can_be_completed_after_export(tmp_path, source):
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings, extra=False, attributes=True)
    sheets = pd.read_excel(settings, sheet_name=None)
    variables = sheets["structure_variables"]
    selection = variables["table_key"].eq("DATA_S")
    variables.loc[selection, "region_from"] = None
    variables.loc[selection, "activity_from"] = "dim: rows, filters: {annotation: selected}"
    with pd.ExcelWriter(settings) as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert report["missing_attributes"]
    assert report["written_cells"]["DATA_S"] == 0
    assert report["unmatched_coordinates"]["DATA_S"] == source.S.size
    book = load_workbook(report["sets_file"])
    sheet = book["_set_ACTIVITY_FROM"]
    for row in range(2, sheet.max_row + 1):
        sheet.cell(row, 2, "selected")
    book.save(report["sets_file"])
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert report["written_cells"]["DATA_S"] == source.S.size
    assert not report["missing_attributes"]


def test_filtered_target_rows_are_reported(tmp_path, source):
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings, extra=False, attributes=True)
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    book = load_workbook(report["sets_file"])
    sheet = book["_set_ACTIVITY_FROM"]
    for row in range(2, sheet.max_row + 1):
        sheet.cell(row, 2, "selected" if row == 2 else "other")
    book.save(report["sets_file"])
    sheets = pd.read_excel(settings, sheet_name=None)
    variables = sheets["structure_variables"]
    selection = variables["table_key"].eq("DATA_S")
    variables.loc[selection, "region_from"] = None
    variables.loc[selection, "activity_from"] = "dim: rows, filters: {annotation: selected}"
    with pd.ExcelWriter(settings) as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert report["written_cells"]["DATA_S"] == source.S.size // 2
    assert report["unmatched_coordinates"]["DATA_S"] == source.S.size // 2
    assert report["extra_input_rows"]["DATA_S"] == source.S.size // 2


def test_foreign_import_origins_use_their_target_set_domain(tmp_path):
    db = mario.load_test("SUT")
    db.to_single_region(db.regions[0], imports_by="commodity", trade_mode="by_region",
                        import_representation="separate")
    axes = {"S": SUT_AXES["S"], "IMP_a": ["Region_from", *SUT_AXES["IMP_a"]]}
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings, axes, extra=False)
    sheets = pd.read_excel(settings, sheet_name=None)
    sets = sheets["structure_sets"]
    sheets["structure_sets"] = pd.concat([sets, pd.DataFrame([{"set_key": "import_origin"}])], ignore_index=True)
    variables = sheets["structure_variables"]
    selected = variables["table_key"].eq("DATA_IMP_a")
    variables.loc[selected, "coordinates"] = variables.loc[selected, "coordinates"].str.replace("region_from", "import_origin")
    variables.loc[selected, "import_origin"] = variables.loc[selected, "region_from"]
    variables.loc[selected, "region_from"] = None
    with pd.ExcelWriter(settings) as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    mapping["sets"]["Region_from"] = ["region_from", "import_origin"]
    report = db.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert not report["missing_values"]
    assert not report["unmatched_coordinates"]
    sets = pd.read_excel(report["sets_file"], sheet_name=None)
    assert sets["_set_REGION_FROM"].iloc[:, 0].tolist() == db.regions
    assert sets["_set_IMPORT_ORIGIN"].iloc[:, 0].tolist() == list(db.IMP_a.index.get_level_values("Region").unique())


@pytest.mark.parametrize("table", ["SUT", "IOT"])
def test_multiregional_standard_models(tmp_path, table):
    db = mario.load_test(table)
    axes = {name: fields for name, fields in SUT_AXES.items() if not name.startswith("IMP")}
    if table == "IOT":
        axes = {
            "Z": ["Region_from", "Sector_from", "Region_to", "Sector_to"],
            "Y": ["Region_from", "Sector_from", "Region_to", "Consumption category_to"],
            "V": ["Factor of production_from", "Region_to", "Sector_to"],
        }
    settings = tmp_path / "settings.xlsx"
    mapping = make_settings(settings, axes, extra=False)
    report = db.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    assert not report["missing_values"]
    assert not report["unmatched_coordinates"]
    for matrix, fields in axes.items():
        assert_matrix_values(report["input_files"][0], db, matrix, fields, mapping)


def make_shared_settings(path, *, scenarios=False):
    sets = pd.DataFrame({"set_key": ["products", "accounts", "extensions"]})
    if scenarios:
        sets = pd.concat([sets, pd.DataFrame([{"set_key": "scenarios", "split_problem": True}])], ignore_index=True)
    rows = []
    for name, row_set in (("use_0", "products"), ("imports_0", "products"), ("extensions_0", "extensions")):
        rows.append({"table_key": name, "type": "exogenous",
                     "coordinates": f"{row_set}, accounts" + (", scenarios" if scenarios else ""),
                     "variables_info": f"input_{name}", row_set: "dim: rows", "accounts": "dim: cols"})
    rows.append({"table_key": "OUTPUT", "type": "endogenous",
                 "coordinates": "products" + (", scenarios" if scenarios else ""),
                 "variables_info": "decision", "products": "dim: rows"})
    with pd.ExcelWriter(path) as writer:
        sets.to_excel(writer, sheet_name="structure_sets", index=False)
        pd.DataFrame(rows).to_excel(writer, sheet_name="structure_variables", index=False)
        pd.DataFrame([{"objective": "Minimize(sum(decision))", "expressions": "decision >= 0"}]).to_excel(
            writer, sheet_name="problem", index=False,
        )
    mapping = {
        "sets": {"Commodity_from": "products", "Activity_to": "accounts",
                 "Consumption category_to": "accounts", "Factor of production_from": "extensions",
                 "Satellite account_from": "extensions"},
        "matrices": {"U": "use_0", "Yc": "use_0", "IMP_a": "imports_0", "IMP_Y": "imports_0",
                     "Va": "extensions_0", "VY": "extensions_0", "Ea": "extensions_0", "EY": "extensions_0"},
    }
    if scenarios:
        mapping["sets"]["Scenario"] = "scenarios"
    return mapping


def assert_shared_values(report, db, mapping, scenario="baseline"):
    for matrix, target in mapping["matrices"].items():
        actual = pd.read_excel(report["input_files"][0], sheet_name=target)
        if "scenarios_Name" in actual:
            actual = actual.loc[actual["scenarios_Name"].eq(scenario)]
        row_header = "extensions_Name" if target == "extensions_0" else "products_Name"
        actual = actual.set_index([row_header, "accounts_Name"])["values"]
        expected = db.query(matrix, scenarios=scenario)
        for i, row in enumerate(expected.index.get_level_values(-1)):
            for j, column in enumerate(expected.columns.get_level_values(-1)):
                assert actual.loc[(row, column)] == pytest.approx(expected.iloc[i, j])


@pytest.mark.parametrize("scenarios", [False, True])
def test_several_matrices_populate_shared_tables(tmp_path, source, scenarios):
    settings = tmp_path / "settings.xlsx"
    mapping = make_shared_settings(settings, scenarios=scenarios)
    selected = ["baseline"]
    if scenarios:
        source.clone_scenario("baseline", "policy")
        source.matrices["policy"]["Yc"] = source.Yc * 2
        selected.append("policy")
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping, scenarios=selected)
    assert not report["pending_matrices"]
    assert not report["missing_values"]
    assert not report["unmatched_coordinates"]
    for target in set(mapping["matrices"].values()):
        expected = sum(source.query(name).size for name, table in mapping["matrices"].items() if table == target)
        assert report["written_cells"][target] == expected * len(selected)
    for scenario in selected:
        assert_shared_values(report, source, mapping, scenario)
    source.matrices["baseline"]["Yc"] = source.Yc * 3
    report = source.to_cvxlab(model_settings=settings, path=tmp_path / "model", mapping=mapping)
    for scenario in selected:
        assert_shared_values(report, source, mapping, scenario)


def test_overlapping_shared_cells_leave_existing_files_intact(tmp_path, source):
    settings = tmp_path / "settings.xlsx"
    mapping = make_shared_settings(settings)
    target = tmp_path / "model"
    source.to_cvxlab(model_settings=settings, path=target, mapping=mapping)
    before = {path: path.read_bytes() for path in target.rglob("*.xlsx")}
    mapping["matrices"]["IMP_a"] = "use_0"
    with pytest.raises(WrongInput, match="use_0.*overlap"):
        source.to_cvxlab(model_settings=settings, path=target, mapping=mapping)
    assert {path: path.read_bytes() for path in target.rglob("*.xlsx")} == before
