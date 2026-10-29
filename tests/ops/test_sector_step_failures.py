"""A failed candidate stays in its parent while independent steps can proceed."""
import hashlib
import json

import cvxpy as cp
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from mario.ops.add_sector_steps import load_checkpoint, verify_preservation
from mario.ops.add_sector_workbook import read_add_sector_workbook
from tests.ops.test_add_sector_steps import balanced_database, workbook


def options(root, **extra):
    return dict(split=True, intermediate_steps=True, save_intermediates=root,
        solver='GUROBI', solver_parameters={'Threads':2,'OutputFlag':0},
        split_model_options=dict(model='Split_sectors_MRIO_quadratic',accounting='inherit',
                                 compact_constraints=True,defer_satellite_recalculation=True,scale=10.), **extra)


def inject_failure(monkeypatch, failed, *, error=None):
    original = mario.Database.add_sectors
    attempted = []

    def add(self, *args, **kwargs):
        if not kwargs.get('intermediate_steps'):
            active = set(self.add_sectors_master.Sector)
            attempted.append(active)
            if active & set(failed):
                # A solver/engine may mutate its candidate before failing.
                z = self.Z.copy();z.iloc[0,0] += 1000.
                self.update_scenarios('baseline',Z=z)
                raise error or cp.error.SolverError('Synthetic numerical failure')
        return original(self, *args, **kwargs)

    monkeypatch.setattr(mario.Database, 'add_sectors', add)
    return attempted


def source_with_deferred_supplier(db, path):
    source = workbook(db,path)
    frames = pd.read_excel(source,sheet_name=None)
    name=frames['Master'].loc[frames['Master'].Sector.eq('Refining'),'Inventory sheet'].iloc[0]
    frame=frames[name]
    frame.loc[0,'Quantity'] -= .01
    frame.loc[len(frame)] = [.01,'M USD','Mining input','Sector','Mining','R1','Update']
    with pd.ExcelWriter(source,engine='openpyxl') as writer:
        for name,frame in frames.items():frame.to_excel(writer,sheet_name=name,index=False)
    return source


def test_continue_projects_failed_supplier_then_resume_restores_fine_prior(tmp_path,monkeypatch):
    if 'GUROBI' not in cp.installed_solvers():pytest.skip('Gurobi is optional')
    db=balanced_database();before=db.copy()
    source=source_with_deferred_supplier(db,tmp_path/'inputs.xlsx')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    root=tmp_path/'steps'
    with monkeypatch.context() as patch:
        attempted=inject_failure(patch,{'Mining'})
        result=db.add_sectors(source,inplace=False,**options(root,on_step_failure='continue'))
    assert attempted==[{'Mining'},{'Refining'}]
    assert set(result.get_index('Sector'))=={'Parent','Stable','Refining'}
    for name in ['Z','Y','V','E','X','EY','VY']:
        pd.testing.assert_frame_equal(db.resolve(name),before.resolve(name),check_exact=True)
    assert result.X.loc[('R1','Sector','Parent')].iloc[0]==pytest.approx(before.X.loc[('R1','Sector','Parent')].iloc[0]-8.4)
    state=result._intermediate_steps_state
    assert state['completed_sectors']==['Refining'] and state['deferred_sectors']==['Mining']
    report=json.loads((root/'run_report.json').read_text())
    assert report['status']=='partial' and report['pending_sectors']==['Mining']
    assert [a['status'] for a in report['attempts']]==['failed','accepted']
    checkpoint=root/'002_Refine_second'
    compiled=read_add_sector_workbook(checkpoint/'step_add_sectors.xlsx',table='IOT')
    assert all('Mining' not in set(frame['DB Item']) for frame in compiled.inventories_by_sheet.values())
    pending=read_add_sector_workbook(checkpoint/'remaining_add_sectors.xlsx',table='IOT')
    assert set(pending.master_sheet.Sector)=={'Mining'}
    restored=load_checkpoint(checkpoint)
    restored.add_sectors(source,**options(root,on_step_failure='continue'))
    assert restored._intermediate_steps_state['deferred_sectors']==[]
    assert restored._intermediate_steps_state['refinement_prior_cells']>0
    assert set(restored.get_index('Sector'))=={'Parent','Stable','Mining','Refining'}
    assert json.loads((root/'run_report.json').read_text())['status']=='complete'
    assert len(list(root.glob('run_report_*.json')))==2
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    report=verify_preservation(before,restored,{'Mining':'Parent','Refining':'Parent'},
        split_model_options=restored._intermediate_steps_state['split_model_options'])
    assert all(r['passed'] for n,r in report.items() if n!='E')


@pytest.mark.parametrize('explicit',[False,True])
def test_default_and_explicit_raise_stop_without_mutating_the_database(tmp_path,monkeypatch,explicit):
    db=balanced_database();original=db.copy();source=workbook(db,tmp_path/'inputs.xlsx')
    attempted=inject_failure(monkeypatch,{'Mining'})
    kwargs={'on_step_failure':'raise'} if explicit else {}
    with pytest.raises(cp.error.SolverError):
        db.add_sectors(source,**options(tmp_path/'steps',**kwargs))
    assert attempted==[{'Mining'}]
    for name in ['Z','Y','V','X']:
        pd.testing.assert_frame_equal(db.resolve(name),original.resolve(name),check_exact=True)
    assert json.loads((tmp_path/'steps/run_report.json').read_text())['status']=='failed'


def test_last_failure_is_reported_after_the_last_accepted_checkpoint(tmp_path,monkeypatch):
    if 'GUROBI' not in cp.installed_solvers():pytest.skip('Gurobi is optional')
    db=balanced_database();source=workbook(db,tmp_path/'inputs.xlsx');root=tmp_path/'steps'
    attempted=inject_failure(monkeypatch,{'Refining'})
    db.add_sectors(source,**options(root,on_step_failure='continue'))
    report=json.loads((root/'run_report.json').read_text())
    assert attempted==[{'Mining'},{'Refining'}]
    assert report['completed_sectors']==['Mining'] and report['deferred_sectors']==['Refining']
    assert report['attempts'][-1]['status']=='failed'
    assert set(load_checkpoint(root/'001_Mine_first').get_index('Sector'))==set(db.get_index('Sector'))


@pytest.mark.parametrize('grouped',[False,True])
def test_all_failures_are_one_pass_and_groups_remain_atomic(tmp_path,monkeypatch,grouped):
    db=balanced_database();original=db.copy();source=workbook(db,tmp_path/'inputs.xlsx')
    if grouped:
        with pd.ExcelWriter(source,engine='openpyxl',mode='a',if_sheet_exists='replace') as writer:
            pd.DataFrame({'Together':['Mining','Refining']}).to_excel(writer,sheet_name='Intermediate steps',index=False)
    attempted=inject_failure(monkeypatch,{'Mining','Refining'})
    db.add_sectors(source,**options(tmp_path/'steps',on_step_failure='continue'))
    assert len(attempted)==(1 if grouped else 2)
    for name in ['Z','Y','V','X']:
        pd.testing.assert_frame_equal(db.resolve(name),original.resolve(name),check_exact=True)
    report=db._intermediate_steps_report
    assert report['completed_sectors']==[] and report['deferred_sectors']==['Mining','Refining']
    assert report['status']=='partial'
    assert not list((tmp_path/'steps').glob('*/state.json'))


def test_a_child_of_a_failed_parent_is_blocked_without_calling_the_solver(tmp_path,monkeypatch):
    db=balanced_database();source=workbook(db,tmp_path/'inputs.xlsx')
    master=pd.read_excel(source,sheet_name='Master')
    master.loc[master.Sector.eq('Refining'),'Parent Sector']='Mining'
    with pd.ExcelWriter(source,engine='openpyxl',mode='a',if_sheet_exists='replace') as writer:
        master.to_excel(writer,sheet_name='Master',index=False)
    attempted=inject_failure(monkeypatch,{'Mining'})
    db.add_sectors(source,**options(tmp_path/'steps',on_step_failure='continue'))
    assert attempted==[{'Mining'}]
    assert [a['status'] for a in db._intermediate_steps_report['attempts']]==['failed','blocked']


def test_stop_boundary_applies_even_when_the_named_step_fails(tmp_path,monkeypatch):
    db=balanced_database();source=workbook(db,tmp_path/'inputs.xlsx')
    attempted=inject_failure(monkeypatch,{'Mining'})
    db.add_sectors(source,stop_after_step='Mine first',**options(tmp_path/'steps',on_step_failure='continue'))
    assert attempted==[{'Mining'}]
    assert db._intermediate_steps_report['deferred_sectors']==['Mining']
    assert db._intermediate_steps_report['pending_sectors']==['Mining','Refining']


@pytest.mark.parametrize('error',[RuntimeError('Programming error'),WrongInput('Invalid inventory schema')])
def test_unexpected_errors_still_raise_under_continue(tmp_path,monkeypatch,error):
    db=balanced_database();source=workbook(db,tmp_path/'inputs.xlsx')
    attempted=inject_failure(monkeypatch,{'Mining'},error=error)
    with pytest.raises(type(error),match=str(error)):
        db.add_sectors(source,**options(tmp_path/'steps',on_step_failure='continue'))
    assert attempted==[{'Mining'}]
    assert db._intermediate_steps_report['status']=='failed'


@pytest.mark.parametrize('value',[None,True,False,1,'skip',[]])
def test_policy_validation_happens_before_any_work(value,tmp_path):
    with pytest.raises(WrongInput,match='on_step_failure'):
        balanced_database().add_sectors(on_step_failure=value)
    assert not list(tmp_path.iterdir())


def test_continue_requires_intermediate_steps():
    with pytest.raises(WrongInput,match='requires intermediate_steps'):
        balanced_database().add_sectors(on_step_failure='continue')
