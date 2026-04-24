"""Centralized SUT view builders and extractors."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mario.compute.ordering import SUTUnifiedOrderingPolicy


def _common_dtype(*blocks: pd.DataFrame | pd.Series) -> np.dtype:
    """Return a dtype able to represent all provided blocks."""
    dtypes = [np.asarray(block).dtype for block in blocks if block is not None]
    if not dtypes:
        return np.dtype(float)

    return np.result_type(*dtypes)


def _zeros(index: pd.Index, columns: pd.Index, dtype: np.dtype) -> pd.DataFrame:
    """Return a zero-filled dataframe with the requested labels."""
    return pd.DataFrame(
        np.zeros((len(index), len(columns)), dtype=dtype),
        index=index,
        columns=columns,
    )


def _reindex_exact(
    block: pd.DataFrame,
    *,
    index: pd.Index | None = None,
    columns: pd.Index | None = None,
    label: str = "block",
) -> pd.DataFrame:
    """Reindex a block only when its labels match the policy exactly."""
    if index is not None:
        missing = index.difference(block.index)
        extra = block.index.difference(index)
        if len(missing) or len(extra):
            raise ValueError(f"{label} row labels do not match the ordering policy.")
        block = block.loc[index, :]

    if columns is not None:
        missing = columns.difference(block.columns)
        extra = block.columns.difference(columns)
        if len(missing) or len(extra):
            raise ValueError(f"{label} column labels do not match the ordering policy.")
        block = block.loc[:, columns]

    return block


def _concat_square_blocks(
    top_left: pd.DataFrame,
    top_right: pd.DataFrame,
    bottom_left: pd.DataFrame,
    bottom_right: pd.DataFrame,
) -> pd.DataFrame:
    """Build a square unified block from four ordered quadrants."""
    top = pd.concat([top_left, top_right], axis=1)
    bottom = pd.concat([bottom_left, bottom_right], axis=1)
    return pd.concat([top, bottom], axis=0)


def _concat_two_part_rows(
    upper: pd.DataFrame,
    lower: pd.DataFrame,
    ordering: SUTUnifiedOrderingPolicy,
    label: str,
) -> pd.DataFrame:
    """Stack activity and commodity row blocks into one unified block."""
    upper = _reindex_exact(upper, index=ordering.activity_index, label=f"{label}.upper")
    lower = _reindex_exact(lower, index=ordering.commodity_index, label=f"{label}.lower")
    return pd.concat([upper, lower], axis=0)


def _concat_two_part_columns(
    left: pd.DataFrame,
    right: pd.DataFrame,
    ordering: SUTUnifiedOrderingPolicy,
    label: str,
) -> pd.DataFrame:
    """Join activity and commodity column blocks into one unified block."""
    left = _reindex_exact(left, columns=ordering.activity_index, label=f"{label}.left")
    right = _reindex_exact(right, columns=ordering.commodity_index, label=f"{label}.right")
    return pd.concat([left, right], axis=1)


def concat_sut_Z(U: pd.DataFrame, S: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified SUT ``Z`` from split ``U`` and ``S`` blocks."""
    dtype = _common_dtype(U, S)
    U = _reindex_exact(U, index=ordering.commodity_index, columns=ordering.activity_index, label="U")
    S = _reindex_exact(S, index=ordering.activity_index, columns=ordering.commodity_index, label="S")
    zeros_aa = _zeros(ordering.activity_index, ordering.activity_index, dtype)
    zeros_cc = _zeros(ordering.commodity_index, ordering.commodity_index, dtype)
    return _concat_square_blocks(zeros_aa, S, U, zeros_cc)


def concat_sut_z(u: pd.DataFrame, s: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified SUT ``z`` from split ``u`` and ``s`` blocks."""
    return concat_sut_Z(u, s, ordering)


def concat_sut_w(
    wcc: pd.DataFrame,
    wca: pd.DataFrame,
    wac: pd.DataFrame,
    waa: pd.DataFrame,
    ordering: SUTUnifiedOrderingPolicy,
) -> pd.DataFrame:
    """Build unified SUT ``w`` from its four split quadrants."""
    waa = _reindex_exact(waa, index=ordering.activity_index, columns=ordering.activity_index, label="waa")
    wac = _reindex_exact(wac, index=ordering.activity_index, columns=ordering.commodity_index, label="wac")
    wca = _reindex_exact(wca, index=ordering.commodity_index, columns=ordering.activity_index, label="wca")
    wcc = _reindex_exact(wcc, index=ordering.commodity_index, columns=ordering.commodity_index, label="wcc")
    return _concat_square_blocks(waa, wac, wca, wcc)


def concat_sut_b(bu: pd.DataFrame, bs: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build a unified SUT direct-output coefficients block from ``bu`` and ``bs``."""
    dtype = _common_dtype(bu, bs)
    bu = _reindex_exact(bu, index=ordering.commodity_index, columns=ordering.activity_index, label="bu")
    bs = _reindex_exact(bs, index=ordering.activity_index, columns=ordering.commodity_index, label="bs")
    zeros_aa = _zeros(ordering.activity_index, ordering.activity_index, dtype)
    zeros_cc = _zeros(ordering.commodity_index, ordering.commodity_index, dtype)
    return _concat_square_blocks(zeros_aa, bs, bu, zeros_cc)


def concat_sut_g(
    gcc: pd.DataFrame,
    gca: pd.DataFrame,
    gac: pd.DataFrame,
    gaa: pd.DataFrame,
    ordering: SUTUnifiedOrderingPolicy,
) -> pd.DataFrame:
    """Build unified SUT ``g`` from its four split Ghosh quadrants."""
    gaa = _reindex_exact(gaa, index=ordering.activity_index, columns=ordering.activity_index, label="gaa")
    gac = _reindex_exact(gac, index=ordering.activity_index, columns=ordering.commodity_index, label="gac")
    gca = _reindex_exact(gca, index=ordering.commodity_index, columns=ordering.activity_index, label="gca")
    gcc = _reindex_exact(gcc, index=ordering.commodity_index, columns=ordering.commodity_index, label="gcc")
    return _concat_square_blocks(gaa, gac, gca, gcc)


def concat_sut_X(Xa: pd.DataFrame, Xc: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified production ``X`` from activity and commodity outputs."""
    return _concat_two_part_rows(Xa, Xc, ordering, "X")


def concat_sut_Y(Ya: pd.DataFrame, Yc: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified final demand ``Y`` from activity and commodity rows."""
    columns = ordering.final_demand_columns
    if columns is None:
        columns = _reindex_exact(Yc, label="Yc").columns

    Ya = _reindex_exact(Ya, index=ordering.activity_index, columns=columns, label="Ya")
    Yc = _reindex_exact(Yc, index=ordering.commodity_index, columns=columns, label="Yc")
    return pd.concat([Ya, Yc], axis=0)


def concat_sut_V(Va: pd.DataFrame, Vc: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified value-added flows ``V`` from split blocks."""
    return _concat_two_part_columns(Va, Vc, ordering, "V")


def concat_sut_v(va: pd.DataFrame, vc: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified value-added coefficients ``v`` from split blocks."""
    return _concat_two_part_columns(va, vc, ordering, "v")


def concat_sut_E(Ea: pd.DataFrame, Ec: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified extension flows ``E`` from split blocks."""
    return _concat_two_part_columns(Ea, Ec, ordering, "E")


def concat_sut_e(ea: pd.DataFrame, ec: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified extension coefficients ``e`` from split blocks."""
    return _concat_two_part_columns(ea, ec, ordering, "e")


def concat_sut_M(Ma: pd.DataFrame, Mc: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified value-added footprints ``M`` from split blocks."""
    return _concat_two_part_columns(Ma, Mc, ordering, "M")


def concat_sut_m(ma: pd.DataFrame, mc: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified value-added multipliers ``m`` from split blocks."""
    return _concat_two_part_columns(ma, mc, ordering, "m")


def concat_sut_F(Fa: pd.DataFrame, Fc: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified satellite footprints ``F`` from split blocks."""
    return _concat_two_part_columns(Fa, Fc, ordering, "F")


def concat_sut_f(fa: pd.DataFrame, fc: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified satellite multipliers ``f`` from split blocks."""
    return _concat_two_part_columns(fa, fc, ordering, "f")


def concat_sut_p(pa: pd.DataFrame, pc: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Build unified price index ``p`` from split activity and commodity rows."""
    return _concat_two_part_rows(pa, pc, ordering, "p")


def build_zero_VY_from_V_Y(V: pd.DataFrame, Y: pd.DataFrame) -> pd.DataFrame:
    """Build a zero-filled factor-by-final-demand block aligned with ``V`` and ``Y``."""
    dtype = _common_dtype(V, Y)
    return _zeros(V.index, Y.columns, dtype)


def extract_U_from_Z(Z: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract split use flows ``U`` from unified ``Z``."""
    return _reindex_exact(Z, index=ordering.unified_index, columns=ordering.unified_index, label="Z").loc[
        ordering.commodity_index, ordering.activity_index
    ]


def extract_S_from_Z(Z: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract split supply flows ``S`` from unified ``Z``."""
    return _reindex_exact(Z, index=ordering.unified_index, columns=ordering.unified_index, label="Z").loc[
        ordering.activity_index, ordering.commodity_index
    ]


def extract_u_from_z(z: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract split use coefficients ``u`` from unified ``z``."""
    return extract_U_from_Z(z, ordering)


def extract_s_from_z(z: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract split supply coefficients ``s`` from unified ``z``."""
    return extract_S_from_Z(z, ordering)


def extract_wcc_from_w(w: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract the ``wcc`` quadrant from unified ``w``."""
    return _reindex_exact(w, index=ordering.unified_index, columns=ordering.unified_index, label="w").loc[
        ordering.commodity_index, ordering.commodity_index
    ]


def extract_wca_from_w(w: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract the ``wca`` quadrant from unified ``w``."""
    return _reindex_exact(w, index=ordering.unified_index, columns=ordering.unified_index, label="w").loc[
        ordering.commodity_index, ordering.activity_index
    ]


def extract_wac_from_w(w: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract the ``wac`` quadrant from unified ``w``."""
    return _reindex_exact(w, index=ordering.unified_index, columns=ordering.unified_index, label="w").loc[
        ordering.activity_index, ordering.commodity_index
    ]


def extract_waa_from_w(w: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract the ``waa`` quadrant from unified ``w``."""
    return _reindex_exact(w, index=ordering.unified_index, columns=ordering.unified_index, label="w").loc[
        ordering.activity_index, ordering.activity_index
    ]


def extract_bu_from_b(b: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract split use-side direct-output coefficients ``bu`` from unified ``b``."""
    return _reindex_exact(b, index=ordering.unified_index, columns=ordering.unified_index, label="b").loc[
        ordering.commodity_index, ordering.activity_index
    ]


def extract_bs_from_b(b: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract split supply-side direct-output coefficients ``bs`` from unified ``b``."""
    return _reindex_exact(b, index=ordering.unified_index, columns=ordering.unified_index, label="b").loc[
        ordering.activity_index, ordering.commodity_index
    ]


def extract_gcc_from_g(g: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract the ``gcc`` quadrant from unified ``g``."""
    return _reindex_exact(g, index=ordering.unified_index, columns=ordering.unified_index, label="g").loc[
        ordering.commodity_index, ordering.commodity_index
    ]


def extract_gca_from_g(g: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract the ``gca`` quadrant from unified ``g``."""
    return _reindex_exact(g, index=ordering.unified_index, columns=ordering.unified_index, label="g").loc[
        ordering.commodity_index, ordering.activity_index
    ]


def extract_gac_from_g(g: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract the ``gac`` quadrant from unified ``g``."""
    return _reindex_exact(g, index=ordering.unified_index, columns=ordering.unified_index, label="g").loc[
        ordering.activity_index, ordering.commodity_index
    ]


def extract_gaa_from_g(g: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract the ``gaa`` quadrant from unified ``g``."""
    return _reindex_exact(g, index=ordering.unified_index, columns=ordering.unified_index, label="g").loc[
        ordering.activity_index, ordering.activity_index
    ]


def extract_Xa_from_X(X: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract activity output ``Xa`` from unified ``X``."""
    return _reindex_exact(X, index=ordering.unified_index, label="X").loc[ordering.activity_index, :]


def extract_Xc_from_X(X: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract commodity output ``Xc`` from unified ``X``."""
    return _reindex_exact(X, index=ordering.unified_index, label="X").loc[ordering.commodity_index, :]


def extract_Va_from_V(V: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract activity-side value-added flows ``Va`` from unified ``V``."""
    return _reindex_exact(V, columns=ordering.unified_index, label="V").loc[:, ordering.activity_index]


def extract_Vc_from_V(V: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract commodity-side value-added flows ``Vc`` from unified ``V``."""
    return _reindex_exact(V, columns=ordering.unified_index, label="V").loc[:, ordering.commodity_index]


def extract_va_from_v(v: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract activity-side value-added coefficients ``va`` from unified ``v``."""
    return extract_Va_from_V(v, ordering)


def extract_vc_from_v(v: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract commodity-side value-added coefficients ``vc`` from unified ``v``."""
    return extract_Vc_from_V(v, ordering)


def extract_Ea_from_E(E: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract activity-side extension flows ``Ea`` from unified ``E``."""
    return _reindex_exact(E, columns=ordering.unified_index, label="E").loc[:, ordering.activity_index]


def extract_Ec_from_E(E: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract commodity-side extension flows ``Ec`` from unified ``E``."""
    return _reindex_exact(E, columns=ordering.unified_index, label="E").loc[:, ordering.commodity_index]


def extract_ea_from_e(e: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract activity-side extension coefficients ``ea`` from unified ``e``."""
    return extract_Ea_from_E(e, ordering)


def extract_ec_from_e(e: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract commodity-side extension coefficients ``ec`` from unified ``e``."""
    return extract_Ec_from_E(e, ordering)


def extract_Ya_from_Y(Y: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract activity-side final demand ``Ya`` from unified ``Y``."""
    return _reindex_exact(
        Y,
        index=ordering.unified_index,
        columns=ordering.final_demand_columns,
        label="Y",
    ).loc[ordering.activity_index, :]


def extract_Yc_from_Y(Y: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract commodity-side final demand ``Yc`` from unified ``Y``."""
    return _reindex_exact(
        Y,
        index=ordering.unified_index,
        columns=ordering.final_demand_columns,
        label="Y",
    ).loc[ordering.commodity_index, :]


def extract_Ma_from_M(M: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract activity-side value-added footprints ``Ma`` from unified ``M``."""
    return _reindex_exact(M, columns=ordering.unified_index, label="M").loc[:, ordering.activity_index]


def extract_Mc_from_M(M: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract commodity-side value-added footprints ``Mc`` from unified ``M``."""
    return _reindex_exact(M, columns=ordering.unified_index, label="M").loc[:, ordering.commodity_index]


def extract_ma_from_m(m: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract activity-side value-added multipliers ``ma`` from unified ``m``."""
    return extract_Ma_from_M(m, ordering)


def extract_mc_from_m(m: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract commodity-side value-added multipliers ``mc`` from unified ``m``."""
    return extract_Mc_from_M(m, ordering)


def extract_Fa_from_F(F: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract activity-side satellite footprints ``Fa`` from unified ``F``."""
    return _reindex_exact(F, columns=ordering.unified_index, label="F").loc[:, ordering.activity_index]


def extract_Fc_from_F(F: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract commodity-side satellite footprints ``Fc`` from unified ``F``."""
    return _reindex_exact(F, columns=ordering.unified_index, label="F").loc[:, ordering.commodity_index]


def extract_fa_from_f(f: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract activity-side satellite multipliers ``fa`` from unified ``f``."""
    return extract_Fa_from_F(f, ordering)


def extract_fc_from_f(f: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract commodity-side satellite multipliers ``fc`` from unified ``f``."""
    return extract_Fc_from_F(f, ordering)


def extract_pa_from_p(p: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract activity-side price index ``pa`` from unified ``p``."""
    return _reindex_exact(p, index=ordering.unified_index, label="p").loc[ordering.activity_index, :]


def extract_pc_from_p(p: pd.DataFrame, ordering: SUTUnifiedOrderingPolicy) -> pd.DataFrame:
    """Extract commodity-side price index ``pc`` from unified ``p``."""
    return _reindex_exact(p, index=ordering.unified_index, label="p").loc[ordering.commodity_index, :]
