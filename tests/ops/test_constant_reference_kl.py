"""Equivalent fixed-prior KL values and domains over 26 orders of magnitude."""
import cvxpy as cp
import numpy as np
import pytest
from mario.ops.split_model import model_constant_kl
from mario.log_exc.exceptions import WrongInput

@pytest.mark.parametrize('kind',['zero','prior','scaled_prior','far_from_prior'])
def test_fixed_reference_equivalence_and_domain(kind):
    q=np.array([1e-25,1e-21,1e-14,1e-7,.01,1.,10.])
    x={'zero':np.zeros(7),'prior':q,'scaled_prior':10*q,'far_from_prior':np.arange(1,8)/10}[kind]
    actual=model_constant_kl(cp.Constant(x),q).value
    expected=cp.kl_div(x,q).value
    np.testing.assert_allclose(actual,expected,rtol=1e-13,atol=1e-14)
    assert np.isposinf(model_constant_kl(cp.Constant(-1.),np.array(1e-25)).value)
    p=cp.Problem(cp.Minimize(cp.sum(model_constant_kl(cp.Variable(7),q))))
    assert p.is_dcp()

@pytest.mark.parametrize('q',[0.,-1.,float('nan'),float('inf')])
def test_bad_reference_rejected(q):
    with pytest.raises(WrongInput,match='strictly positive'):
        model_constant_kl(cp.Variable(),np.array(q))


def test_endogenous_reference_is_not_snapshotted_as_a_constant():
    q=cp.Variable();q.value=1.
    with pytest.raises(WrongInput,match='endogenous'):
        model_constant_kl(cp.Variable(),q)
