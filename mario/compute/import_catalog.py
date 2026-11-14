"""Native import blocks and price equations for open single-region models."""

from mario.compute.catalog import (
    ADD, ACTIVITY, COMMODITY, FINAL_USE, REGION, SECTOR,
    SUT_ACTIVITY_AXIS, SUT_COMMODITY_AXIS, _concat, _formula, _parsed, _spec,
)
from mario.model.enums import TableKind
from mario.model.labels import PRICE_INDEX_LABEL


IMPORT_DESCRIPTIONS = {
    "IMP": "External import flows into domestic production.",
    "IMP_a": "External use imports purchased by domestic activities.",
    "IMP_c": "External supply imports entering domestic commodity markets.",
    "IMP_Y": "External imports delivered directly to final demand.",
    "imp": "External import coefficients per unit of domestic output.",
    "imp_a": "External use import coefficients per unit of activity output.",
    "imp_c": "External supply import coefficients per unit of commodity output.",
    "im": "Direct and indirect import requirements per unit of final output.",
    "im_a": "Direct and indirect import requirements per unit of activity output.",
    "im_c": "Direct and indirect import requirements per unit of commodity output.",
    "IM": "Import requirements allocated to domestic final output.",
    "IM_a": "Import requirements through activity final output, allocated to commodities.",
    "IM_c": "Import requirements allocated to commodity final output.",
}


def import_catalog(table):
    """Return the catalog for the separate-import accounting representation."""
    table = TableKind.coerce(table)
    activity = SUT_ACTIVITY_AXIS if table == TableKind.SUT else (REGION, SECTOR)
    commodity = SUT_COMMODITY_AXIS
    demand = (REGION, FINAL_USE)
    rows = ()  # Runtime block specs supply observed origin/item descriptors.
    catalog = {}

    def add(name, columns, *strategies):
        catalog[name] = _spec(table, name, ADD, rows, columns, *strategies, notes=(IMPORT_DESCRIPTIONS[name],))

    add("IMP_Y", demand, _parsed(True))
    if table == TableKind.IOT:
        add("IMP", activity, _parsed(True), _formula(("imp", "X"), "build_iot_V_from_v_X", "IMP = imp diag(X)"))
        add("imp", activity, _formula(("IMP", "X"), "build_iot_v_from_V_X", "imp = IMP diag(X)^-1"))
        add("im", activity,
            _formula(("imp", "z"), "build_iot_m_from_v_z", "im = imp (I-z)^-1"),
            _formula(("imp", "w"), "build_iot_m_from_v_w", "im = imp w"))
        add("IM", activity, _formula(("im", "Y"), "build_iot_M_from_m_Y", "IM = im diag(Y 1)"))
        catalog["p"] = _spec(
            table, "p", ADD, activity, (PRICE_INDEX_LABEL,),
            _formula(("m", "im"), "build_price_from_factor_and_import_multipliers", "p = m.T 1 + im.T 1"),
        )
        return catalog

    for suffix, columns, output, flow_builder, coefficient_builder in (
        ("a", activity, "Xa", "build_sut_Va_from_va_Xa", "build_sut_va_from_Va_Xa"),
        ("c", commodity, "Xc", "build_sut_Vc_from_vc_Xc", "build_sut_vc_from_Vc_Xc"),
    ):
        flow, coefficient = f"IMP_{suffix}", f"imp_{suffix}"
        add(flow, columns, _parsed(True), _formula((coefficient, output), flow_builder, f"{flow} = {coefficient} diag({output})"))
        add(coefficient, columns, _formula((flow, output), coefficient_builder, f"{coefficient} = {flow} diag({output})^-1"))
    add("im_a", activity,
        _formula(("imp_a", "s", "u", "imp_c"), "build_sut_ma_from_va_s_u", "im_a = (imp_a + imp_c u) (I-su)^-1"),
        _formula(("imp_a", "waa", "imp_c", "u"), "build_sut_ma_from_va_waa", "im_a = (imp_a + imp_c u) waa"))
    add("im_c", commodity,
        _formula(("imp_a", "s", "u", "imp_c"), "build_sut_mc_from_va_s_u", "im_c = (imp_a s + imp_c) (I-us)^-1"),
        _formula(("imp_a", "s", "wcc", "imp_c"), "build_sut_mc_from_va_s_wcc", "im_c = (imp_a s + imp_c) wcc"))
    add("IM_a", commodity, _formula(("im_a", "s", "Yc"), "build_sut_Ma_from_ma_s_Yc", "IM_a = im_a s diag(Yc 1)"))
    add("IM_c", commodity, _formula(("im_c", "Yc"), "build_sut_Mc_from_mc_Yc", "IM_c = im_c diag(Yc 1)"))
    for name, sources, builder in (
        ("IMP", ("IMP_a", "IMP_c"), "concat_sut_V"),
        ("imp", ("imp_a", "imp_c"), "concat_sut_v"),
        ("im", ("im_a", "im_c"), "concat_sut_m"),
        ("IM", ("IM_a", "IM_c"), "concat_sut_M"),
    ):
        add(name, (REGION, "Commodity/Activity"), _concat(sources, builder, f"{name} = concatenate({', '.join(sources)})"))
    for name, domestic, imported, columns in (
        ("pa", "ma", "im_a", activity), ("pc", "mc", "im_c", commodity),
    ):
        catalog[name] = _spec(
            table, name, ADD, columns, (PRICE_INDEX_LABEL,),
            _formula((domestic, imported), "build_price_from_factor_and_import_multipliers", f"{name} = {domestic}.T 1 + {imported}.T 1"),
        )
    return catalog
