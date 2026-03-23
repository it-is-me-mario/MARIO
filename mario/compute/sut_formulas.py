"""Pure SUT compute formulas for MARIO 2."""

from __future__ import annotations

import numpy as np
import pandas as pd

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
from mario.model.labels import ITEM_LABEL, PRICE_INDEX_LABEL, PRODUCTION_LABEL


def _vector_series(vector: pd.DataFrame | pd.Series, *, label: str) -> pd.Series:
    if isinstance(vector, pd.Series):
        return vector.copy()

    if isinstance(vector, pd.DataFrame):
        if vector.shape[1] != 1:
            raise ValueError(f"{label} must be a single-column block.")
        return vector.iloc[:, 0].copy()

    raise TypeError(f"{label} must be a pandas Series or single-column DataFrame.")


def _production_frame(vector: pd.Series) -> pd.DataFrame:
    frame = as_column_frame(vector, PRODUCTION_LABEL)
    frame.columns = pd.Index([PRODUCTION_LABEL], name=ITEM_LABEL)
    return frame


def build_sut_wcc_from_u_s(u: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    require_same_columns(u, s.index, lhs_name="u", rhs_name="s.index")
    require_same_index(u, s.columns, lhs_name="u", rhs_name="s.columns")
    product = u.dot(s)
    validate_square(product)
    return safe_inverse(identity_like(product) - product)


def build_sut_wca_from_u_s(u: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    require_same_columns(u, s.index, lhs_name="u", rhs_name="s.index")
    return build_sut_wcc_from_u_s(u, s).dot(u)


def build_sut_wac_from_s_u(s: pd.DataFrame, u: pd.DataFrame) -> pd.DataFrame:
    require_same_columns(s, u.index, lhs_name="s", rhs_name="u.index")
    return build_sut_waa_from_s_u(s, u).dot(s)


def build_sut_waa_from_s_u(s: pd.DataFrame, u: pd.DataFrame) -> pd.DataFrame:
    require_same_columns(s, u.index, lhs_name="s", rhs_name="u.index")
    require_same_index(s, u.columns, lhs_name="s", rhs_name="u.columns")
    product = s.dot(u)
    validate_square(product)
    return safe_inverse(identity_like(product) - product)


def build_sut_Xa_from_S_Ya(S: pd.DataFrame, Ya: pd.DataFrame) -> pd.DataFrame:
    y_total = sum_final_demand(Ya)
    require_same_index(S, y_total, lhs_name="S", rhs_name="Ya_total")
    total = S.sum(axis=1) + y_total
    return _production_frame(total)


def build_sut_Xa_from_s_Xc(s: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(s, x_c.index, lhs_name="s", rhs_name="Xc")
    total = s.dot(x_c)
    return _production_frame(total)


def build_sut_Xc_from_U_Yc(U: pd.DataFrame, Yc: pd.DataFrame) -> pd.DataFrame:
    y_total = sum_final_demand(Yc)
    require_same_index(U, y_total, lhs_name="U", rhs_name="Yc_total")
    total = U.sum(axis=1) + y_total
    return _production_frame(total)


def build_sut_Xc_from_wcc_Yc(wcc: pd.DataFrame, Yc: pd.DataFrame) -> pd.DataFrame:
    validate_square(wcc)
    y_total = sum_final_demand(Yc)
    require_same_index(wcc, y_total, lhs_name="wcc", rhs_name="Yc_total")
    total = wcc.dot(y_total)
    return _production_frame(total)


def build_sut_U_from_u_Xa(u: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(u, x_a.index, lhs_name="u", rhs_name="Xa")
    values = u.to_numpy(dtype=float) @ diag_from_vector(x_a)
    return pd.DataFrame(values, index=u.index, columns=u.columns)


def build_sut_u_from_U_Xa(U: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(U, x_a.index, lhs_name="U", rhs_name="Xa")
    values = U.to_numpy(dtype=float) @ np.diagflat(inverse_vector(x_a).to_numpy(dtype=float))
    return pd.DataFrame(values, index=U.index, columns=U.columns)


def build_sut_S_from_s_Xc(s: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(s, x_c.index, lhs_name="s", rhs_name="Xc")
    values = s.to_numpy(dtype=float) @ diag_from_vector(x_c)
    return pd.DataFrame(values, index=s.index, columns=s.columns)


def build_sut_s_from_S_Xc(S: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(S, x_c.index, lhs_name="S", rhs_name="Xc")
    values = S.to_numpy(dtype=float) @ np.diagflat(inverse_vector(x_c).to_numpy(dtype=float))
    return pd.DataFrame(values, index=S.index, columns=S.columns)


def build_sut_Va_from_va_Xa(va: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(va, x_a.index, lhs_name="va", rhs_name="Xa")
    values = va.to_numpy(dtype=float) @ diag_from_vector(x_a)
    return pd.DataFrame(values, index=va.index, columns=va.columns)


def build_sut_Vc_from_vc_Xc(vc: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(vc, x_c.index, lhs_name="vc", rhs_name="Xc")
    values = vc.to_numpy(dtype=float) @ diag_from_vector(x_c)
    return pd.DataFrame(values, index=vc.index, columns=vc.columns)


def build_sut_va_from_Va_Xa(Va: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(Va, x_a.index, lhs_name="Va", rhs_name="Xa")
    values = Va.to_numpy(dtype=float) @ np.diagflat(inverse_vector(x_a).to_numpy(dtype=float))
    return pd.DataFrame(values, index=Va.index, columns=Va.columns)


def build_sut_vc_from_Vc_Xc(Vc: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(Vc, x_c.index, lhs_name="Vc", rhs_name="Xc")
    values = Vc.to_numpy(dtype=float) @ np.diagflat(inverse_vector(x_c).to_numpy(dtype=float))
    return pd.DataFrame(values, index=Vc.index, columns=Vc.columns)


def build_sut_Ea_from_ea_Xa(ea: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(ea, x_a.index, lhs_name="ea", rhs_name="Xa")
    values = ea.to_numpy(dtype=float) @ diag_from_vector(x_a)
    return pd.DataFrame(values, index=ea.index, columns=ea.columns)


def build_sut_Ec_from_ec_Xc(ec: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(ec, x_c.index, lhs_name="ec", rhs_name="Xc")
    values = ec.to_numpy(dtype=float) @ diag_from_vector(x_c)
    return pd.DataFrame(values, index=ec.index, columns=ec.columns)


def build_sut_ea_from_Ea_Xa(Ea: pd.DataFrame, Xa: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_a = _vector_series(Xa, label="Xa")
    require_same_columns(Ea, x_a.index, lhs_name="Ea", rhs_name="Xa")
    values = Ea.to_numpy(dtype=float) @ np.diagflat(inverse_vector(x_a).to_numpy(dtype=float))
    return pd.DataFrame(values, index=Ea.index, columns=Ea.columns)


def build_sut_ec_from_Ec_Xc(Ec: pd.DataFrame, Xc: pd.DataFrame | pd.Series) -> pd.DataFrame:
    x_c = _vector_series(Xc, label="Xc")
    require_same_columns(Ec, x_c.index, lhs_name="Ec", rhs_name="Xc")
    values = Ec.to_numpy(dtype=float) @ np.diagflat(inverse_vector(x_c).to_numpy(dtype=float))
    return pd.DataFrame(values, index=Ec.index, columns=Ec.columns)


def build_sut_Mc_from_mc_Yc(mc: pd.DataFrame, Yc: pd.DataFrame) -> pd.DataFrame:
    y_total = sum_final_demand(Yc)
    require_same_columns(mc, y_total.index, lhs_name="mc", rhs_name="Yc_total")
    values = mc.to_numpy(dtype=float) @ np.diagflat(y_total.to_numpy(dtype=float))
    return pd.DataFrame(values, index=mc.index, columns=mc.columns)


def build_sut_Ma_from_ma_Ya(ma: pd.DataFrame, Ya: pd.DataFrame) -> pd.DataFrame:
    y_total = sum_final_demand(Ya)
    require_same_columns(ma, y_total.index, lhs_name="ma", rhs_name="Ya_total")
    values = ma.to_numpy(dtype=float) @ np.diagflat(y_total.to_numpy(dtype=float))
    return pd.DataFrame(values, index=ma.index, columns=ma.columns)


def build_sut_ma_from_va_waa(va: pd.DataFrame, waa: pd.DataFrame) -> pd.DataFrame:
    validate_square(waa)
    require_same_columns(va, waa.index, lhs_name="va", rhs_name="waa")
    return va.dot(waa)


def build_sut_mc_from_va_s_wcc(va: pd.DataFrame, s: pd.DataFrame, wcc: pd.DataFrame) -> pd.DataFrame:
    validate_square(wcc)
    require_same_columns(va, s.index, lhs_name="va", rhs_name="s.index")
    require_same_columns(s, wcc.index, lhs_name="s", rhs_name="wcc")
    return va.dot(s).dot(wcc)


def build_sut_Fc_from_fc_Yc(fc: pd.DataFrame, Yc: pd.DataFrame) -> pd.DataFrame:
    y_total = sum_final_demand(Yc)
    require_same_columns(fc, y_total.index, lhs_name="fc", rhs_name="Yc_total")
    values = fc.to_numpy(dtype=float) @ np.diagflat(y_total.to_numpy(dtype=float))
    return pd.DataFrame(values, index=fc.index, columns=fc.columns)


def build_sut_Fa_from_fa_Ya(fa: pd.DataFrame, Ya: pd.DataFrame) -> pd.DataFrame:
    y_total = sum_final_demand(Ya)
    require_same_columns(fa, y_total.index, lhs_name="fa", rhs_name="Ya_total")
    values = fa.to_numpy(dtype=float) @ np.diagflat(y_total.to_numpy(dtype=float))
    return pd.DataFrame(values, index=fa.index, columns=fa.columns)


def build_sut_fa_from_ea_waa(ea: pd.DataFrame, waa: pd.DataFrame) -> pd.DataFrame:
    validate_square(waa)
    require_same_columns(ea, waa.index, lhs_name="ea", rhs_name="waa")
    return ea.dot(waa)


def build_sut_fc_from_ea_s_wcc(ea: pd.DataFrame, s: pd.DataFrame, wcc: pd.DataFrame) -> pd.DataFrame:
    validate_square(wcc)
    require_same_columns(ea, s.index, lhs_name="ea", rhs_name="s.index")
    require_same_columns(s, wcc.index, lhs_name="s", rhs_name="wcc")
    return ea.dot(s).dot(wcc)


def build_sut_pc_from_vc(
    va: pd.DataFrame,
    vc: pd.DataFrame,
    wac: pd.DataFrame,
    wcc: pd.DataFrame,
) -> pd.DataFrame:
    direct_a = va.sum(axis=0)
    direct_c = vc.sum(axis=0)
    require_same_index(wac, direct_a, lhs_name="wac", rhs_name="va.sum(0)")
    require_same_index(wcc, direct_c, lhs_name="wcc", rhs_name="vc.sum(0)")
    values = wac.T.dot(direct_a) + wcc.T.dot(direct_c)
    return as_column_frame(values, PRICE_INDEX_LABEL)


def build_sut_pa_from_va(
    va: pd.DataFrame,
    vc: pd.DataFrame,
    waa: pd.DataFrame,
    wca: pd.DataFrame,
) -> pd.DataFrame:
    direct_a = va.sum(axis=0)
    direct_c = vc.sum(axis=0)
    require_same_index(waa, direct_a, lhs_name="waa", rhs_name="va.sum(0)")
    require_same_index(wca, direct_c, lhs_name="wca", rhs_name="vc.sum(0)")
    values = waa.T.dot(direct_a) + wca.T.dot(direct_c)
    return as_column_frame(values, PRICE_INDEX_LABEL)
