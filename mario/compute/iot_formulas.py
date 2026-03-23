"""Pure IOT compute formulas for MARIO 2."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mario.compute.ghosh_formulas import build_iot_b_from_X_Z, build_iot_g_from_b
from mario.compute.helpers import (
    as_column_frame,
    diag_from_vector,
    identity_like,
    inverse_vector,
    require_same_columns,
    require_same_index,
    safe_inverse,
    sum_final_demand,
    validate_square,
)
from mario.model.labels import PRICE_INDEX_LABEL, PRODUCTION_LABEL


def build_iot_Z_from_z_X(z: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    validate_square(z)
    require_same_index(z, X, lhs_name="z", rhs_name="X")
    values = z.to_numpy(dtype=float) @ diag_from_vector(X)
    return pd.DataFrame(values, index=z.index, columns=z.columns)


def build_iot_z_from_Z_X(Z: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    validate_square(Z)
    require_same_index(Z, X, lhs_name="Z", rhs_name="X")
    values = Z.to_numpy(dtype=float) @ np.diagflat(inverse_vector(X).to_numpy(dtype=float))
    return pd.DataFrame(values, index=Z.index, columns=Z.columns)


def build_iot_w_from_z(z: pd.DataFrame) -> pd.DataFrame:
    validate_square(z)
    return safe_inverse(identity_like(z) - z)


def build_iot_X_from_Z_Y(Z: pd.DataFrame, Y: pd.DataFrame) -> pd.DataFrame:
    validate_square(Z)
    require_same_index(Z, Y, lhs_name="Z", rhs_name="Y")
    total = Z.sum(axis=1) + sum_final_demand(Y)
    return as_column_frame(total, PRODUCTION_LABEL)


def build_iot_X_from_w_Y(w: pd.DataFrame, Y: pd.DataFrame) -> pd.DataFrame:
    validate_square(w)
    y_total = sum_final_demand(Y)
    require_same_index(w, y_total, lhs_name="w", rhs_name="Y_total")
    total = w.dot(y_total)
    return as_column_frame(total, PRODUCTION_LABEL)


def build_iot_V_from_v_X(v: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    require_same_columns(v, X.index, lhs_name="v", rhs_name="X")
    values = v.to_numpy(dtype=float) @ diag_from_vector(X)
    return pd.DataFrame(values, index=v.index, columns=v.columns)


def build_iot_v_from_V_X(V: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    require_same_columns(V, X.index, lhs_name="V", rhs_name="X")
    values = V.to_numpy(dtype=float) @ np.diagflat(inverse_vector(X).to_numpy(dtype=float))
    return pd.DataFrame(values, index=V.index, columns=V.columns)


def build_iot_E_from_e_X(e: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    require_same_columns(e, X.index, lhs_name="e", rhs_name="X")
    values = e.to_numpy(dtype=float) @ diag_from_vector(X)
    return pd.DataFrame(values, index=e.index, columns=e.columns)


def build_iot_e_from_E_X(E: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    require_same_columns(E, X.index, lhs_name="E", rhs_name="X")
    values = E.to_numpy(dtype=float) @ np.diagflat(inverse_vector(X).to_numpy(dtype=float))
    return pd.DataFrame(values, index=E.index, columns=E.columns)


def build_iot_m_from_v_w(v: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    validate_square(w)
    require_same_columns(v, w.index, lhs_name="v", rhs_name="w")
    return v.dot(w)


def build_iot_M_from_m_Y(m: pd.DataFrame, Y: pd.DataFrame) -> pd.DataFrame:
    y_total = sum_final_demand(Y)
    require_same_columns(m, y_total.index, lhs_name="m", rhs_name="Y_total")
    values = m.to_numpy(dtype=float) @ np.diagflat(y_total.to_numpy(dtype=float))
    return pd.DataFrame(values, index=m.index, columns=m.columns)


def build_iot_f_from_e_w(e: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    validate_square(w)
    require_same_columns(e, w.index, lhs_name="e", rhs_name="w")
    return e.dot(w)


def build_iot_F_from_f_Y(f: pd.DataFrame, Y: pd.DataFrame) -> pd.DataFrame:
    y_total = sum_final_demand(Y)
    require_same_columns(f, y_total.index, lhs_name="f", rhs_name="Y_total")
    values = f.to_numpy(dtype=float) @ np.diagflat(y_total.to_numpy(dtype=float))
    return pd.DataFrame(values, index=f.index, columns=f.columns)


def build_iot_p_from_v_w(v: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    validate_square(w)
    require_same_columns(v, w.index, lhs_name="v", rhs_name="w")
    direct_value_added = v.sum(axis=0)
    values = w.T.dot(direct_value_added)
    return pd.DataFrame(values.to_numpy(dtype=float), index=w.columns, columns=[PRICE_INDEX_LABEL])
