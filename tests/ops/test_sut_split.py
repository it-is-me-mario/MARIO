"""Tests for the SUT sector split of ``Database.add_sectors``."""

import importlib.util
import warnings

import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.ops.add_sector_split_sut import (
    build_sut_split_priors,
    build_sut_split_structure,
    prepare_sut_split_support,
)
from mario.ops.add_sector_workbook import read_add_sector_workbook, validate_sut_add_mode

from .sut_split_helpers import ADD_SECTOR_PATH, VALUE_ADDED, build_example_database, read_expected


@pytest.fixture()
def guide_db():
    db = build_example_database()
    db.read_add_sectors_excel(ADD_SECTOR_PATH, read_inventories=True, split=True)
    return db


# ---------------------------------------------------------------------------
# Workbook reading and add/split mode
# ---------------------------------------------------------------------------
def test_guide_workbook_is_read_as_sut_split(guide_db):
    assert guide_db.to_split_activities == ["a2b"]
    assert guide_db.to_split_commodities == ["c2b"]
    assert guide_db.parented_commodities == ["c2b"]
    assert set(guide_db.split_info) == {
        "Total outputs",
        "Supply coef",
        "Use coef",
        "Final dem share",
        "Exclusions use",
        "Exclusions supply",
        "Tolerances",
    }


def test_sut_workbook_without_split_columns_is_all_add():
    master = pd.DataFrame({"Activity": ["x"], "Add or Split": [None]})
    assert validate_sut_add_mode(master) == "add"


def test_sut_workbook_cannot_mix_add_and_split():
    master = pd.DataFrame({"Activity": ["x", "y", "z"], "Add or Split": ["Split", "Add", "Split"]})
    with pytest.raises(WrongInput, match="cannot mix"):
        validate_sut_add_mode(master)


def test_sut_workbook_rejects_unknown_mode():
    master = pd.DataFrame({"Activity": ["x"], "Add or Split": ["Merge"]})
    with pytest.raises(WrongInput, match="accepts only"):
        validate_sut_add_mode(master)


def test_mixed_mode_workbook_fails_at_read_time(tmp_path):
    frame = pd.read_excel(ADD_SECTOR_PATH, sheet_name=None)
    frame["Master"].loc[0, "Add or Split"] = "Add"
    path = tmp_path / "mixed.xlsx"
    with pd.ExcelWriter(path) as writer:
        for name, sheet in frame.items():
            sheet.to_excel(writer, sheet_name=name, index=False)
    with pytest.raises(WrongInput, match="cannot mix"):
        read_add_sector_workbook(path, table="SUT", parse_split=True)


def test_optional_split_sheets_can_be_omitted(tmp_path):
    frame = pd.read_excel(ADD_SECTOR_PATH, sheet_name=None)
    path = tmp_path / "minimal.xlsx"
    with pd.ExcelWriter(path) as writer:
        for name, sheet in frame.items():
            if name in {"Exclusions use", "Exclusions supply", "Tolerances"}:
                continue
            sheet.to_excel(writer, sheet_name=name, index=False)
    workbook = read_add_sector_workbook(path, table="SUT", parse_split=True)
    assert workbook.split_info["Exclusions use"].empty
    assert workbook.split_info["Exclusions supply"].empty
    assert workbook.split_info["Tolerances"].empty


def test_required_split_sheet_is_enforced(tmp_path):
    frame = pd.read_excel(ADD_SECTOR_PATH, sheet_name=None)
    path = tmp_path / "missing.xlsx"
    with pd.ExcelWriter(path) as writer:
        for name, sheet in frame.items():
            if name == "Supply coef":
                continue
            sheet.to_excel(writer, sheet_name=name, index=False)
    with pytest.raises(Exception, match="Supply coef"):
        read_add_sector_workbook(path, table="SUT", parse_split=True)


# ---------------------------------------------------------------------------
# Validation of the split-support sheets
# ---------------------------------------------------------------------------
def test_structure_of_the_guide(guide_db):
    structure = build_sut_split_structure(guide_db)
    assert structure.activity_parent == {"a2b": "a2"}
    assert structure.commodity_parent == {"c2b": "c2"}
    assert structure.stable_activities == ["a1"]
    assert structure.parent_commodities == ["c2"]
    assert structure.all_activities == ["a1", "a2", "a2b"]


def test_missing_total_output_is_rejected(guide_db):
    guide_db.split_info["Total outputs"] = guide_db.split_info["Total outputs"].iloc[1:]
    with pytest.raises(WrongInput, match="missing total output"):
        prepare_sut_split_support(guide_db)


def test_new_commodity_in_supply_coef_is_rejected(guide_db):
    sheet = guide_db.split_info["Supply coef"].copy()
    sheet.loc[0, "Commodity_to"] = "c2b"
    guide_db.split_info["Supply coef"] = sheet
    with pytest.raises(WrongInput, match="commodity inventory"):
        prepare_sut_split_support(guide_db)


def test_final_demand_share_outside_unit_interval_is_rejected(guide_db):
    sheet = guide_db.split_info["Final dem share"].copy()
    sheet.loc[0, "Share"] = 1.5
    guide_db.split_info["Final dem share"] = sheet
    with pytest.raises(WrongInput, match="between 0 and 1"):
        prepare_sut_split_support(guide_db)


def test_child_output_larger_than_parent_is_rejected(guide_db):
    sheet = guide_db.split_info["Total outputs"].copy()
    sheet.loc[0, "Quantity"] = 1000.0
    guide_db.split_info["Total outputs"] = sheet
    structure = prepare_sut_split_support(guide_db)
    with pytest.raises(WrongInput, match="larger than parent"):
        build_sut_split_priors(guide_db, structure)


# ---------------------------------------------------------------------------
# Priors: golden test against the guide
# ---------------------------------------------------------------------------
@pytest.fixture()
def guide_priors(guide_db):
    structure = prepare_sut_split_support(guide_db)
    return build_sut_split_priors(guide_db, structure)


def _assert_block(actual: pd.DataFrame, expected: dict, *, label: str):
    for (row, column), value in expected.items():
        got = float(actual.loc[row, column])
        assert got == pytest.approx(value, abs=1e-9), f"{label}[{row}, {column}]: {got} != {value}"


def test_priors_reproduce_the_reference_use(guide_priors):
    expected = read_expected()["Z"]
    # The use of a split commodity by an existing activity is free (solved by CVXLab): compare the
    # rows of unsplit commodities and the columns of the new activity, which the inventories fix.
    rows = [i for i in expected.index if i[1] == "Commodity"]
    cols = [c for c in expected.columns if c[1] == "Activity"]
    for row in rows:
        for col in cols:
            if row[2] != "c1" and col[2] != "a2b":
                continue
            got = float(guide_priors.U0.loc[(row[0], row[2]), (col[0], col[2])])
            assert got == pytest.approx(float(expected.loc[row, col]), abs=1e-9), (row, col)


def test_priors_reproduce_the_reference_final_demand(guide_priors):
    expected = read_expected()["Y"]
    for row in (i for i in expected.index if i[1] == "Commodity"):
        for col in expected.columns:
            got = float(guide_priors.Y0.loc[(row[0], row[2]), (col[0], col[2])])
            assert got == pytest.approx(float(expected.loc[row, col]), abs=1e-9), (row, col)


def test_priors_reproduce_the_reference_outputs(guide_priors):
    assert guide_priors.Xnew[("DE", "a2b")] == pytest.approx(10.8)
    assert guide_priors.Xnew[("IT", "a2b")] == pytest.approx(8.3)
    assert guide_priors.Xnew[("DE", "a2")] == 0.0
    assert guide_priors.Xc[("DE", "c2b")] == pytest.approx(15.0)
    assert guide_priors.Xc[("IT", "c2b")] == pytest.approx(10.0)


def test_priors_zero_mask_follows_exclusions_and_original_zeros(guide_priors):
    zero = guide_priors.zero_M
    # Exclusions supply
    assert bool(zero.loc[("DE", "a1"), ("DE", "c2b")])
    assert bool(zero.loc[("IT", "a2"), ("DE", "c2b")])
    assert bool(zero.loc[("DE", "a2b"), ("DE", "c1")])
    # inherited from the original table (a1 never makes c2 in DE -> DE)
    assert bool(zero.loc[("DE", "a1"), ("DE", "c2")])
    # a cell that is free
    assert not bool(zero.loc[("DE", "a2b"), ("DE", "c2b")])


def test_priors_keep_parent_plus_children_equal_to_original(guide_priors):
    original = guide_priors.original
    U0, M0, Y0, V0 = guide_priors.U0, guide_priors.M0, guide_priors.Y0, guide_priors.V0
    for region in ("DE", "IT"):
        for r2 in ("DE", "IT"):
            # parent activity column of a stable commodity + child column == original
            got = U0.loc[(region, "c1"), (r2, "a2")] + U0.loc[(region, "c1"), (r2, "a2b")]
            assert got == pytest.approx(original.U.loc[(region, "c1"), (r2, "a2")])
            # Make parent cell + children == original
            block = M0.loc[[(region, "a2"), (region, "a2b")], [(r2, "c2"), (r2, "c2b")]].to_numpy().sum()
            assert block == pytest.approx(original.M.loc[(region, "a2"), (r2, "c2")])
            # Final demand
            assert (Y0.loc[(region, "c2")] + Y0.loc[(region, "c2b")]).to_numpy() == pytest.approx(
                original.Y.loc[(region, "c2")].to_numpy()
            )
    assert (V0.loc["Value added", ("DE", "a2")] + V0.loc["Value added", ("DE", "a2b")]) == pytest.approx(12.7)


def test_missing_final_demand_share_warns_and_uses_zero(guide_db):
    guide_db.split_info["Final dem share"] = guide_db.split_info["Final dem share"].iloc[:3]
    structure = prepare_sut_split_support(guide_db)
    with pytest.warns(UserWarning, match="no share"):
        priors = build_sut_split_priors(guide_db, structure)
    assert priors.Y0.loc[("IT", "c2b"), ("IT", "Final demand")] == 0.0
    assert priors.Y0.loc[("IT", "c2"), ("IT", "Final demand")] == pytest.approx(14.1)


def test_priors_clip_negative_parent_with_a_warning(guide_db):
    sheet = guide_db.split_info["Total outputs"].copy()
    # child as large as its parent in use terms makes some parent cells negative
    inventory = guide_db.add_sectors_workbook.inventories_by_sheet["a2b_DE"]
    inventory.loc[inventory["DB Item"] == "c1", "Quantity"] = np.where(
        inventory.loc[inventory["DB Item"] == "c1", "DB Region"] == "DE", 5.0, 0.0
    )
    structure = prepare_sut_split_support(guide_db)
    with pytest.warns(UserWarning, match="clipped"):
        priors = build_sut_split_priors(guide_db, structure)
    assert (priors.U0.to_numpy() >= 0).all()


# ---------------------------------------------------------------------------
# Database.add_sectors integration
# ---------------------------------------------------------------------------
def _cvxlab_available():
    return importlib.util.find_spec("cvxlab") is not None


needs_cvxlab = pytest.mark.skipif(not _cvxlab_available(), reason="CVXLab is not installed")


def test_split_workbook_without_split_flag_is_rejected(tmp_path):
    db = build_example_database()
    with pytest.raises(WrongInput, match="split=True"):
        db.add_sectors(io=ADD_SECTOR_PATH, inplace=False)


def test_add_workbook_with_split_flag_is_rejected(tmp_path):
    frame = pd.read_excel(ADD_SECTOR_PATH, sheet_name=None)
    frame["Master"]["Add or Split"] = "Add"
    path = tmp_path / "all_add.xlsx"
    with pd.ExcelWriter(path) as writer:
        for name, sheet in frame.items():
            sheet.to_excel(writer, sheet_name=name, index=False)
    db = build_example_database()
    with pytest.raises(WrongInput, match="No sectors are marked as 'Split'"):
        db.add_sectors(io=path, split=True, cvxlab_path=tmp_path, inplace=False)


def test_split_requires_cvxlab_path():
    db = build_example_database()
    with pytest.raises(WrongInput, match="cvxlab_path"):
        db.add_sectors(io=ADD_SECTOR_PATH, split=True, inplace=False)


@needs_cvxlab
def test_only_input_data_gen_writes_cvxlab_inputs(tmp_path):
    db = build_example_database()
    new = db.add_sectors(
        io=ADD_SECTOR_PATH, split=True, cvxlab_path=tmp_path, only_input_data_gen=True, inplace=False
    )
    model_dir = tmp_path / "mario_add_sector_split_sut"
    assert (model_dir / "sets.xlsx").exists()
    tables = pd.read_excel(model_dir / "input_data" / "input_data.xlsx", sheet_name=None)
    assert {"Uold", "Mold", "Yold", "Vold", "U0", "M0", "Y0", "V0", "Xnew", "Zero_U", "Zero_M"} <= set(tables)
    identity = tables["I_act_p_pn"].set_index(["activity_to_Name", "activity_from_Name"])["values"]
    assert identity.to_dict() == {("a2", "a2"): 1, ("a2b", "a2"): 1}
    sets = pd.read_excel(model_dir / "sets.xlsx", sheet_name="_set_COMMODITY_FROM")
    assert dict(zip(sets["commodity_from_Name"], sets["commodity_from_category"])) == {
        "c1": "stable",
        "c2": "parent",
        "c2b": "new",
    }
    # without a solve, the prior scenario is promoted to baseline
    assert list(new.scenarios) == ["baseline"]
    assert "a2b" in new.get_index("Activity") and "c2b" in new.get_index("Commodity")


@pytest.fixture(scope="module")
def solved_split(tmp_path_factory):
    pytest.importorskip("cvxlab")
    db = build_example_database()
    folder = tmp_path_factory.mktemp("cvxlab_sut")
    new = db.add_sectors(io=ADD_SECTOR_PATH, split=True, cvxlab_path=folder, inplace=False)
    return db, new


@needs_cvxlab
def test_split_adds_the_new_items(solved_split):
    original, new = solved_split
    assert new.get_index("Activity") == ["a1", "a2", "a2b"]
    assert new.get_index("Commodity") == ["c1", "c2", "c2b"]
    assert new.units["Activity"].loc["a2b", "unit"] == "M EUR"
    assert list(new.scenarios) == ["baseline"]


@needs_cvxlab
def test_split_keeps_parent_plus_children_equal_to_original(solved_split):
    original, new = solved_split
    U_old, S_old = original.U, original.S
    U_new, S_new = new.U, new.S
    for region in ("DE", "IT"):
        for r2 in ("DE", "IT"):
            for commodity in ("c1",):
                total = (
                    U_new.loc[(region, "Commodity", commodity), (r2, "Activity", "a2")]
                    + U_new.loc[(region, "Commodity", commodity), (r2, "Activity", "a2b")]
                )
                assert total == pytest.approx(U_old.loc[(region, "Commodity", commodity), (r2, "Activity", "a2")], rel=1e-4)
            block = S_new.loc[
                [(region, "Activity", "a2"), (region, "Activity", "a2b")],
                [(r2, "Commodity", "c2"), (r2, "Commodity", "c2b")],
            ].to_numpy().sum()
            assert block == pytest.approx(S_old.loc[(region, "Activity", "a2"), (r2, "Commodity", "c2")], rel=1e-4)
    # stable cells are untouched
    assert S_new.loc[("DE", "Activity", "a1"), ("DE", "Commodity", "c1")] == pytest.approx(14.4)


@needs_cvxlab
def test_split_is_balanced_and_respects_known_outputs(solved_split):
    _, new = solved_split
    X = new.X["production"]
    assert X[("DE", "Activity", "a2b")] == pytest.approx(10.8, rel=1e-4)
    assert X[("IT", "Activity", "a2b")] == pytest.approx(8.3, rel=1e-4)
    # outputs are consistent with the aggregated ones
    assert X[("DE", "Activity", "a2")] + X[("DE", "Activity", "a2b")] == pytest.approx(35.7, rel=1e-4)
    assert X[("DE", "Commodity", "c2")] + X[("DE", "Commodity", "c2b")] == pytest.approx(37.0, rel=1e-4)
    # activity balance: purchases + value added = output
    U, V = new.U, new.V
    for region in ("DE", "IT"):
        for activity in ("a1", "a2", "a2b"):
            column = (region, "Activity", activity)
            assert U[column].sum() + V[column].sum() == pytest.approx(X[column], rel=1e-4)


@needs_cvxlab
def test_split_stays_close_to_the_reference_disaggregation(solved_split):
    """The reference table is the ground truth the inventories were derived from.

    The optimization only sees the priors, so it recovers the reference approximately: the Make
    table within 0.5, final demand exactly (it is fixed by the shares), and the value added of the
    new activities as the output not paid to inputs.
    """

    _, new = solved_split
    reference = read_expected()
    Z = reference["Z"]
    make = Z.loc[[i for i in Z.index if i[1] == "Activity"], [c for c in Z.columns if c[1] == "Commodity"]]
    assert np.abs(new.S.to_numpy() - make.to_numpy()).max() < 0.5
    final = reference["Y"].loc[[i for i in reference["Y"].index if i[1] == "Commodity"]]
    # exact up to the tolerance band of the constraints (eps = 1e-5 of the flow) and the solver accuracy
    assert np.abs(new.Y.loc[final.index, final.columns].to_numpy() - final.to_numpy()).max() < 1e-3
    va = new.V.loc[VALUE_ADDED]
    for region, expected in (("DE", 1.1), ("IT", 1.3)):
        assert va[(region, "Activity", "a2b")] == pytest.approx(expected, abs=1.0)
    assert va[("DE", "Activity", "a2")] + va[("DE", "Activity", "a2b")] == pytest.approx(12.7, rel=1e-4)


@needs_cvxlab
def test_split_respects_exclusions(solved_split):
    _, new = solved_split
    S = new.S
    assert S.loc[("DE", "Activity", "a1"), ("DE", "Commodity", "c2")] == pytest.approx(0, abs=1e-6)
    assert S.loc[("DE", "Activity", "a2b"), ("DE", "Commodity", "c1")] == pytest.approx(0, abs=1e-6)
    assert S.loc[("IT", "Activity", "a2"), ("DE", "Commodity", "c2b")] == pytest.approx(0, abs=1e-6)
    assert (new.U.to_numpy() >= -1e-9).all()


@needs_cvxlab
def test_split_satellite_accounts_follow_parent_intensity(solved_split):
    original, new = solved_split
    E_old, E_new = original.E, new.E
    # the new activity inherits the parent intensity and the total is preserved
    total = E_new.loc["CO2", ("DE", "Activity", "a2")] + E_new.loc["CO2", ("DE", "Activity", "a2b")]
    assert total == pytest.approx(E_old.loc["CO2", ("DE", "Activity", "a2")])
    ratio = E_new.loc["CO2", ("DE", "Activity", "a2b")] / new.X["production"][("DE", "Activity", "a2b")]
    assert ratio == pytest.approx(E_old.loc["CO2", ("DE", "Activity", "a2")] / 35.7)


@needs_cvxlab
def test_split_keep_all_steps_and_parent_rename(tmp_path):
    db = build_example_database()
    new = db.add_sectors(
        io=ADD_SECTOR_PATH,
        split=True,
        cvxlab_path=tmp_path,
        keep_all_split_steps=True,
        parent_names={"Activity": {"a2": "a2_rest"}, "Commodity": {"c2": "c2_rest"}},
        inplace=False,
    )
    assert set(new.scenarios) == {"baseline", "original", "split_baseline", "split_cvxlab"}
    assert new.get_index("Activity") == ["a1", "a2_rest", "a2b"]
    assert new.get_index("Commodity") == ["c1", "c2_rest", "c2b"]
    assert "a2_rest" in new.units["Activity"].index
    assert ("DE", "Activity", "a2_rest") in new.X.index


# ---------------------------------------------------------------------------
# Templates and satellite inventories
# ---------------------------------------------------------------------------
def test_sut_template_gets_split_sheets_when_master_is_marked_split(tmp_path):
    from openpyxl import load_workbook

    db = build_example_database()
    path = tmp_path / "template.xlsx"
    db.get_add_sectors_excel(path=path, items=["x"], regions=["DE"], item="Activity")
    master = pd.read_excel(path, sheet_name="Master")
    assert {"Parent Commodity", "Add or Split"} <= set(master.columns)
    assert master["Add or Split"].tolist() == ["Add"]

    master["Add or Split"] = "Split"
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        master.to_excel(writer, sheet_name="Master", index=False)
    db.read_add_sectors_excel(path)
    db.get_inventory_sheets(path)
    sheets = set(load_workbook(path).sheetnames)
    assert {
        "Total outputs", "Supply coef", "Use coef", "Final dem share", "Exclusions use", "Exclusions supply", "Tolerances"
    } <= sheets
    assert "Trades" not in sheets


def test_satellite_inventory_rows_override_parent_intensity(guide_db):
    inventories = guide_db.add_sectors_workbook.inventories_by_sheet
    extra = pd.DataFrame(
        [{"Quantity": 10.0, "Unit": "kg", "Input": None, "Item type": "Satellite account", "DB Item": "CO2",
          "DB Region": None, "Change type": "Update"}]
    )
    inventories["a2b_DE"] = pd.concat([inventories["a2b_DE"], extra], ignore_index=True)
    structure = prepare_sut_split_support(guide_db)
    priors = build_sut_split_priors(guide_db, structure)
    from mario.ops.add_sector_split_sut import assemble_sut_split_flows

    flows = assemble_sut_split_flows(
        structure, priors.original, priors,
        U=priors.U0, M=priors.M0, Y=priors.Y0, V=priors.V0, Xa=priors.Xa, Xc=priors.Xc,
    )
    E = flows["E"]
    # 10 kg per unit of the 10.8 output of a2b in DE; IT keeps the parent intensity
    assert E.loc["CO2", ("DE", "Activity", "a2b")] == pytest.approx(108.0)
    assert E.loc["CO2", ("IT", "Activity", "a2b")] == pytest.approx(1.0 / 35 * 8.3)


# ---------------------------------------------------------------------------
# Unknown items are rejected
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sheet, column, value",
    [
        ("Supply coef", "Commodity_to", "nope"),
        ("Supply coef", "Activity_from", "nope"),
        ("Exclusions use", "Commodity_from", "nope"),
        ("Exclusions use", "Activity_to", "nope"),
        ("Exclusions supply", "Activity_from", "nope"),
        ("Exclusions supply", "Commodity_to", "nope"),
        ("Supply coef", "Region_to", "XX"),
    ],
)
def test_unknown_items_in_split_sheets_are_rejected(guide_db, sheet, column, value):
    frame = guide_db.split_info[sheet].copy()
    frame.loc[0, column] = value
    guide_db.split_info[sheet] = frame
    with pytest.raises(WrongInput, match="unknown"):
        prepare_sut_split_support(guide_db)


# ---------------------------------------------------------------------------
# Use coef sheet (optional, new commodity rows of the Use matrix)
# ---------------------------------------------------------------------------
USE_COEF_COLUMNS = ["Region_from", "Region_to", "Commodity_from", "Activity_to", "Coefficient", "Source", "Notes"]


def _with_use_coef(db, rows):
    db.split_info["Use coef"] = pd.DataFrame(rows, columns=USE_COEF_COLUMNS)
    return db


def test_use_coef_sheet_is_optional_and_empty_when_absent(guide_db):
    assert list(guide_db.split_info["Use coef"].columns) == USE_COEF_COLUMNS
    assert guide_db.split_info["Use coef"].empty
    prepare_sut_split_support(guide_db)
    assert guide_db.split_info["Use coef"].empty


def test_valid_use_coef_rows_are_normalised(guide_db):
    _with_use_coef(
        guide_db,
        [
            [" DE ", "DE", "c2b", "a1", 0.1, None, None],  # stable column
            ["DE", "IT", "c2b", "a2", 0, None, None],  # parent column, cross-region
        ],
    )
    prepare_sut_split_support(guide_db)
    sheet = guide_db.split_info["Use coef"]
    assert sheet["Region_from"].tolist() == ["DE", "DE"]
    assert sheet["Coefficient"].tolist() == [0.1, 0.0]


@pytest.mark.parametrize(
    "row, match",
    [
        (["XX", "DE", "c2b", "a1", 0.1, None, None], "unknown regions"),
        (["DE", "XX", "c2b", "a1", 0.1, None, None], "unknown regions"),
        (["DE", "DE", "c1", "a1", 0.1, None, None], "unknown commodities not marked for split"),
        (["DE", "DE", "c2", "a1", 0.1, None, None], "unknown commodities not marked for split"),
        (["DE", "DE", "c2b", "nope", 0.1, None, None], "unknown activities"),
        (["DE", "DE", "c2b", "a2b", 0.1, None, None], "new activities"),
        (["DE", "DE", "c2b", "a1", -0.1, None, None], "cannot be negative"),
        (["DE", "DE", "c2b", "a1", "abc", None, None], "Invalid numeric"),
    ],
)
def test_use_coef_validation(guide_db, row, match):
    _with_use_coef(guide_db, [row])
    with pytest.raises(WrongInput, match=match):
        prepare_sut_split_support(guide_db)


def test_duplicated_use_coef_rows_are_rejected(guide_db):
    row = ["DE", "DE", "c2b", "a1", 0.1, None, None]
    _with_use_coef(guide_db, [row, row[:4] + [0.2, None, None]])
    with pytest.raises(WrongInput, match="duplicated"):
        prepare_sut_split_support(guide_db)


def test_blank_use_coef_rows_are_dropped(guide_db):
    _with_use_coef(guide_db, [[None] * 7, ["DE", "DE", "c2b", "a1", 0.1, None, None]])
    prepare_sut_split_support(guide_db)
    assert len(guide_db.split_info["Use coef"]) == 1


# ---------------------------------------------------------------------------
# Prior of the new-commodity rows of the Use matrix
# ---------------------------------------------------------------------------
def _use_priors(db, coefficients=None, **kwargs):
    if coefficients is not None:
        _with_use_coef(db, coefficients)
    structure = prepare_sut_split_support(db)
    return build_sut_split_priors(db, structure, **kwargs)


def _share(priors, region):
    return float(priors.Xc[(region, "c2b")] / priors.original.Xc[(region, "c2")])


def test_use_prior_blocks_add_up_to_the_original_cells(guide_priors):
    U0, original = guide_priors.U0, guide_priors.original.U
    for region in ("DE", "IT"):
        for r2 in ("DE", "IT"):
            for activity in ("a1", "a2"):
                total = U0.loc[[(region, "c2"), (region, "c2b")], (r2, activity)].sum()
                if activity == "a2":  # the parent column also gives room to the new activity
                    total += U0.loc[[(region, "c2"), (region, "c2b")], (r2, "a2b")].sum()
                assert total == pytest.approx(original.loc[(region, "c2"), (r2, activity)]), (region, r2, activity)


def test_use_prior_baseline_splits_by_commodity_output(guide_priors):
    U0, original = guide_priors.U0, guide_priors.original.U
    share_de = 15.0 / 37.0
    # stable column: the original cell is split by the output of the commodity (region of the row)
    assert U0.loc[("DE", "c2b"), ("DE", "a1")] == pytest.approx(share_de * 5.0)
    assert U0.loc[("DE", "c2"), ("DE", "a1")] == pytest.approx((1 - share_de) * 5.0)
    assert U0.loc[("DE", "c2b"), ("IT", "a1")] == pytest.approx(share_de * 1.0)  # cross-region cell
    # parent column: the budget is the original cell minus the use of the new activity (3 + 1)
    assert U0.loc[("DE", "c2b"), ("DE", "a2")] == pytest.approx(share_de * 6.0)
    assert U0.loc[("DE", "c2"), ("DE", "a2")] == pytest.approx((1 - share_de) * 6.0)


def test_use_prior_leaves_already_priored_cells_untouched(guide_priors):
    # stable commodity rows keep the existing prior (original minus the new activity's use)
    assert guide_priors.U0.loc[("DE", "c1"), ("DE", "a2")] == pytest.approx(6.0)
    assert guide_priors.U0.loc[("DE", "c1"), ("DE", "a1")] == pytest.approx(2.0)


def test_use_coef_replaces_the_baseline_of_a_stable_column(guide_db):
    priors = _use_priors(guide_db, [["DE", "DE", "c2b", "a1", 0.1, None, None]])
    child = 0.1 * priors.Xa[("DE", "a1")]
    assert priors.U0.loc[("DE", "c2b"), ("DE", "a1")] == pytest.approx(child)
    assert priors.U0.loc[("DE", "c2"), ("DE", "a1")] == pytest.approx(5.0 - child)


def test_use_coef_on_a_parent_column_uses_the_residual_output_and_the_budget(guide_db):
    priors = _use_priors(guide_db, [["DE", "DE", "c2b", "a2", 0.1, None, None]])
    child = 0.1 * priors.Xa[("DE", "a2")]  # residual output of the parent activity, 24.9
    assert child == pytest.approx(2.49)
    assert priors.U0.loc[("DE", "c2b"), ("DE", "a2")] == pytest.approx(child)
    assert priors.U0.loc[("DE", "c2"), ("DE", "a2")] == pytest.approx(6.0 - child)
    block = priors.U0.loc[[("DE", "c2"), ("DE", "c2b")], [("DE", "a2"), ("DE", "a2b")]].to_numpy().sum()
    assert block == pytest.approx(10.0)


def test_use_coef_flow_uses_the_region_of_the_activity(guide_db):
    priors = _use_priors(guide_db, [["DE", "IT", "c2b", "a1", 0.02, None, None]])
    assert priors.U0.loc[("DE", "c2b"), ("IT", "a1")] == pytest.approx(0.02 * priors.Xa[("IT", "a1")])
    assert priors.Xa[("IT", "a1")] != priors.Xa[("DE", "a1")]
    # the other regions keep the baseline
    assert priors.U0.loc[("DE", "c2b"), ("DE", "a1")] == pytest.approx(_share(priors, "DE") * 5.0)


def test_use_coef_with_negative_residual_falls_back_to_the_baseline(guide_db):
    baseline = _use_priors(guide_db)
    guide_db.split_info["Use coef"] = pd.DataFrame(
        [["DE", "DE", "c2b", "a1", 1.0, None, None]], columns=USE_COEF_COLUMNS
    )  # 17.4 > the original cell (5)
    with pytest.warns(UserWarning, match="would make the residual parent negative.*1 cells"):
        priors = build_sut_split_priors(guide_db, prepare_sut_split_support(guide_db))
    pd.testing.assert_frame_equal(priors.U0, baseline.U0)


def test_fallback_warnings_are_aggregated(guide_db):
    rows = [[r, "DE", "c2b", a, 50.0, None, None] for r in ("DE",) for a in ("a1", "a2")]
    _with_use_coef(guide_db, rows)
    with pytest.warns(UserWarning, match="2 cells") as record:
        build_sut_split_priors(guide_db, prepare_sut_split_support(guide_db))
    assert sum("residual parent negative" in str(w.message) for w in record) == 1


def test_use_coef_on_a_zero_cell_is_ignored_with_a_warning(guide_db):
    # (IT, c2b) -> (DE, a1) is a structural zero (original cell is zero / excluded)
    _with_use_coef(guide_db, [["IT", "DE", "c2b", "a1", 0.5, None, None]])
    with pytest.warns(UserWarning, match="cells known to be zero are ignored"):
        priors = build_sut_split_priors(guide_db, prepare_sut_split_support(guide_db))
    assert priors.U0.loc[("IT", "c2b"), ("DE", "a1")] == 0.0


def test_masked_cell_mass_goes_to_the_other_cells_of_the_group(guide_db):
    sheet = guide_db.split_info["Exclusions use"]
    guide_db.split_info["Exclusions use"] = pd.concat(
        [sheet, pd.DataFrame([{"Region_from": "DE", "Region_to": "DE", "Commodity_from": "c2b", "Activity_to": "a1"}])],
        ignore_index=True,
    )
    priors = _use_priors(guide_db)
    assert priors.U0.loc[("DE", "c2b"), ("DE", "a1")] == 0.0
    assert priors.U0.loc[("DE", "c2"), ("DE", "a1")] == pytest.approx(5.0)


def test_parent_column_with_too_large_new_activity_use_gets_zeros_and_a_warning(guide_db):
    inventory = guide_db.add_sectors_workbook.inventories_by_sheet["a2b_DE"]
    inventory.loc[(inventory["DB Item"] == "c2") & (inventory["DB Region"] == "DE"), "Quantity"] = 1.0
    structure = prepare_sut_split_support(guide_db)
    with pytest.warns(UserWarning, match="already use more of the parent cell"):
        priors = build_sut_split_priors(guide_db, structure)
    assert priors.U0.loc[("DE", "c2b"), ("DE", "a2")] == 0.0
    assert priors.U0.loc[("DE", "c2"), ("DE", "a2")] == 0.0


def test_parent_commodity_without_output_keeps_everything_in_the_parent(guide_db):
    sheet = guide_db.split_info["Total outputs"].copy()
    sheet.loc[sheet["Commodity"] == "c2b", "Quantity"] = 0.0
    guide_db.split_info["Total outputs"] = sheet
    priors = _use_priors(guide_db)
    assert priors.U0.loc[("DE", "c2b"), ("DE", "a1")] == 0.0
    assert priors.U0.loc[("DE", "c2"), ("DE", "a1")] == pytest.approx(5.0)


def _reference_use_coef(db):
    """"Use coef" rows of the new commodity taken from the reference table (stable + parent columns)."""

    priors = build_sut_split_priors(db, prepare_sut_split_support(db))
    Z = read_expected()["Z"]
    rows = [
        [r, s, "c2b", a, float(Z.loc[(r, "Commodity", "c2b"), (s, "Activity", a)]) / float(priors.Xa[(s, a)]), None, None]
        for r in ("DE", "IT")
        for s in ("DE", "IT")
        for a in ("a1", "a2")
    ]
    return rows


@needs_cvxlab
def test_use_coef_from_the_reference_gets_the_solution_closer_to_it(tmp_path):
    reference = read_expected()
    Z = reference["Z"]
    use_rows = [i for i in Z.index if i == i and i[1] == "Commodity" and i[2] == "c2b"]
    use_cols = [c for c in Z.columns if c[1] == "Activity"]

    def solve(folder, coefficients):
        db = build_example_database()
        db.read_add_sectors_excel(ADD_SECTOR_PATH, read_inventories=True, split=True)
        rows = _reference_use_coef(db) if coefficients else []

        def add(sheets):
            sheets["Use coef"] = pd.DataFrame(rows, columns=USE_COEF_COLUMNS)

        from .sut_split_helpers import write_modified_workbook

        path = write_modified_workbook(ADD_SECTOR_PATH, folder, add)
        new = build_example_database().add_sectors(io=path, split=True, cvxlab_path=folder, inplace=False)
        make = Z.loc[[i for i in Z.index if i[1] == "Activity"], [c for c in Z.columns if c[1] == "Commodity"]]
        use = new.U.loc[use_rows, use_cols] - Z.loc[use_rows, use_cols]
        return np.abs(new.S.to_numpy() - make.to_numpy()).max(), np.abs(use.to_numpy()).max()

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    make_baseline, use_baseline = solve(tmp_path / "a", coefficients=False)
    make_coef, use_coef = solve(tmp_path / "b", coefficients=True)
    assert make_coef < make_baseline and use_coef < use_baseline
    assert make_coef < 0.5 and use_coef < 0.05


# ---------------------------------------------------------------------------
# Which cells of the Use prior reach the optimisation (U0_objective)
# ---------------------------------------------------------------------------
def _new_rows_in_plain_columns(priors):
    structure = priors.structure
    rows = [i for i in priors.U0.index if structure.commodity_category(i[1]) != "stable"]
    cols = [c for c in priors.U0.columns if structure.activity_category(c[1]) != "new"]
    return rows, cols


def test_without_coefficients_no_use_cell_of_the_new_rows_enters_the_optimisation(guide_priors):
    rows, cols = _new_rows_in_plain_columns(guide_priors)
    assert (guide_priors.U0_objective.loc[rows, cols].to_numpy() == 0).all()
    assert (guide_priors.U0.loc[rows, cols].to_numpy() > 0).any()  # the baseline itself is kept
    # every other prior cell (stable rows, new-activity columns) is handed over unchanged
    pd.testing.assert_frame_equal(
        guide_priors.U0_objective.drop(index=rows), guide_priors.U0.drop(index=rows), check_exact=False
    )
    new_columns = [c for c in guide_priors.U0.columns if c not in cols]
    pd.testing.assert_frame_equal(
        guide_priors.U0_objective[new_columns], guide_priors.U0[new_columns], check_exact=False
    )


def test_only_the_coefficient_cell_and_the_residual_parent_are_informed(guide_db):
    priors = _use_priors(guide_db, [["DE", "DE", "c2b", "a1", 0.1, None, None]])
    objective, full = priors.U0_objective, priors.U0
    for row in (("DE", "c2b"), ("DE", "c2")):
        assert objective.loc[row, ("DE", "a1")] == full.loc[row, ("DE", "a1")] > 0
    # a different column / region of the same commodities stays a free baseline guess
    assert objective.loc[("DE", "c2b"), ("IT", "a1")] == 0 and full.loc[("DE", "c2b"), ("IT", "a1")] > 0
    assert objective.loc[("DE", "c2"), ("DE", "a2")] == 0 and objective.loc[("DE", "c2b"), ("DE", "a2")] == 0


def test_fallback_and_ignored_coefficients_inform_nothing(guide_db):
    rows = [["DE", "DE", "c2b", "a1", 1.0, None, None], ["IT", "DE", "c2b", "a1", 0.5, None, None]]
    _with_use_coef(guide_db, rows)
    with pytest.warns(UserWarning):
        priors = build_sut_split_priors(guide_db, prepare_sut_split_support(guide_db))
    structure = priors.structure
    pn_rows = [i for i in priors.U0.index if structure.commodity_category(i[1]) != "stable"]
    cols = [c for c in priors.U0.columns if structure.activity_category(c[1]) != "new"]
    assert (priors.U0_objective.loc[pn_rows, cols].to_numpy() == 0).all()


def test_children_without_a_coefficient_are_left_free():
    from mario.ops.add_sector_split_sut import SutSplitStructure, _fill_new_commodity_use_prior, _informed_use_prior

    structure = SutSplitStructure(
        regions=["R"], activities=["a1"], commodities=["c1"], new_activities=[], new_commodities=["n1", "n2"],
        activity_parent={}, commodity_parent={"n1": "c1", "n2": "c1"}, master_rows=pd.DataFrame(),
    )
    rows = pd.MultiIndex.from_product([["R"], ["c1", "n1", "n2"]], names=["Region", "Item"])
    cols = pd.MultiIndex.from_tuples([("R", "a1")], names=["Region", "Item"])
    old = pd.DataFrame([[50.0], [0.0], [0.0]], index=rows, columns=cols)
    kwargs = dict(
        structure=structure, old_U=old,
        Xa=pd.Series([200.0], index=cols),
        Xc=pd.Series([60.0, 10.0, 30.0], index=rows),
        Xc_orig=pd.Series([100.0], index=pd.MultiIndex.from_tuples([("R", "c1")])),
        zero_U=pd.DataFrame(False, index=rows, columns=cols),
    )
    coef = pd.DataFrame([["R", "R", "n1", "a1", 0.1, None, None]], columns=USE_COEF_COLUMNS)
    U0, informed = _fill_new_commodity_use_prior(old.copy(), use_coef=coef, **kwargs)
    assert U0[("R", "a1")].tolist() == pytest.approx([50 - 20 - 15, 20, 15])  # n2 keeps its baseline (30 %)
    assert informed[("R", "a1")].tolist() == [True, True, False]
    objective = _informed_use_prior(U0, informed, structure)
    assert objective[("R", "a1")].tolist() == pytest.approx([15, 20, 0])
