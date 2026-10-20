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
from mario.compute.sut_formulas import (
    build_sut_U_from_u_Xa,
    build_sut_u_from_U_Xa,
    build_sut_S_from_s_Xc,
    build_sut_s_from_S_Xc,
    build_sut_c_from_S_Xa,
    build_sut_Xa_from_S_Ya,
    build_sut_Xc_from_U_Yc,
    build_sut_wcc_from_u_s,
    build_sut_wca_from_u_s,
    build_sut_wac_from_s_u,
    build_sut_waa_from_s_u,
    build_sut_bu_from_Xc_U,
    build_sut_bs_from_Xa_S,
    build_sut_gcc_from_bu_bs,
    build_sut_gca_from_gcc_bu,
    build_sut_gac_from_gaa_bs,
    build_sut_gaa_from_bs_bu,
    build_sut_pa_from_va,
    build_sut_pc_from_vc,
    build_sut_Ea_from_ea_Xa,
    build_sut_Ec_from_ec_Xc,
    build_sut_Fa_from_fa_s_Yc,
    build_sut_Fc_from_fc_Yc,
    build_sut_Ma_from_ma_s_Yc,
    build_sut_Mc_from_mc_Yc,
    build_sut_Va_from_va_Xa,
    build_sut_Vc_from_vc_Xc,
    build_sut_ea_from_Ea_Xa,
    build_sut_ec_from_Ec_Xc,
    build_sut_fa_from_ea_waa,
    build_sut_fc_from_ea_s_wcc,
    build_sut_ma_from_va_waa,
    build_sut_mc_from_va_s_wcc,
    build_sut_va_from_Va_Xa,
    build_sut_vc_from_Vc_Xc,
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
    r"""Calculate the ``X`` total production vector from ``Z`` and ``Y``.

    .. math::

        X = Z\mathbf{1} + Y\mathbf{1}

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

    Notes
    -----
    ``Z.sum(axis=1) + Y.sum(axis=1)`` gives one value per production
    node. The returned single column is named ``production``.
    """
    return build_iot_X_from_Z_Y(Z, Y)


def calc_Z(z, X):
    r"""Calculate the ``Z`` intersectoral transaction flows matrix.

    .. math::

        Z = z\,\operatorname{diag}(X)

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
    r"""Calculate the ``w`` Leontief inverse matrix.

    .. math::

        w = (I-z)^{-1}

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
    r"""Calculate the ``g`` Ghosh coefficients matrix.

    .. math::

        g = (I-b)^{-1}

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
    r"""Calculate the ``X`` total production vector from ``w`` and ``Y``.

    .. math::

        X = w\,(Y\mathbf{1})

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

    Notes
    -----
    Final demand is summed across its columns before multiplication.
    The returned single column is named ``production``.
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
    r"""Calculate the ``X`` total production vector directly from ``z`` and ``Y``.

    .. math::

        (I-z)X = Y\mathbf{1}

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

    Notes
    -----
    The equivalent inverse expression is :math:`X=(I-z)^{-1}(Y\mathbf{1})`.
    The returned single column is named ``production``.
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
    r"""Calculate the ``E`` environmental transaction flows matrix.

    .. math::

        E = e\,\operatorname{diag}(X)

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
    r"""Calculate the ``V`` value added transaction flows matrix.

    .. math::

        V = v\,\operatorname{diag}(X)

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


def calc_Va(va, Xa):
    r"""Calculate the ``Va`` activity-side value added flows matrix.

    .. math::

        V_a = v_a\,\operatorname{diag}(X_a)

    Parameters
    ----------
    va : pandas.DataFrame
        Direct value added coefficients, with factors on rows and activity nodes on columns.
    Xa : pandas.DataFrame
        Activity production vector. Its index must match ``va.columns``.

    Returns
    -------
    pandas.DataFrame
        Activity-side flows, with the same index and columns as ``va``.
    """
    return build_sut_Va_from_va_Xa(va, Xa)


def calc_Vc(vc, Xc):
    r"""Calculate the ``Vc`` commodity-side value added flows matrix.

    .. math::

        V_c = v_c\,\operatorname{diag}(X_c)

    Parameters
    ----------
    vc : pandas.DataFrame
        Direct value added coefficients, with factors on rows and commodity nodes on columns.
    Xc : pandas.DataFrame
        Commodity production vector. Its index must match ``vc.columns``.

    Returns
    -------
    pandas.DataFrame
        Commodity-side flows, with the same index and columns as ``vc``.
    """
    return build_sut_Vc_from_vc_Xc(vc, Xc)


def calc_e(E, X):
    r"""Calculate the ``e`` environmental transaction coefficients matrix.

    .. math::

        e = E\,\operatorname{diag}(X)^{-1}

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

    Notes
    -----
    Inverse production is computed elementwise. A zero production
    entry has inverse zero, so the corresponding column is set to zero.
    """
    return build_iot_e_from_E_X(E, X)


def calc_Ea(ea, Xa):
    r"""Calculate the ``Ea`` activity-side environmental flows matrix.

    .. math::

        E_a = e_a\,\operatorname{diag}(X_a)

    Parameters
    ----------
    ea : pandas.DataFrame
        Direct environmental coefficients, with accounts on rows and activity nodes on columns.
    Xa : pandas.DataFrame
        Activity production vector. Its index must match ``ea.columns``.

    Returns
    -------
    pandas.DataFrame
        Activity-side flows, with the same index and columns as ``ea``.
    """
    return build_sut_Ea_from_ea_Xa(ea, Xa)


def calc_Ec(ec, Xc):
    r"""Calculate the ``Ec`` commodity-side environmental flows matrix.

    .. math::

        E_c = e_c\,\operatorname{diag}(X_c)

    Parameters
    ----------
    ec : pandas.DataFrame
        Direct environmental coefficients, with accounts on rows and commodity nodes on columns.
    Xc : pandas.DataFrame
        Commodity production vector. Its index must match ``ec.columns``.

    Returns
    -------
    pandas.DataFrame
        Commodity-side flows, with the same index and columns as ``ec``.
    """
    return build_sut_Ec_from_ec_Xc(ec, Xc)


def calc_p(v, w):
    r"""Calculate the ``p`` price index vector from ``v`` and ``w``.

    .. math::

        p = w^{\mathsf{T}}v^{\mathsf{T}}\mathbf{1}

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

    Notes
    -----
    Value added is summed over all factor rows before multiplying by
    ``w.T``. The result has the production nodes on its index and one
    column named ``price index``.
    """
    return build_iot_p_from_v_w(v, w)


def calc_v(V, X):
    r"""Calculate the ``v`` value added coefficients matrix.

    .. math::

        v = V\,\operatorname{diag}(X)^{-1}

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

    Notes
    -----
    Inverse production is computed elementwise. A zero production
    entry has inverse zero, so the corresponding column is set to zero.
    """
    return build_iot_v_from_V_X(V, X)


def calc_va(Va, Xa):
    r"""Calculate the ``va`` activity-side value added coefficients matrix.

    .. math::

        v_a = V_a\,\operatorname{diag}(X_a)^{-1}

    Inverse production is computed elementwise; zero production entries
    have inverse zero and set the corresponding coefficient columns to zero.

    Parameters
    ----------
    Va : pandas.DataFrame
        Direct value added flows, with factors on rows and activity nodes on columns.
    Xa : pandas.DataFrame
        Activity production vector. Its index must match ``Va.columns``.

    Returns
    -------
    pandas.DataFrame
        Activity-side coefficients, with the same index and columns as ``Va``.
    """
    return build_sut_va_from_Va_Xa(Va, Xa)


def calc_vc(Vc, Xc):
    r"""Calculate the ``vc`` commodity-side value added coefficients matrix.

    .. math::

        v_c = V_c\,\operatorname{diag}(X_c)^{-1}

    Inverse production is computed elementwise; zero production entries
    have inverse zero and set the corresponding coefficient columns to zero.

    Parameters
    ----------
    Vc : pandas.DataFrame
        Direct value added flows, with factors on rows and commodity nodes on columns.
    Xc : pandas.DataFrame
        Commodity production vector. Its index must match ``Vc.columns``.

    Returns
    -------
    pandas.DataFrame
        Commodity-side coefficients, with the same index and columns as ``Vc``.
    """
    return build_sut_vc_from_Vc_Xc(Vc, Xc)


def calc_m(v, w):
    r"""Calculate the ``m`` total (direct+indirect) value added coefficients matrix.

    .. math::

        m = v\,w

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


def calc_ma(va, waa, vc=None, u=None):
    r"""Calculate the ``ma`` activity-side total value added coefficients matrix.

    .. math::

        m_a = (v_a + v_c\,u)\,w_{aa}

    When ``vc=None``, the commodity term is omitted and ``u`` is
    not needed. Supplying ``vc`` without ``u`` raises ``ValueError``.

    Parameters
    ----------
    va : pandas.DataFrame
        Activity-side direct value added coefficients: factors by activity nodes.
    waa : pandas.DataFrame
        Activity-to-activity Leontief inverse. Its row axis must match
        the columns of ``va``.
    vc : pandas.DataFrame, optional
        Commodity-side direct value added coefficients. Defaults to zero.
        Its row axis must match ``va.index``.
    u : pandas.DataFrame, optional
        Use coefficients: commodity nodes by activity nodes. Required
        when ``vc`` is supplied.

    Returns
    -------
    pandas.DataFrame
        Total direct and indirect coefficients, with factors on rows
        and activity nodes on columns.
    """
    return build_sut_ma_from_va_waa(va, waa, vc=vc, u=u)


def calc_mc(va, s, wcc, vc=None):
    r"""Calculate the ``mc`` commodity-side total value added coefficients matrix.

    .. math::

        m_c = (v_a\,s + v_c)\,w_{cc}

    When ``vc=None``, the commodity-side direct term is omitted.

    Parameters
    ----------
    va : pandas.DataFrame
        Activity-side direct value added coefficients: factors by activity nodes.
    s : pandas.DataFrame
        Supply coefficients: activity nodes by commodity nodes. Its
        row axis must match the columns of ``va``.
    wcc : pandas.DataFrame
        Commodity-to-commodity Leontief inverse. Its row axis must
        match ``s.columns``.
    vc : pandas.DataFrame, optional
        Commodity-side direct value added coefficients. Defaults to zero.
        Its row axis must match ``va.index`` and its columns
        must match ``s.columns``.

    Returns
    -------
    pandas.DataFrame
        Total direct and indirect coefficients, with factors on rows
        and commodity nodes on columns.
    """
    return build_sut_mc_from_va_s_wcc(va, s, wcc, vc=vc)


def calc_M(m, Y):
    r"""Calculate the ``M`` total (direct+indirect) value added transaction matrix.

    .. math::

        M = m\,\operatorname{diag}(Y\mathbf{1})

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
        column is scaled by final demand summed over categories for its
        production node.

    Notes
    -----
    Final demand is summed across its columns, then each column of
    ``m`` is scaled by the corresponding total. The output keeps the
    factors and production-node axes of ``m``; it does not keep the
    final-demand category columns of ``Y``.
    """
    return build_iot_M_from_m_Y(m, Y)


def calc_Ma(ma, s, Yc):
    r"""Calculate the ``Ma`` activity-side total value added flows matrix.

    .. math::

        M_a = m_a\,\operatorname{diag}\!\left(s\,(Y_c\mathbf{1})\right)

    Final demand is summed across its columns and mapped to activities
    through ``s`` before scaling the multiplier columns.
    The output columns represent production nodes, rather than final-demand
    categories.

    Parameters
    ----------
    ma : pandas.DataFrame
        Total value added coefficients: factors by activity nodes.
    s : pandas.DataFrame
        Supply coefficients: activity nodes by commodity nodes. Its
        row axis must match the columns of ``ma``.
    Yc : pandas.DataFrame
        Commodity final demand: commodity nodes by final-demand
        categories and regions.

    Returns
    -------
    pandas.DataFrame
        Footprint flows with the same index and columns as ``ma``.
    """
    return build_sut_Ma_from_ma_s_Yc(ma, s, Yc)


def calc_Mc(mc, Yc):
    r"""Calculate the ``Mc`` commodity-side total value added flows matrix.

    .. math::

        M_c = m_c\,\operatorname{diag}\!\left(Y_c\mathbf{1}\right)

    Final demand is summed across its columns
    before scaling the multiplier columns.
    The output columns represent production nodes, rather than final-demand
    categories.

    Parameters
    ----------
    mc : pandas.DataFrame
        Total value added coefficients: factors by commodity nodes.
    Yc : pandas.DataFrame
        Commodity final demand: commodity nodes by final-demand
        categories and regions.

    Returns
    -------
    pandas.DataFrame
        Footprint flows with the same index and columns as ``mc``.
    """
    return build_sut_Mc_from_mc_Yc(mc, Yc)


def calc_z(Z, X):
    r"""Calculate the ``z`` intersectoral transaction coefficients matrix.

    .. math::

        z = Z\,\operatorname{diag}(X)^{-1}

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

    Notes
    -----
    Inverse production is computed elementwise. A zero production
    entry has inverse zero, so the corresponding column is set to zero.
    """
    return build_iot_z_from_Z_X(Z, X)


def calc_b(X, Z):
    r"""Calculate the ``b`` intersectoral transaction direct-output coefficients matrix.

    .. math::

        b = \operatorname{diag}(X)^{-1}Z

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

    Notes
    -----
    Inverse production is computed elementwise. A zero production
    entry has inverse zero, so the corresponding row is set to zero.
    """
    return build_iot_b_from_X_Z(X, Z)


def calc_F(f, Y):
    r"""Calculate the ``F`` total (direct+indirect) environmental transaction flows matrix.

    .. math::

        F = f\,\operatorname{diag}(Y\mathbf{1})

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

    Notes
    -----
    Final demand is summed across its columns, then each column of
    ``f`` is scaled by the corresponding total. The output keeps the
    accounts and production-node axes of ``f``; it does not keep the
    final-demand category columns of ``Y``.
    """
    return build_iot_F_from_f_Y(f, Y)


def calc_Fa(fa, s, Yc):
    r"""Calculate the ``Fa`` activity-side total environmental flows matrix.

    .. math::

        F_a = f_a\,\operatorname{diag}\!\left(s\,(Y_c\mathbf{1})\right)

    Final demand is summed across its columns and mapped to activities
    through ``s`` before scaling the multiplier columns.
    The output columns represent production nodes, rather than final-demand
    categories.

    Parameters
    ----------
    fa : pandas.DataFrame
        Total environmental coefficients: accounts by activity nodes.
    s : pandas.DataFrame
        Supply coefficients: activity nodes by commodity nodes. Its
        row axis must match the columns of ``fa``.
    Yc : pandas.DataFrame
        Commodity final demand: commodity nodes by final-demand
        categories and regions.

    Returns
    -------
    pandas.DataFrame
        Footprint flows with the same index and columns as ``fa``.
    """
    return build_sut_Fa_from_fa_s_Yc(fa, s, Yc)


def calc_Fc(fc, Yc):
    r"""Calculate the ``Fc`` commodity-side total environmental flows matrix.

    .. math::

        F_c = f_c\,\operatorname{diag}\!\left(Y_c\mathbf{1}\right)

    Final demand is summed across its columns
    before scaling the multiplier columns.
    The output columns represent production nodes, rather than final-demand
    categories.

    Parameters
    ----------
    fc : pandas.DataFrame
        Total environmental coefficients: accounts by commodity nodes.
    Yc : pandas.DataFrame
        Commodity final demand: commodity nodes by final-demand
        categories and regions.

    Returns
    -------
    pandas.DataFrame
        Footprint flows with the same index and columns as ``fc``.
    """
    return build_sut_Fc_from_fc_Yc(fc, Yc)


def calc_f(e, w):
    r"""Calculate the ``f`` total (direct+indirect) environmental transaction coefficients matrix.

    .. math::

        f = e\,w

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


def calc_fa(ea, waa, ec=None, u=None):
    r"""Calculate the ``fa`` activity-side total environmental coefficients matrix.

    .. math::

        f_a = (e_a + e_c\,u)\,w_{aa}

    When ``ec=None``, the commodity term is omitted and ``u`` is
    not needed. Supplying ``ec`` without ``u`` raises ``ValueError``.

    Parameters
    ----------
    ea : pandas.DataFrame
        Activity-side direct environmental coefficients: accounts by activity nodes.
    waa : pandas.DataFrame
        Activity-to-activity Leontief inverse. Its row axis must match
        the columns of ``ea``.
    ec : pandas.DataFrame, optional
        Commodity-side direct environmental coefficients. Defaults to zero.
        Its row axis must match ``ea.index``.
    u : pandas.DataFrame, optional
        Use coefficients: commodity nodes by activity nodes. Required
        when ``ec`` is supplied.

    Returns
    -------
    pandas.DataFrame
        Total direct and indirect coefficients, with accounts on rows
        and activity nodes on columns.
    """
    return build_sut_fa_from_ea_waa(ea, waa, ec=ec, u=u)


def calc_fc(ea, s, wcc, ec=None):
    r"""Calculate the ``fc`` commodity-side total environmental coefficients matrix.

    .. math::

        f_c = (e_a\,s + e_c)\,w_{cc}

    When ``ec=None``, the commodity-side direct term is omitted.

    Parameters
    ----------
    ea : pandas.DataFrame
        Activity-side direct environmental coefficients: accounts by activity nodes.
    s : pandas.DataFrame
        Supply coefficients: activity nodes by commodity nodes. Its
        row axis must match the columns of ``ea``.
    wcc : pandas.DataFrame
        Commodity-to-commodity Leontief inverse. Its row axis must
        match ``s.columns``.
    ec : pandas.DataFrame, optional
        Commodity-side direct environmental coefficients. Defaults to zero.
        Its row axis must match ``ea.index`` and its columns
        must match ``s.columns``.

    Returns
    -------
    pandas.DataFrame
        Total direct and indirect coefficients, with accounts on rows
        and commodity nodes on columns.
    """
    return build_sut_fc_from_ea_s_wcc(ea, s, wcc, ec=ec)


def calc_ea(Ea, Xa):
    r"""Calculate the ``ea`` activity-side environmental coefficients matrix.

    .. math::

        e_a = E_a\,\operatorname{diag}(X_a)^{-1}

    Inverse production is computed elementwise; zero production entries
    have inverse zero and set the corresponding coefficient columns to zero.

    Parameters
    ----------
    Ea : pandas.DataFrame
        Direct environmental flows, with accounts on rows and activity nodes on columns.
    Xa : pandas.DataFrame
        Activity production vector. Its index must match ``Ea.columns``.

    Returns
    -------
    pandas.DataFrame
        Activity-side coefficients, with the same index and columns as ``Ea``.
    """
    return build_sut_ea_from_Ea_Xa(Ea, Xa)


def calc_ec(Ec, Xc):
    r"""Calculate the ``ec`` commodity-side environmental coefficients matrix.

    .. math::

        e_c = E_c\,\operatorname{diag}(X_c)^{-1}

    Inverse production is computed elementwise; zero production entries
    have inverse zero and set the corresponding coefficient columns to zero.

    Parameters
    ----------
    Ec : pandas.DataFrame
        Direct environmental flows, with accounts on rows and commodity nodes on columns.
    Xc : pandas.DataFrame
        Commodity production vector. Its index must match ``Ec.columns``.

    Returns
    -------
    pandas.DataFrame
        Commodity-side coefficients, with the same index and columns as ``Ec``.
    """
    return build_sut_ec_from_Ec_Xc(Ec, Xc)


def calc_f_from_z(
    e,
    z,
    *,
    method: str | None = None,
    solver: str | None = None,
    strategy: str | None = None,
):
    r"""Calculate the ``f`` total (direct+indirect) environmental transaction coefficients matrix.

    .. math::

        (I-z)^{\mathsf{T}}f^{\mathsf{T}} = e^{\mathsf{T}}

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

    Notes
    -----
    The returned matrix is :math:`f=e(I-z)^{-1}`. The solve operates
    on its transpose and returns the original account-by-node orientation.
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
    r"""Calculate the ``m`` total (direct+indirect) value added coefficients matrix.

    .. math::

        (I-z)^{\mathsf{T}}m^{\mathsf{T}} = v^{\mathsf{T}}

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

    Notes
    -----
    The returned matrix is :math:`m=v(I-z)^{-1}`. The solve operates
    on its transpose and returns the original factor-by-node orientation.
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
    r"""Calculate the ``p`` price index vector directly from ``v`` and ``z``.

    .. math::

        (I-z)^{\mathsf{T}}p = v^{\mathsf{T}}\mathbf{1}

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

    Notes
    -----
    Value added is summed over all factor rows. The result has the
    production nodes on its index and one column named ``price index``.
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
    r"""Calculate a diagonalized representation of ``f``.

    .. math::

        f_{\mathrm{dis}} = \operatorname{diag}(e_k)\,w

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

    Notes
    -----
    ``e`` must contain one account with one coefficient per production
    node. Rows identify contributing nodes and columns identify the
    receiving nodes. Summing the rows recovers that account in ``calc_f``.
    For multiple accounts, use ``db.f_ex(...)``.
    """
    values = np.diagflat(dense_values(e).reshape(-1)) @ dense_values(w)
    result = pd.DataFrame(values, index=w.index, columns=w.columns)
    result.index = getattr(e, "columns", w.index)
    return result


def calc_y(Y):
    r"""Normalize the ``Y`` final demand matrix by its grand total.

    .. math::

        y = \frac{Y}{\sum_{i,j}Y_{ij}}

    Parameters
    ----------
    Y : pandas.DataFrame
        ``Y`` final demand matrix.

    Returns
    -------
    pandas.DataFrame
        Shares of the ``Y`` final demand matrix, computed as
        ``Y / Y.sum().sum()``.

    Notes
    -----
    Normalization uses one grand total for the whole matrix, rather
    than normalizing each row or column separately. A zero grand total
    is not replaced: pandas division can produce NaN or infinite values.
    """
    return Y / Y.sum().sum()


def calc_u(U, Xa):
    r"""Calculate the SUT use coefficients matrix ``u``.

    .. math::

        u = U\operatorname{diag}(X_a)^{-1}

    Parameters
    ----------
    U : pandas.DataFrame
        Use flows, with commodity rows and activity columns.
    Xa : pandas.DataFrame or pandas.Series
        Activity production, indexed exactly like the columns of ``U``.
        A DataFrame must have one column.

    Returns
    -------
    pandas.DataFrame
        Use coefficients, with the commodity rows and activity columns of ``U``.

    Notes
    -----
    Each column is divided by activity production. A zero production value
    sets the corresponding coefficient column to zero. The same equation
    applies under IT and PT.

    Examples
    --------
    .. code-block:: python

        import mario

        u = mario.calc_u(U, Xa)
    """
    return build_sut_u_from_U_Xa(U, Xa)


def calc_U(u, Xa):
    r"""Calculate the SUT use flows matrix ``U``.

    .. math::

        U = u\operatorname{diag}(X_a)

    Parameters
    ----------
    u : pandas.DataFrame
        Use coefficients, with commodity rows and activity columns.
    Xa : pandas.DataFrame or pandas.Series
        Activity production, indexed exactly like the columns of ``u``.
        A DataFrame must have one column.

    Returns
    -------
    pandas.DataFrame
        Use flows, with the commodity rows and activity columns of ``u``.
    """
    return build_sut_U_from_u_Xa(u, Xa)


def calc_s(S, Xc=None, *, Xa=None, tech_assumption=None):
    r"""Calculate the SUT supply coefficients matrix ``s`` under IT or PT.

    .. math::

        s = \begin{cases}
            S\operatorname{diag}(X_c)^{-1} & \text{IT},\\
            \left(S^{\mathsf{T}}\operatorname{diag}(X_a)^{-1}\right)^{-1}
            & \text{PT}.
        \end{cases}

    Parameters
    ----------
    S : pandas.DataFrame
        Supply flows, with activity rows and commodity columns.
    Xc : pandas.DataFrame or pandas.Series, optional
        Commodity production, required under IT and unused under PT. Its
        index must match the columns of ``S``. A DataFrame must have one column.
    Xa : pandas.DataFrame or pandas.Series, optional
        Activity production, required under PT and unused under IT. Its
        index must match the rows of ``S``. A DataFrame must have one column.
    tech_assumption : {"industry-based", "product-based", "IT", "PT"}, optional
        Technology assumption; defaults to industry-based (IT).

    Returns
    -------
    pandas.DataFrame
        Supply coefficients, with the activity rows and commodity columns of ``S``.

    Notes
    -----
    IT supports rectangular supply tables and treats inverse zero production
    as zero. PT requires a square supply table and ``Xa``; a missing ``Xa``
    raises ``ValueError``. The PT matrix inverse falls back to the
    Moore-Penrose pseudo-inverse for a singular product-mix matrix.

    Examples
    --------
    .. code-block:: python

        import mario

        s_it = mario.calc_s(S, Xc)
        s_pt = mario.calc_s(S, Xa=Xa, tech_assumption="PT")
    """
    return build_sut_s_from_S_Xc(S, Xc, Xa=Xa, tech_assumption=tech_assumption)


def calc_S(s, Xc=None, *, Xa=None, tech_assumption=None):
    r"""Calculate the SUT supply flows matrix ``S`` under IT or PT.

    .. math::

        S = \begin{cases}
            s\operatorname{diag}(X_c) & \text{IT},\\
            \left(c\operatorname{diag}(X_a)\right)^{\mathsf{T}},
            \quad c=s^{-1} & \text{PT}.
        \end{cases}

    Parameters
    ----------
    s : pandas.DataFrame
        Supply coefficients, with activity rows and commodity columns.
    Xc : pandas.DataFrame or pandas.Series, optional
        Commodity production, required under IT and unused under PT. Its
        index must match the columns of ``s``. A DataFrame must have one column.
    Xa : pandas.DataFrame or pandas.Series, optional
        Activity production, required under PT and unused under IT. Its
        index must match the rows of ``s``. A DataFrame must have one column.
    tech_assumption : {"industry-based", "product-based", "IT", "PT"}, optional
        Technology assumption; defaults to industry-based (IT).

    Returns
    -------
    pandas.DataFrame
        Supply flows, with the activity rows and commodity columns of ``s``.

    Notes
    -----
    IT supports rectangular supply tables. PT requires square ``s`` and
    ``Xa``; a missing ``Xa`` raises ``ValueError``. The PT matrix inverse
    falls back to the Moore-Penrose pseudo-inverse for singular ``s``.

    Examples
    --------
    .. code-block:: python

        import mario

        S_it = mario.calc_S(s_it, Xc)
        S_pt = mario.calc_S(s_pt, Xa=Xa, tech_assumption="PT")
    """
    return build_sut_S_from_s_Xc(s, Xc, Xa=Xa, tech_assumption=tech_assumption)


def calc_c(S, Xa):
    r"""Calculate the SUT product-mix matrix ``c`` for product-based technology.

    .. math::

        c = S^{\mathsf{T}}\operatorname{diag}(X_a)^{-1}

    Parameters
    ----------
    S : pandas.DataFrame
        Supply flows, with activity rows and commodity columns.
    Xa : pandas.DataFrame or pandas.Series
        Activity production, indexed exactly like the rows of ``S``.
        A DataFrame must have one column.

    Returns
    -------
    pandas.DataFrame
        Product-mix coefficients, with the commodity columns of ``S`` as rows
        and its activity rows as columns.

    Notes
    -----
    This helper explicitly uses the product-based definition. Inverse zero
    activity production is treated as zero. For a nonsingular square product
    mix, the PT supply coefficients satisfy ``s = c^-1``.
    """
    return build_sut_c_from_S_Xa(S, Xa, tech_assumption="PT")


def calc_Xa(S, Ya):
    r"""Calculate SUT activity production ``Xa`` from supply flows and final demand.

    .. math::

        X_a = S\mathbf{1} + Y_a\mathbf{1}

    Parameters
    ----------
    S : pandas.DataFrame
        Supply flows, with activity rows and commodity columns.
    Ya : pandas.DataFrame
        Activity final demand, with the same row index as ``S``.
        Pass an explicitly zero block when activity final demand is absent.

    Returns
    -------
    pandas.DataFrame
        Activity production, indexed like the rows of ``S``, with one column
        named ``production``.
    """
    return build_sut_Xa_from_S_Ya(S, Ya)


def calc_Xc(U, Yc):
    r"""Calculate SUT commodity production ``Xc`` from use flows and final demand.

    .. math::

        X_c = U\mathbf{1} + Y_c\mathbf{1}

    Parameters
    ----------
    U : pandas.DataFrame
        Use flows, with commodity rows and activity columns.
    Yc : pandas.DataFrame
        Commodity final demand, with the same row index as ``U``.

    Returns
    -------
    pandas.DataFrame
        Commodity production, indexed like the rows of ``U``, with one column
        named ``production``.
    """
    return build_sut_Xc_from_U_Yc(U, Yc)


def calc_wcc(u, s):
    r"""Calculate the SUT commodity-to-commodity Leontief block ``wcc``.

    .. math::

        w_{cc} = (I-us)^{-1}

    Parameters
    ----------
    u : pandas.DataFrame
        Use coefficients, with commodity rows and activity columns.
    s : pandas.DataFrame
        Supply coefficients, with activity rows and commodity columns.
        Its row index must match the columns of ``u`` and its columns must
        match the row index of ``u``, including order.

    Returns
    -------
    pandas.DataFrame
        Leontief block, with the commodity rows and commodity columns of ``u @ s``.

    Notes
    -----
    Rectangular use/supply tables are supported. The inverse falls back to
    the Moore-Penrose pseudo-inverse if the system matrix is singular.
    """
    return build_sut_wcc_from_u_s(u, s)


def calc_wca(u, s):
    r"""Calculate the SUT commodity-to-activity Leontief block ``wca``.

    .. math::

        w_{ca} = (I-us)^{-1}u = w_{cc}u

    Parameters
    ----------
    u : pandas.DataFrame
        Use coefficients, with commodity rows and activity columns.
    s : pandas.DataFrame
        Supply coefficients, with activity rows and commodity columns.
        Its row index must match the columns of ``u`` and its columns must
        match the row index of ``u``, including order.

    Returns
    -------
    pandas.DataFrame
        Leontief block, with the commodity rows and activity columns of ``u``.

    Notes
    -----
    Rectangular use/supply tables are supported. The inverse falls back to
    the Moore-Penrose pseudo-inverse if the system matrix is singular.
    """
    return build_sut_wca_from_u_s(u, s)


def calc_wac(s, u):
    r"""Calculate the SUT activity-to-commodity Leontief block ``wac``.

    .. math::

        w_{ac} = (I-su)^{-1}s = w_{aa}s

    Parameters
    ----------
    s : pandas.DataFrame
        Supply coefficients, with activity rows and commodity columns.
        Its row index must match the columns of ``u`` and its columns must
        match the row index of ``u``, including order.
    u : pandas.DataFrame
        Use coefficients, with commodity rows and activity columns.

    Returns
    -------
    pandas.DataFrame
        Leontief block, with the activity rows and commodity columns of ``s``.

    Notes
    -----
    Rectangular use/supply tables are supported. The inverse falls back to
    the Moore-Penrose pseudo-inverse if the system matrix is singular.
    """
    return build_sut_wac_from_s_u(s, u)


def calc_waa(s, u):
    r"""Calculate the SUT activity-to-activity Leontief block ``waa``.

    .. math::

        w_{aa} = (I-su)^{-1}

    Parameters
    ----------
    s : pandas.DataFrame
        Supply coefficients, with activity rows and commodity columns.
        Its row index must match the columns of ``u`` and its columns must
        match the row index of ``u``, including order.
    u : pandas.DataFrame
        Use coefficients, with commodity rows and activity columns.

    Returns
    -------
    pandas.DataFrame
        Leontief block, with the activity rows and activity columns of ``s @ u``.

    Notes
    -----
    Rectangular use/supply tables are supported. The inverse falls back to
    the Moore-Penrose pseudo-inverse if the system matrix is singular.
    """
    return build_sut_waa_from_s_u(s, u)


def calc_bu(Xc, U):
    r"""Calculate the SUT use direct-output coefficients ``bu``.

    .. math::

        b_u = \operatorname{diag}(X_c)^{-1}U

    Parameters
    ----------
    Xc : pandas.DataFrame or pandas.Series
        Commodity production, indexed exactly like the rows of ``U``.
        A DataFrame must have one column.
    U : pandas.DataFrame
        Use flows, with commodity rows and activity columns.

    Returns
    -------
    pandas.DataFrame
        Direct-output coefficients, with the commodity rows and activity
        columns of ``U``.

    Notes
    -----
    Each row is divided by commodity production. A zero production value
    sets the corresponding coefficient row to zero.
    """
    return build_sut_bu_from_Xc_U(Xc, U)


def calc_bs(Xa, S):
    r"""Calculate the SUT supply direct-output coefficients ``bs``.

    .. math::

        b_s = \operatorname{diag}(X_a)^{-1}S

    Parameters
    ----------
    Xa : pandas.DataFrame or pandas.Series
        Activity production, indexed exactly like the rows of ``S``.
        A DataFrame must have one column.
    S : pandas.DataFrame
        Supply flows, with activity rows and commodity columns.

    Returns
    -------
    pandas.DataFrame
        Direct-output coefficients, with the activity rows and commodity
        columns of ``S``.

    Notes
    -----
    Each row is divided by activity production. A zero production value
    sets the corresponding coefficient row to zero.
    """
    return build_sut_bs_from_Xa_S(Xa, S)


def calc_gcc(bu, bs):
    r"""Calculate the SUT Ghosh block ``gcc``.

    .. math::

        g_{cc} = (I-b_u b_s)^{-1}

    Parameters
    ----------
    bu : pandas.DataFrame
        Use direct-output coefficients, with commodity rows and activity columns.
    bs : pandas.DataFrame
        Supply direct-output coefficients, with activity rows and commodity
        columns. Its rows and columns must match the columns and rows of
        ``bu``, respectively, including order.

    Returns
    -------
    pandas.DataFrame
        Ghosh block, with commodity nodes on both axes.

    Notes
    -----
    The inverse falls back to the Moore-Penrose pseudo-inverse if the
    system matrix is singular.
    """
    return build_sut_gcc_from_bu_bs(bu, bs)


def calc_gca(gcc, bu):
    r"""Calculate the SUT Ghosh block ``gca``.

    .. math::

        g_{ca} = g_{cc}b_u

    Parameters
    ----------
    gcc : pandas.DataFrame
        Commodity-to-commodity Ghosh block, with columns matching the
        commodity rows of ``bu``.
    bu : pandas.DataFrame
        Use direct-output coefficients, with commodity rows and activity columns.

    Returns
    -------
    pandas.DataFrame
        Ghosh block, with the commodity rows of ``gcc`` and activity columns of ``bu``.
    """
    return build_sut_gca_from_gcc_bu(gcc, bu)


def calc_gac(gaa, bs):
    r"""Calculate the SUT Ghosh block ``gac``.

    .. math::

        g_{ac} = g_{aa}b_s

    Parameters
    ----------
    gaa : pandas.DataFrame
        Activity-to-activity Ghosh block, with columns matching the activity
        rows of ``bs``.
    bs : pandas.DataFrame
        Supply direct-output coefficients, with activity rows and commodity columns.

    Returns
    -------
    pandas.DataFrame
        Ghosh block, with the activity rows of ``gaa`` and commodity columns of ``bs``.
    """
    return build_sut_gac_from_gaa_bs(gaa, bs)


def calc_gaa(bs, bu):
    r"""Calculate the SUT Ghosh block ``gaa``.

    .. math::

        g_{aa} = (I-b_s b_u)^{-1}

    Parameters
    ----------
    bs : pandas.DataFrame
        Supply direct-output coefficients, with activity rows and commodity
        columns. Its rows and columns must match the columns and rows of
        ``bu``, respectively, including order.
    bu : pandas.DataFrame
        Use direct-output coefficients, with commodity rows and activity columns.

    Returns
    -------
    pandas.DataFrame
        Ghosh block, with activity nodes on both axes.

    Notes
    -----
    The inverse falls back to the Moore-Penrose pseudo-inverse if the
    system matrix is singular.
    """
    return build_sut_gaa_from_bs_bu(bs, bu)


def calc_pa(va, vc, waa, wca):
    r"""Calculate the SUT activity price index ``pa``.

    .. math::

        p_a = w_{aa}^{\mathsf{T}}v_a^{\mathsf{T}}\mathbf{1} + w_{ca}^{\mathsf{T}}v_c^{\mathsf{T}}\mathbf{1}

    Parameters
    ----------
    va : pandas.DataFrame
        Direct value-added coefficients, with factor rows and activity columns.
        The columns must match the row index of ``waa``.
    vc : pandas.DataFrame
        Direct value-added coefficients, with factor rows and commodity columns.
        The columns must match the row index of ``wca``.
    waa : pandas.DataFrame
        Leontief block with activity rows and activity columns.
    wca : pandas.DataFrame
        Leontief block with commodity rows and activity columns, matching
        the columns of ``waa``.

    Returns
    -------
    pandas.DataFrame
        Price index, indexed by activity nodes, with one column named
        ``price index``.

    Notes
    -----
    All value-added factor rows are summed before applying the transposed
    Leontief blocks. Both activity and commodity direct contributions
    are included.
    """
    return build_sut_pa_from_va(va, vc, waa, wca)


def calc_pc(va, vc, wac, wcc):
    r"""Calculate the SUT commodity price index ``pc``.

    .. math::

        p_c = w_{ac}^{\mathsf{T}}v_a^{\mathsf{T}}\mathbf{1} + w_{cc}^{\mathsf{T}}v_c^{\mathsf{T}}\mathbf{1}

    Parameters
    ----------
    va : pandas.DataFrame
        Direct value-added coefficients, with factor rows and activity columns.
        The columns must match the row index of ``wac``.
    vc : pandas.DataFrame
        Direct value-added coefficients, with factor rows and commodity columns.
        The columns must match the row index of ``wcc``.
    wac : pandas.DataFrame
        Leontief block with activity rows and commodity columns.
    wcc : pandas.DataFrame
        Leontief block with commodity rows and commodity columns, matching
        the columns of ``wac``.

    Returns
    -------
    pandas.DataFrame
        Price index, indexed by commodity nodes, with one column named
        ``price index``.

    Notes
    -----
    All value-added factor rows are summed before applying the transposed
    Leontief blocks. Both activity and commodity direct contributions
    are included.
    """
    return build_sut_pc_from_vc(va, vc, wac, wcc)



def X_inverse(X):
    """Return the inverse-production vector as a dense NumPy array."""
    return dense_values(inverse_vector(X))


def linkages_calculation(cut_diag, matrices, multi_mode, normalized):
    """Return backward and forward linkage indicators."""
    def _safe_ratio(numerator, denominator):
        ratio = numerator.astype(float).div(denominator.astype(float))
        return ratio.where(denominator.astype(float) != 0)

    def _safe_share(part, whole):
        share = part.astype(float).div(whole.astype(float))
        return share.where(whole.astype(float) != 0)

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

        base_totals = {
            "Total Forward": links[("Total Forward", "Local")] + links[("Total Forward", "Foreign")],
            "Total Backward": links[("Total Backward", "Local")] + links[("Total Backward", "Foreign")],
            "Direct Forward": links[("Direct Forward", "Local")] + links[("Direct Forward", "Foreign")],
            "Direct Backward": links[("Direct Backward", "Local")] + links[("Direct Backward", "Foreign")],
        }

        share_columns = {}
        for measure, total in base_totals.items():
            share_columns[(measure, "Local Share")] = _safe_share(links[(measure, "Local")], total)
            share_columns[(measure, "Foreign Share")] = _safe_share(
                links[(measure, "Foreign")], total
            )

        share_frame = pd.DataFrame(share_columns, index=links.index)
        links = pd.concat([links, share_frame], axis=1)

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
        forward_amplification = _safe_ratio(forward_total.iloc[:, 0], forward_direct.iloc[:, 0]).to_frame(
            "Forward Amplification"
        )
        backward_amplification = _safe_ratio(
            backward_total.iloc[:, 0], backward_direct.iloc[:, 0]
        ).to_frame("Backward Amplification")

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
            [
                forward_total,
                backward_total,
                forward_direct,
                backward_direct,
                forward_amplification,
                backward_amplification,
            ],
            axis=1,
        )

    return links
