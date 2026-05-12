"""Built-in GHG aggregation for MARIO databases.

Defines a small registry of GHG satellite-account profiles per supported
parser (EXIOBASE, EORA, GLORIA, EMERGING, ...) together with their default
GWP-100 factors, and a `calc_ghg` helper used by `Database.calc_ghg()`.

The registry can be extended at runtime via :func:`register_ghg_profile`.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple
import pandas as pd


# ---------------------------------------------------------------- registry
# Each entry is a dict with:
#   match : substring or tuple of substrings (case-insensitive, AND-matched)
#           against db.meta.source / db.meta.name
#   gwp   : {satellite-account label : GWP-100 factor}
#   unit  : unit label used for the aggregated row (default "kg CO2eq")
#
# Profiles are evaluated in declaration order; the first matching profile
# wins. Put the more specific profile (more substrings) first.
GHG_PROFILES: Dict[str, dict] = {
    # ---------------- EXIOBASE 3.x monetary (IOT and SUT) ----------------
    # Satellite labels look like "CO2 - combustion - air".  GWP-100 from
    # IPCC AR6 (with feedbacks).  Only combustion CO2/CH4/N2O are listed
    # here because those are the ones used in the JIE 2025 paper; extend
    # the dict (or pass `gwp=...`) to include non-combustion / agriculture
    # / waste rows.
    "exiobase_monetary": {
        "match": ("exiobase", "monetary"),
        "unit": "kg CO2eq",
        "gwp": {
            "CO2 - combustion - air": 1.0,
            "CH4 - combustion - air": 29.7,
            "N2O - combustion - air": 264.8,
            "HFC - air": 1.0,
            "SF6 - air": 23506.0,
            "CO - combustion - air": 4.1,
        },
    },
    # ---------------- EXIOBASE 3.3.18 hybrid (HSUT / HIOT) ---------------
    # Hybrid uses the "Emiss" extension; row labels are decorated by the
    # parser as "<substance> (<compartment> - Emiss)" and are expressed in
    # mass units (typically kg).  Only the air compartment is included.
    "exiobase_hybrid": {
        "match": ("exiobase", "hybrid"),
        "unit": "kg CO2eq",
        "gwp": {
            "CO2 (air - Emiss)": 1.0,
            "CH4 (air - Emiss)": 29.7,
            "N2O (air - Emiss)": 264.8,
            "SF6 (air - Emiss)": 23506.0,
            "CO (air - Emiss)": 4.1,
        },
    },
    # ---------------- EORA26 ---------------------------------------------
    # EORA26 satellite labels look like
    #   "I-GHG-<gas> emissions (Gg) - <sub-source>"
    # with one row per (gas, sub-source). With ``match_mode='prefix'`` the
    # GWP keys are interpreted as label prefixes and every matching row is
    # weighted by the same factor (so all sub-sources for the same gas are
    # summed together). GWP-100 factors from IPCC AR6 (with feedbacks).
    # "CO2b" rows hold biogenic CO2 (GWP=0 by convention) and are skipped.
    "eora": {
        "match": "eora",
        "match_mode": "prefix",
        "unit": "Gg CO2eq",
        "gwp": {
            "I-GHG-CO2 emissions": 1.0,
            "I-GHG-CH4 emissions": 29.7,
            "I-GHG-N2O emissions": 264.8,
            "I-GHG-HFC23 emissions": 14600.0,
            "I-GHG-HFC32 emissions": 771.0,
            "I-GHG-HFC125 emissions": 3740.0,
            "I-GHG-HFC134a emissions": 1530.0,
            "I-GHG-HFC143a emissions": 5810.0,
            "I-GHG-HFC152a emissions": 164.0,
            "I-GHG-HFC227ea emissions": 3600.0,
            "I-GHG-HFC236fa emissions": 8690.0,
            "I-GHG-HFC245fa emissions": 962.0,
            "I-GHG-HFC365mfc emissions": 914.0,
            "I-GHG-HFC4310mee emissions": 1600.0,
            "I-GHG-CF4 emissions": 7380.0,
            "I-GHG-C2F6 emissions": 12400.0,
            "I-GHG-C3F8 emissions": 9290.0,
            "I-GHG-C4F10 emissions": 10000.0,
            "I-GHG-C5F12 emissions": 9220.0,
            "I-GHG-C6F14 emissions": 8620.0,
            "I-GHG-C7F16 emissions": 8410.0,
            "I-GHG-cC4F8 emissions": 10200.0,
            "I-GHG-SF6 emissions": 23500.0,
            "I-GHG-NF3 emissions": 17400.0,
        },
    },
    "gloria": {
        "match": "gloria",
        "unit": "kg CO2eq",
        "gwp": {
            "Emissions (EDGAR) | 'co2_excl_short_cycle_org_c_total_EDGAR_consistent'": 1.0,
            "Emissions (EDGAR) | 'ch4_total_EDGAR_consistent'": 29.7,
            "Emissions (EDGAR) | 'n2o_total_EDGAR_consistent'": 264.8,
            "Emissions (EDGAR) | 'hfc_23_total_EDGAR_consistent'": 1.0,
            "Emissions (EDGAR) | 'sf6_total_EDGAR_consistent'": 23506.0,
            "Emissions (EDGAR) | 'co_total_EDGAR_consistent'": 4.1,
        },
    },
    "emerging": {
        "match": "emerging",
        "unit": "Mt CO2eq",
        # EMERGING reports already-aggregated CO2eq emissions per energy
        # carrier (see EMERGING_CO2_LABELS in mario.parsers.specs).
        "gwp": {
            "Coal": 1.0,
            "Natural gas": 1.0,
            "Oil products": 1.0,
            "Crude, NGL, Ref Feeds.": 1.0,
            "Oil shale & oil sands": 1.0,
            "Peat & Peat products": 1.0,
            "Other": 1.0,
        },
    },
}


def register_ghg_profile(name: str, match, gwp: Dict[str, float],
                         unit: str = "kg CO2eq",
                         match_mode: str = "exact") -> None:
    """Register or overwrite a GHG profile.

    ``match`` may be a single substring or a tuple of substrings; all
    substrings must appear (case-insensitive) in the database metadata for
    the profile to auto-detect.

    ``match_mode`` controls how ``gwp`` keys are matched against the
    satellite-account index: ``'exact'`` (default) requires equality;
    ``'prefix'`` weights every row whose label starts with the key.
    """
    GHG_PROFILES[name] = {"match": match, "unit": unit, "gwp": dict(gwp),
                          "match_mode": match_mode}


def _autodetect_profile(db) -> Optional[str]:
    """Match db.meta.source / db.meta.name against profile substrings."""
    haystack = " ".join(
        str(getattr(db.meta, attr, "") or "") for attr in ("source", "name")
    ).lower()
    for name, spec in GHG_PROFILES.items():
        match = spec["match"]
        needles = (match,) if isinstance(match, str) else tuple(match)
        if all(n.lower() in haystack for n in needles):
            return name
    return None


def _ghg_row(matrix: pd.DataFrame, gwp: Dict[str, float],
             label: str, match_mode: str = "exact") -> pd.Series:
    """Multiply each ghg row by its GWP and return their sum as a Series
    indexed by ``matrix.columns`` and named ``label``.

    With ``match_mode='prefix'`` every row whose index label starts with a
    gwp key is weighted by that key's factor (multiple rows per key allowed).
    """
    if match_mode == "prefix":
        rows, weights = [], []
        for prefix, factor in gwp.items():
            mask = matrix.index.astype(str).str.startswith(prefix)
            if mask.any():
                rows.append(matrix.loc[mask])
                weights.append(pd.Series(factor, index=matrix.index[mask]))
        if not rows:
            raise KeyError(
                "None of the requested GHG accounts were found in the database."
            )
        sub = pd.concat(rows, axis=0)
        w = pd.concat(weights, axis=0)
        return sub.mul(w, axis=0).sum(axis=0).rename(label)

    available = [g for g in gwp if g in matrix.index]
    if not available:
        raise KeyError(
            "None of the requested GHG accounts were found in the database."
        )
    weights = pd.Series({g: gwp[g] for g in available})
    return matrix.loc[available].mul(weights, axis=0).sum(axis=0).rename(label)


def calc_ghg(
    db,
    profile: Optional[str] = None,
    gwp: Optional[Dict[str, float]] = None,
    label: str = "GHG",
    unit: Optional[str] = None,
    inplace: bool = False,
) -> Tuple[pd.Series, pd.Series]:
    """Aggregate GHG satellite accounts into a single ``label`` row.

    Parameters
    ----------
    db:
        A :class:`mario.Database` instance.
    profile:
        Name of a registered profile. When ``None`` the profile is
        auto-detected from ``db.meta.source`` / ``db.meta.name``.
    gwp:
        Optional ``{account: factor}`` mapping. Overrides the profile's
        default factors when given.
    label:
        Satellite-account label used for the aggregated row.
    unit:
        Unit string stored in ``db.units['Satellite account']`` for the new
        row. Defaults to the profile unit (``"kg CO2eq"``).
    inplace:
        When ``True``, the new row is appended to the baseline ``e`` and
        ``f`` matrices and to the satellite-account units table.

    Returns
    -------
    (pandas.Series, pandas.Series)
        The aggregated GHG intensity (e) and footprint (f) row Series.
    """
    if gwp is None:
        if profile is None:
            profile = _autodetect_profile(db)
        if profile is None or profile not in GHG_PROFILES:
            raise ValueError(
                "Could not auto-detect a GHG profile; pass `profile=` or "
                "`gwp=` explicitly. Registered profiles: "
                f"{sorted(GHG_PROFILES)}"
            )
        spec = GHG_PROFILES[profile]
        gwp = spec["gwp"]
        if unit is None:
            unit = spec.get("unit", "kg CO2eq")
        match_mode = spec.get("match_mode", "exact")
    else:
        if unit is None:
            unit = "kg CO2eq"
        match_mode = "exact"

    e_row = _ghg_row(db.e, gwp, label, match_mode=match_mode)
    f_row = _ghg_row(db.f, gwp, label, match_mode=match_mode)

    if inplace:
        db.matrices["baseline"]["e"] = pd.concat(
            [db.e, e_row.to_frame().T], axis=0
        )
        if "f" in db.matrices["baseline"]:
            db.matrices["baseline"]["f"] = pd.concat(
                [db.f, f_row.to_frame().T], axis=0
            )
        sat_units = db.units["Satellite account"]
        if isinstance(sat_units, pd.DataFrame):
            sat_units.loc[label] = unit
        else:  # Series
            sat_units.loc[label] = unit

    return e_row, f_row
