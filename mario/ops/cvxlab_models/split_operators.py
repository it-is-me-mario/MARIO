"""Numerical operators shared by the explicit MRIO model workbooks.

Workbook expressions define the objectives and constraints. These operators
slice masks, implement their named convex losses and read numerical weights.
They never write or select a model formulation.
"""
import cvxpy as cp
import numpy as np

from mario.log_exc.exceptions import WrongInput
from mario.ops.split_model import (
    _values, model_active_kl, model_signed_kl, model_quadratic,
    model_masked_values, model_prior_signed_values, model_legacy_entropy,
    _entropy_floor, model_constant_kl,
)


def scalar(value):
    result = np.asarray(value.value if hasattr(value, 'value') else value, dtype=float)
    if result.size != 1 or not np.isfinite(result).all():
        raise WrongInput('A model control must be one finite scalar.')
    return float(result.reshape(-1)[0])


def quadratic(a, prior, zero, floor):
    return model_quadratic(a, prior, zero, reference_floor=scalar(floor))


def legacy_entropy(a, prior, floor):
    return model_legacy_entropy(a, prior, reference_floor=scalar(floor))


def active_kl(a, prior, zero, floor):
    return model_active_kl(a, prior, zero, reference_floor=scalar(floor))


def signed_kl(a, prior, zero, floor):
    return model_signed_kl(a, prior, zero, reference_floor=scalar(floor))


def weighted_quadratic(a, prior, zero, weight, floor):
    w = scalar(weight)
    return cp.Constant(0.) if w == 0 else w * quadratic(a, prior, zero, floor)


def weighted_active_kl(a, prior, zero, weight, floor):
    w = scalar(weight)
    return cp.Constant(0.) if w == 0 else w * active_kl(a, prior, zero, floor)


def weighted_signed_kl(a, prior, zero, weight, floor):
    w = scalar(weight)
    return cp.Constant(0.) if w == 0 else w * signed_kl(a, prior, zero, floor)


def weighted_signed_values(a, prior, zero, weight):
    return cp.Constant(0.) if scalar(weight) == 0 else model_prior_signed_values(a, prior, zero)


def _selected(a, prior, zero, selector):
    q = _values(prior).reshape(-1)
    active = (_values(zero).reshape(-1) == 0) & (_values(selector).reshape(-1) > 0)
    positions = np.flatnonzero(active)
    return cp.reshape(a, (a.size,), order='C')[positions] if positions.size else None, q[active]


def _positive_loss(a, prior, zero, selector, floor, *, legacy=False):
    vector, q = _selected(a, prior, zero, selector)
    if vector is None:
        return cp.Constant(0.)
    if (q < 0).any():
        raise WrongInput('Negative Capital/Labor or other nonnegative-factor prior in an entropy model. '
                         'Correct the source explicitly or use the constrained quadratic model; '
                         'priors are never silently made positive.')
    reference = q + _entropy_floor(q, scalar(floor))
    return cp.sum(cp.rel_entr(vector, reference) if legacy else model_constant_kl(vector, reference))


def positive_va_kl(a, prior, zero, selector, floor):
    return _positive_loss(a, prior, zero, selector, floor)


def positive_va_entropy(a, prior, zero, selector, floor):
    return _positive_loss(a, prior, zero, selector, floor, legacy=True)


def _free_loss(positive, negative, prior, zero, selector, floor, *, legacy=False):
    p, q = _selected(positive, prior, zero, selector)
    n, _ = _selected(negative, prior, zero, selector)
    if p is None:
        return cp.Constant(0.)
    epsilon = _entropy_floor(q, scalar(floor))
    loss = cp.rel_entr if legacy else model_constant_kl
    # Both components have positive numerical support. Neither prior sign is a
    # hard domain for the net value V = positive - negative.
    return cp.sum(loss(p, np.maximum(q, 0) + epsilon) + loss(n, np.maximum(-q, 0) + epsilon))


def free_va_kl(positive, negative, prior, zero, selector, floor):
    return _free_loss(positive, negative, prior, zero, selector, floor)


def free_va_entropy(positive, negative, prior, zero, selector, floor):
    return _free_loss(positive, negative, prior, zero, selector, floor, legacy=True)


def refinement_entropy(a, prior, selector, floor=None):
    vector, q = _selected(a, prior, cp.Constant(np.zeros(prior.shape)), selector)
    if vector is None:
        return cp.Constant(0.)
    # The three-argument form belongs to the historical staged workbook.
    # Every explicit MRIO workbook passes its data-derived Entropy_floor.
    epsilon = 1e-8 if floor is None else _entropy_floor(q, scalar(floor))
    return cp.sum(cp.rel_entr(vector, q + epsilon))
