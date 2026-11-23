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


def _problem_and_variables(name):
    workbook = openpyxl.load_workbook(MODELS_DIR / name / "model_settings.xlsx")
    return _sheet(workbook, "structure_variables"), _sheet(workbook, "problem")


def test_split_sut_model_has_the_use_prior_of_the_new_commodities():
    variables, problem = _problem_and_variables("Split_sut")
    by_name = variables.set_index("variables_info")
    for name, columns in (("U0_pn_s", "stable"), ("U0_pn_p", "parent"), ("U_pn_p", "parent")):
        row = by_name.loc[name]
        assert row["commodity_from"] == "dim: rows, filters: {category: [parent, new]}"
        assert row["activity_to"] == f"dim: cols, filters: {{category: [{columns}]}}"
    assert by_name.loc["U0_pn_s", "table_key"] == by_name.loc["U0_pn_p", "table_key"] == "U0"
    assert by_name.loc["U0_pn_s", "type"] == "exogenous" and by_name.loc["U_pn_p", "type"] == "endogenous"
    objective = problem["objective"].dropna().iloc[0]
    assert "kl_active(U_pn_s,U0_pn_s)" in objective and "kl_active(U_pn_p,U0_pn_p)" in objective
    # the existing terms are untouched
    assert "kl(U_s_p,U0_s_p)" in objective and "kl(U_c_n,U0_c_n)" in objective
    assert "kl_signed(V,V0)" in objective and "kl_signed(Y,Y0)" in objective
    assert "entropy" not in objective  # complete Kullback-Leibler distance everywhere


def test_split_sut_com_model_has_the_use_prior_of_the_new_commodities():
    variables, problem = _problem_and_variables("Split_sut_com")
    row = variables.set_index("variables_info").loc["U0_pn"]
    assert row["table_key"] == "U0" and row["type"] == "exogenous"
    assert row["coordinates"] == "commodity_from,region_from,activity_to,region_to"
    assert row["commodity_from"] == "dim: rows, filters: {category: [parent, new]}"
    assert row["activity_to"] == "dim: cols"
    objective = problem["objective"].dropna().iloc[0]
    assert "kl_active(U_pn,U0_pn)" in objective and "kl(M_pn,M0_pn)" in objective
    assert "kl_signed(Y_pn,Y0_pn)" in objective and "entropy" not in objective


def test_split_sut_act_model_has_the_complete_kl_objective_and_no_use_prior_of_new_commodities():
    variables, problem = _problem_and_variables("Split_sut_act")
    objective = problem["objective"].dropna().iloc[0]
    assert objective == "Minimize(sum(kl(U_pn,U0_pn))+sum(kl(M_pn,M0_pn))+sum(kl_signed(V_pn,V0_pn)))"
    assert "kl_active" not in objective and "entropy" not in objective
    assert not any(str(name).startswith("U0_pn_") for name in variables["variables_info"])


@pytest.mark.parametrize("name", ["Split_sut", "Split_sut_com", "Split_sut_act"])
def test_kl_active_leaves_zero_prior_cells_out_of_the_objective(name):
    cp = pytest.importorskip("cvxpy")
    spec = importlib.util.spec_from_file_location(f"{name}_operators", MODELS_DIR / name / "user_defined_operators.py")
    operators = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(operators)

    prior = np.array([[0.0, 2.0], [3.0, 0.0]])
    A, A0 = cp.Variable((2, 2), nonneg=True), cp.Parameter((2, 2), value=prior)
    expression = operators.kl_active(A, A0)
    assert expression.is_dcp()
    A.value = np.array([[5.0, 2.0], [6.0, 7.0]])
    def kl_div(x, y):  # x log(x / y) - x + y: the complete Kullback-Leibler distance
        return x * np.log(x / y) - x + y

    expected = np.array([[0.0, kl_div(2, 2 + 1e-8)], [kl_div(6, 3 + 1e-8), 0.0]])
    np.testing.assert_allclose(expression.value, expected, atol=1e-9)
    # the plain distance would penalise the zero-prior cells
    assert operators.kl(A, A0).value[0, 0] > 50
    # complete KL is zero at the prior and never negative; the incomplete entropy goes negative below the prior
    A.value = prior
    np.testing.assert_allclose(operators.kl(A, A0).value, 0.0, atol=1e-6)
    A.value = 0.5 * prior
    assert (operators.kl(A, A0).value >= 0).all()
    assert (operators.entropy(A, A0).value < 0).any()
    with pytest.raises(ValueError, match="same shape"):
        operators.kl_active(cp.Variable((3, 3)), A0)


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
    # U0 only carries the new-commodity rows of the Use matrix; there is no value-added prior
    assert priors.U0 is not None and priors.V0 is None
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


def test_commodity_only_use_prior_splits_the_parent_rows(com_priors):
    _, priors, _ = com_priors
    U0, original = priors.U0, priors.original.U
    for region in ("DE", "IT"):
        rows = [(region, "c2"), (region, "c2b")]
        # no activity is split: every column is a stable one and the group adds up to the original row
        assert U0.loc[rows].sum().to_numpy() == pytest.approx(original.loc[(region, "c2")].reindex(U0.columns).to_numpy())
        share = priors.Xc[(region, "c2b")] / priors.original.Xc[(region, "c2")]
        assert U0.loc[(region, "c2b")].to_numpy() == pytest.approx(share * original.loc[(region, "c2")].to_numpy())


def test_commodity_only_use_coef_is_applied(tmp_path):
    def add(sheets):
        sheets["Use coef"] = _use_coef_sheet()

    path = write_modified_workbook(VARIANT_ADD_SECTOR_PATHS[VARIANT_COMMODITIES], tmp_path, add)
    db = _read(VARIANT_COMMODITIES, path)
    prepare_sut_split_support(db)
    priors = build_sut_split_priors(db)
    assert priors.U0.loc[("DE", "c2b"), ("DE", "a1")] == pytest.approx(0.1 * priors.Xa[("DE", "a1")])


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


def test_commodity_only_bridge_hands_only_informed_use_cells_to_the_model(com_priors, tmp_path):
    _, priors, _ = com_priors
    columns = ["commodity_from_Name", "region_from_Name", "activity_to_Name", "region_to_Name"]
    cells = [("c2b", "DE", "a1", "DE"), ("c2", "DE", "a2", "IT"), ("c2b", "IT", "a1", "DE")]

    def filled(p):
        return build_sut_split_input_tables(p, {"U0": _blank(columns, cells)})["U0"].set_index(columns)["values"]

    # no coefficient: the baseline is only a guess, the model gets no prior for these cells
    assert (filled(priors) == 0).all()
    assert priors.U0.loc[("DE", "c2b"), ("DE", "a1")] > 0  # ... although the full prior keeps it

    def add(sheets):
        sheets["Use coef"] = _use_coef_sheet()

    path = write_modified_workbook(VARIANT_ADD_SECTOR_PATHS[VARIANT_COMMODITIES], tmp_path, add)
    db = _read(VARIANT_COMMODITIES, path)
    prepare_sut_split_support(db)
    informed = build_sut_split_priors(db)
    values = filled(informed)
    assert values[("c2b", "DE", "a1", "DE")] == pytest.approx(0.1 * informed.Xa[("DE", "a1")])
    assert values[("c2", "DE", "a2", "IT")] == 0 and values[("c2b", "IT", "a1", "DE")] == 0


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
        # the commodity-only model has a prior for the Use of the new commodities (no value-added prior)
        assert "Y0" in keys and "U0" in keys and "V0" not in keys
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
        assert {"M0", "Y0", "U0", "Xnew"} <= set(tables) and "V0" not in tables


def _use_coef_sheet():
    return pd.DataFrame(
        [["DE", "DE", "c2b", "a1", 0.1, None, None]],
        columns=["Region_from", "Region_to", "Commodity_from", "Activity_to", "Coefficient", "Source", "Notes"],
    )


def test_use_coef_sheet_is_optional_in_every_variant():
    for variant in (VARIANT_ACTIVITIES, VARIANT_COMMODITIES):
        assert _read(variant).split_info["Use coef"].empty


def test_commodity_only_split_keeps_use_coef(tmp_path):
    def add(sheets):
        sheets["Use coef"] = _use_coef_sheet()

    path = write_modified_workbook(VARIANT_ADD_SECTOR_PATHS[VARIANT_COMMODITIES], tmp_path, add)
    db = _read(VARIANT_COMMODITIES, path)
    prepare_sut_split_support(db)
    assert len(db.split_info["Use coef"]) == 1


def test_activity_only_split_ignores_use_coef_with_a_warning(tmp_path):
    def add(sheets):
        sheets["Use coef"] = _use_coef_sheet()

    path = write_modified_workbook(VARIANT_ADD_SECTOR_PATHS[VARIANT_ACTIVITIES], tmp_path, add)
    db = _read(VARIANT_ACTIVITIES, path)
    with pytest.warns(UserWarning, match="Use coef.*ignored"):
        prepare_sut_split_support(db)
    assert db.split_info["Use coef"].empty


@pytest.mark.parametrize("name", ["Split_sut", "Split_sut_com", "Split_sut_act"])
def test_sut_models_use_the_complete_kl_distance_everywhere(name):
    _, problem = _problem_and_variables(name)
    objective = problem["objective"].dropna().iloc[0]
    assert "entropy" not in objective and "kl(" in objective and "kl_signed(" in objective


@pytest.mark.parametrize("name", ["Split_sut", "Split_sut_com", "Split_sut_act"])
def test_kl_and_kl_signed_operators(name):
    cp = pytest.importorskip("cvxpy")
    spec = importlib.util.spec_from_file_location(f"{name}_ops", MODELS_DIR / name / "user_defined_operators.py")
    operators = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(operators)

    prior = np.array([[2.0, -3.0], [4.0, 0.0]])
    A = cp.Variable((2, 2))
    A0 = cp.Parameter((2, 2), value=prior)
    A.value = np.array([[3.0, -2.0], [1.0, 1.0]])
    kl_div = lambda x, y: x * np.log(x / y) - x + y
    plain = operators.kl(cp.Variable((2, 2), nonneg=True), A0)
    assert plain.is_dcp()
    signed = operators.kl_signed(A, A0)
    assert signed.is_dcp()
    # the sign of the prior is kept: a negative prior is compared with -A
    expected = np.array(
        [[kl_div(3.0, 2.0 + 1e-8), kl_div(2.0, 3.0 + 1e-8)], [kl_div(1.0, 4.0 + 1e-8), kl_div(1.0, 1e-8)]]
    )
    np.testing.assert_allclose(signed.value, expected, atol=1e-9)
    # zero at the prior (complete distance), whatever the sign
    A.value = prior
    np.testing.assert_allclose(operators.kl_signed(A, A0).value, 0.0, atol=1e-6)
    with pytest.raises(ValueError, match="same shape"):
        operators.kl_signed(cp.Variable((3, 3)), A0)
