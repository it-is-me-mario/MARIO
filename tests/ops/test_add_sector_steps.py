"""Actual sequential solves, conservative projections and checkpoint recovery."""
from dataclasses import replace
import json

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from mario.ops.add_sector_steps import (
    compile_step, load_checkpoint, validate_plan, verify_preservation,
)
from mario.ops.add_sector_workbook import read_add_sector_workbook


def balanced_database():
    index = pd.MultiIndex.from_product([["R1", "R2"], ["Sector"], ["Parent", "Stable"]],
                                       names=["Region", "Level", "Item"])
    demand = pd.MultiIndex.from_product([["R1", "R2"], ["Consumption category"], ["Households"]], names=index.names)
    z = pd.DataFrame([[20, 15, 4, 5], [10, 54, 5, 5], [5, 5, 18, 11], [3, 5, 9, 41]], index=index, columns=index, dtype=float)
    y = pd.DataFrame([[15, 25], [20, 45], [15, 30], [35, 30]], index=index, columns=demand, dtype=float)
    v = pd.DataFrame([[46, 60, 48, 61]], index=["Value added"], columns=index, dtype=float)
    e = pd.DataFrame([[10, 5, 20, 10]], index=["CO2"], columns=index, dtype=float)
    ey = pd.DataFrame([[4, 2]], index=e.index, columns=demand, dtype=float)
    units = {kind: pd.DataFrame({"unit": [unit] * len(labels)}, index=labels) for kind, labels, unit in (
        ("Sector", ["Parent", "Stable"], "M USD"),
        ("Factor of production", ["Value added"], "M USD"), ("Satellite account", ["CO2"], "tonne"))}
    return mario.Database(name="Balanced step fixture", table="IOT", Z=z, Y=y, V=v, E=e, EY=ey, units=units)


def workbook(db, path, *, second_quantity=8.4):
    db.get_add_sectors_excel(path=path, items=["Mining", "Refining"], regions=["R1"], intermediate_steps=True)
    master = pd.read_excel(path, sheet_name="Master").astype(object)
    master["Parent Sector"] = "Parent"
    master["Unit"] = "M USD"
    master["Add or Split"] = "Split"
    column = ("R1", "Sector", "Parent")
    rows = [[float(value), "M USD", item, kind, item, region, "Update"]
            for (region, kind, item), value in db.z[column].items()]
    rows.append([float(db.v[column].iloc[0]), "M USD", "Value added", "Factor of production", "Value added", None, "Update"])
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        master.to_excel(writer, sheet_name="Master", index=False)
        for i, sheet in enumerate(master["Inventory sheet"]):
            values = [list(row) for row in rows]
            if i == 0:
                # Mining already knows it buys a future refining product.
                values[0][0] -= .01
                values.append([.01, "M USD", "Refining input", "Sector", "Refining", "R1", "Update"])
            pd.DataFrame(values, columns=["Quantity", "Unit", "Input", "Item type", "DB Item", "DB Region", "Change type"]).to_excel(writer, sheet_name=sheet, index=False)
        pd.DataFrame({"Mine first": ["Mining"], "Refine second": ["Refining"]}).to_excel(writer, sheet_name="Intermediate steps", index=False)
        pd.DataFrame([["Mining", "R1", 8.4, "M USD", "test", None], ["Refining", "R1", second_quantity, "M USD", "test", None]],
                     columns=["Sector", "Region", "Quantity", "Unit", "Source", "Notes"]).to_excel(writer, sheet_name="Total outputs", index=False)
        pd.DataFrame({"tol_Name": ["delta", "eps"], "values": [0.0, 0.0]}).to_excel(writer, sheet_name="Tolerances", index=False)
    return path


def test_template_and_plan_validation(tmp_path):
    db = balanced_database()
    source = workbook(db, tmp_path / "input.xlsx")
    payload = read_add_sector_workbook(source, table="IOT")
    assert list(payload.intermediate_steps) == ["Mine first", "Refine second"]
    assert validate_plan(payload, db.get_index("Sector"))[0][0] == ("Mine first", ["Mining"])
    with pytest.raises(WrongInput, match="exactly once"):
        validate_plan(replace(payload, intermediate_steps={"bad": ["Mining", "Mining"]}), db.get_index("Sector"))
    with pytest.raises(WrongInput, match="mandatory"):
        db.add_sectors(source, split=True, intermediate_steps=True)
    assert set(db.get_index("Sector")) == {"Parent", "Stable"}


def test_future_inputs_are_projected_and_summed_without_mutating_source(tmp_path):
    db = balanced_database()
    payload = read_add_sector_workbook(workbook(db, tmp_path / "input.xlsx"), table="IOT")
    name = payload.master_sheet.loc[payload.master_sheet.Sector.eq("Mining"), "Inventory sheet"].iloc[0]
    frame = payload.inventories_by_sheet[name].copy()
    extra = frame.iloc[[0]].copy()
    extra["DB Item"] = "Refining"
    extra["Quantity"] = 0.01
    inventories = dict(payload.inventories_by_sheet)
    inventories[name] = pd.concat([frame, extra], ignore_index=True)
    payload = replace(payload, inventories_by_sheet=inventories)
    compiled = compile_step(payload, ["Mining"], db.get_index("Sector"), {"Mining": "Parent", "Refining": "Parent"})
    result = compiled.inventories_by_sheet[name]
    assert "Refining" not in set(result["DB Item"])
    coordinate = result["DB Item"].eq("Parent") & result["DB Region"].eq(extra["DB Region"].iloc[0])
    assert result.loc[coordinate, "Quantity"].iloc[0] == pytest.approx(float(frame.iloc[0].Quantity) + .02)
    assert "Refining" in set(payload.inventories_by_sheet[name]["DB Item"])


def test_failed_second_solve_keeps_first_checkpoint_and_can_resume(tmp_path):
    db = balanced_database()
    original = db.copy()
    source = workbook(db, tmp_path / "input.xlsx", second_quantity=1e6)
    checkpoints = tmp_path / "checkpoints"
    with pytest.raises(Exception):
        db.add_sectors(source, split=True, intermediate_steps=True, save_intermediates=checkpoints,
                       solver="CLARABEL", solver_parameters={"tol_gap_abs": 1e-9, "tol_feas": 1e-9, "tol_gap_rel": 1e-9})
    first = checkpoints / "001_Mine_first"
    assert (first / "state.json").exists()
    assert "Mining" in db.get_index("Sector")
    assert "Refining" not in db.get_index("Sector")
    assert all(v["passed"] for v in verify_preservation(original, db, {"Mining": "Parent"}).values())
    resumed = load_checkpoint(first)
    pending = first / "remaining_add_sectors.xlsx"
    frames = pd.read_excel(pending, sheet_name=None)
    assert set(frames["Master"].Sector) == {"Refining"}
    frames["Total outputs"]["Quantity"] = 8.4
    # Save an edited revision outside the immutable checkpoint.
    revision = tmp_path / "revised.xlsx"
    with pd.ExcelWriter(revision, engine="openpyxl") as writer:
        for name, frame in frames.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    resumed.add_sectors(revision, split=True, intermediate_steps=True, save_intermediates=checkpoints,
                        solver="CLARABEL", solver_parameters={"tol_gap_abs": 1e-9, "tol_feas": 1e-9, "tol_gap_rel": 1e-9})
    assert set(resumed.get_index("Sector")) == {"Parent", "Stable", "Mining", "Refining"}
    second = checkpoints / "002_Refine_second"
    reloaded = load_checkpoint(second)
    assert all(v["passed"] for v in verify_preservation(db, reloaded, {"Refining": "Parent"}).values())
    np.testing.assert_allclose(reloaded.X.loc[("R1", "Sector", "Mining")], db.X.loc[("R1", "Sector", "Mining")], atol=1e-6)
    state = json.loads((second / "state.json").read_text())
    assert state["completed_sectors"] == ["Mining", "Refining"]
    assert state["refinement_prior_cells"] > 0
    assert 'Mining' in state['canonical_inventories']
    assert float(reloaded.Z.loc[("R1", "Sector", "Refining"), ("R1", "Sector", "Mining")]) > 1e-4
    assert all(v["passed"] for v in verify_preservation(original, reloaded, {"Mining": "Parent", "Refining": "Parent"}).values())

    # A completed observation cannot be edited by resubmitting the full plan.
    frames = pd.read_excel(source, sheet_name=None)
    frames['INV_001'].loc[0, 'Quantity'] += .1
    changed = tmp_path / 'changed_completed.xlsx'
    with pd.ExcelWriter(changed, engine='openpyxl') as writer:
        for name, frame in frames.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    with pytest.raises(WrongInput, match='Completed sector'):
        load_checkpoint(first).add_sectors(changed, split=True, intermediate_steps=True,
                                          save_intermediates=tmp_path / 'forbidden')


def test_preservation_rejects_an_altered_previous_result():
    db = balanced_database()
    changed = db.copy()
    z = changed.Z.copy()
    z.iloc[0, 0] += 1
    changed.update_scenarios("baseline", Z=z)
    with pytest.raises(WrongInput, match="preserve preceding Z"):
        verify_preservation(db, changed, {})


@pytest.mark.parametrize('negative_inventory', [False, True])
def test_grouped_split_inplace_false_preserves_the_original(tmp_path, negative_inventory):
    db = balanced_database()
    if negative_inventory:
        y = db.Y.copy()
        y.iloc[0] = [-2, 42]  # Retain the row total while allowing negative inventories.
        db.update_scenarios('baseline', Y=y)
    source = workbook(db, tmp_path / 'input.xlsx')
    with pd.ExcelWriter(source, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        pd.DataFrame({'Both together': ['Mining', 'Refining']}).to_excel(writer, sheet_name='Intermediate steps', index=False)
    result = db.add_sectors(source, split=True, intermediate_steps=True, inplace=False,
                            save_intermediates=tmp_path / 'checkpoints', solver='CLARABEL',
                            solver_parameters={'tol_gap_abs': 1e-9, 'tol_feas': 1e-9, 'tol_gap_rel': 1e-9})
    assert set(db.get_index('Sector')) == {'Parent', 'Stable'}
    assert {'Mining', 'Refining'} <= set(result.get_index('Sector'))
    assert (tmp_path / 'checkpoints/001_Both_together/state.json').exists()
    assert all(v['passed'] for v in verify_preservation(db, result, {'Mining': 'Parent', 'Refining': 'Parent'}).values())
    if negative_inventory:
        for sector in ('Parent', 'Mining', 'Refining'):
            assert result.Y.loc[('R1', 'Sector', sector)].iloc[0] <= 1e-6
