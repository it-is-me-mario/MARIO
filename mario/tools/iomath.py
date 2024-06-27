# -*- coding: utf-8 -*-
"""
this module contains the io calculation functions
"""
import pandas as pd
import numpy as np
from copy import deepcopy as dc

from mario.log_exc.logger import log_time
import logging

from mario.tools.constants import _ENUM

logger = logging.getLogger(__name__)


def calc_all_shock(z, e, v, Y):
    w = calc_w(z)
    X = calc_X_from_w(w, Y)
    E = calc_E(e, X)
    V = calc_V(v, X)
    Z = calc_Z(z, X)

    return {
        _ENUM.X: X,
        _ENUM.E: E,
        _ENUM.V: V,
        _ENUM.Z: Z,
        _ENUM.Y: Y,
        _ENUM.e: e,
        _ENUM.v: v,
        _ENUM.z: z,
    }


def calc_X(
    Z,
    Y,
):
    """Calculates the production vector

    .. math::
        X = z\cdot X + Y

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
        Z = z\cdot \hat{X}

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
        x = w\cdot Y

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
        E = e\cdot \hat{X}

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
        V = v\cdot\hat{X}

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
        e = E\cdot \hat{X}^{-1}


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
        p = v\cdot w

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
        v = V\cdot \hat{X}^{-1}

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
        m = v\cdot w

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
        M = m\cdot \hat{Y}

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
        z = Z\cdot \hat{X}^{-1}

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
        \hat{X}^{-1}\cdot Z

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
        F = f\cdot hat{Y}

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
        f = e\cdot w

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


def calc_f_dis(e, w):
    """Calculates Footprint coefficients matrix disaggregated by origin sector and region

    .. math::
        f_dis = \hat{e} \cdot w

    Parameters
    ----------
    e : pd.DataFrame
        Satellite transaction coefficients matrix
    w : pd.DataFrame
        Leontief coefficients matrix

    Returns
    -------
    pd.DataFrame
        Footprint coefficients matrix disaggregated by origin sector and region
    """

    f_dis = np.diagflat(e.values) @ w
    f_dis.index = e.columns

    return f_dis


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


def linkages_calculation(cut_diag, matrices, multi_mode, normalized):
    """calculates the linkages"""
    if cut_diag:
        for key, value in matrices.items():
            np.fill_diagonal(value.values, 0)

    if multi_mode:
        link_types = [
            "Total Forward",
            "Total Backward",
            "Direct Forward",
            "Direct Backward",
        ]
        geo_types = ["Local", "Foreign"]
        links = pd.DataFrame(
            0,
            index=matrices[_ENUM.g].index,
            columns=pd.MultiIndex.from_product([link_types, geo_types]),
        )

        for index, values in links.iterrows():
            links.loc[index, ("Total Forward", "Local")] = (
                matrices[_ENUM.g].loc[index, index[0]].sum().sum()
            )
            links.loc[index, ("Total Forward", "Foreign")] = (
                matrices[_ENUM.g].loc[index].sum().sum()
                - matrices[_ENUM.g].loc[index, index[0]].sum().sum()
            )

            links.loc[index, ("Total Backward", "Local")] = (
                matrices[_ENUM.w].T.loc[index, index[0]].sum().sum()
            )
            links.loc[index, ("Total Backward", "Foreign")] = (
                matrices[_ENUM.w].T.loc[index].sum().sum()
                - matrices[_ENUM.w].T.loc[index, index[0]].sum().sum()
            )

            links.loc[index, ("Direct Forward", "Local")] = (
                matrices[_ENUM.b].loc[index, index[0]].sum().sum()
            )
            links.loc[index, ("Direct Forward", "Foreign")] = (
                matrices[_ENUM.b].loc[index].sum().sum()
                - matrices[_ENUM.b].loc[index, index[0]].sum().sum()
            )

            links.loc[index, ("Direct Backward", "Local")] = (
                matrices[_ENUM.z].T.loc[index, index[0]].sum().sum()
            )
            links.loc[index, ("Direct Backward", "Foreign")] = (
                matrices[_ENUM.z].T.loc[index].sum().sum()
                - matrices[_ENUM.z].T.loc[index, index[0]].sum().sum()
            )

        if normalized:
            log_time(
                logger,
                "Normalization not available for multi-regional mode.",
                "warning",
            )

    # Computing linkages as if there were only one unique region
    else:
        _forward_t = matrices[_ENUM.g].sum(axis=1).to_frame()
        _backward_t = matrices[_ENUM.w].sum(axis=0).to_frame()
        _forward_d = matrices[_ENUM.b].sum(axis=1).to_frame()
        _backward_d = matrices[_ENUM.z].sum(axis=0).to_frame()

        _forward_t.columns = ["Total Forward"]
        _backward_t.columns = ["Total Backward"]
        _forward_d.columns = ["Direct Forward"]
        _backward_d.columns = ["Direct Backward"]

        if normalized:
            _forward_t.iloc[:, 0] = _forward_t.iloc[:, 0] / np.average(
                _forward_t.values
            )
            _backward_t.iloc[:, 0] = _backward_t.iloc[:, 0] / np.average(
                _backward_t.values
            )
            _forward_d.iloc[:, 0] = _forward_d.iloc[:, 0] / np.average(
                _forward_d.values
            )
            _backward_d.iloc[:, 0] = _backward_d.iloc[:, 0] / np.average(
                _backward_d.values
            )

        links = pd.concat([_forward_t, _backward_t, _forward_d, _backward_d], axis=1)

    return links
