"""Actual sequential solves, conservative projections and checkpoint recovery."""
from dataclasses import replace
import json
import hashlib

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


def test_payload_writer_preserves_standard_pandas_workbook_contents(tmp_path, monkeypatch):
    from zipfile import ZipFile
    from mario.ops import add_sector_steps as steps
    source = workbook(balanced_database(), tmp_path / 'source.xlsx')
    payload = read_add_sector_workbook(source, table='IOT', require_inventory_sheets=True)
    reference, optimized = tmp_path / 'reference.xlsx', tmp_path / 'optimized.xlsx'
    with monkeypatch.context() as patch:
        patch.setattr(steps, '_SectorWorkbookWriter',
                      lambda path: pd.ExcelWriter(path, engine='openpyxl'))
        steps.write_workbook_payload(payload, reference)
    steps.write_workbook_payload(payload, optimized)
    with ZipFile(reference) as before, ZipFile(optimized) as after:
        assert before.namelist() == after.namelist()
        # Creation timestamps may differ; cell XML, types, styles, relationships
        # and the intermediate plan must remain identical to the prior writer.
        assert all(before.read(n) == after.read(n) for n in before.namelist()
                   if n != 'docProps/core.xml')


@pytest.mark.parametrize('layout',['database','.'])
def test_checkpoint_database_layout_preserves_independent_outputs(tmp_path,layout):
    db=balanced_database()
    db.matrices['baseline']['X']=db.X+.01
    directory=tmp_path/layout
    db.to_parquet(path=directory,flows=True,coefficients=False,include_meta=True)
    state=dict(format='mario-sector-steps-v1',status='complete',split_model_options={'accounting':'inherit'},
               files={str(p.relative_to(tmp_path)):hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in directory.rglob('*') if p.is_file()})
    if layout=='.':state['database_directory']='.'
    (tmp_path/'state.json').write_text(json.dumps(state))
    reloaded=load_checkpoint(tmp_path)
    pd.testing.assert_frame_equal(reloaded.X,db.X)
    with (directory/'flows/X.parquet').open('ab') as stream:stream.write(b'changed')
    with pytest.raises(WrongInput,match='Checkpoint file changed'):
        load_checkpoint(tmp_path)


@pytest.mark.parametrize('directory',['../outside','/tmp',''])
def test_checkpoint_database_directory_cannot_escape_its_root(tmp_path,directory):
    (tmp_path/'state.json').write_text(json.dumps(dict(format='mario-sector-steps-v1',status='complete',
                                                     files={},database_directory=directory)))
    with pytest.raises(WrongInput,match='database directory'):
        load_checkpoint(tmp_path)


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


def test_stop_after_named_step_saves_checkpoint_and_resumable_pending_plan(tmp_path):
    db=balanced_database()
    source=workbook(db,tmp_path/'input.xlsx',second_quantity=1e6)
    checkpoints=tmp_path/'checkpoints'
    for bad in ['Unknown',1]:
        with pytest.raises(WrongInput,match='pending group'):
            db.add_sectors(source,split=True,intermediate_steps=True,save_intermediates=checkpoints,
                           stop_after_step=bad)
    assert not checkpoints.exists()
    with pytest.raises(WrongInput,match='requires intermediate_steps'):
        db.add_sectors(source,stop_after_step='Mine first')
    db.add_sectors(source,split=True,intermediate_steps=True,save_intermediates=checkpoints,
                   stop_after_step='Mine first',solver='CLARABEL',
                   solver_parameters={'tol_gap_abs':1e-9,'tol_feas':1e-9,'tol_gap_rel':1e-9})
    first=checkpoints/'001_Mine_first'
    restored=load_checkpoint(first)
    assert 'Mining' in restored.get_index('Sector') and 'Refining' not in restored.get_index('Sector')
    pending=read_add_sector_workbook(first/'remaining_add_sectors.xlsx',table='IOT')
    assert pending.intermediate_steps=={'Refine second':['Refining']}
    assert set(pending.master_sheet.Sector)=={'Refining'}
    assert len(list(checkpoints.iterdir()))==1


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


def test_deferred_E_is_explicit_and_does_not_disable_monetary_preservation():
    from mario.ops.split_model import normalize_options
    db = balanced_database()
    changed = db.copy()
    e = changed.E.copy()
    e.iloc[0,0] += 100.
    changed.update_scenarios('baseline',E=e)
    with pytest.raises(WrongInput,match='preserve preceding E'):
        verify_preservation(db,changed,{})
    options = normalize_options({'defer_satellite_recalculation':True})
    report = verify_preservation(db,changed,{},split_model_options=options)
    assert report['E'] == {'passed':None,'enforced':False,'status':'deferred','requires_recalculation':True}
    assert all(record['passed'] for name,record in report.items() if name!='E')
    v = changed.V.copy()
    v.iloc[0,0] += 1.
    changed.update_scenarios('baseline',V=v)
    with pytest.raises(WrongInput,match='preserve preceding V'):
        verify_preservation(db,changed,{},split_model_options=options)


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


@pytest.mark.parametrize('compact',[False,True])
@pytest.mark.parametrize('loss',['kl','quadratic'])
@pytest.mark.parametrize('defer_e',[False,True])
def test_inherited_accounting_signed_priors_and_scaling_across_two_steps(tmp_path,compact,loss,defer_e):
    """Preserve a nonclosed baseline, signed taxes and stocks without new error."""
    db = balanced_database()
    supplied_output = db.X.copy()
    v = db.V.copy()
    v.loc['Value added'] += 2.
    v.loc['Value added',('R1','Sector','Parent')] += .25
    v.loc['Tax'] = -2.
    import copy
    units = copy.deepcopy(db.units)
    units['Factor of production'].loc['Tax','unit'] = 'M USD'
    y = db.Y.copy()
    y.iloc[0] = [-2.,42.125]
    db = mario.Database(name='Inherited signed fixture',table='IOT',Z=db.Z,Y=y,V=v,E=db.E,EY=db.EY,units=units)
    db.reset_to_flows('baseline')
    db.matrices['baseline']['X'] = supplied_output
    source = workbook(db,tmp_path/'input.xlsx')
    frames = pd.read_excel(source,sheet_name=None)
    coefficient = float(db.v.loc['Tax',('R1','Sector','Parent')])
    for name,frame in frames.items():
        if name.startswith('INV_'):
            # Child source priors are balanced; the supplied parent discrepancy
            # remains in the baseline and is allocated explicitly by the model.
            frame.loc[frame['Item type'].eq('Factor of production'),'Quantity'] -= .25/84.
            frame.loc[len(frame)] = [coefficient,'M USD','Tax','Factor of production','Tax',None,'Update']
            if defer_e:
                # Deliberately inconsistent satellites must not block the
                # monetary split when they will be rebuilt afterwards.
                frame.loc[len(frame)] = [1.,'tonne','CO2','Satellite account','CO2',None,'Update']
    with pd.ExcelWriter(source,engine='openpyxl') as writer:
        for name,frame in frames.items():
            frame.to_excel(writer,sheet_name=name,index=False)
    options = dict(accounting='inherit',value_added_loss='signed_kl',final_demand_weight=.1,
                   complete_intermediate_priors=True,check_feasibility=True,scale=10.,compact_constraints=compact,
                   defer_satellite_recalculation=defer_e)
    if loss=='quadratic':
        options.update(value_added_loss='quadratic',flow_loss='quadratic')
    with pytest.raises(WrongInput,match='feasibility check returned infeasible'):
        db.add_sectors(source,split=True,intermediate_steps=True,inplace=False,
                       save_intermediates=tmp_path/'strict',solver='CLARABEL',
                       split_model_options=dict(check_feasibility=True,scale=10.))
    solve = dict(split=True,intermediate_steps=True,inplace=False,
                 save_intermediates=tmp_path/'checkpoints',solver='CLARABEL',split_model_options=options,
                 solver_parameters={'tol_gap_abs':1e-10,'tol_feas':1e-11,'tol_gap_rel':1e-10,
                                    'static_regularization_constant':1e-11,
                                    'dynamic_regularization_delta':2e-9,'max_iter':600})
    partial = db.add_sectors(source,stop_after_step='Mine first',**solve)
    if loss == 'quadratic' and not compact and not defer_e:
        historical = partial.copy()
        historical._intermediate_steps_state.pop('split_model_revision')
        with pytest.raises(WrongInput, match='factor domains changed'):
            historical.add_sectors(source, **solve)
        changed_definition = partial.copy()
        changed_definition._intermediate_steps_state['model_definition']['source_sha256'] = {}
        with pytest.raises(WrongInput, match='model definition changed'):
            changed_definition.add_sectors(source, **solve)
    if not defer_e and loss=='quadratic' and compact:
        # A strict checkpoint written before the new option has the same
        # meaning as its current default False and remains resumable.
        path = tmp_path/'checkpoints/001_Mine_first/state.json'
        old_state = json.loads(path.read_text())
        old_state['split_model_options'].pop('defer_satellite_recalculation')
        old_state.pop('pending_recalculations')
        path.write_text(json.dumps(old_state))
    reloaded = load_checkpoint(tmp_path/'checkpoints/001_Mine_first')
    pd.testing.assert_frame_equal(reloaded.X,partial.X)
    result = reloaded.add_sectors(source,**solve)
    normalized = result._intermediate_steps_state['split_model_options']
    report = verify_preservation(db,result,{'Mining':'Parent','Refining':'Parent'},split_model_options=normalized)
    assert all(record['passed'] for name,record in report.items() if name!='E' or not defer_e)
    assert report['E']['passed'] is (None if defer_e else True)
    assert report['new_sector_column_accounting']['max_absolute_inherited_residual']>0
    assert report['inherited_row_accounting']['max_absolute_inherited_residual']>0
    assert float(db.V.loc['Tax',('R1','Sector','Parent')])==-2.
    for sector in ('Parent','Mining','Refining'):
        assert float(result.V.loc['Tax',('R1','Sector',sector)])<0
        assert float(result.Y.loc[('R1','Sector',sector)].iloc[0])<=1e-6
    restored = load_checkpoint(tmp_path/'checkpoints/002_Refine_second')
    pd.testing.assert_frame_equal(restored.X,result.X)
    assert restored._intermediate_steps_state['pending_recalculations'] == (['E'] if defer_e else [])
    with pytest.raises(WrongInput,match='options changed'):
        restored.add_sectors(source,split=True,intermediate_steps=True,save_intermediates=tmp_path/'forbidden')
