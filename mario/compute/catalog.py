"""Authoritative Python compute catalog for the parallel MARIO 2 core."""

from __future__ import annotations

from mario.compute.types import (
    AxisSpec,
    ConcatStrategy,
    ExtractStrategy,
    FormulaStrategy,
    MatrixKey,
    MatrixSpec,
    MatrixStatus,
    ParsedStrategy,
)
from mario.model.enums import TableKind
from mario.model.labels import (
    COMMODITY_ACTIVITY_LABEL,
    INDEX_LABELS,
    ITEM_LABEL,
    PRICE_INDEX_LABEL,
    PRODUCTION_LABEL,
)

REGION = INDEX_LABELS["r"]
SECTOR = INDEX_LABELS["s"]
ACTIVITY = INDEX_LABELS["a"]
COMMODITY = INDEX_LABELS["c"]
FINAL_USE = INDEX_LABELS["n"]
SATELLITE = INDEX_LABELS["k"]
FACTOR = INDEX_LABELS["f"]

CATALOG_OPEN_QUESTIONS = (
    "SUT unified w in the spreadsheet duplicates wac and omits waa; keep the "
    "Python builder ordered as wcc, wca, wac, waa until confirmed.",
    "SUT unified M references Ma and Mc, but the spreadsheet only defines Mc.",
    "SUT unified F references Fa and Fc, but the spreadsheet only defines Fc.",
    "The spreadsheet formula for b remains ambiguous; keep Ghosh formulas isolated "
    "and easy to revise.",
)


def _axes(rows: tuple[str, ...], cols: tuple[str, ...]) -> AxisSpec:
    """Build a lightweight axis specification for one matrix."""
    return AxisSpec(rows=rows, cols=cols)


def _parsed(required: bool, *notes: str) -> ParsedStrategy:
    """Declare a strategy that only accepts already-materialized blocks."""
    return ParsedStrategy(required=required, notes=tuple(notes))


def _extract(source: str, extractor: str, expr: str, *notes: str) -> ExtractStrategy:
    """Declare a strategy that extracts one block from an existing source."""
    return ExtractStrategy(
        source=source,
        extractor=extractor,
        spreadsheet_expr=expr,
        notes=tuple(notes),
    )


def _concat(
    sources: tuple[str, ...],
    builder: str,
    expr: str,
    *notes: str,
) -> ConcatStrategy:
    """Declare a strategy that concatenates pre-resolved source blocks."""
    return ConcatStrategy(
        sources=sources,
        builder=builder,
        spreadsheet_expr=expr,
        notes=tuple(notes),
    )


def _formula(
    inputs: tuple[str, ...],
    function: str,
    expr: str,
    *notes: str,
) -> FormulaStrategy:
    """Declare a strategy backed by a named pure formula implementation."""
    return FormulaStrategy(
        inputs=inputs,
        function=function,
        spreadsheet_expr=expr,
        notes=tuple(notes),
    )


def _spec(
    table: TableKind,
    name: str,
    status: MatrixStatus,
    rows: tuple[str, ...],
    cols: tuple[str, ...],
    *strategies,
    notes: tuple[str, ...] = (),
    todo: str | None = None,
) -> MatrixSpec:
    """Build one matrix specification entry for the authoritative catalog."""
    return MatrixSpec(
        key=MatrixKey(table_kind=table, name=name),
        status=status,
        axes=_axes(rows, cols),
        strategies=tuple(strategies),
        notes=notes,
        todo=todo,
    )


IOT = TableKind.IOT
SUT = TableKind.SUT
KEEP = MatrixStatus.KEEP
ADD = MatrixStatus.ADD

IOT_ENTITY_AXIS = (REGION, SECTOR, ITEM_LABEL)
IOT_FINAL_USE_AXIS = (REGION, FINAL_USE, ITEM_LABEL)
SUT_UNIFIED_AXIS = (REGION, COMMODITY_ACTIVITY_LABEL, ITEM_LABEL)
SUT_ACTIVITY_AXIS = (REGION, ACTIVITY, ITEM_LABEL)
SUT_COMMODITY_AXIS = (REGION, COMMODITY, ITEM_LABEL)

COMPUTE_CATALOG = {
    IOT: {
        "Z": _spec(
            IOT,
            "Z",
            KEEP,
            IOT_ENTITY_AXIS,
            IOT_ENTITY_AXIS,
            _formula(("z", "X"), "build_iot_Z_from_z_X", "Z = z @ diag(X)"),
        ),
        "z": _spec(
            IOT,
            "z",
            KEEP,
            IOT_ENTITY_AXIS,
            IOT_ENTITY_AXIS,
            _formula(("Z", "X"), "build_iot_z_from_Z_X", "z = Z @ minverse(diag(X))"),
        ),
        "w": _spec(
            IOT,
            "w",
            KEEP,
            IOT_ENTITY_AXIS,
            IOT_ENTITY_AXIS,
            _formula(("z",), "build_iot_w_from_z", "w = minverse(identity - z)"),
        ),
        "Y": _spec(
            IOT,
            "Y",
            KEEP,
            IOT_ENTITY_AXIS,
            IOT_FINAL_USE_AXIS,
            _parsed(True),
        ),
        "X": _spec(
            IOT,
            "X",
            KEEP,
            IOT_ENTITY_AXIS,
            (PRODUCTION_LABEL,),
            _formula(("Z", "Y"), "build_iot_X_from_Z_Y", "X = Z.sum(1) + Y.sum(1)"),
            _formula(
                ("w", "Y"),
                "build_iot_X_from_w_Y",
                "X = w @ Y",
                "Use final-demand totals instead of the full Y matrix.",
            ),
        ),
        "V": _spec(
            IOT,
            "V",
            KEEP,
            (FACTOR,),
            IOT_ENTITY_AXIS,
            _formula(("v", "X"), "build_iot_V_from_v_X", "V = v @ diag(X)"),
        ),
        "v": _spec(
            IOT,
            "v",
            KEEP,
            (FACTOR,),
            IOT_ENTITY_AXIS,
            _formula(("V", "X"), "build_iot_v_from_V_X", "v = V @ minverse(diag(X))"),
        ),
        "E": _spec(
            IOT,
            "E",
            KEEP,
            (SATELLITE,),
            IOT_ENTITY_AXIS,
            _formula(("e", "X"), "build_iot_E_from_e_X", "E = e @ diag(X)"),
        ),
        "e": _spec(
            IOT,
            "e",
            KEEP,
            (SATELLITE,),
            IOT_ENTITY_AXIS,
            _formula(("E", "X"), "build_iot_e_from_E_X", "e = E @ minverse(diag(X))"),
        ),
        "EY": _spec(
            IOT,
            "EY",
            KEEP,
            (SATELLITE,),
            IOT_FINAL_USE_AXIS,
            _parsed(True),
        ),
        "M": _spec(
            IOT,
            "M",
            KEEP,
            (FACTOR,),
            IOT_ENTITY_AXIS,
            _formula(
                ("m", "Y"),
                "build_iot_M_from_m_Y",
                "M = m @ diag(Y)",
                "Use diag(Y_total) instead of diagonalizing the full Y matrix.",
            ),
        ),
        "m": _spec(
            IOT,
            "m",
            KEEP,
            (FACTOR,),
            IOT_ENTITY_AXIS,
            _formula(("v", "w"), "build_iot_m_from_v_w", "m = v @ w"),
        ),
        "F": _spec(
            IOT,
            "F",
            KEEP,
            (SATELLITE,),
            IOT_ENTITY_AXIS,
            _formula(
                ("f", "Y"),
                "build_iot_F_from_f_Y",
                "F = f @ diag(Y)",
                "Use diag(Y_total) instead of diagonalizing the full Y matrix.",
            ),
        ),
        "f": _spec(
            IOT,
            "f",
            KEEP,
            (SATELLITE,),
            IOT_ENTITY_AXIS,
            _formula(("e", "w"), "build_iot_f_from_e_w", "f = e @ w"),
        ),
        "g": _spec(
            IOT,
            "g",
            KEEP,
            IOT_ENTITY_AXIS,
            IOT_ENTITY_AXIS,
            _formula(("b",), "build_iot_g_from_b", "g = minverse(identity - b)"),
        ),
        "b": _spec(
            IOT,
            "b",
            KEEP,
            IOT_ENTITY_AXIS,
            IOT_ENTITY_AXIS,
            _formula(("X", "Z"), "build_iot_b_from_X_Z", "b = minverse(diag(X) @ Z)"),
            todo=CATALOG_OPEN_QUESTIONS[3],
        ),
        "p": _spec(
            IOT,
            "p",
            KEEP,
            IOT_ENTITY_AXIS,
            (PRICE_INDEX_LABEL,),
            _formula(
                ("v", "w"),
                "build_iot_p_from_v_w",
                "transpose(m.sum(0))",
                "Keep the established calc_p(v, w) semantics; it is equivalent to summing m = v @ w.",
            ),
        ),
    },
    SUT: {
        "Z": _spec(
            SUT,
            "Z",
            KEEP,
            SUT_UNIFIED_AXIS,
            SUT_UNIFIED_AXIS,
            _concat(("U", "S"), "concat_sut_Z", "Concat U and S"),
        ),
        "z": _spec(
            SUT,
            "z",
            KEEP,
            SUT_UNIFIED_AXIS,
            SUT_UNIFIED_AXIS,
            _concat(("u", "s"), "concat_sut_z", "Concat u and s"),
        ),
        "w": _spec(
            SUT,
            "w",
            KEEP,
            SUT_UNIFIED_AXIS,
            SUT_UNIFIED_AXIS,
            _concat(
                ("wcc", "wca", "wac", "waa"),
                "concat_sut_w",
                "Concat wac, wac, wcc and wca",
                "Use the four quadrants in centralized ordering despite the spreadsheet typo.",
            ),
            todo=CATALOG_OPEN_QUESTIONS[0],
        ),
        "wcc": _spec(
            SUT,
            "wcc",
            ADD,
            SUT_COMMODITY_AXIS,
            SUT_COMMODITY_AXIS,
            _extract("w", "extract_wcc_from_w", "Extracted from w, only if available"),
            _formula(("u", "s"), "build_sut_wcc_from_u_s", "wcc = minverse(identity - u @ s)"),
        ),
        "wca": _spec(
            SUT,
            "wca",
            ADD,
            SUT_COMMODITY_AXIS,
            SUT_ACTIVITY_AXIS,
            _extract("w", "extract_wca_from_w", "Extracted from w, only if available"),
            _formula(("u", "s"), "build_sut_wca_from_u_s", "wca = minverse(identity - u @ s) @ u"),
        ),
        "wac": _spec(
            SUT,
            "wac",
            ADD,
            SUT_ACTIVITY_AXIS,
            SUT_COMMODITY_AXIS,
            _extract("w", "extract_wac_from_w", "Extracted from w, only if available"),
            _formula(("s", "u"), "build_sut_wac_from_s_u", "wac = minverse(identity - s @ u) @ s"),
        ),
        "waa": _spec(
            SUT,
            "waa",
            ADD,
            SUT_ACTIVITY_AXIS,
            SUT_ACTIVITY_AXIS,
            _extract("w", "extract_waa_from_w", "Extracted from w, only if available"),
            _formula(("s", "u"), "build_sut_waa_from_s_u", "waa = minverse(identity - s @ u)"),
        ),
        "Y": _spec(
            SUT,
            "Y",
            KEEP,
            SUT_UNIFIED_AXIS,
            IOT_FINAL_USE_AXIS,
            _concat(("Ya", "Yc"), "concat_sut_Y", "Concat Ya and Yc"),
        ),
        "X": _spec(
            SUT,
            "X",
            KEEP,
            SUT_UNIFIED_AXIS,
            (PRODUCTION_LABEL,),
            _concat(("Xa", "Xc"), "concat_sut_X", "Concat Xa and Xc"),
        ),
        "Xa": _spec(
            SUT,
            "Xa",
            ADD,
            SUT_ACTIVITY_AXIS,
            (PRODUCTION_LABEL,),
            _extract("X", "extract_Xa_from_X", "Extracted from X, only if available"),
            _formula(
                ("S", "Ya"),
                "build_sut_Xa_from_S_Ya",
                "Xa = S.sum(1) + Ya.sum(1), Ya is not necessarily always present",
                "This branch is optional because Ya is not guaranteed by all parsers.",
            ),
            _formula(("s", "Xc"), "build_sut_Xa_from_s_Xc", "Xa = s @ Xc"),
        ),
        "Xc": _spec(
            SUT,
            "Xc",
            ADD,
            SUT_COMMODITY_AXIS,
            (PRODUCTION_LABEL,),
            _extract("X", "extract_Xc_from_X", "Extracted from X, only if available"),
            _formula(("U", "Yc"), "build_sut_Xc_from_U_Yc", "Xc = U.sum(1) + Yc.sum(1)"),
            _formula(
                ("wcc", "Yc"),
                "build_sut_Xc_from_wcc_Yc",
                "Xc = wcc @ Yc",
                "Use final-demand totals instead of the full Yc matrix.",
            ),
        ),
        "V": _spec(
            SUT,
            "V",
            KEEP,
            (FACTOR,),
            SUT_UNIFIED_AXIS,
            _concat(("Va", "Vc"), "concat_sut_V", "Concat Va and Vc"),
        ),
        "v": _spec(
            SUT,
            "v",
            KEEP,
            (FACTOR,),
            SUT_UNIFIED_AXIS,
            _concat(("va", "vc"), "concat_sut_v", "Concat va and vc"),
        ),
        "E": _spec(
            SUT,
            "E",
            KEEP,
            (SATELLITE,),
            SUT_UNIFIED_AXIS,
            _concat(("Ea", "Ec"), "concat_sut_E", "Concat Ea and Ec"),
        ),
        "e": _spec(
            SUT,
            "e",
            KEEP,
            (SATELLITE,),
            SUT_UNIFIED_AXIS,
            _concat(("ea", "ec"), "concat_sut_e", "Concat ea and ec"),
        ),
        "U": _spec(
            SUT,
            "U",
            KEEP,
            SUT_COMMODITY_AXIS,
            SUT_ACTIVITY_AXIS,
            _extract("Z", "extract_U_from_Z", "Extracted from Z, only if available"),
            _formula(("u", "Xa"), "build_sut_U_from_u_Xa", "U = u @ diag(Xa)"),
        ),
        "u": _spec(
            SUT,
            "u",
            KEEP,
            SUT_COMMODITY_AXIS,
            SUT_ACTIVITY_AXIS,
            _extract("z", "extract_u_from_z", "Extracted from z, only if available"),
            _formula(("U", "Xa"), "build_sut_u_from_U_Xa", "u = U @ minverse(diag(Xa))"),
        ),
        "S": _spec(
            SUT,
            "S",
            KEEP,
            SUT_ACTIVITY_AXIS,
            SUT_COMMODITY_AXIS,
            _extract("Z", "extract_S_from_Z", "Extracted from Z, only if available"),
            _formula(("s", "Xc"), "build_sut_S_from_s_Xc", "S = s @ diag(Xc)"),
        ),
        "s": _spec(
            SUT,
            "s",
            KEEP,
            SUT_ACTIVITY_AXIS,
            SUT_COMMODITY_AXIS,
            _extract("z", "extract_s_from_z", "Extracted from z, only if available"),
            _formula(("S", "Xc"), "build_sut_s_from_S_Xc", "s = S @ minverse(diag(Xc))"),
        ),
        "EY": _spec(
            SUT,
            "EY",
            KEEP,
            (SATELLITE,),
            IOT_FINAL_USE_AXIS,
            _parsed(True),
        ),
        "M": _spec(
            SUT,
            "M",
            KEEP,
            (FACTOR,),
            SUT_UNIFIED_AXIS,
            _concat(
                ("Ma", "Mc"),
                "concat_sut_M",
                "Concat Ma and Mc",
                "Keep unresolved until Ma is explicitly formalized.",
            ),
            todo=CATALOG_OPEN_QUESTIONS[1],
        ),
        "m": _spec(
            SUT,
            "m",
            KEEP,
            (FACTOR,),
            SUT_UNIFIED_AXIS,
            _concat(("ma", "mc"), "concat_sut_m", "Concat ma and mc"),
        ),
        "F": _spec(
            SUT,
            "F",
            KEEP,
            (SATELLITE,),
            SUT_UNIFIED_AXIS,
            _concat(
                ("Fa", "Fc"),
                "concat_sut_F",
                "Concat Fa and Fc",
                "Keep unresolved until Fa is explicitly formalized.",
            ),
            todo=CATALOG_OPEN_QUESTIONS[2],
        ),
        "f": _spec(
            SUT,
            "f",
            KEEP,
            (SATELLITE,),
            SUT_UNIFIED_AXIS,
            _concat(("fa", "fc"), "concat_sut_f", "Concat fa and fc"),
        ),
        "g": _spec(
            SUT,
            "g",
            KEEP,
            SUT_UNIFIED_AXIS,
            SUT_UNIFIED_AXIS,
            _formula(("b",), "build_sut_g_from_b", "g = minverse(identity - b)"),
        ),
        "b": _spec(
            SUT,
            "b",
            KEEP,
            SUT_UNIFIED_AXIS,
            SUT_UNIFIED_AXIS,
            _formula(("X", "Z"), "build_sut_b_from_X_Z", "b = minverse(diag(X) @ Z)"),
            todo=CATALOG_OPEN_QUESTIONS[3],
        ),
        "p": _spec(
            SUT,
            "p",
            KEEP,
            SUT_UNIFIED_AXIS,
            (PRICE_INDEX_LABEL,),
            _concat(("pa", "pc"), "concat_sut_p", "Concat pa and pc"),
        ),
        "Va": _spec(
            SUT,
            "Va",
            ADD,
            (FACTOR,),
            SUT_ACTIVITY_AXIS,
            _extract("V", "extract_Va_from_V", "Extracted from V, only if available"),
            _formula(("va", "Xa"), "build_sut_Va_from_va_Xa", "Va = va @ diag(Xa)"),
        ),
        "Vc": _spec(
            SUT,
            "Vc",
            ADD,
            (FACTOR,),
            SUT_COMMODITY_AXIS,
            _extract("V", "extract_Vc_from_V", "Extracted from V, only if available"),
            _formula(("vc", "Xc"), "build_sut_Vc_from_vc_Xc", "Vc = vc @ diag(Xc)"),
        ),
        "va": _spec(
            SUT,
            "va",
            ADD,
            (FACTOR,),
            SUT_ACTIVITY_AXIS,
            _extract("v", "extract_va_from_v", "Extracted from v, only if available"),
            _formula(("Va", "Xa"), "build_sut_va_from_Va_Xa", "va = Va @ minverse(diag(Xa))"),
        ),
        "vc": _spec(
            SUT,
            "vc",
            ADD,
            (FACTOR,),
            SUT_COMMODITY_AXIS,
            _extract("v", "extract_vc_from_v", "Extracted from v, only if available"),
            _formula(("Vc", "Xc"), "build_sut_vc_from_Vc_Xc", "vc = Vc @ minverse(diag(Xc))"),
        ),
        "Ea": _spec(
            SUT,
            "Ea",
            ADD,
            (SATELLITE,),
            SUT_ACTIVITY_AXIS,
            _extract("E", "extract_Ea_from_E", "Extracted from E, only if available"),
            _formula(("ea", "Xa"), "build_sut_Ea_from_ea_Xa", "Ea = ea @ diag(Xa)"),
        ),
        "Ec": _spec(
            SUT,
            "Ec",
            ADD,
            (SATELLITE,),
            SUT_COMMODITY_AXIS,
            _extract("E", "extract_Ec_from_E", "Extracted from E, only if available"),
            _formula(("ec", "Xc"), "build_sut_Ec_from_ec_Xc", "Ec = ec @ diag(Xc)"),
        ),
        "ea": _spec(
            SUT,
            "ea",
            ADD,
            (SATELLITE,),
            SUT_ACTIVITY_AXIS,
            _extract("e", "extract_ea_from_e", "Extracted from e, only if available"),
            _formula(("Ea", "Xa"), "build_sut_ea_from_Ea_Xa", "ea = Ea @ minverse(diag(Xa))"),
        ),
        "ec": _spec(
            SUT,
            "ec",
            ADD,
            (SATELLITE,),
            SUT_COMMODITY_AXIS,
            _extract("e", "extract_ec_from_e", "Extracted from e, only if available"),
            _formula(("Ec", "Xc"), "build_sut_ec_from_Ec_Xc", "ec = Ec @ minverse(diag(Xc))"),
        ),
        "Ya": _spec(
            SUT,
            "Ya",
            ADD,
            SUT_ACTIVITY_AXIS,
            IOT_FINAL_USE_AXIS,
            _parsed(False, "Optional parsed block for sources that provide activity final use."),
            _extract("Y", "extract_Ya_from_Y", "Extracted from Y, only if available"),
        ),
        "Yc": _spec(
            SUT,
            "Yc",
            ADD,
            SUT_COMMODITY_AXIS,
            IOT_FINAL_USE_AXIS,
            _parsed(True),
            _extract("Y", "extract_Yc_from_Y", "Extracted from Y, only if available"),
        ),
        "Mc": _spec(
            SUT,
            "Mc",
            ADD,
            (FACTOR,),
            SUT_COMMODITY_AXIS,
            _extract("M", "extract_Mc_from_M", "Extracted from M, only if available"),
            _formula(
                ("mc", "Yc"),
                "build_sut_Mc_from_mc_Yc",
                "Mc = mc @ diag(Yc)",
                "Use diag(Yc_total) instead of diagonalizing the full Yc matrix.",
            ),
        ),
        "Ma": _spec(
            SUT,
            "Ma",
            ADD,
            (FACTOR,),
            SUT_ACTIVITY_AXIS,
            _extract("M", "extract_Ma_from_M", "Extracted from M, only if available"),
            _formula(
                ("ma", "Ya"),
                "build_sut_Ma_from_ma_Ya",
                "Ma = ma @ diag(Ya)",
                "Use diag(Ya_total) instead of diagonalizing the full Ya matrix.",
            ),
        ),
        "ma": _spec(
            SUT,
            "ma",
            ADD,
            (FACTOR,),
            SUT_ACTIVITY_AXIS,
            _extract("m", "extract_ma_from_m", "Extracted from m, only if available"),
            _formula(("va", "waa"), "build_sut_ma_from_va_waa", "ma = va @ waa"),
        ),
        "mc": _spec(
            SUT,
            "mc",
            ADD,
            (FACTOR,),
            SUT_COMMODITY_AXIS,
            _extract("m", "extract_mc_from_m", "Extracted from m, only if available"),
            _formula(("va", "s", "wcc"), "build_sut_mc_from_va_s_wcc", "mc = va @ s @ wcc"),
        ),
        "Fc": _spec(
            SUT,
            "Fc",
            ADD,
            (SATELLITE,),
            SUT_COMMODITY_AXIS,
            _extract("F", "extract_Fc_from_F", "Extracted from F, only if available"),
            _formula(
                ("fc", "Yc"),
                "build_sut_Fc_from_fc_Yc",
                "Fc = fc @ diag(Yc)",
                "Use diag(Yc_total) instead of diagonalizing the full Yc matrix.",
            ),
        ),
        "Fa": _spec(
            SUT,
            "Fa",
            ADD,
            (SATELLITE,),
            SUT_ACTIVITY_AXIS,
            _extract("F", "extract_Fa_from_F", "Extracted from F, only if available"),
            _formula(
                ("fa", "Ya"),
                "build_sut_Fa_from_fa_Ya",
                "Fa = fa @ diag(Ya)",
                "Use diag(Ya_total) instead of diagonalizing the full Ya matrix.",
            ),
        ),
        "fa": _spec(
            SUT,
            "fa",
            ADD,
            (SATELLITE,),
            SUT_ACTIVITY_AXIS,
            _extract("f", "extract_fa_from_f", "Extracted from f, only if available"),
            _formula(("ea", "waa"), "build_sut_fa_from_ea_waa", "fa = ea @ waa"),
        ),
        "fc": _spec(
            SUT,
            "fc",
            ADD,
            (SATELLITE,),
            SUT_COMMODITY_AXIS,
            _extract("f", "extract_fc_from_f", "Extracted from f, only if available"),
            _formula(("ea", "s", "wcc"), "build_sut_fc_from_ea_s_wcc", "fc = ea @ s @ wcc"),
        ),
        "pc": _spec(
            SUT,
            "pc",
            ADD,
            SUT_COMMODITY_AXIS,
            (PRICE_INDEX_LABEL,),
            _extract("p", "extract_pc_from_p", "Extracted from p, only if available"),
            _formula(
                ("va", "vc", "wac", "wcc"),
                "build_sut_pc_from_vc",
                "pc = transpose(wac) @ transpose(va.sum(0)) + transpose(wcc) @ transpose(vc.sum(0))",
                "Preserve the established calc_p semantics on the split SUT system.",
            ),
        ),
        "pa": _spec(
            SUT,
            "pa",
            ADD,
            SUT_ACTIVITY_AXIS,
            (PRICE_INDEX_LABEL,),
            _extract("p", "extract_pa_from_p", "Extracted from p, only if available"),
            _formula(
                ("va", "vc", "waa", "wca"),
                "build_sut_pa_from_va",
                "pa = transpose(waa) @ transpose(va.sum(0)) + transpose(wca) @ transpose(vc.sum(0))",
                "Preserve the established calc_p semantics on the split SUT system.",
            ),
        ),
    },
}


def get_matrix_spec(table: "TableKind | str", name: str) -> MatrixSpec:
    """Return the catalog entry for one matrix on one table kind."""
    table_kind = TableKind.coerce(table)
    return COMPUTE_CATALOG[table_kind][name]


def available_matrix_names(table: "TableKind | str") -> tuple[str, ...]:
    """Return the matrix names exposed by the catalog for a table kind."""
    table_kind = TableKind.coerce(table)
    return tuple(COMPUTE_CATALOG[table_kind].keys())
