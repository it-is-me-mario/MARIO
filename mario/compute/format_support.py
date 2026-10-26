"""Accounting conventions of public calculations, shared by documentation views."""

from mario.compute.catalog import COMPUTE_CATALOG


_SUT_HELPERS = {
    "calc_Va", "calc_Vc", "calc_va", "calc_vc", "calc_Ea", "calc_Ec", "calc_ea", "calc_ec",
    "calc_ma", "calc_mc", "calc_Ma", "calc_Mc", "calc_fa", "calc_fc", "calc_Fa", "calc_Fc",
    "calc_u", "calc_U", "calc_s", "calc_S", "calc_c", "calc_Xa", "calc_Xc",
    "calc_wcc", "calc_wca", "calc_wac", "calc_waa", "calc_bu", "calc_bs",
    "calc_gcc", "calc_gca", "calc_gac", "calc_gaa", "calc_pa", "calc_pc",
}


def calculation_formats(symbol):
    """Return documented table conventions; bare-array helpers do not dispatch."""
    name = symbol.rsplit(".", 1)[-1]
    if symbol.startswith("mario.calc_"):
        return ("SUT",) if name in _SUT_HELPERS else ("IOT",)
    name = {"lower_u": "u", "lower_s": "s"}.get(name, name)
    name = name.removesuffix("_all") if name.endswith("_ex_all") else name
    if name == "calc_spa":
        return ("IOT",)
    if name in {"calc_all", "resolve", "resolve_many", "explain", "available_matrices", "get_block_spec"}:
        return ("IOT", "SUT", "NAM")
    formats = tuple(kind.value for kind, entries in COMPUTE_CATALOG.items() if name in entries)
    if formats:
        return formats
    if name.startswith("calc_") or name in {"f_ex", "m_ex", "p_ex", "fa_ex", "fc_ex", "ma_ex", "mc_ex", "pa_ex", "pc_ex"}:
        return ("IOT", "SUT") if name.startswith("calc_") else (("SUT",) if name[1:2] in {"a", "c"} else ("IOT",))
    return ()


def api_formats(symbol):
    """Add supported NAM entry points/shared operations to calculation labels.

    The NAM facade owns its implemented operation subset. Do not infer NAM
    support from inheritance: inherited IOT/SUT methods are explicitly guarded.
    Unclassified non-calculation APIs retain an unspecified format label.
    """
    formats = calculation_formats(symbol)
    if formats:
        return formats
    if symbol in {"mario.parse_figaro", "mario.parse_from_excel", "mario.write_parse_template"}:
        return ("IOT", "SUT", "NAM")
    if symbol.startswith("mario.api.nam.NAMDatabase."):
        return ("NAM",)
    if symbol.startswith(("mario.CoreModel.", "mario.Database.")):
        from mario.api.nam import NAMDatabase

        if symbol.rsplit(".", 1)[-1] in NAMDatabase.__dict__:
            return ("IOT", "SUT", "NAM")
    return ()
