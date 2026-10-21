"""Packaged formulations and factor-type domains; no real MRIO run."""
import hashlib
from pathlib import Path

import cvxpy as cp
import numpy as np
from openpyxl import load_workbook
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.ops.split_model import model_catalogue, normalize_options, select_model_template
from mario.ops.cvxlab_bridge import _prepare_split_model_directory
from mario.ops.cvxlab_models.split_operators import positive_va_kl, free_va_kl, quadratic, model_masked_values, refinement_entropy

ROOT = Path(__file__).resolve().parents[2] / 'mario/ops/cvxlab_models'


def problem_rows(path):
    book = load_workbook(path, read_only=True, data_only=True)
    rows = [row[:3] for row in book['problem'].values]
    book.close()
    return rows


@pytest.mark.parametrize('name', model_catalogue())
@pytest.mark.parametrize('accounting', ['strict', 'inherit'])
@pytest.mark.parametrize('compact', [False, True])
def test_each_objective_and_constraint_profile_is_an_existing_workbook(tmp_path, name, accounting, compact):
    options = normalize_options(dict(model=name, accounting=accounting, compact_constraints=compact))
    template, workbook = select_model_template(options)
    source = ROOT / template / workbook
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = _prepare_split_model_directory(main_dir_path=tmp_path, model_dir_name='model',
                                                template_name=template, settings_filename=workbook)
    assert problem_rows(destination / 'model_settings.xlsx') == problem_rows(source)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    expressions = [str(r[2]) for r in problem_rows(source)]
    assert 'model_masked_values(V,V_nonnegative_mask) >= 0' in expressions
    assert not any('model_prior_signed_values(V' in e for e in expressions)
    if options['value_added_loss'] != 'quadratic':
        assert 'model_masked_values(V-V_signed_positive+V_signed_negative,V_signed_mask) == 0' in expressions


def test_model_choice_and_old_loss_options_select_the_same_static_workbook():
    a = normalize_options(dict(model='Split_sectors_MRIO_quadratic', accounting='inherit'))
    b = normalize_options(dict(value_added_loss='quadratic', flow_loss='quadratic', complete_intermediate_priors=True,
                               accounting='inherit'))
    assert a == b
    with pytest.raises(WrongInput, match='requires'):
        normalize_options(dict(model='Split_sectors_MRIO_KL', value_added_loss='quadratic'))


@pytest.mark.parametrize('loss', ['kl', 'quadratic'])
@pytest.mark.parametrize('prior_sign', [-1., 0., 1.])
@pytest.mark.parametrize('target_sign', [-1., 1.])
def test_tax_and_margins_can_cross_prior_sign_without_negative_capital_or_labor(loss, prior_sign, target_sign):
    # Capital, Labor, TTM, Tax. No structural zeros in this synthetic example.
    v = cp.Variable(4)
    q = cp.Constant([2., 3., prior_sign, prior_sign])
    positive_mask = cp.Constant([1., 1., 0., 0.])
    signed_mask = cp.Constant([0., 0., 1., 1.])
    zero = cp.Constant(np.zeros(4))
    floor = cp.Constant(1e-8)
    target = np.array([2., 1.]) * target_sign
    constraints = [model_masked_values(v, positive_mask) >= 0, v[2:] == target, cp.sum(v[:2]) == 5.]
    if loss == 'quadratic':
        objective = quadratic(v, q, zero, floor)
    else:
        p, n = cp.Variable(4, nonneg=True), cp.Variable(4, nonneg=True)
        constraints += [model_masked_values(v-p+n, signed_mask) == 0,
                        model_masked_values(p, positive_mask) == 0, model_masked_values(n, positive_mask) == 0]
        objective = positive_va_kl(v, q, zero, positive_mask, floor) + free_va_kl(p, n, q, zero, signed_mask, floor)
    problem = cp.Problem(cp.Minimize(objective), constraints)
    assert problem.is_dcp()
    if loss == 'quadratic':
        assert problem.is_qp()
    problem.solve(solver='CLARABEL')
    assert problem.status in ('optimal', 'optimal_inaccurate')
    assert (v.value[:2] >= -1e-7).all()
    np.testing.assert_allclose(v.value[2:], target, atol=1e-6)
    forbidden = cp.Problem(cp.Minimize(objective), constraints + [v[0] == -1.])
    forbidden.solve(solver='CLARABEL')
    assert forbidden.status in ('infeasible', 'infeasible_inaccurate')


def test_entropy_rejects_negative_nonnegative_factor_priors_without_changing_them():
    q = cp.Constant([-1., 2.])
    with pytest.raises(WrongInput, match='never silently'):
        positive_va_kl(cp.Variable(2), q, cp.Constant([0., 0.]), cp.Constant([1., 1.]), cp.Constant(1e-8))
    np.testing.assert_array_equal(q.value, [-1., 2.])


def test_mrio_refinement_uses_explicit_support_and_historical_form_is_unchanged():
    a, q, selected = cp.Constant([.04]), cp.Constant([.03]), cp.Constant([1.])
    np.testing.assert_allclose(refinement_entropy(a, q, selected, cp.Constant(1e-6)).value,
                               cp.sum(cp.rel_entr(a, q+1e-6)).value)
    np.testing.assert_allclose(refinement_entropy(a, q, selected).value,
                               cp.sum(cp.rel_entr(a, q+1e-8)).value)
