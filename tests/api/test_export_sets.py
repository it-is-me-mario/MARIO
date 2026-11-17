"""Native set exports describe the current database without changing its state."""

from copy import deepcopy

from openpyxl import load_workbook
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from tests.api.test_regional_indexes import regional_database


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_export_sets_current_members_scenarios_and_state(table, tmp_path):
    db = mario.load_test(table)
    db.to_single_region(db.regions[0], imports_by="commodity" if table == "SUT" else "sector")
    db.clone_scenario("baseline", "alternative")
    before = deepcopy(db.matrices)
    expected = db.get_index("all")

    path = db.export_sets(tmp_path / "nested" / "sets.xlsx")

    assert path == tmp_path / "nested" / "sets.xlsx"
    frames = pd.read_excel(path, sheet_name=None, keep_default_na=False)
    assert list(frames) == [*db.sets, "Scenario"]
    for name, members in expected.items():
        assert list(frames[name]) == [name]
        assert frames[name][name].tolist() == members
    assert "imports" in frames["Factor of production"]["Factor of production"].tolist()
    assert frames["Scenario"]["Scenario"].tolist() == ["baseline", "alternative"]
    assert db.get_index("all") == expected
    assert list(db.matrices) == list(before)
    for scenario, blocks in before.items():
        assert set(db.matrices[scenario]) == set(blocks)
        for name, frame in blocks.items():
            pd.testing.assert_frame_equal(db.matrices[scenario][name], frame)


def test_export_sets_preserves_observed_regional_membership(tmp_path):
    db = regional_database(
        {"IT": ["A1"], "FR": ["A2", "A3"]},
        {"IT": ["C1", "C2"], "FR": ["C1"]},
        {"IT": ["HH"], "FR": ["HH", "GOV"]},
    )
    path = db.export_sets(tmp_path / "regional.xlsx", include_scenarios=False)
    frames = pd.read_excel(path, sheet_name=None)
    assert "Scenario" not in frames
    assert frames["Activity"].columns.tolist() == ["Region", "Activity"]
    assert frames["Activity"].values.tolist() == [["IT", "A1"], ["FR", "A2"], ["FR", "A3"]]
    assert frames["Commodity"].values.tolist() == [["IT", "C1"], ["IT", "C2"], ["FR", "C1"]]
    assert frames["Consumption category"].values.tolist() == [["IT", "HH"], ["FR", "HH"], ["FR", "GOV"]]
    assert frames["Region"].columns.tolist() == ["Region"]
    assert frames["Satellite account"].values.tolist() == [["CO2"]]


def test_export_sets_keeps_literal_labels_and_native_names(tmp_path, isolated_session_settings):
    settings = mario.download_settings()
    settings["index"]["a"] = "Industries"
    mario.upload_settings(settings)
    labels = ['=1+1', 'Activity, with "quotes"', 'https://example.test/activity']
    db = regional_database(
        {"IT": labels}, {"IT": ["C"]},
    )
    path = db.export_sets(tmp_path / "literal.xlsx")
    book = load_workbook(path)
    try:
        assert "Activity" in book.sheetnames
        assert "Industries" not in book.sheetnames
        assert db.get_index("Industries") == labels
        sheet = book["Activity"]
        assert [cell.value for row in sheet.iter_rows(min_row=2) for cell in row] == labels
        assert all(cell.data_type == "s" for row in sheet.iter_rows(min_row=2) for cell in row)
        assert sheet["A4"].hyperlink is None
    finally:
        book.close()


def test_export_sets_default_path_and_directory_input(tmp_path):
    db = mario.load_test("IOT")
    db.directory = tmp_path
    assert db.export_sets() == tmp_path / "Database" / "sets.xlsx"
    assert db.export_sets(tmp_path / "other") == tmp_path / "other" / "sets.xlsx"


def test_export_sets_rejects_wrong_suffix(tmp_path):
    db = mario.load_test("IOT")
    with pytest.raises(WrongInput, match=".xlsx"):
        db.export_sets(tmp_path / "sets.csv")
    assert not (tmp_path / "sets.csv").exists()
