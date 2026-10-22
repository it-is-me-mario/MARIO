"""One database identity registry tying together GHG, compute and concordances.

Definitions are metadata, not model state. Public inspection returns independent
copies. Runtime consumers retain the same live registries used by the legacy
GHG/profile import paths, including user-registered entries.
"""
from copy import deepcopy
import re

from mario.database_profiles.compute import PARSER_COMPUTE_PROFILES
from mario.database_profiles.ghg import GHG_PROFILES, autodetect_profile
from mario.database_profiles.concordances import CLASSIFICATIONS, AGGREGATION_LEVELS, load_manifest
from mario.log_exc.exceptions import WrongInput


def _record(label, pattern, *, parsers=(), ghg=(), concordances=None, notes=()):
    return dict(label=label, pattern=pattern, parsers=list(parsers),
                ghg_profile_ids=list(ghg), concordance_family=concordances, notes=list(notes))


DATABASE_PROFILES = {
    "bonsai": _record("BONSAI", r"\bbonsai\b", parsers=("bonsai",), ghg=("bonsai",), concordances="BONSAI",
        notes=("Native GHG defaults reproduce BONSAI AR6 GWP100, including Accelerated CO2. The documentation explorer's AR5 three-gas comparison is a separate analytical recipe.",
               "HIOT sectors are reference products; the supplied process association supports a qualified activity lookup. Regional classifications vary.")),
    "exiobase": _record("EXIOBASE", r"\bexiobase\b", parsers=("exiobase", "exiobase_3", "exiobase_sut", "hybrid_iot_exiobase", "hybrid_sut_exiobase"),
        ghg=("exiobase_monetary", "exiobase_hybrid"), concordances="EXIOBASE",
        notes=("Monetary and Hybrid variants have distinct native rows and concordance identities. Industry-by-industry and product-by-product sectors are distinguished.",)),
    "gloria": _record("GLORIA", r"\bgloria\b", parsers=("gloria",), ghg=("gloria",), concordances="GLORIA",
        notes=("Concordance identities cover release 060. The native GHG calculation uses the selected mass-reported EDGAR gas rows; the explorer's native CO2eq inventory is a separate recipe.",)),
    "emerging": _record("EMERGING", r"\bemerging\b", parsers=("emerging",), ghg=("emerging",), concordances="EMERGING",
        notes=("GHG rows are already characterised source CO2eq and are not recharacterised by changing an IPCC argument. Fine CPA links remain unverified.",)),
    "adb": _record("ADB", r"\badb\b|asian development bank", parsers=("adb",), ghg=("adb",), concordances="ADB",
        notes=("The native GHG row is already characterised source CO2eq; IPCC arguments do not recharacterise its gases.",)),
    "eora": _record("EORA", r"\beora(?:26)?\b", parsers=("eora",), ghg=("eora",),
        notes=("GHG aggregation supports named Eora26 gas rows. No verified fine concordance is currently bundled.",)),
    "figaro": _record("FIGARO", r"\bfigaro\b", parsers=("figaro",), concordances="FIGARO"),
    "oecd": _record("OECD", r"\b(oecd|icio)\b", parsers=("oecd",), concordances="OECD"),
    "wiod": _record("WIOD", r"\bwiod\b", parsers=("wiod",), concordances="WIOD"),
    "gtap": _record("GTAP", r"\bgtap\b", parsers=("gtap",), concordances="GTAP"),
    "ceda": _record("CEDA", r"\bceda\b", concordances="CEDA",
        notes=("The explorer's native commodity descriptors have qualified producing-activity routes; these are not activity/product identities.",)),
    "useeio": _record("USEEIO", r"\buseeio\b", parsers=("useeio",)),
}


def identify_database(database):
    """Identify a registry family, preferring parser source over display name."""
    if isinstance(database, str):
        token = re.sub(r"[^a-z0-9]", "", database.casefold())
        for key, spec in DATABASE_PROFILES.items():
            if token == key or token == re.sub(r"[^a-z0-9]", "", spec["label"].casefold()):
                return {"id": key, **spec}
        values = [database]
    else:
        values = [getattr(database.meta, field, None) for field in ("source", "name")]
    for value in values:
        if not value:
            continue
        found = [(key, spec) for key, spec in DATABASE_PROFILES.items()
                 if re.search(spec["pattern"], str(value), flags=re.IGNORECASE)]
        if len(found) == 1:
            key, spec = found[0]
            return {"id": key, **spec}
    raise WrongInput("No database profile matches the source metadata. Known profiles: " + ", ".join(DATABASE_PROFILES))


def get_database_profile(database=None):
    """Inspect registered database metadata without parsing or calculating data.

    Parameters
    ----------
    database : str or Database, optional
        Family name (e.g. ``"gloria"``), or a parsed Database. Omit to return
        every known family, keyed by registry identifier.

    Returns
    -------
    dict
        Database identity, native GHG definitions, parser compute presets and
        packaged concordance editions/variants. For a Database, also identify
        its selected GHG profile and native-set concordance availability.

    Notes
    -----
    Compute presets are parser-selected preferences, not the current session
    settings. Inspect ``mario.download_settings()`` for active settings. GHG
    API defaults do not establish the IPCC basis of already characterised
    source CO2eq rows. Returned dictionaries can be edited without changing
    the registries; existing registration and settings APIs remain authoritative.
    """
    if database is None:
        return {key: get_database_profile(key) for key in DATABASE_PROFILES}
    identity = identify_database(database)
    instance = not isinstance(database, str)
    selected = autodetect_profile(database) if instance else None
    ghg_ids = list(identity["ghg_profile_ids"])
    if selected and selected not in ghg_ids:
        ghg_ids.append(selected)
    family = identity["concordance_family"]
    catalogue = load_manifest()
    variants = [p for p in catalogue["profiles"] if p["family"] == family] if family else []
    availability, unavailable_reason = None, None
    if instance and family:
        from mario.model.concordances import available_concordances
        try:
            availability = available_concordances(database)
        except WrongInput as exc:
            availability = {}
            unavailable_reason = str(exc)
    result = {
        "id": identity["id"], "label": identity["label"],
        "database": {field: getattr(database.meta, field, None) for field in
                     ("name", "source", "year", "table", "version", "sector_type")} if instance else None,
        "parsers": identity["parsers"],
        "ghg": {"profiles": {key: GHG_PROFILES[key] for key in ghg_ids if key in GHG_PROFILES},
                "selected_profile": selected,
                "api_defaults": {"ipcc_report": "AR6", "time_horizon": 100}},
        "compute": {"parser_presets": {key: PARSER_COMPUTE_PROFILES[key] for key in identity["parsers"] if key in PARSER_COMPUTE_PROFILES},
                    "scope": "Preferred session settings applied by the parser on success; not current settings or persisted user defaults."},
        "concordances": {"supported": bool(variants), "as_of": catalogue["as_of"] if variants else None,
                         "profiles": variants, "available": availability,
                         "unavailable_reason": unavailable_reason,
                         "classifications": {key: {"label": value[0], "kind": value[1],
                                                  "aggregation_levels": list(AGGREGATION_LEVELS.get(key, {}))}
                                             for key, value in CLASSIFICATIONS.items()
                            if any(key in p.get("classifications", p["direct_classifications"]) for p in variants)}},
        "notes": identity["notes"],
    }
    return deepcopy(result)
