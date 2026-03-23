"""Public numerical primitives backed by the MARIO compute engine."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from mario.compute.ghosh_formulas import build_iot_b_from_X_Z, build_iot_g_from_b
from mario.compute.helpers import inverse_vector
from mario.compute.iot_formulas import (
    build_iot_E_from_e_X,
    build_iot_F_from_f_Y,
    build_iot_M_from_m_Y,
    build_iot_V_from_v_X,
    build_iot_X_from_w_Y,
    build_iot_X_from_Z_Y,
    build_iot_Z_from_z_X,
    build_iot_e_from_E_X,
    build_iot_f_from_e_w,
    build_iot_m_from_v_w,
    build_iot_p_from_v_w,
    build_iot_v_from_V_X,
    build_iot_w_from_z,
    build_iot_z_from_Z_X,
)
from mario.log_exc.logger import log_time
from mario.model.conventions import _ENUM

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


def calc_X(Z, Y):
    return build_iot_X_from_Z_Y(Z, Y)


def calc_Z(z, X):
    return build_iot_Z_from_z_X(z, X)


def calc_w(z):
    return build_iot_w_from_z(z)


def calc_g(b):
    return build_iot_g_from_b(b)


def calc_X_from_w(w, Y):
    return build_iot_X_from_w_Y(w, Y)


def calc_X_from_z(z, Y):
    return calc_X_from_w(calc_w(z), Y)


def calc_E(e, X):
    return build_iot_E_from_e_X(e, X)


def calc_V(v, X):
    return build_iot_V_from_v_X(v, X)


def calc_e(E, X):
    return build_iot_e_from_E_X(E, X)


def calc_p(v, w):
    return build_iot_p_from_v_w(v, w)


def calc_v(V, X):
    return build_iot_v_from_V_X(V, X)


def calc_m(v, w):
    return build_iot_m_from_v_w(v, w)


def calc_M(m, Y):
    return build_iot_M_from_m_Y(m, Y)


def calc_z(Z, X):
    return build_iot_z_from_Z_X(Z, X)


def calc_b(X, Z):
    return build_iot_b_from_X_Z(X, Z)


def calc_F(f, Y):
    return build_iot_F_from_f_Y(f, Y)


def calc_f(e, w):
    return build_iot_f_from_e_w(e, w)


def calc_f_dis(e, w):
    values = np.diagflat(np.asarray(e, dtype=float)) @ w.to_numpy(dtype=float)
    result = pd.DataFrame(values, index=w.index, columns=w.columns)
    result.index = getattr(e, "columns", w.index)
    return result


def calc_y(Y):
    return Y / Y.sum().sum()


def X_inverse(X):
    return inverse_vector(X).to_numpy(dtype=float)


def linkages_calculation(cut_diag, matrices, multi_mode, normalized):
    """Return backward and forward linkage indicators."""
    if cut_diag:
        for value in matrices.values():
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

        for index, _ in links.iterrows():
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

    else:
        forward_total = matrices[_ENUM.g].sum(axis=1).to_frame()
        backward_total = matrices[_ENUM.w].sum(axis=0).to_frame()
        forward_direct = matrices[_ENUM.b].sum(axis=1).to_frame()
        backward_direct = matrices[_ENUM.z].sum(axis=0).to_frame()

        forward_total.columns = ["Total Forward"]
        backward_total.columns = ["Total Backward"]
        forward_direct.columns = ["Direct Forward"]
        backward_direct.columns = ["Direct Backward"]

        if normalized:
            forward_total.iloc[:, 0] = forward_total.iloc[:, 0] / np.average(
                forward_total.values
            )
            backward_total.iloc[:, 0] = backward_total.iloc[:, 0] / np.average(
                backward_total.values
            )
            forward_direct.iloc[:, 0] = forward_direct.iloc[:, 0] / np.average(
                forward_direct.values
            )
            backward_direct.iloc[:, 0] = backward_direct.iloc[:, 0] / np.average(
                backward_direct.values
            )

        links = pd.concat(
            [forward_total, backward_total, forward_direct, backward_direct],
            axis=1,
        )

    return links
