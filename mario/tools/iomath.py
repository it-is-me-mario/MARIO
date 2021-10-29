# -*- coding: utf-8 -*-
"""
this module contains the io calculation functions
"""
import pandas as pd
import numpy as np
from copy import deepcopy as dc


def calc_all_shock(z, e, v, Y):

    w = calc_w(z)
    X = calc_X_from_w(w, Y)
    E = calc_E(e, X)
    V = calc_V(v, X)
    Z = calc_Z(z, X)

    return {"X": X, "E": E, "V": V, "Z": Z, "Y": Y, "e": e, "v": v, "z": z}


def calc_X(
    Z,
    Y,
):
    """Calculates the production vector

    .. math::
        X = z.X + Y

    Parameters
    ----------
    Z : pd.DataFrame
        Intersectoral transaction flows matrix
    Y : pd.DataFrame
        Final demand flows matrix

    Returns
    -------
    pd.DataFrame
        Production flows vector
    """

    return pd.DataFrame(Z.sum(1) + Y.sum(1), columns=["production"])


def calc_Z(
    z,
    X,
):
    """Calculates Intersectoral transaction flows matrix

    .. math::
        Z = z.\hat{X}

    Parameters
    ----------
    z : pd.DataFrame
        Intersectoral transaction coefficients matrix
    Y : pd.DataFrame
        Final demand flows matrix

    Returns
    -------
    pd.DataFrame
        Intersectoral transaction flows matrix
    """
    X = dc(X)
    if isinstance(X, pd.DataFrame):
        X = X.sum(1)
    _X = np.diagflat(X.values)

    return pd.DataFrame(z.values @ _X, index=z.index, columns=z.columns)


def calc_w(z):
    """Calculates Leontief coefficients matrix

    .. math::
        w = (I - z)^{-1}

    Parameters
    ----------
    z : pd.DataFrame
        Intersectoral transaction coefficients matrix

    Returns
    -------
    pd.Dataframe
        Leontief coefficients matrix
    """
    I = np.eye(z.shape[0])

    return pd.DataFrame(np.linalg.inv(I - z.values), index=z.index, columns=z.columns)


def calc_g(b):
    """Calculates Ghosh coefficients matrix

    .. math::
        g = (I - b)^{-1}

    Parameters
    ----------
    b : pd.DataFrame
        Intersectoral transaction direct-output coefficients matrix

    Returns
    -------
    pd.DataFrame
        Gosh coefficients matrix

    """

    return calc_w(b)


def calc_X_from_w(
    w,
    Y,
):
    """Calculates Production vector from Leontief coefficients matrix

    .. math::
        x = w.Y

    Parameters
    ----------
    w : pd.DataFrame
        Leontief coefficients matrix
    Y : pd.DataFrame
        Final demand flows matrix

    Returns
    -------
    pd.DataFrame
        Production flows vector
    """
    if isinstance(Y, pd.DataFrame):
        Y = dc(Y.sum(1))

    return pd.DataFrame(w.dot(Y).values, index=Y.index, columns=["production"])


def calc_X_from_z(z, Y):
    """Calculates Production vector from Intersectoral transaction coefficients matrix

    .. math::
        x = (I - z)^{-1} Y

    Parameters
    ----------
    z : pd.DataFrame
        Intersectoral transaction coefficients matrix
    Y : pd.DataFrame
        Final demand flows matrix

    Returns
    -------
    pd.DataFrame
        Production flows vector
    """

    if isinstance(Y, pd.DataFrame):
        Y = dc(Y.sum(1))

    w = calc_w(z)

    return pd.DataFrame(w.dot(Y).values, index=Y.index, columns=["production"])


def calc_E(e, X):
    """Calculates satellite transaction flows matrix

    .. math::
        E = e.\hat{X}

    Parameters
    ----------
    e : pd.DataFrame
        Satellite transaction coefficients matrix
    X: pd.DataFrame
        Production flows vector

    Returns
    -------
    pd.DataFrame
        Satellite transaction flows matrix
    """
    return calc_Z(e, X)


def calc_V(v, X):
    """Calculates Factor of production transaction flows matrix

    .. math::
        V = v.\hat{X}

    Parameters
    ----------
    v : pd.DataFrame
        Factor of production transaction coefficients matrix
    X: pd.DataFrame
        Production flows vector

    Returns
    -------
    pd.DataFrame
        Factor of production transaction flows matrix
    """
    return calc_Z(v, X)


def calc_e(E, X):
    """Calculates Satellite transaction coefficients matrix

    .. math::
        e = E.\hat{X}^{-1}


    Parameters
    ----------
    E : pd.DataFrame
        Satellite transaction flows matrix
    X : pd.DataFrame
        Production flows vector

    Returns
    -------
    pd.DataFrame
        Satellite transaction coefficients matrix
    """
    return calc_z(E, X)


def calc_p(
    v,
    w,
):
    """Calculating Price index coefficients vector

    .. math::
        p = v.w

    Parameters
    ----------
    v : pd.DataFrame
        Factor of production transaction coefficients matrix
    w : pd.DataFrame
        Leontief coefficients matrix

    Returns
    -------
    pd.DataFrame
        Price index coefficients vector
    """
    v = v.sum().values.reshape(1, v.shape[1])

    return pd.DataFrame(
        np.array(v @ w.values).T, columns=["price index"], index=w.columns
    )


def calc_v(
    V,
    X,
):
    """Calculates Factor of production transaction coefficients matrix

    .. math::
        v = V.\hat{X}^{-1}

    Parameters
    ----------
    V : pd.DataFrame
        Factor of production transaction flows matrix
    X : pd.DataFrame
        Production flows vector

    Returns
    -------
    pd.DataFrame
        Factor of production transaction coefficients matrix
    """
    return calc_z(V, X)


def calc_m(v, w):
    """Calculates Multipliers coefficients matrix

    .. math::
        m = v.w

    Parameters
    ----------
    v : pd.DataFrame
        Factor of production transaction coefficients matrix
    w : pd.DataFrame
        Leontief coefficients matrix

    Returns
    -------
    pd.DataFrame
        Multipliers coefficients matrix
    """
    return calc_f(v, w)


def calc_M(m, Y):
    """Calculates Economic impact matrix


    .. math::
        M = m.\hat{Y}

    Parameters
    ----------
    m : pd.DataFrame
        Multipliers coefficients matrix
    Y : pd.DataFrame
        Final Demand flows matrix

    Returns
    -------
    pd.DataFrame
        Economic impact flows matrix
    """

    return calc_F(m, Y)


def calc_z(Z, X):
    """Calculates Intersectoral transaction coefficients matrix

    .. math::
        z = Z.\hat{X}^{-1}

    Parameters
    ----------
    Z : pd.DataFrame
        Intersectoral transaction flows matrix
    X : pd.DataFrame
        Production flows vector

    Returns
    -------
    pd.DataFrame
        Intersectoral transaction coefficients matrix
    """
    X_inv = X_inverse(X)
    X_inv = np.diagflat(X_inv)

    return pd.DataFrame(Z.values @ X_inv, index=Z.index, columns=Z.columns)


def calc_b(X, Z):
    """Calculates Intersectoral transaction direct-output coefficients matrix (for Ghosh model)

    .. math::
        \hat{X}^{-1}.Z

    Parameters
    ----------
    X : pd.DataFrame
        Production flows vector
    Z : pd.DataFrame
        Intersectoral transaction flows matrix

    Returns
    -------
    pd.DataFrame
        Intersectoral transaction direct-output coefficients
    """
    X_inv = X_inverse(X)
    X_inv = np.diagflat(X_inv)

    return pd.DataFrame(X_inv @ Z.values, index=Z.index, columns=Z.columns)


def calc_F(f, Y):
    """Calculates Footprint flows matrix

    .. math::
        F = f.\hat{Y}

    Parameters
    ----------
    f : pd.DataFrame
        Footprint coefficients matrix
    Y : pd.DataFrame
        Final Demand flows matrix

    Returns
    -------
    pd.DataFrame
        Footprint flows matrix
    """

    return calc_Z(f, Y)


def calc_f(e, w):
    """Calculates Footprint coefficients matrix

    .. math::
        f = e.w

    Parameters
    ----------
    e : pd.DataFrame
        Satellite transaction coefficients matrix
    w : pd.DataFrame
        Leontief coefficients matrix

    Returns
    -------
    pd.DataFrame
        Footprint coefficients matrix
    """
    return e.dot(w)


def calc_y(Y):
    """Calculates Final demand share coefficients matrix

    Parameters
    ----------
    Y : pd.DataFrame
        Final demand flows matrix

    Returns
    -------
    pd.DataFrame
        Final demand share coefficients matrix
    """
    return Y / Y.sum().sum()


def X_inverse(X):

    X_inv = dc(X)

    if isinstance(X_inv, (pd.Series, pd.DataFrame)):
        X_inv = X_inv.values.astype(float)

    X_inv[X_inv != 0] = 1 / X_inv[X_inv != 0]

    return X_inv
