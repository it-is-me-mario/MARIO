"""Prior-only threshold/floor experiment: units, signs and fixed data."""
import copy
import json
from types import SimpleNamespace

import cvxpy as cp
import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.ops.split_model import (
    normalize_options, prepare_prior_references, fill_numerical_controls,
    model_active_kl, model_signed_kl, verify_model_solution,
)
from mario.ops.cvxlab_models.split_operators import positive_va_kl, free_va_kl


def tables():
    result = {name: pd.DataFrame({'values': values}) for name, values in {
        'Z_use0': [0., 4e-7, 1e-6, 1., 8.947417109454698e-16],
        'Z_supply0': [0., 2e-6], 'Y0': [-4e-7, -2., 0., 2., 1e-6],
        'V0': [-4e-7, -2., 0., 2.], 'Zold': [8e-16, 1.],
        'Yold': [-4e-7], 'Vold': [-4e-7], 'X': [1e-16], 'XT': [1e-16],
        'Trade': [4e-7], 'RowResidual': [-1e-16], 'ColumnResidual': [1e-16],
        'Zero_Y_mask': [0., 1.], 'Negative_Y_mask': [1., 0.],
        'tol': [0., 0.]}.items()}
    result['Model_controls'] = pd.DataFrame({'model_control_Name':
        ['y_weight', 'supply_weight', 'reference_floor', 'entropy_floor']})
    return result


@pytest.mark.parametrize('scale', [1., 1000.])
def test_only_objective_priors_change_and_signed_y_domain_survives(tmp_path, scale):
    data = tables()
    before = copy.deepcopy(data)
    options = normalize_options(dict(model='Split_sectors_MRIO_KL',
        final_demand_weight=.1, supply_weight=1., prior_zero_tolerance=1e-6, scale=scale))
    prepare_prior_references(data, options, tmp_path)
    np.testing.assert_array_equal(data['Z_use0']['values'], [1e-8, 1e-8, 1e-6, 1., 1e-8])
    np.testing.assert_array_equal(data['Y0']['values'], [-1e-8, -2., 1e-8, 2., 1e-6])
    np.testing.assert_array_equal(data['V0']['values'], [0., -2., 0., 2.])
    for name in data.keys() - {'Z_use0', 'Z_supply0', 'Y0', 'V0'}:
        pd.testing.assert_frame_equal(data[name], before[name])
    fill_numerical_controls(data, options, tmp_path)
    support = json.loads((tmp_path/'entropy_support.json').read_text())
    assert support['coefficient'] == 1e-8
    assert support['coefficient_scaled'] == 1e-8/scale
    assert support['reference_operation'] == 'maximum'
    audit = pd.read_csv(tmp_path/'prior_preparation.csv')
    assert (audit.loc[audit.table.eq('Y0') & audit.original_prior.lt(0), 'reference_written'] < 0).all()
    assert json.loads((tmp_path/'prior_preparation.json').read_text())['tables']['Z_use0']['thresholded_nonzero'] == 2


def test_disabled_policy_leaves_every_reference_unchanged(tmp_path):
    data = tables()
    before = copy.deepcopy(data)
    prepare_prior_references(data, normalize_options(dict(model='Split_sectors_MRIO_KL')), tmp_path)
    for name in data:
        pd.testing.assert_frame_equal(data[name], before[name])
    assert not (tmp_path/'prior_preparation.json').exists()


def test_max_preserves_nonzero_references_and_floors_only_allowed_zero_cells():
    q = cp.Constant([1., 0., 2.])
    a = cp.Constant([1., .5, 0.])
    loss = model_active_kl(a, q, cp.Constant([0., 0., 1.]), reference_floor=.1)
    np.testing.assert_allclose(loss.value, cp.sum(cp.kl_div([1., .5], [1., .1])).value)
    # Equality at an unchanged positive reference has exactly zero KL.
    assert model_active_kl(cp.Constant([1.]), cp.Constant([1.]), reference_floor=.1).value == pytest.approx(0.)


def test_small_negative_y_keeps_its_domain_without_signed_zero_metadata(tmp_path):
    data = tables()
    options = normalize_options(dict(model='Split_sectors_MRIO_KL', final_demand_weight=.1, prior_zero_tolerance=1e-6))
    prepare_prior_references(data, options, tmp_path)
    prior = cp.Constant(data['Y0']['values'].to_numpy())
    right_sign = model_signed_kl(cp.Constant([-1e-8, -2., 0., 2., 1e-6]), prior, reference_floor=1e-8)
    wrong_sign = model_signed_kl(cp.Constant([1e-8, -2., 0., 2., 1e-6]), prior, reference_floor=1e-8)
    assert np.isfinite(right_sign.value)
    assert not np.isfinite(wrong_sign.value)


def test_free_tax_references_are_floored_componentwise_and_keep_large_negative_prior():
    q, zero, select = cp.Constant([-3., 0., 4.]), cp.Constant([0., 0., 0.]), cp.Constant([1., 1., 1.])
    p, n, eps = cp.Constant([0., 0., 4.]), cp.Constant([3., 0., 0.]), cp.Constant(.1)
    actual = free_va_kl(p, n, q, zero, select, eps)
    expected = cp.sum(cp.kl_div(p, [.1, .1, 4.]) + cp.kl_div(n, [3., .1, .1]))
    np.testing.assert_allclose(actual.value, expected.value)
    assert positive_va_kl(cp.Constant([4.]), cp.Constant([4.]), cp.Constant([0.]), cp.Constant([1.]), eps).value == pytest.approx(0.)


@pytest.mark.parametrize('value', [-1., 0., True, float('nan')])
def test_invalid_threshold_is_rejected(value):
    with pytest.raises(WrongInput, match='prior_zero_tolerance'):
        normalize_options(dict(model='Split_sectors_MRIO_KL', prior_zero_tolerance=value))


def test_diagnostics_preserve_the_raw_failed_point_and_identify_entropy_domain(tmp_path):
    x = cp.Variable(2, name='Y')
    x.value = [-1e-4, 1.]
    objective = cp.Minimize(model_active_kl(x, cp.Constant([1., 1.]), reference_floor=.1))
    problem = SimpleNamespace(constraints=[cp.sum(x) == 1.], objective=objective,
        value=float('inf'), status='optimal', solver_stats=SimpleNamespace(solve_time=0.), variables=lambda: [x])
    model = SimpleNamespace(core=SimpleNamespace(problem=SimpleNamespace(
        numerical_problems={None: pd.DataFrame([{'problem': problem}])})))
    with pytest.raises(WrongInput, match='Nonfinite model solution objective'):
        verify_model_solution(model, tmp_path, normalize_options(dict(require_finite_objective=True)))
    records = json.loads((tmp_path/'model_solution.json').read_text())
    assert records[0]['entropy_operands'][0]['operands'][0]['negative_cells'] == 1
    details = json.loads((tmp_path/'constraint_diagnostics.json').read_text())
    assert any(r['origin'] == 'objective_domain' and r['failed_cells'] for r in details)
    np.testing.assert_array_equal(np.load(tmp_path/'returned_solution_scaled.npz')['variable_0'], [-1e-4, 1.])
    np.testing.assert_array_equal(x.value, [-1e-4, 1.])
