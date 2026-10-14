"""Tests for the commodity-only and activity-only variants of the SUT split."""

import importlib.util
import logging
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.ops.add_sector_split_sut import (
    MODE_ACTIVITIES,
    MODE_COMMODITIES,
    build_sut_split_priors,
    prepare_sut_split_support,
)
from mario.ops.add_sector_workbook import sut_split_variant
from mario.ops.cvxlab_bridge import _resolve_split_solver
from mario.ops.cvxlab_bridge_sut import (
    CVXLAB_SUT_PREFERRED_SOLVERS,
    CVXLAB_SUT_TEMPLATE_NAMES,
    build_sut_split_input_tables,
)

from .sut_split_helpers import (
    ADD_SECTOR_PATH,
    VARIANT_ACTIVITIES,
    VARIANT_ADD_SECTOR_PATHS,
    VARIANT_COMMODITIES,
    build_example_database,
    read_variant_truth,
    write_modified_workbook,
)

MODELS_DIR = Path(__file__).resolve().parents[2] / "mario" / "ops" / "cvxlab_models"


def _cvxlab_available():
    return importlib.util.find_spec("cvxlab") is not None


needs_cvxlab = pytest.mark.skipif(not _cvxlab_available(), reason="CVXLab is not installed")


def _read(variant, path=None):
    db = build_example_database()
    db.read_add_sectors_excel(path or VARIANT_ADD_SECTOR_PATHS[variant], read_inventories=True, split=True)
    return db


def _sheet(workbook, name):
    frame = pd.DataFrame(workbook[name].values)
    frame.columns = frame.iloc[0]
    return frame.iloc[1:].reset_index(drop=True)


# ---------------------------------------------------------------------------
# The models: templates and tolerance inequalities
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["Split_sut", "Split_sut_com", "Split_sut_act"])
def test_templates_ship_with_tolerances(name):
    folder = MODELS_DIR / name
    for filename in ("model_settings.xlsx", "user_defined_constants.py", "user_defined_operators.py"):
        assert (folder / filename).exists()

    workbook = openpyxl.load_workbook(folder / "model_settings.xlsx")
    sets = _sheet(workbook, "structure_sets").set_index("set_key")
    assert sets.loc["scalar", "filters"] == "tolerance: [delta, eps]"

    variables = _sheet(workbook, "structure_variables")
    tol = variables[variables["table_key"] == "tol"]
    assert sorted(tol["variables_info"]) == ["delta", "eps"]

    expressions = list(_sheet(workbook, "problem")["expressions"].dropna())
    equalities = [e for e in expressions if "==" in e]
    # only the zero masks stay equalities
    assert equalities and all(e.startswith("mult(") and "Zero_" in e for e in equalities)
    inequalities = [e for e in expressions if "<=" in e or ">=" in e]
    assert inequalities
    assert all(any(f"(1{sign}{name})" in e for sign in "+-" for name in ("delta", "eps")) for e in inequalities)
    # the activity and commodity balances use delta; consistency with the originals and Xnew use eps
    assert any("(1+delta)" in e for e in inequalities) and any("(1+eps)" in e for e in inequalities)


def test_template_names_by_mode():
    assert CVXLAB_SUT_TEMPLATE_NAMES == {
        "both": "Split_sut",
        "commodities": "Split_sut_com",
        "activities": "Split_sut_act",
    }


def test_sut_bridge_prefers_clarabel_then_ecos_then_scs():
    assert CVXLAB_SUT_PREFERRED_SOLVERS == ("CLARABEL", "ECOS", "SCS")
    assert _resolve_split_solver("MOSEK", preferred=CVXLAB_SUT_PREFERRED_SOLVERS) == "MOSEK"
    cp = pytest.importorskip("cvxpy")
    installed = set(cp.installed_solvers())
    expected = next((s for s in CVXLAB_SUT_PREFERRED_SOLVERS if s in installed), None)
    assert _resolve_split_solver(None, preferred=CVXLAB_SUT_PREFERRED_SOLVERS) == expected


# ---------------------------------------------------------------------------
# Workbook contract per variant
# ---------------------------------------------------------------------------
def test_variant_is_read_from_the_master_sheet():
    master = pd.DataFrame({"Activity": ["a2b", None], "Commodity": [None, "c2b"]})
    assert sut_split_variant(master) == "both"
    assert sut_split_variant(master.iloc[[0]]) == "activities"
    assert sut_split_variant(master.iloc[[1]]) == "commodities"


def test_activity_workbook_needs_no_final_demand_share():
    db = _read(VARIANT_ACTIVITIES)
    assert db.to_split_activities == ["a2b"] and db.to_split_commodities == []
    assert db.split_info["Final dem share"].empty
    assert not db.split_info["Supply coef"].empty


def test_commodity_workbook_needs_no_supply_coef():
    db = _read(VARIANT_COMMODITIES)
    assert db.to_split_commodities == ["c2b"] and db.to_split_activities == []
    assert db.split_info["Supply coef"].empty
    assert not db.split_info["Final dem share"].empty


def test_combined_workbook_still_requires_both_sheets(tmp_path):
    def drop(sheets):
        del sheets["Supply coef"]

    path = write_modified_workbook(ADD_SECTOR_PATH, tmp_path, drop)
    db = build_example_database()
    with pytest.raises(Exception, match="Supply coef"):
        db.read_add_sectors_excel(path, read_inventories=True, split=True)


def test_variant_workbooks_still_require_the_sheet_they_use(tmp_path):
    def drop_supply(sheets):
        del sheets["Supply coef"]

    def drop_shares(sheets):
        del sheets["Final dem share"]

    db = build_example_database()
    with pytest.raises(Exception, match="Supply coef"):
        db.read_add_sectors_excel(
            write_modified_workbook(VARIANT_ADD_SECTOR_PATHS[VARIANT_ACTIVITIES], tmp_path, drop_supply),
            read_inventories=True,
            split=True,
        )
    with pytest.raises(Exception, match="Final dem share"):
        db.read_add_sectors_excel(
            write_modified_workbook(VARIANT_ADD_SECTOR_PATHS[VARIANT_COMMODITIES], tmp_path, drop_shares),
            read_inventories=True,
            split=True,
        )


def test_unused_sheet_with_data_is_ignored_with_a_warning(tmp_path):
    def add_shares(sheets):
        sheets["Final dem share"] = pd.read_excel(
            VARIANT_ADD_SECTOR_PATHS[VARIANT_COMMODITIES], sheet_name="Final dem share"
        )

    path = write_modified_workbook(VARIANT_ADD_SECTOR_PATHS[VARIANT_ACTIVITIES], tmp_path, add_shares)
    db = _read(VARIANT_ACTIVITIES, path)
    with pytest.warns(UserWarning, match="Final dem share.*ignored"):
        structure = prepare_sut_split_support(db)
    assert structure.mode == MODE_ACTIVITIES
    assert db.split_info["Final dem share"].empty

    def add_supply(sheets):
        sheets["Supply coef"] = pd.read_excel(
            VARIANT_ADD_SECTOR_PATHS[VARIANT_ACTIVITIES], sheet_name="Supply coef"
        )

    path = write_modified_workbook(VARIANT_ADD_SECTOR_PATHS[VARIANT_COMMODITIES], tmp_path, add_supply)
    db = _read(VARIANT_COMMODITIES, path)
    with pytest.warns(UserWarning, match="Supply coef.*ignored"):
        prepare_sut_split_support(db)
    assert db.split_info["Supply coef"].empty


def test_rows_of_a_used_sheet_naming_unmarked_items_still_error(tmp_path):
    def wrong_item(sheets):
        sheets["Supply coef"].loc[0, "Activity_from"] = "a1"

    path = write_modified_workbook(VARIANT_ADD_SECTOR_PATHS[VARIANT_ACTIVITIES], tmp_path, wrong_item)
    db = _read(VARIANT_ACTIVITIES, path)
    with pytest.raises(WrongInput, match="not marked for split"):
        prepare_sut_split_support(db)


@pytest.mark.parametrize("variant", [VARIANT_ACTIVITIES, VARIANT_COMMODITIES])
def test_tolerance_sheet_checks(variant, tmp_path):
    def tolerances(values):
        def modify(sheets):
            sheets["Tolerances"] = pd.DataFrame(values, columns=["tol_Name", "values"])

        return modify

    path = write_modified_workbook(
        VARIANT_ADD_SECTOR_PATHS[variant], tmp_path, tolerances([("delta", -1e-5), ("eps", 1e-5)])
    )
    with pytest.raises(WrongInput, match="negative"):
        prepare_sut_split_support(_read(variant, path))

    path = write_modified_workbook(
        VARIANT_ADD_SECTOR_PATHS[variant], tmp_path, tolerances([("delta", 5e-2), ("eps", 1e-5)])
    )
    with pytest.warns(UserWarning, match="exceed"):
        prepare_sut_split_support(_read(variant, path))

    path = write_modified_workbook(
        VARIANT_ADD_SECTOR_PATHS[variant], tmp_path, tolerances([("delta", 1e-5), ("eps", 1e-5), ("other", 1.0)])
    )
    db = _read(variant, path)
    with pytest.warns(UserWarning, match="other"):
        prepare_sut_split_support(db)
    assert sorted(db.split_info["Tolerances"]["tol_Name"]) == ["delta", "eps"]


# ---------------------------------------------------------------------------
# Priors per variant, against the ground truth
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def act_priors():
    db = _read(VARIANT_ACTIVITIES)
    prepare_sut_split_support(db)
    return db, build_sut_split_priors(db), read_variant_truth(VARIANT_ACTIVITIES)


@pytest.fixture(scope="module")
def com_priors():
    db = _read(VARIANT_COMMODITIES)
    prepare_sut_split_support(db)
    return db, build_sut_split_priors(db), read_variant_truth(VARIANT_COMMODITIES)


def _two_level(frame):
    frame = frame.copy()
    frame.index = frame.index.droplevel(1)
    frame.columns = frame.columns.droplevel(1)
    return frame


def test_activity_only_priors(act_priors):
    _, priors, truth = act_priors
    assert priors.mode == MODE_ACTIVITIES
    assert priors.Y0 is None
    assert priors.U0 is not None and priors.V0 is not None
    # Xnew is the total cost of the new activity, indexed by (Region, activity)
    known = priors.Xnew[priors.Xnew > 0].to_dict()
    assert known == {("DE", "a2b"): pytest.approx(10.8), ("IT", "a2b"): pytest.approx(7.3)}
    Z = _two_level(truth.Z)
    new_columns = [c for c in priors.U0.columns if c[1] == "a2b"]
    assert np.abs(priors.U0[new_columns] - Z.loc[priors.U0.index, new_columns]).to_numpy().max() < 1e-9
    new_rows = [r for r in priors.M0.index if r[1] == "a2b"]
    assert np.abs(priors.M0.loc[new_rows] - Z.loc[new_rows, priors.M0.columns]).to_numpy().max() < 1e-9
    value_added = truth.V.loc["Value added"]
    for region in ("DE", "IT"):
        assert priors.V0.loc["Value added", (region, "a2b")] == pytest.approx(value_added[(region, "Activity", "a2b")])


def test_commodity_only_priors(com_priors):
    _, priors, truth = com_priors
    assert priors.mode == MODE_COMMODITIES
    assert priors.U0 is None and priors.V0 is None
    assert priors.Y0 is not None
    # Xnew is the total use of the new commodity, indexed by (Region, commodity)
    known = priors.Xnew[priors.Xnew > 0].to_dict()
    assert known == {("DE", "c2b"): pytest.approx(11.5), ("IT", "c2b"): pytest.approx(3.3)}
    Z = _two_level(truth.Z)
    new_columns = [c for c in priors.M0.columns if c[1] == "c2b"]
    assert np.abs(priors.M0[new_columns] - Z.loc[priors.M0.index, new_columns]).to_numpy().max() < 1e-9
    Y = _two_level(truth.Y)
    new_rows = [r for r in priors.Y0.index if r[1] == "c2b"]
    assert np.abs(priors.Y0.loc[new_rows] - Y.loc[new_rows]).to_numpy().max() < 1e-9
    # the same number scales the supply shares: supply of the new commodity equals its known use
    assert priors.M0[("DE", "c2b")].sum() == pytest.approx(11.5)


def test_combined_priors_keep_every_block():
    db = build_example_database()
    db.read_add_sectors_excel(ADD_SECTOR_PATH, read_inventories=True, split=True)
    prepare_sut_split_support(db)
    priors = build_sut_split_priors(db)
    assert priors.mode == "both"
    assert all(block is not None for block in (priors.U0, priors.M0, priors.Y0, priors.V0))
    # as before, Xnew only constrains the new activities
    assert {item for _, item in priors.Xnew[priors.Xnew > 0].index} == {"a2b"}


# ---------------------------------------------------------------------------
# Bridge input tables (no CVXLab needed)
# ---------------------------------------------------------------------------
def _blank(columns, rows):
    return pd.DataFrame(rows, columns=columns).assign(values=0.0)


def test_input_tables_commodity_xnew_and_tolerances_by_name(com_priors):
    _, priors, _ = com_priors
    blank = {
        "Xnew": _blank(["commodity_from_Name", "region_from_Name"], [("c2b", "DE"), ("c2b", "IT")]),
        "tol": _blank(["scalar_Name"], [("delta",), ("eps",)]),
    }
    tolerances = pd.DataFrame({"tol_Name": ["eps", "delta"], "values": [2e-5, 3e-5]})
    tables = build_sut_split_input_tables(priors, blank, tolerances=tolerances)
    xnew = tables["Xnew"].set_index(["commodity_from_Name", "region_from_Name"])["values"]
    assert xnew.to_dict() == {("c2b", "DE"): pytest.approx(11.5), ("c2b", "IT"): pytest.approx(3.3)}
    tol = tables["tol"].set_index("scalar_Name")["values"]
    assert tol.to_dict() == {"delta": 3e-5, "eps": 2e-5}


def test_input_tables_activity_xnew_and_no_prior_error(act_priors):
    _, priors, _ = act_priors
    blank = {"Xnew": _blank(["activity_to_Name", "region_to_Name"], [("a2b", "DE"), ("a2b", "IT")])}
    tables = build_sut_split_input_tables(priors, blank)
    xnew = tables["Xnew"].set_index(["activity_to_Name", "region_to_Name"])["values"]
    assert xnew.to_dict() == {("a2b", "DE"): pytest.approx(10.8), ("a2b", "IT"): pytest.approx(7.3)}
    # a model that declares a table whose prior the variant does not build is a configuration error
    with pytest.raises(WrongInput, match="Y0"):
        build_sut_split_input_tables(priors, {"Y0": _blank(["commodity_from_Name"], [("c1",)])})


# ---------------------------------------------------------------------------
# Solved variants (need CVXLab and a solver)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module", params=[VARIANT_ACTIVITIES, VARIANT_COMMODITIES])
def solved_variant(request, tmp_path_factory):
    pytest.importorskip("cvxlab")
    variant = request.param
    db = build_example_database()
    folder = tmp_path_factory.mktemp(f"cvxlab_sut_{variant}")
    new = db.add_sectors(io=VARIANT_ADD_SECTOR_PATHS[variant], split=True, cvxlab_path=folder, inplace=False)
    return variant, db, new, read_variant_truth(variant), folder


@needs_cvxlab
def test_variant_adds_only_its_items(solved_variant):
    variant, _, new, _, _ = solved_variant
    if variant == VARIANT_ACTIVITIES:
        assert new.get_index("Activity") == ["a1", "a2", "a2b"] and new.get_index("Commodity") == ["c1", "c2"]
    else:
        assert new.get_index("Activity") == ["a1", "a2"] and new.get_index("Commodity") == ["c1", "c2", "c2b"]
    assert list(new.scenarios) == ["baseline"]


@needs_cvxlab
def test_variant_uses_its_own_model(solved_variant):
    variant, _, _, _, folder = solved_variant
    settings = pd.read_excel(
        folder / "mario_add_sector_split_sut" / "model_settings.xlsx", sheet_name="structure_variables"
    )
    keys = set(settings["table_key"])
    xnew = settings[settings["table_key"] == "Xnew"].iloc[0]
    if variant == VARIANT_ACTIVITIES:
        assert "U0" in keys and "Y0" not in keys
        assert xnew["coordinates"] == "activity_to,region_to"
    else:
        assert "Y0" in keys and "U0" not in keys
        assert xnew["coordinates"] == "commodity_from,region_from"


@needs_cvxlab
def test_variant_recovers_the_identified_blocks(solved_variant):
    variant, _, new, truth, _ = solved_variant
    for name in ("S", "Y", "V"):
        solved = getattr(new, name)
        expected = getattr(truth, name).loc[solved.index, solved.columns]
        assert np.abs(solved.to_numpy() - expected.to_numpy()).max() < 1e-3
    if variant == VARIANT_ACTIVITIES:
        # every block has a prior in the activity-only model
        expected = truth.U.loc[new.U.index, new.U.columns]
        assert np.abs(new.U.to_numpy() - expected.to_numpy()).max() < 1e-3
    # (the Use of the split commodity is not identified by the commodity-only model: not compared)


@needs_cvxlab
def test_variant_keeps_parent_plus_children_equal_to_original(solved_variant):
    variant, original, new, _, _ = solved_variant
    children = {"a2b": "a2"} if variant == VARIANT_ACTIVITIES else {"c2b": "c2"}
    for name in ("U", "S", "Y", "V"):
        old, current = getattr(original, name), getattr(new, name)
        current = current.rename(index=children, columns=children)
        current = current.T.groupby(level=[0, 1, 2], sort=False).sum().T
        if current.index.nlevels == 3:  # V has the factors of production as a flat row index
            current = current.groupby(level=[0, 1, 2], sort=False).sum()
        current = current.loc[old.index, old.columns]
        assert np.abs(current.to_numpy() - old.to_numpy()).max() < 1e-3 * max(1.0, np.abs(old.to_numpy()).max())


@needs_cvxlab
def test_commodity_only_split_leaves_emissions_and_value_added_alone(solved_variant):
    variant, original, new, _, _ = solved_variant
    if variant != VARIANT_COMMODITIES:
        pytest.skip("commodity-only check")
    activities = [c for c in original.E.columns if c[1] == "Activity"]
    assert np.allclose(new.E.loc[:, activities].to_numpy(), original.E.loc[:, activities].to_numpy())
    assert np.allclose(new.V.loc[:, activities].to_numpy(), original.V.loc[:, activities].to_numpy(), atol=1e-6)
    assert np.allclose(new.EY.to_numpy(), original.EY.to_numpy())


@needs_cvxlab
@pytest.mark.parametrize("variant", [VARIANT_ACTIVITIES, VARIANT_COMMODITIES])
def test_variant_logs_residuals_and_names_the_variant(variant, tmp_path, caplog):
    db = build_example_database()
    with caplog.at_level(logging.INFO):
        db.add_sectors(io=VARIANT_ADD_SECTOR_PATHS[variant], split=True, cvxlab_path=tmp_path, inplace=False)
    label = "activity-only" if variant == VARIANT_ACTIVITIES else "commodity-only"
    messages = [record.getMessage() for record in caplog.records]
    assert any(f"Largest relative residuals of the {label} split" in m for m in messages)
    assert not any("deviates by" in m for m in messages)


@needs_cvxlab
@pytest.mark.parametrize("variant", [VARIANT_ACTIVITIES, VARIANT_COMMODITIES])
def test_only_input_data_gen_writes_variant_inputs(variant, tmp_path):
    db = build_example_database()
    db.add_sectors(
        io=VARIANT_ADD_SECTOR_PATHS[variant],
        split=True,
        cvxlab_path=tmp_path,
        only_input_data_gen=True,
        inplace=False,
    )
    path = tmp_path / "mario_add_sector_split_sut" / "input_data" / "input_data.xlsx"
    tables = pd.read_excel(path, sheet_name=None)
    assert dict(zip(tables["tol"]["scalar_Name"], tables["tol"]["values"])) == {"delta": 1e-5, "eps": 1e-5}
    if variant == VARIANT_ACTIVITIES:
        assert {"U0", "M0", "V0", "Xnew"} <= set(tables) and "Y0" not in tables
    else:
        assert {"M0", "Y0", "Xnew"} <= set(tables) and "U0" not in tables and "V0" not in tables
