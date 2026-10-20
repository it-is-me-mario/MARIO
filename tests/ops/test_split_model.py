"""Mathematical contracts of the opt-in convex IOT split model."""
import json
from types import SimpleNamespace

import cvxpy as cp
import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.ops.split_model import (check_feasibility, inherited_accounting, model_signed_kl,
                                   model_quadratic, model_prior_signed_values, normalize_options)


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
    assert report['status']=='optimal' and report['max_constraint_violation_scaled']<1e-8
