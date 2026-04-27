"""Public numerical primitives backed by the MARIO compute engine."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from mario.compute.helpers import dense_values, inverse_vector
from mario.compute.iot_formulas import (
    build_iot_b_from_X_Z,
    build_iot_E_from_e_X,
    build_iot_F_from_f_Y,
    build_iot_g_from_b,
    build_iot_M_from_m_Y,
    build_iot_X_from_z_Y,
    build_iot_V_from_v_X,
    build_iot_X_from_w_Y,
    build_iot_X_from_Z_Y,
    build_iot_Z_from_z_X,
    build_iot_e_from_E_X,
    build_iot_f_from_e_z,
    build_iot_f_from_e_w,
    build_iot_m_from_v_z,
    build_iot_m_from_v_w,
    build_iot_p_from_v_z,
    build_iot_p_from_v_w,
    build_iot_v_from_V_X,
    build_iot_w_from_z,
    build_iot_z_from_Z_X,
)
from mario.compute.types import ResolutionContext
from mario.log_exc.logger import log_time
from mario.model.conventions import _ENUM

logger = logging.getLogger(__name__)


def calc_all_shock(
    z,
    e,
    v,
    Y,
    *,
    method: str | None = None,
    solver: str | None = None,
    strategy: str | None = None,
):
    """Recompute the main IOT blocks after shocking direct coefficients.

    Parameters
    ----------
    z, e, v, Y:
        Shocked direct coefficients and final demand.
    method:
        Optional runtime compute method override passed to the direct ``X`` solve.
    solver:
        Optional linear solver override passed to the direct ``X`` solve.
    strategy:
        Optional sparse linear strategy override passed to the direct ``X`` solve.
    """
    X = calc_X_from_z(z, Y, method=method, solver=solver, strategy=strategy)
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
    """Calculate the ``X`` total production vector from ``Z`` and ``Y``.

    Parameters
    ----------
    Z : pandas.DataFrame
        ``Z`` intersectoral transaction flows matrix.
    Y : pandas.DataFrame
        ``Y`` final demand matrix with the same row axis as ``Z``.

    Returns
    -------
    pandas.DataFrame
        ``X`` total production vector, computed as row totals of ``Z`` plus
        row totals of ``Y``.
    """
    return build_iot_X_from_Z_Y(Z, Y)


def calc_Z(z, X):
    """Calculate the ``Z`` intersectoral transaction flows matrix.

    Parameters
    ----------
    z : pandas.DataFrame
        ``z`` intersectoral transaction coefficients matrix.
    X : pandas.DataFrame
        ``X`` total production vector. Its index must match the columns of
        ``z``.

    Returns
    -------
    pandas.DataFrame
        ``Z`` intersectoral transaction flows matrix. Each column of ``z`` is
        scaled by the corresponding production value in ``X``.
    """
    return build_iot_Z_from_z_X(z, X)


def calc_w(z):
    """Calculate the ``w`` Leontief inverse matrix.

    Parameters
    ----------
    z : pandas.DataFrame
        Square ``z`` intersectoral transaction coefficients matrix.

    Returns
    -------
    pandas.DataFrame
        ``w`` Leontief inverse matrix, computed as ``(I - z)^-1``.
    """
    return build_iot_w_from_z(z)


def calc_g(b):
    """Calculate the ``g`` Ghosh coefficients matrix.

    Parameters
    ----------
    b : pandas.DataFrame
        Square ``b`` intersectoral transaction direct-output coefficients
        matrix.

    Returns
    -------
    pandas.DataFrame
        ``g`` Ghosh coefficients matrix, computed as ``(I - b)^-1``.
    """
    return build_iot_g_from_b(b)


def calc_X_from_w(w, Y):
    """Calculate the ``X`` total production vector from ``w`` and ``Y``.

    Parameters
    ----------
    w : pandas.DataFrame
        ``w`` Leontief inverse matrix.
    Y : pandas.DataFrame
        ``Y`` final demand matrix.

    Returns
    -------
    pandas.DataFrame
        ``X`` total production vector computed from ``w`` and total final
        demand from ``Y``.
    """
    return build_iot_X_from_w_Y(w, Y)


def calc_X_from_z(
    z,
    Y,
    *,
    method: str | None = None,
    solver: str | None = None,
    strategy: str | None = None,
):
    """Calculate the ``X`` total production vector directly from ``z`` and ``Y``.

    This is the direct path for ``X``. Under ``method="solve"``, MARIO solves
    the linear system ``(I - z) X = Y_total`` without materializing the
    ``w`` Leontief inverse matrix.

    Parameters
    ----------
    z : pandas.DataFrame
        ``z`` intersectoral transaction coefficients matrix.
    Y : pandas.DataFrame
        ``Y`` final demand matrix.
    method : str, optional
        Optional runtime compute method override. Accepted values are
        ``"auto"``, ``"inverse"`` and ``"solve"``.
    solver : str, optional
        Optional linear solver backend used when the solve path is selected.
    strategy : str, optional
        Optional sparse linear strategy used when the solve path is selected.

    Returns
    -------
    pandas.DataFrame
        ``X`` total production vector.
    """
    return build_iot_X_from_z_Y(
        z,
        Y,
        context=ResolutionContext(
            compute_method=method,
            linear_solver=solver,
            linear_strategy=strategy,
        ),
    )


def calc_E(e, X):
    """Calculate the ``E`` environmental transaction flows matrix.

    Parameters
    ----------
    e : pandas.DataFrame
        ``e`` environmental transaction coefficients matrix.
    X : pandas.DataFrame
        ``X`` total production vector.

    Returns
    -------
    pandas.DataFrame
        ``E`` environmental transaction flows matrix.
    """
    return build_iot_E_from_e_X(e, X)


def calc_V(v, X):
    """Calculate the ``V`` value added transaction flows matrix.

    Parameters
    ----------
    v : pandas.DataFrame
        ``v`` value added coefficients matrix.
    X : pandas.DataFrame
        ``X`` total production vector.

    Returns
    -------
    pandas.DataFrame
        ``V`` value added transaction flows matrix.
    """
    return build_iot_V_from_v_X(v, X)


def calc_e(E, X):
    """Calculate the ``e`` environmental transaction coefficients matrix.

    Parameters
    ----------
    E : pandas.DataFrame
        ``E`` environmental transaction flows matrix.
    X : pandas.DataFrame
        ``X`` total production vector.

    Returns
    -------
    pandas.DataFrame
        ``e`` environmental transaction coefficients matrix.
    """
    return build_iot_e_from_E_X(E, X)


def calc_p(v, w):
    """Calculate the ``p`` price index vector from ``v`` and ``w``.

    Parameters
    ----------
    v : pandas.DataFrame
        ``v`` value added coefficients matrix.
    w : pandas.DataFrame
        ``w`` Leontief inverse matrix.

    Returns
    -------
    pandas.DataFrame
        ``p`` price index vector.
    """
    return build_iot_p_from_v_w(v, w)


def calc_v(V, X):
    """Calculate the ``v`` value added coefficients matrix.

    Parameters
    ----------
    V : pandas.DataFrame
        ``V`` value added transaction flows matrix.
    X : pandas.DataFrame
        ``X`` total production vector.

    Returns
    -------
    pandas.DataFrame
        ``v`` value added coefficients matrix.
    """
    return build_iot_v_from_V_X(V, X)


def calc_m(v, w):
    """Calculate the ``m`` total (direct+indirect) value added coefficients matrix.

    Parameters
    ----------
    v : pandas.DataFrame
        ``v`` value added coefficients matrix.
    w : pandas.DataFrame
        ``w`` Leontief inverse matrix.

    Returns
    -------
    pandas.DataFrame
        ``m`` total (direct+indirect) value added coefficients matrix, computed
        as ``v @ w``.
    """
    return build_iot_m_from_v_w(v, w)


def calc_M(m, Y):
    """Calculate the ``M`` total (direct+indirect) value added transaction matrix.

    Parameters
    ----------
    m : pandas.DataFrame
        ``m`` total (direct+indirect) value added coefficients matrix.
    Y : pandas.DataFrame
        ``Y`` final demand matrix.

    Returns
    -------
    pandas.DataFrame
        ``M`` total (direct+indirect) value added transaction matrix. Each
        column is scaled by total final demand for that destination/use column.
    """
    return build_iot_M_from_m_Y(m, Y)


def calc_z(Z, X):
    """Calculate the ``z`` intersectoral transaction coefficients matrix.

    Parameters
    ----------
    Z : pandas.DataFrame
        ``Z`` intersectoral transaction flows matrix.
    X : pandas.DataFrame
        ``X`` total production vector.

    Returns
    -------
    pandas.DataFrame
        ``z`` intersectoral transaction coefficients matrix.
    """
    return build_iot_z_from_Z_X(Z, X)


def calc_b(X, Z):
    """Calculate the ``b`` intersectoral transaction direct-output coefficients matrix.

    Parameters
    ----------
    X : pandas.DataFrame
        ``X`` total production vector.
    Z : pandas.DataFrame
        ``Z`` intersectoral transaction flows matrix.

    Returns
    -------
    pandas.DataFrame
        ``b`` intersectoral transaction direct-output coefficients matrix.
        Rows of ``Z`` are scaled by inverse production.
    """
    return build_iot_b_from_X_Z(X, Z)


def calc_F(f, Y):
    """Calculate the ``F`` total (direct+indirect) environmental transaction flows matrix.

    Parameters
    ----------
    f : pandas.DataFrame
        ``f`` total (direct+indirect) environmental transaction coefficients
        matrix.
    Y : pandas.DataFrame
        ``Y`` final demand matrix.

    Returns
    -------
    pandas.DataFrame
        ``F`` total (direct+indirect) environmental transaction flows matrix.
    """
    return build_iot_F_from_f_Y(f, Y)


def calc_f(e, w):
    """Calculate the ``f`` total (direct+indirect) environmental transaction coefficients matrix.

    Parameters
    ----------
    e : pandas.DataFrame
        ``e`` environmental transaction coefficients matrix.
    w : pandas.DataFrame
        ``w`` Leontief inverse matrix.

    Returns
    -------
    pandas.DataFrame
        ``f`` total (direct+indirect) environmental transaction coefficients
        matrix, computed as ``e @ w``.
    """
    return build_iot_f_from_e_w(e, w)


def calc_f_from_z(
    e,
    z,
    *,
    method: str | None = None,
    solver: str | None = None,
    strategy: str | None = None,
):
    """Calculate the ``f`` total (direct+indirect) environmental transaction coefficients matrix.

    This is the direct path for ``f``. Under ``method="solve"``, MARIO solves
    the transposed system without materializing the ``w`` Leontief inverse
    matrix.

    Parameters
    ----------
    e : pandas.DataFrame
        ``e`` environmental transaction coefficients matrix.
    z : pandas.DataFrame
        ``z`` intersectoral transaction coefficients matrix.
    method : str, optional
        Optional runtime compute method override. Accepted values are
        ``"auto"``, ``"inverse"`` and ``"solve"``.
    solver : str, optional
        Optional linear solver backend used when the solve path is selected.
    strategy : str, optional
        Optional sparse linear strategy used when the solve path is selected.

    Returns
    -------
    pandas.DataFrame
        ``f`` total (direct+indirect) environmental transaction coefficients
        matrix.
    """
    return build_iot_f_from_e_z(
        e,
        z,
        context=ResolutionContext(
            compute_method=method,
            linear_solver=solver,
            linear_strategy=strategy,
        ),
    )


def calc_m_from_z(
    v,
    z,
    *,
    method: str | None = None,
    solver: str | None = None,
    strategy: str | None = None,
):
    """Calculate the ``m`` total (direct+indirect) value added coefficients matrix.

    This is the direct path for ``m``. Under ``method="solve"``, MARIO solves
    the transposed system without materializing the ``w`` Leontief inverse
    matrix.

    Parameters
    ----------
    v : pandas.DataFrame
        ``v`` value added coefficients matrix.
    z : pandas.DataFrame
        ``z`` intersectoral transaction coefficients matrix.
    method : str, optional
        Optional runtime compute method override. Accepted values are
        ``"auto"``, ``"inverse"`` and ``"solve"``.
    solver : str, optional
        Optional linear solver backend used when the solve path is selected.
    strategy : str, optional
        Optional sparse linear strategy used when the solve path is selected.

    Returns
    -------
    pandas.DataFrame
        ``m`` total (direct+indirect) value added coefficients matrix.
    """
    return build_iot_m_from_v_z(
        v,
        z,
        context=ResolutionContext(
            compute_method=method,
            linear_solver=solver,
            linear_strategy=strategy,
        ),
    )


def calc_p_from_z(
    v,
    z,
    *,
    method: str | None = None,
    solver: str | None = None,
    strategy: str | None = None,
):
    """Calculate the ``p`` price index vector directly from ``v`` and ``z``.

    This is the direct path for ``p``. Under ``method="solve"``, MARIO solves
    the transposed system without materializing the ``w`` Leontief inverse
    matrix.

    Parameters
    ----------
    v : pandas.DataFrame
        ``v`` value added coefficients matrix.
    z : pandas.DataFrame
        ``z`` intersectoral transaction coefficients matrix.
    method : str, optional
        Optional runtime compute method override. Accepted values are
        ``"auto"``, ``"inverse"`` and ``"solve"``.
    solver : str, optional
        Optional linear solver backend used when the solve path is selected.
    strategy : str, optional
        Optional sparse linear strategy used when the solve path is selected.

    Returns
    -------
    pandas.DataFrame
        ``p`` price index vector.
    """
    return build_iot_p_from_v_z(
        v,
        z,
        context=ResolutionContext(
            compute_method=method,
            linear_solver=solver,
            linear_strategy=strategy,
        ),
    )


def calc_f_dis(e, w):
    """Calculate a diagonalized representation of ``f``.

    Parameters
    ----------
    e : pandas.DataFrame or pandas.Series
        ``e`` environmental transaction coefficients to diagonalize.
    w : pandas.DataFrame
        ``w`` Leontief inverse matrix.

    Returns
    -------
    pandas.DataFrame
        Diagonalized representation of the ``f`` total (direct+indirect)
        environmental transaction coefficients matrix, built as
        ``diag(e) @ w``.
    """
    values = np.diagflat(dense_values(e).reshape(-1)) @ dense_values(w)
    result = pd.DataFrame(values, index=w.index, columns=w.columns)
    result.index = getattr(e, "columns", w.index)
    return result


def calc_y(Y):
    """Normalize the ``Y`` final demand matrix by its grand total.

    Parameters
    ----------
    Y : pandas.DataFrame
        ``Y`` final demand matrix.

    Returns
    -------
    pandas.DataFrame
        Shares of the ``Y`` final demand matrix, computed as
        ``Y / Y.sum().sum()``.
    """
    return Y / Y.sum().sum()


def X_inverse(X):
    """Return the inverse-production vector as a dense NumPy array."""
    return dense_values(inverse_vector(X))


def linkages_calculation(cut_diag, matrices, multi_mode, normalized):
    """Return backward and forward linkage indicators."""
    if cut_diag:
        for value in matrices.values():
            for position in range(min(value.shape)):
                value.iat[position, position] = 0.0

    if multi_mode:
        link_types = [
            "Total Forward",
            "Total Backward",
            "Direct Forward",
            "Direct Backward",
        ]
        geo_types = ["Local", "Foreign"]
        links = pd.DataFrame(
            0.0,
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
        forward_total = matrices[_ENUM.g].sum(axis=1).to_frame().astype(float)
        backward_total = matrices[_ENUM.w].sum(axis=0).to_frame().astype(float)
        forward_direct = matrices[_ENUM.b].sum(axis=1).to_frame().astype(float)
        backward_direct = matrices[_ENUM.z].sum(axis=0).to_frame().astype(float)

        forward_total.columns = ["Total Forward"]
        backward_total.columns = ["Total Backward"]
        forward_direct.columns = ["Direct Forward"]
        backward_direct.columns = ["Direct Backward"]

        if normalized:
            forward_total.iloc[:, 0] = forward_total.iloc[:, 0] / np.average(
                dense_values(forward_total)
            )
            backward_total.iloc[:, 0] = backward_total.iloc[:, 0] / np.average(
                dense_values(backward_total)
            )
            forward_direct.iloc[:, 0] = forward_direct.iloc[:, 0] / np.average(
                dense_values(forward_direct)
            )
            backward_direct.iloc[:, 0] = backward_direct.iloc[:, 0] / np.average(
                dense_values(backward_direct)
            )

        links = pd.concat(
            [forward_total, backward_total, forward_direct, backward_direct],
            axis=1,
        )

    return links
