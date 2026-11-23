"""Resume-policy checks that never build or run an optimization problem."""
from copy import deepcopy
import json

import cvxpy as cp
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from mario.ops.add_sector_steps import _validate_resume_model_options
from mario.ops.split_model import MODEL_REVISION, describe_model, normalize_options


def options(**changes):
    return normalize_options(dict(model='Split_sectors_MRIO_quadratic',
                                  accounting='inherit', check_feasibility=True,
                                  feasibility_solver='GUROBI', scale=1000., **changes))


@pytest.mark.parametrize('changes', [
    {'check_feasibility': False}, {'feasibility_solver': 'HIGHS'},
    {'check_feasibility': False, 'feasibility_solver': ['GUROBI', 'HIGHS']},
])
def test_preflight_controls_may_change_without_changing_the_model(changes):
    previous = options()
    original = deepcopy(previous)
    current = {**previous, **changes}
    transition = _validate_resume_model_options(previous, current)
    assert not transition['model_changed']
    assert transition['preflight_changes'] == {
        key: {'previous': previous[key], 'current': value} for key, value in changes.items()}
    assert previous == original
    assert _validate_resume_model_options(current, current)['preflight_changes'] == {}


@pytest.mark.parametrize('key,value', [
    ('accounting', 'strict'), ('scale', 1.), ('final_demand_weight', .2),
    ('solution_cleanup', 'postprocess'), ('require_finite_objective', True),
])
def test_disabling_preflight_does_not_allow_other_control_changes(key, value):
    previous = options()
    current = {**previous, 'check_feasibility': False, key: value}
    with pytest.raises(WrongInput, match='Split model options changed'):
        _validate_resume_model_options(previous, current, allow_model_change=True)


def test_objective_changes_still_require_explicit_permission():
    previous = options()
    current = normalize_options(dict(model='Split_sectors_MRIO_KL', accounting='inherit',
                                     check_feasibility=False, feasibility_solver='GUROBI', scale=1000.))
    with pytest.raises(WrongInput, match='Split model options changed'):
        _validate_resume_model_options(previous, current)
    transition = _validate_resume_model_options(previous, current, allow_model_change=True)
    assert transition['model_changed']
    assert set(transition['preflight_changes']) == {'check_feasibility'}


@pytest.mark.parametrize('reverse', [False, True])
def test_preflight_exception_does_not_allow_switching_historical_models(reverse):
    previous, current = None, options()
    if reverse:
        previous, current = current, previous
    with pytest.raises(WrongInput, match='historical and named models'):
        _validate_resume_model_options(previous, current, allow_model_change=True)


def test_failed_retry_records_the_preflight_change_without_running_a_solver(tmp_path, monkeypatch):
    from tests.ops.test_add_sector_steps import balanced_database, workbook
    db = balanced_database()
    before = db.Z.copy()
    source = workbook(db, tmp_path/'inputs.xlsx')
    previous = options()
    state = dict(completed_sectors=['Stable'], split_model_options=previous,
                 split_model_revision=MODEL_REVISION, model_definition=describe_model(previous, staged=True))
    db._intermediate_steps_state = deepcopy(state)
    original = mario.Database.add_sectors
    attempted = []

    def fail_candidate(self, *args, **kwargs):
        if not kwargs.get('intermediate_steps'):
            attempted.append(set(self.add_sectors_master.Sector))
            raise cp.error.SolverError('Synthetic failure before any solver call')
        return original(self, *args, **kwargs)

    def forbid_solver(*args, **kwargs):
        raise AssertionError('This test must not run a solver')

    monkeypatch.setattr(mario.Database, 'add_sectors', fail_candidate)
    monkeypatch.setattr(cp.Problem, 'solve', forbid_solver)
    root = tmp_path/'retry'
    db.add_sectors(source, split=True, intermediate_steps=True,
                   save_intermediates=root, on_step_failure='continue',
                   split_model_options={**previous, 'check_feasibility': False})
    report = json.loads((root/'run_report.json').read_text())
    assert len(attempted) == 2
    assert report['status'] == 'partial'
    assert report['preflight_options']['check_feasibility'] is False
    assert report['preflight_option_changes'] == {
        'check_feasibility': {'previous': True, 'current': False}}
    assert db._intermediate_steps_state == state
    assert db.Z.equals(before)
    assert not list(root.glob('*/state.json'))
