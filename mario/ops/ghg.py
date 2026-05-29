"""Built-in GHG aggregation for MARIO databases.

Defines a small registry of GHG satellite-account profiles per supported
parser (EXIOBASE, EORA, GLORIA, EMERGING, ...) together with their default
GWP-100 factors, and a `calc_ghg` helper used by `Database.calc_ghg()`.

The registry can be extended at runtime via :func:`register_ghg_profile`.
"""
from __future__ import annotations

from typing import Dict, Optional
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
            'I-GHG-CO2 emissions (Gg) - Public electricity and heat production': 1,
            'I-GHG-CO2 emissions (Gg) - Other Energy Industries': 1,
            'I-GHG-CO2 emissions (Gg) - Manufacturing Industries and Construction': 1,
            'I-GHG-CO2 emissions (Gg) - Domestic aviation': 1,
            'I-GHG-CO2 emissions (Gg) - Road transportation': 1,
            'I-GHG-CO2 emissions (Gg) - Rail transportation': 1,
            'I-GHG-CO2 emissions (Gg) - Inland navigation': 1,
            'I-GHG-CO2 emissions (Gg) - Other transportation': 1,
            'I-GHG-CO2 emissions (Gg) - Residential and other sectors': 1,
            'I-GHG-CO2 emissions (Gg) - Fugitive emissions from solid fuels': 1,
            'I-GHG-CO2 emissions (Gg) - Fugitive emissions from oil and gas': 1,
            'I-GHG-CO2 emissions (Gg) - Memo: International aviation': 1,
            'I-GHG-CO2 emissions (Gg) - Memo: International navigation': 1,
            'I-GHG-CO2 emissions (Gg) - Production of minerals': 1,
            'I-GHG-CO2 emissions (Gg) - Cement production': 1,
            'I-GHG-CO2 emissions (Gg) - Lime production': 1,
            'I-GHG-CO2 emissions (Gg) - Production of chemicals': 1,
            'I-GHG-CO2 emissions (Gg) - Production of metals': 1,
            'I-GHG-CO2 emissions (Gg) - Production of pulp/paper/food/drink': 1,
            'I-GHG-CO2 emissions (Gg) - Production of halocarbons and SF6': 1,
            'I-GHG-CO2 emissions (Gg) - Refrigeration and Air Conditioning': 1,
            'I-GHG-CO2 emissions (Gg) - Foam Blowing': 1,
            'I-GHG-CO2 emissions (Gg) - Fire Extinguishers': 1,
            'I-GHG-CO2 emissions (Gg) - Aerosols': 1,
            'I-GHG-CO2 emissions (Gg) - F-gas as Solvent': 1,
            'I-GHG-CO2 emissions (Gg) - Semiconductor/Electronics Manufacture': 1,
            'I-GHG-CO2 emissions (Gg) - Electrical Equipment': 1,
            'I-GHG-CO2 emissions (Gg) - Other F-gas use': 1,
            'I-GHG-CO2 emissions (Gg) - Non-energy use of lubricants/waxes (CO2)': 1,
            'I-GHG-CO2 emissions (Gg) - Solvent and other product use: paint': 1,
            'I-GHG-CO2 emissions (Gg) - Solvent and other product use: degrease': 1,
            'I-GHG-CO2 emissions (Gg) - Solvent and other product use: chemicals': 1,
            'I-GHG-CO2 emissions (Gg) - Solvent and other product use: other': 1,
            'I-GHG-CO2 emissions (Gg) - Enteric fermentation': 1,
            'I-GHG-CO2 emissions (Gg) - Manure management': 1,
            'I-GHG-CO2 emissions (Gg) - Rice cultivation': 1,
            'I-GHG-CO2 emissions (Gg) - Direct soil emissions': 1,
            'I-GHG-CO2 emissions (Gg) - Manure in pasture/range/paddock': 1,
            'I-GHG-CO2 emissions (Gg) - Indirect N2O from agriculture': 1,
            'I-GHG-CO2 emissions (Gg) - Other direct soil emissions': 1,
            'I-GHG-CO2 emissions (Gg) - Savanna burning': 1,
            'I-GHG-CO2 emissions (Gg) - Agricultural waste burning': 1,
            'I-GHG-CO2 emissions (Gg) - Forest fires': 1,
            'I-GHG-CO2 emissions (Gg) - Grassland fires': 1,
            'I-GHG-CO2 emissions (Gg) - Decay of wetlands/peatlands': 1,
            'I-GHG-CO2 emissions (Gg) - Other vegetation fires': 1,
            'I-GHG-CO2 emissions (Gg) - Forest Fires-Post burn decay': 1,
            'I-GHG-CO2 emissions (Gg) - Solid waste disposal on land': 1,
            'I-GHG-CO2 emissions (Gg) - Wastewater handling': 1,
            'I-GHG-CO2 emissions (Gg) - Waste incineration': 1,
            'I-GHG-CO2 emissions (Gg) - Other waste handling': 1,
            'I-GHG-CO2 emissions (Gg) - Fossil fuel fires': 1,
            'I-GHG-CO2 emissions (Gg) - Indirect N2O from non-agricultural NOx': 1,
            'I-GHG-CO2 emissions (Gg) - Indirect N2O from non-agricultural NH3': 1,
            'I-GHG-CO2 emissions (Gg) - Other sources': 1.0,
            'I-GHG-CH4 emissions (Gg) - Public electricity and heat production': 29.7,
            'I-GHG-CH4 emissions (Gg) - Other Energy Industries': 29.7,
            'I-GHG-CH4 emissions (Gg) - Manufacturing Industries and Construction': 29.7,
            'I-GHG-CH4 emissions (Gg) - Domestic aviation': 29.7,
            'I-GHG-CH4 emissions (Gg) - Road transportation': 29.7,
            'I-GHG-CH4 emissions (Gg) - Rail transportation': 29.7,
            'I-GHG-CH4 emissions (Gg) - Inland navigation': 29.7,
            'I-GHG-CH4 emissions (Gg) - Other transportation': 29.7,
            'I-GHG-CH4 emissions (Gg) - Residential and other sectors': 29.7,
            'I-GHG-CH4 emissions (Gg) - Fugitive emissions from solid fuels': 29.7,
            'I-GHG-CH4 emissions (Gg) - Fugitive emissions from oil and gas': 29.7,
            'I-GHG-CH4 emissions (Gg) - Memo: International aviation': 29.7,
            'I-GHG-CH4 emissions (Gg) - Memo: International navigation': 29.7,
            'I-GHG-CH4 emissions (Gg) - Production of minerals': 29.7,
            'I-GHG-CH4 emissions (Gg) - Cement production': 29.7,
            'I-GHG-CH4 emissions (Gg) - Lime production': 29.7,
            'I-GHG-CH4 emissions (Gg) - Production of chemicals': 29.7,
            'I-GHG-CH4 emissions (Gg) - Production of metals': 29.7,
            'I-GHG-CH4 emissions (Gg) - Production of pulp/paper/food/drink': 29.7,
            'I-GHG-CH4 emissions (Gg) - Production of halocarbons and SF6': 29.7,
            'I-GHG-CH4 emissions (Gg) - Refrigeration and Air Conditioning': 29.7,
            'I-GHG-CH4 emissions (Gg) - Foam Blowing': 29.7,
            'I-GHG-CH4 emissions (Gg) - Fire Extinguishers': 29.7,
            'I-GHG-CH4 emissions (Gg) - Aerosols': 29.7,
            'I-GHG-CH4 emissions (Gg) - F-gas as Solvent': 29.7,
            'I-GHG-CH4 emissions (Gg) - Semiconductor/Electronics Manufacture': 29.7,
            'I-GHG-CH4 emissions (Gg) - Electrical Equipment': 29.7,
            'I-GHG-CH4 emissions (Gg) - Other F-gas use': 29.7,
            'I-GHG-CH4 emissions (Gg) - Non-energy use of lubricants/waxes (CO2)': 29.7,
            'I-GHG-CH4 emissions (Gg) - Solvent and other product use: paint': 29.7,
            'I-GHG-CH4 emissions (Gg) - Solvent and other product use: degrease': 29.7,
            'I-GHG-CH4 emissions (Gg) - Solvent and other product use: chemicals': 29.7,
            'I-GHG-CH4 emissions (Gg) - Solvent and other product use: other': 29.7,
            'I-GHG-CH4 emissions (Gg) - Enteric fermentation': 29.7,
            'I-GHG-CH4 emissions (Gg) - Manure management': 29.7,
            'I-GHG-CH4 emissions (Gg) - Rice cultivation': 29.7,
            'I-GHG-CH4 emissions (Gg) - Direct soil emissions': 29.7,
            'I-GHG-CH4 emissions (Gg) - Manure in pasture/range/paddock': 29.7,
            'I-GHG-CH4 emissions (Gg) - Indirect N2O from agriculture': 29.7,
            'I-GHG-CH4 emissions (Gg) - Other direct soil emissions': 29.7,
            'I-GHG-CH4 emissions (Gg) - Savanna burning': 29.7,
            'I-GHG-CH4 emissions (Gg) - Agricultural waste burning': 29.7,
            'I-GHG-CH4 emissions (Gg) - Forest fires': 29.7,
            'I-GHG-CH4 emissions (Gg) - Grassland fires': 29.7,
            'I-GHG-CH4 emissions (Gg) - Decay of wetlands/peatlands': 29.7,
            'I-GHG-CH4 emissions (Gg) - Other vegetation fires': 29.7,
            'I-GHG-CH4 emissions (Gg) - Forest Fires-Post burn decay': 29.7,
            'I-GHG-CH4 emissions (Gg) - Solid waste disposal on land': 29.7,
            'I-GHG-CH4 emissions (Gg) - Wastewater handling': 29.7,
            'I-GHG-CH4 emissions (Gg) - Waste incineration': 29.7,
            'I-GHG-CH4 emissions (Gg) - Other waste handling': 29.7,
            'I-GHG-CH4 emissions (Gg) - Fossil fuel fires': 29.7,
            'I-GHG-CH4 emissions (Gg) - Indirect N2O from non-agricultural NOx': 29.7,
            'I-GHG-CH4 emissions (Gg) - Indirect N2O from non-agricultural NH3': 29.7,
            'I-GHG-CH4 emissions (Gg) - Other sources': 29.7,
            'I-GHG-N2O emissions (Gg) - Public electricity and heat production': 264.8,
            'I-GHG-N2O emissions (Gg) - Other Energy Industries': 264.8,
            'I-GHG-N2O emissions (Gg) - Manufacturing Industries and Construction': 264.8,
            'I-GHG-N2O emissions (Gg) - Domestic aviation': 264.8,
            'I-GHG-N2O emissions (Gg) - Road transportation': 264.8,
            'I-GHG-N2O emissions (Gg) - Rail transportation': 264.8,
            'I-GHG-N2O emissions (Gg) - Inland navigation': 264.8,
            'I-GHG-N2O emissions (Gg) - Other transportation': 264.8,
            'I-GHG-N2O emissions (Gg) - Residential and other sectors': 264.8,
            'I-GHG-N2O emissions (Gg) - Fugitive emissions from solid fuels': 264.8,
            'I-GHG-N2O emissions (Gg) - Fugitive emissions from oil and gas': 264.8,
            'I-GHG-N2O emissions (Gg) - Memo: International aviation': 264.8,
            'I-GHG-N2O emissions (Gg) - Memo: International navigation': 264.8,
            'I-GHG-N2O emissions (Gg) - Production of minerals': 264.8,
            'I-GHG-N2O emissions (Gg) - Cement production': 264.8,
            'I-GHG-N2O emissions (Gg) - Lime production': 264.8,
            'I-GHG-N2O emissions (Gg) - Production of chemicals': 264.8,
            'I-GHG-N2O emissions (Gg) - Production of metals': 264.8,
            'I-GHG-N2O emissions (Gg) - Production of pulp/paper/food/drink': 264.8,
            'I-GHG-N2O emissions (Gg) - Production of halocarbons and SF6': 264.8,
            'I-GHG-N2O emissions (Gg) - Refrigeration and Air Conditioning': 264.8,
            'I-GHG-N2O emissions (Gg) - Foam Blowing': 264.8,
            'I-GHG-N2O emissions (Gg) - Fire Extinguishers': 264.8,
            'I-GHG-N2O emissions (Gg) - Aerosols': 264.8,
            'I-GHG-N2O emissions (Gg) - F-gas as Solvent': 264.8,
            'I-GHG-N2O emissions (Gg) - Semiconductor/Electronics Manufacture': 264.8,
            'I-GHG-N2O emissions (Gg) - Electrical Equipment': 264.8,
            'I-GHG-N2O emissions (Gg) - Other F-gas use': 264.8,
            'I-GHG-N2O emissions (Gg) - Non-energy use of lubricants/waxes (CO2)': 264.8,
            'I-GHG-N2O emissions (Gg) - Solvent and other product use: paint': 264.8,
            'I-GHG-N2O emissions (Gg) - Solvent and other product use: degrease': 264.8,
            'I-GHG-N2O emissions (Gg) - Solvent and other product use: chemicals': 264.8,
            'I-GHG-N2O emissions (Gg) - Solvent and other product use: other': 264.8,
            'I-GHG-N2O emissions (Gg) - Enteric fermentation': 264.8,
            'I-GHG-N2O emissions (Gg) - Manure management': 264.8,
            'I-GHG-N2O emissions (Gg) - Rice cultivation': 264.8,
            'I-GHG-N2O emissions (Gg) - Direct soil emissions': 264.8,
            'I-GHG-N2O emissions (Gg) - Manure in pasture/range/paddock': 264.8,
            'I-GHG-N2O emissions (Gg) - Indirect N2O from agriculture': 264.8,
            'I-GHG-N2O emissions (Gg) - Other direct soil emissions': 264.8,
            'I-GHG-N2O emissions (Gg) - Savanna burning': 264.8,
            'I-GHG-N2O emissions (Gg) - Agricultural waste burning': 264.8,
            'I-GHG-N2O emissions (Gg) - Forest fires': 264.8,
            'I-GHG-N2O emissions (Gg) - Grassland fires': 264.8,
            'I-GHG-N2O emissions (Gg) - Decay of wetlands/peatlands': 264.8,
            'I-GHG-N2O emissions (Gg) - Other vegetation fires': 264.8,
            'I-GHG-N2O emissions (Gg) - Forest Fires-Post burn decay': 264.8,
            'I-GHG-N2O emissions (Gg) - Solid waste disposal on land': 264.8,
            'I-GHG-N2O emissions (Gg) - Wastewater handling': 264.8,
            'I-GHG-N2O emissions (Gg) - Waste incineration': 264.8,
            'I-GHG-N2O emissions (Gg) - Other waste handling': 264.8,
            'I-GHG-N2O emissions (Gg) - Fossil fuel fires': 264.8,
            'I-GHG-N2O emissions (Gg) - Indirect N2O from non-agricultural NOx': 264.8,
            'I-GHG-N2O emissions (Gg) - Indirect N2O from non-agricultural NH3': 264.8,
            'I-GHG-N2O emissions (Gg) - Other sources': 264.8,        
        },
    },
    "adb": {
        "match": "adb",
        "unit": "Gigagrams of Carbon Dioxide equivalent (Gg of CO2e)",
        "gwp": {
            'GHG | Total by substance': 1.0,
        }
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


def _matched_ghg_labels(index: pd.Index, gwp: Dict[str, float],
                        match_mode: str = "exact") -> list[str]:
    """Return the source account labels used by the GHG aggregation."""
    labels = pd.Index(index)

    if match_mode == "prefix":
        matched: list[str] = []
        as_text = labels.astype(str)
        for prefix in gwp:
            matched.extend(labels[as_text.str.startswith(prefix)].tolist())
        matched = list(dict.fromkeys(matched))
    else:
        matched = [label for label in gwp if label in labels]

    if not matched:
        raise KeyError(
            "None of the requested GHG accounts were found in the database."
        )

    return matched


def _resolve_ghg_unit(db, labels: list[str], unit: Optional[str]) -> str:
    """Validate that aggregated accounts share one unit and return it."""
    sat_units = db.units["Satellite account"]
    source_units = sat_units.loc[pd.Index(labels).unique()]

    if isinstance(source_units, pd.DataFrame):
        if "unit" in source_units.columns:
            source_units = source_units["unit"]
        else:
            source_units = source_units.iloc[:, 0]

    unique_units = pd.Index(source_units.dropna().tolist()).unique().tolist()
    if len(unique_units) != 1:
        raise ValueError(
            "GHG accounts can be aggregated only when they all share the same unit. "
            f"Found units for {labels}: {unique_units}"
        )

    source_unit = unique_units[0]
    if unit is not None and unit != source_unit:
        raise ValueError(
            f"Requested unit '{unit}' does not match the aggregated GHG accounts unit "
            f"'{source_unit}'."
        )

    return source_unit


def calc_ghg(
    db,
    profile: Optional[str] = None,
    gwp: Optional[Dict[str, float]] = None,
    label: str = "GHG",
    unit: Optional[str] = None,
    inplace: bool = True,
):
    """Aggregate GHG satellite accounts into a new satellite-account row.

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
        Optional unit override. When omitted, MARIO reuses the shared unit of
        the aggregated satellite accounts and raises when those units differ.
    inplace:
        When ``True`` mutate the current database. When ``False`` return a
        modified copy.

    Returns
    -------
    Database | None
        Modified database when ``inplace=False``, otherwise ``None``.
    """
    target = db if inplace else db.copy()

    if gwp is None:
        if profile is None:
            profile = _autodetect_profile(target)
        if profile is None or profile not in GHG_PROFILES:
            raise ValueError(
                "Could not auto-detect a GHG profile; pass `profile=` or "
                "`gwp=` explicitly. Registered profiles: "
                f"{sorted(GHG_PROFILES)}"
            )
        spec = GHG_PROFILES[profile]
        gwp = spec["gwp"]
        match_mode = spec.get("match_mode", "exact")
    else:
        match_mode = "exact"

    if label in target.get_index("Satellite account"):
        raise ValueError(
            f"Satellite account '{label}' already exists in the database."
        )

    matched_labels = _matched_ghg_labels(target.E.index, gwp, match_mode=match_mode)
    resolved_unit = _resolve_ghg_unit(target, matched_labels, unit)

    extension_row = _ghg_row(target.E, gwp, label, match_mode=match_mode)
    final_demand_row = _ghg_row(target.EY, gwp, label, match_mode=match_mode)

    extension = extension_row.to_frame().T
    extension_fd = final_demand_row.to_frame().T
    unit_frame = pd.DataFrame({"unit": [resolved_unit]}, index=extension.index.copy())

    target.add_extensions(
        io=extension,
        matrix="E",
        units=unit_frame,
        inplace=True,
        calc_all=True,
        EY=extension_fd,
    )

    if not inplace:
        return target
