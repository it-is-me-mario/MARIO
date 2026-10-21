"""Mathematical contracts of the opt-in convex IOT split model."""
import json
from types import SimpleNamespace

import cvxpy as cp
import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.ops.split_model import (check_feasibility, inherited_accounting, model_signed_kl,
                                   model_quadratic, model_prior_signed_values, normalize_options,
                                   proportional_row_reference)


@pytest.mark.parametrize('sparse', [False, True])
@pytest.mark.parametrize('value,accepted', [(0., True), (-1e-4, False)])
def test_solution_validation_checks_sparse_domains_without_changing_tolerance(tmp_path, sparse, value, accepted):
    from scipy.sparse import csc_matrix
    from mario.ops.split_model import verify_model_solution
    values = np.array([[1., 0.], [0., value]])
    operand = cp.Constant(csc_matrix(values) if sparse else values)
    problem = SimpleNamespace(constraints=[operand >= 0.], objective=cp.Minimize(cp.Constant(0.)),
                              value=0., status='optimal', solver_stats=SimpleNamespace(solve_time=0.))
    frame = pd.DataFrame([{'problem': problem}])
    model = SimpleNamespace(core=SimpleNamespace(problem=SimpleNamespace(numerical_problems={None: frame})))
    if accepted:
        verify_model_solution(model, tmp_path, normalize_options({}))
    else:
        with pytest.raises(WrongInput, match='constraint cells'):
            verify_model_solution(model, tmp_path, normalize_options({}))
    report = json.loads((tmp_path/'model_solution.json').read_text())[0]
    assert report['failed_constraint_cells'] == (0 if accepted else 1)


@pytest.mark.skipif('GUROBI' not in cp.installed_solvers(), reason='Gurobi is optional')
@pytest.mark.parametrize('negative_musd,accepted', [(2e-8, True), (1e-4, False)])
def test_gurobi_probe_uses_existing_envelope_without_changing_original_problem(tmp_path, negative_musd, accepted):
    x = cp.Variable()
    original = cp.Problem(cp.Minimize(cp.square(x)), [x >= 0, x == -negative_musd/1000.])
    constraints = tuple(original.constraints)
    frame = pd.DataFrame([{'problem': original}])
    model = SimpleNamespace(core=SimpleNamespace(problem=SimpleNamespace(numerical_problems={None: frame})))
    options = normalize_options({'check_feasibility': True, 'feasibility_solver': 'GUROBI', 'scale': 1000.})
    if accepted:
        check_feasibility(model, tmp_path, options)
    else:
        with pytest.raises(WrongInput, match='infeasible'):
            check_feasibility(model, tmp_path, options)
    report = json.loads((tmp_path/'feasibility.json').read_text())[0]
    assert report['status'] == ('optimal' if accepted else 'infeasible')
    assert report['absolute_feasibility_band_scaled']*1000. == pytest.approx(1e-6)
    assert tuple(original.constraints) == constraints and x.value is None


def test_signed_kl_keeps_an_already_consistent_mixed_sign_prior():
    x = cp.Variable(2)
    prior = cp.Constant([5.,-15.])
    problem = cp.Problem(cp.Minimize(model_signed_kl(x,prior)),[cp.sum(x)==-10.])
    assert problem.is_dcp()
    problem.solve(solver='CLARABEL')
    np.testing.assert_allclose(x.value,[5.,-15.],atol=1e-3)


def test_linear_feasibility_retains_implicit_entropy_domains(tmp_path):
    x = cp.Variable()
    original = cp.Problem(cp.Minimize(cp.rel_entr(x,1.)),[x==-1.])
    frame = pd.DataFrame([{'problem':original}])
    model = SimpleNamespace(core=SimpleNamespace(problem=SimpleNamespace(numerical_problems={None:frame})))
    with pytest.raises(WrongInput,match='infeasible'):
        check_feasibility(model,tmp_path,normalize_options({'check_feasibility':True}))
    assert json.loads((tmp_path/'feasibility.json').read_text())[0]['status']=='infeasible'


def test_structural_zero_is_excluded_from_the_signed_loss():
    x = cp.Variable(2)
    loss = model_signed_kl(x,cp.Constant([-2.,0.]),cp.Constant([0.,1.]))
    problem = cp.Problem(cp.Minimize(loss),[x[1]==0.])
    problem.solve(solver='CLARABEL')
    np.testing.assert_allclose(x.value,[-2.,0.],atol=1e-3)


@pytest.mark.parametrize('output,children,expected',[(10.,[0.,4.,6.],[0.,.08,.12]),(0.,[0.,0.,0.],[.2,0.,0.])])
def test_inherited_discrepancy_survives_exhausted_and_zero_output_parent(output,children,expected):
    index = pd.MultiIndex.from_tuples([('R','Sector','Parent')])
    data = {'Z':pd.DataFrame([[0.]],index=index,columns=index),
            'Y':pd.DataFrame([[output]],index=index),
            'V':pd.DataFrame([[output+.2]],columns=index),
            'X':pd.DataFrame({'production':[output]},index=index)}
    before = SimpleNamespace(resolve=lambda name,scenario:data[name])
    refined = pd.DataFrame({'production':children},index=pd.MultiIndex.from_tuples(
        [('R','Sector',name) for name in ('Parent','A','B')]))
    actual = inherited_accounting(before,refined,{'A':'Parent','B':'Parent'})
    np.testing.assert_allclose(actual['column'],expected,atol=1e-12)
    np.testing.assert_allclose(actual['row'],0.,atol=1e-12)


def test_signed_kl_is_invariant_to_numerical_flow_scaling():
    a = cp.Constant([-3.,.2])
    prior = cp.Constant([-2.,.1])
    original = model_signed_kl(a,prior).value
    scaled = model_signed_kl(a/1000.,prior/1000.,reference_floor=1e-11).value*1000.
    np.testing.assert_allclose(scaled,original,rtol=1e-12)


def test_quadratic_retains_signed_domain_and_unit_invariance():
    prior = cp.Constant([5.,-15.])
    x = cp.Variable(2)
    problem = cp.Problem(cp.Minimize(model_quadratic(x,prior)),
                         [cp.sum(x)==-10.,model_prior_signed_values(x,prior)>=0])
    assert problem.is_qp()
    problem.solve(solver='CLARABEL')
    np.testing.assert_allclose(x.value,[5.,-15.],atol=1e-5)
    a = cp.Constant([4.,-14.])
    np.testing.assert_allclose(model_quadratic(a,prior).value,
                               1000.*model_quadratic(a/1000.,prior/1000.,reference_floor=1e-11).value)


def test_feasibility_reports_sparse_parameter_domains(tmp_path):
    from scipy.sparse import csc_matrix
    x = cp.Variable((2,2))
    original = cp.Problem(cp.Minimize(cp.sum(cp.rel_entr(x,cp.Constant(csc_matrix(np.ones((2,2))))))),[x==1.])
    frame = pd.DataFrame([{'problem':original}])
    model = SimpleNamespace(core=SimpleNamespace(problem=SimpleNamespace(numerical_problems={None:frame})))
    check_feasibility(model,tmp_path,normalize_options({'check_feasibility':True}))
    report = json.loads((tmp_path/'feasibility.json').read_text())[0]
    assert report['status']=='optimal'
    assert report['max_constraint_violation_scaled'] <= report['absolute_feasibility_band_scaled'] + 1e-10


@pytest.mark.parametrize('scale', [1., 1000.])
@pytest.mark.parametrize('negative_musd,accepted', [(2e-8, True), (1e-4, False)])
def test_feasibility_uses_existing_absolute_tolerance_without_changing_the_qp(tmp_path, scale, negative_musd, accepted):
    x = cp.Variable()
    original = cp.Problem(cp.Minimize(cp.square(x)), [x >= 0, x == -negative_musd / scale])
    original_constraints = tuple(original.constraints)
    frame = pd.DataFrame([{'problem': original}])
    model = SimpleNamespace(core=SimpleNamespace(problem=SimpleNamespace(numerical_problems={None: frame})))
    options = normalize_options({'check_feasibility': True, 'scale': scale})
    if accepted:
        check_feasibility(model, tmp_path, options)
    else:
        with pytest.raises(WrongInput, match='infeasible'):
            check_feasibility(model, tmp_path, options)
    report = json.loads((tmp_path / 'feasibility.json').read_text())[0]
    assert report['status'] == ('optimal' if accepted else 'infeasible')
    assert report['absolute_feasibility_band_scaled'] * scale == pytest.approx(1e-6)
    assert report['dual_certificate_requested'] is False
    assert tuple(original.constraints) == original_constraints
    assert x.value is None


@pytest.mark.parametrize('total,split',[(10.,[4.,2.,4.]),(0.,[0.,0.,0.])])
def test_joint_row_priors_preserve_signed_totals_and_ignore_child_order(total,split):
    old_x = pd.DataFrame({'production':[total]},index=pd.MultiIndex.from_tuples([('R','Sector','P')]))
    new_x = pd.DataFrame({'production':split},index=pd.MultiIndex.from_tuples(
        [('R','Sector',s) for s in ['P','A','B']]))
    original = pd.DataFrame([['R','P','C1',-2.],['R','P','C2',12.]],
                            columns=['region_from_Name','sector_from_Name','category','values'])
    table = pd.DataFrame([['R',s,c,0.] for s in ['B','P','A'] for c in ['C2','C1']],columns=original.columns)
    actual = proportional_row_reference(table,original,new_x,old_x,{'A':'P','B':'P'})
    shares = [1.,0.,0.] if total==0 else np.array(split)/total
    for s,share in zip(['P','A','B'],shares):
        np.testing.assert_allclose(actual.loc[actual.sector_from_Name.eq(s),'values'],[12.*share,-2.*share])
    np.testing.assert_allclose(actual.groupby('category')['values'].sum(),[-2.,12.])
    reverse = proportional_row_reference(table.iloc[::-1].reset_index(drop=True),original,new_x,old_x,{'A':'P','B':'P'})
    pd.testing.assert_frame_equal(actual.sort_values(['sector_from_Name','category']).reset_index(drop=True),
                                  reverse.sort_values(['sector_from_Name','category']).reset_index(drop=True))
