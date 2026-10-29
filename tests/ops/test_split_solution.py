"""Optimal MRIO exports retain diagnostics without monetary rejection gates."""
import json
import sqlite3
from types import SimpleNamespace

import cvxpy as cp
import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.ops.split_model import normalize_options, verify_model_solution
from mario.ops.split_solution import effective_validation_options, project_solution


def fixture(tmp_path, scale=1000.):
    raw = {'Z_use': [-.0004, 1.], 'Z_supply': [.00001, 1.], 'Y': [-.00001, -2.],
           'V': [-.000007, -3.], 'V_signed_positive': [-.000001, .000001],
           'V_signed_negative': [.000001, 3.000001]}
    variables = {name: cp.Variable((2, 1), name=name) for name in raw}
    for name, variable in variables.items():
        variable.value = np.array(raw[name]).reshape(2, 1) / scale
    z, supply, y, v, vp, vn = (variables[n] for n in raw)
    constraints = [z >= 0, cp.sum(z) == 1./scale, supply[0] == 0,
                   y[0] >= 0, y[1] <= 0, v[0] >= 0, vp >= 0, vn >= 0,
                   vp[0] == 0, vn[0] == 0, v[1] == vp[1] - vn[1]]
    objective = cp.Minimize(-cp.sum(cp.entr(z)) - cp.sum(cp.entr(supply)) - cp.entr(y[0]))
    problem = SimpleNamespace(constraints=constraints, objective=objective, value=float('inf'),
        status='optimal', solver_stats=SimpleNamespace(solve_time=0.), variables=lambda: list(variables.values()))
    model = SimpleNamespace(core=SimpleNamespace(problem=SimpleNamespace(
        numerical_problems={None: pd.DataFrame([{'problem': problem}])})))
    with sqlite3.connect(tmp_path/'database.db') as conn:
        def save(name, values):
            pd.DataFrame(dict(id=[1, 2], item=['A', 'B'], values=values)).to_sql(name, conn, index=False)
        for name in raw:
            save(name, [None, None])
        for name, values in {'Zero_use_mask': [0, 0], 'Zero_supply_mask': [1, 0],
                'Zero_Y_mask': [0, 0], 'Y0': [1, -2], 'Zero_V_mask': [0, 0],
                'V_nonnegative_mask': [1, 0]}.items():
            save(name, values)
    options = normalize_options(dict(model='Split_sectors_MRIO_KL', scale=scale,
        require_finite_objective=True, solution_cleanup=dict(max_cell_adjustment=.001,
            absolute_tolerance=.01, relative_tolerance=1e-8)))
    return model, variables, options


@pytest.mark.parametrize('scale', [1., 1000.])
def test_cleanup_preserves_signed_values_and_saves_raw_and_cleaned_points(tmp_path, scale):
    model, variables, options = fixture(tmp_path, scale)
    verify_model_solution(model, tmp_path, options)
    np.testing.assert_array_equal(variables['Z_use'].value.ravel()*scale, [0., 1.])
    np.testing.assert_array_equal(variables['Y'].value.ravel()*scale, [0., -2.])
    np.testing.assert_array_equal(variables['V'].value.ravel()*scale, [0., -3.])
    assert variables['Z_supply'].value[0] == 0
    for name in ('V_signed_positive', 'V_signed_negative'):
        assert variables[name].value[0] == 0
    record = json.loads((tmp_path/'model_solution.json').read_text())[0]
    assert record['objective_finite'] and record['failed_constraint_cells'] == 0
    assert record['validation'] == 'approximate_after_cleanup'
    assert not json.loads((tmp_path/'raw_model_solution.json').read_text())[0]['objective_finite']
    audit = json.loads((tmp_path/'solution_cleanup.json').read_text())
    assert audit['status'] == 'accepted_with_cleanup' and not audit['optimality_certified']
    assert not audit['targets_changed'] and not audit['baseline_changed']
    raw = np.load(tmp_path/'returned_solution_scaled.npz')
    cleaned = np.load(tmp_path/'cleaned_solution_scaled.npz')
    index = json.loads((tmp_path/'returned_solution_index.json').read_text())
    key = next(r['array'] for r in index if r['name'] == 'Z_use')
    assert raw[key][0] < 0 and cleaned[key][0] == 0


def test_large_correction_is_rejected_before_any_assignment(tmp_path):
    model, variables, options = fixture(tmp_path)
    variables['Z_use'].value[0] = -.002/options['scale']
    snapshots = {name: var.value.copy() for name, var in variables.items()}
    with pytest.raises(WrongInput, match='max_cell_adjustment'):
        project_solution(model, tmp_path, options)
    for name, variable in variables.items():
        np.testing.assert_array_equal(variable.value, snapshots[name])


def test_cleanup_does_not_bypass_accounting_validation(tmp_path):
    model, variables, options = fixture(tmp_path)
    variables['Z_use'].value[1] = 2./options['scale']
    with pytest.raises(WrongInput, match='constraint cells'):
        verify_model_solution(model, tmp_path, options)
    assert json.loads((tmp_path/'solution_cleanup.json').read_text())['status'] == 'rejected_after_cleanup'
    raw = np.load(tmp_path/'returned_solution_scaled.npz')
    index = json.loads((tmp_path/'returned_solution_index.json').read_text())
    key = next(r['array'] for r in index if r['name'] == 'Z_use')
    assert raw[key][0] < 0  # Failed post-cleanup validation must retain the raw point.


def test_small_residual_is_reported_under_both_acceptance_envelopes(tmp_path):
    model, variables, options = fixture(tmp_path)
    variables['Z_use'].value[1] = 1.005/options['scale']
    verify_model_solution(model, tmp_path, options)
    record = json.loads((tmp_path/'model_solution.json').read_text())[0]
    assert record['failed_constraint_cells'] == 0 and record['strict_failed_constraint_cells'] > 0
    assert record['max_constraint_violation'] == pytest.approx(.005)


@pytest.mark.parametrize('policy', [{}, {'absolute_tolerance': .01},
    dict(max_cell_adjustment=-1, absolute_tolerance=.01, relative_tolerance=1e-8),
    dict(max_cell_adjustment=.001, absolute_tolerance=float('nan'), relative_tolerance=1e-8)])
def test_invalid_cleanup_policy_is_rejected(policy):
    with pytest.raises(WrongInput, match='solution_cleanup'):
        normalize_options(dict(model='Split_sectors_MRIO_KL', solution_cleanup=policy))


def test_cleanup_tolerance_applies_to_monetary_preservation_but_not_fixed_x():
    from mario.ops.add_sector_steps import verify_preservation
    axis = pd.MultiIndex.from_tuples([('R', 'Sector', 'P')], names=['Region', 'Level', 'Item'])
    blocks = {n: pd.DataFrame([[v]], index=axis, columns=axis)
              for n, v in {'Z': 1., 'Y': 9., 'V': 9., 'X': 10., 'EY': 0., 'VY': 0.}.items()}
    before = SimpleNamespace(resolve=lambda name, **kwargs: blocks[name])
    result = {n: frame.copy() for n, frame in blocks.items()}
    result['Z'].iloc[0, 0] += .005
    after = SimpleNamespace(resolve=lambda name, **kwargs: result[name])
    options = normalize_options(dict(model='Split_sectors_MRIO_KL', accounting='inherit',
        defer_satellite_recalculation=True, solution_cleanup=dict(max_cell_adjustment=.001,
            absolute_tolerance=.01, relative_tolerance=1e-8)))
    report = verify_preservation(before, after, {}, split_model_options=options)
    assert report['Z']['passed'] and not report['Z']['strict_passed']
    result['X'].iloc[0, 0] += .005
    with pytest.raises(WrongInput, match='preserve preceding X'):
        verify_preservation(before, after, {}, split_model_options=options)


def test_postprocess_exports_large_corrections_and_reports_residuals(tmp_path):
    model, variables, options = fixture(tmp_path)
    options = normalize_options({**options, 'solution_cleanup': 'postprocess'})
    variables['Z_use'].value[:] = np.array([[-100.], [2.]])/options['scale']
    verify_model_solution(model, tmp_path, options)
    assert variables['Z_use'].value[0] == 0
    assert variables['V'].value[1] < 0 and variables['Y'].value[1] < 0
    record = json.loads((tmp_path/'model_solution.json').read_text())[0]
    assert record['objective_finite'] and record['failed_constraint_cells'] > 0
    assert not record['residuals_enforced'] and record['economic_review'] == 'pending'
    audit = json.loads((tmp_path/'solution_cleanup.json').read_text())
    assert audit['status'] == 'postprocessed_pending_review'
    assert audit['blocks']['Z_use']['maximum_adjustment_original_units'] == 100.
    assert 'max_cell_adjustment' not in audit['policy']


@pytest.mark.parametrize('status', ['optimal_inaccurate', 'infeasible', 'user_limit'])
def test_postprocess_keeps_nonoptimal_statuses_distinct(tmp_path, status):
    model, _, options = fixture(tmp_path)
    options = normalize_options({**options, 'solution_cleanup': 'postprocess'})
    model.core.problem.numerical_problems[None].iloc[0]['problem'].status = status
    with pytest.raises(WrongInput, match='optimal solver status'):
        verify_model_solution(model, tmp_path, options)


def test_postprocess_still_rejects_nonfinite_data(tmp_path):
    model, variables, options = fixture(tmp_path)
    options = normalize_options({**options, 'solution_cleanup': 'postprocess'})
    variables['Z_use'].save_value(np.array([[np.nan], [1.]]))
    with pytest.raises(WrongInput, match='Invalid returned solution'):
        verify_model_solution(model, tmp_path, options)


def test_postprocess_keeps_preservation_discrepancies_as_diagnostics():
    from mario.ops.add_sector_steps import verify_preservation
    axis = pd.MultiIndex.from_tuples([('R', 'Sector', 'P')], names=['Region', 'Level', 'Item'])
    blocks = {n: pd.DataFrame([[v]], index=axis, columns=axis)
              for n, v in {'Z': 1., 'Y': 9., 'V': 9., 'X': 10., 'EY': 0., 'VY': 0.}.items()}
    before = SimpleNamespace(resolve=lambda name, **kwargs: blocks[name])
    result = {n: frame.copy() for n, frame in blocks.items()}
    result['Z'].iloc[0, 0] += 2.
    after = SimpleNamespace(resolve=lambda name, **kwargs: result[name])
    options = normalize_options(dict(model='Split_sectors_MRIO_KL', accounting='inherit',
        defer_satellite_recalculation=True, solution_cleanup='postprocess'))
    report = verify_preservation(before, after, {}, split_model_options=options)
    assert not report['Z']['passed'] and not report['inherited_row_accounting']['passed']
    assert not report['numerical_validation']['residuals_enforced']
    assert report['numerical_validation']['economic_review'] == 'pending'


@pytest.mark.parametrize('residual', [9e-6, 1e3])
def test_optimal_quadratic_export_has_no_monetary_cutoff(tmp_path, monkeypatch, residual):
    from mario.ops import cvxlab_bridge as bridge
    model, variables, _ = fixture(tmp_path)
    for name in ['V_signed_positive', 'V_signed_negative']:
        del variables[name]
    problem = model.core.problem.numerical_problems[None].at[0, 'problem']
    z = variables['Z_use']
    problem.constraints = [z >= 0, cp.sum(z) == (1. + residual)/1000.]
    problem.objective = cp.Minimize(cp.sum_squares(z))
    problem.value = problem.objective.value
    options = normalize_options(dict(model='Split_sectors_MRIO_quadratic', scale=1000.,
                                    require_finite_objective=True))
    model.core.problem.problem_status = {'split': 'optimal'}
    model.refresh_database_and_initialize_problem = lambda **kw: None
    exported = []
    model.load_results_to_database = lambda **kw: exported.append(True)
    monkeypatch.setattr(bridge, '_solve_initialized_split_model', lambda *a: None)
    bridge._run_split_model(model, dest_dir=tmp_path, solver='GUROBI',
                            solver_parameters={}, split_model_options=options)
    assert exported == [True]
    assert options['solution_cleanup'] is None  # no change to the mathematical model settings
    np.testing.assert_array_equal(variables['Z_use'].value.ravel()*1000., [0., 1.])
    assert variables['Y'].value[1] < 0 and variables['V'].value[1] < 0
    record = json.loads((tmp_path/'model_solution.json').read_text())[0]
    assert record['failed_constraint_cells'] > 0 and not record['residuals_enforced']
    assert record['max_constraint_violation'] == pytest.approx(residual)
    assert (tmp_path/'returned_solution_scaled.npz').is_file()
    assert (tmp_path/'cleaned_solution_scaled.npz').is_file()


@pytest.mark.parametrize('statuses', [[], ['infeasible'], ['optimal_inaccurate'], ['optimal', 'user_limit']])
def test_automatic_export_policy_does_not_promote_other_statuses(statuses):
    options = normalize_options(dict(model='Split_sectors_MRIO_quadratic'))
    assert effective_validation_options(options, statuses) is options
    assert effective_validation_options(None, ['optimal']) is None


@pytest.mark.parametrize('name', ['Split_sectors_MRIO_KL', 'Split_sectors_MRIO_quadratic',
                                 'Split_sectors_MRIO_partial_entropy_V_signed_kl'])
def test_standard_policy_is_separate_from_economic_settings_and_legacy_limits(name):
    options = {'model': name, 'solution_cleanup': {'max_cell_adjustment': 1e-6}, 'scale': 1000.}
    result = effective_validation_options(options, ['optimal'])
    assert result['solution_cleanup'] == {'validation': 'report_only'}
    assert options['solution_cleanup'] == {'max_cell_adjustment': 1e-6}
    assert result['model'] == name and result['scale'] == 1000.


def test_report_only_preservation_keeps_fixed_monetary_residuals_visible():
    from mario.ops.add_sector_steps import verify_preservation
    axis = pd.MultiIndex.from_tuples([('R', 'Sector', 'P')], names=['Region', 'Level', 'Item'])
    blocks = {n: pd.DataFrame([[v]], index=axis, columns=axis)
              for n, v in {'Z': 1., 'Y': 9., 'V': 9., 'X': 10., 'EY': 0., 'VY': 0.}.items()}
    result = {n: frame.copy() for n, frame in blocks.items()}
    result['X'].iloc[0, 0] += 9e-6
    result['VY'].iloc[0, 0] += 9e-6
    before = SimpleNamespace(resolve=lambda name, **kw: blocks[name])
    after = SimpleNamespace(resolve=lambda name, **kw: result[name])
    options = normalize_options(dict(model='Split_sectors_MRIO_quadratic', accounting='inherit',
                                    defer_satellite_recalculation=True))
    report = verify_preservation(before, after, {}, split_model_options=
                                 effective_validation_options(options, ['optimal']))
    assert not report['X']['passed'] and not report['VY']['passed']
    assert not report['numerical_validation']['residuals_enforced']


def test_checkpoint_compatibility_distinguishes_validation_code_from_math():
    from copy import deepcopy
    from mario.ops.add_sector_steps import compatible_model_definition
    recorded = {'template': 'Split_sectors_MRIO_quadratic', 'source_sha256': {'model.xlsx': 'original'},
                'shared_operators_sha256': {'split_model.py': 'fixed', 'split_operators.py': 'fixed',
                                            'split_solution.py': 'old-policy'}}
    current = deepcopy(recorded)
    current['shared_operators_sha256']['split_solution.py'] = 'new-policy'
    assert compatible_model_definition(recorded, current)
    assert recorded['shared_operators_sha256']['split_solution.py'] == 'old-policy'
    for container, name in [('shared_operators_sha256', 'split_model.py'),
                            ('shared_operators_sha256', 'split_operators.py'),
                            ('source_sha256', 'model.xlsx')]:
        changed = deepcopy(current)
        changed[container][name] = 'new-math'
        assert not compatible_model_definition(recorded, changed)
    assert not compatible_model_definition(None, current)
