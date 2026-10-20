"""Built-in GHG aggregation for MARIO databases.

Defines a small registry of GHG satellite-account profiles per supported
parser (EXIOBASE, EORA, GLORIA, EMERGING, ...) together with their default
GWP factors, and a `calc_ghg` helper used by `Database.calc_ghg()`.

The registry can be extended at runtime via :func:`register_ghg_profile`.
"""
from __future__ import annotations

import copy
from numbers import Real
from typing import Dict, Optional, Union
import numpy as np
import pandas as pd

from mario.compute.catalog import available_matrix_names, get_matrix_spec
from mario.ops.extensions import SATELLITE, _invalidate_dependent_operators

GWPScalar = Union[int, float]
GWPValue = Union[GWPScalar, Dict[int, Dict[str, GWPScalar]]]
GWPMapping = Dict[str, GWPValue]

GWPs = {
    'GHG': 1,
    'Carbon dioxide': 1,
    'Methane - fossil': {
        100: {
            'AR6': 29.8,
            'AR5': 30,
            'AR4': 25,
        },
    },
    'Methane - non fossil': {
        100: {
            'AR6': 29.8,
            'AR5': 30,
            'AR4': 25,
        },
    },
    'Nitrous oxide': {
        100: {
            'AR6': 273,
            'AR5': 265,
            'AR4': 298,
        }
    }
}


# ---------------------------------------------------------------- registry
# Each entry is a dict with:
#   match : substring or tuple of substrings (case-insensitive, AND-matched)
#           against db.meta.source / db.meta.name
#   gwp   : {satellite-account label : GWP factor or
#            {time_horizon: {ipcc_report: factor}}}
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
            "CO2 - combustion - air": GWPs['Carbon dioxide'],
            "CH4 - combustion - air": GWPs['Methane - fossil'],
            "N2O - combustion - air": GWPs['Nitrous oxide'],
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
            "Carbon dioxide, fossil (air - Emiss)": GWPs['Carbon dioxide'],
            "CH4 (air - Emiss)": GWPs['Methane - fossil'],
            "N2O (air - Emiss)": GWPs['Nitrous oxide'],
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
            'I-GHG-CO2 emissions (Gg) - Public electricity and heat production': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Other Energy Industries': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Manufacturing Industries and Construction': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Domestic aviation': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Road transportation': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Rail transportation': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Inland navigation': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Other transportation': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Residential and other sectors': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Fugitive emissions from solid fuels': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Fugitive emissions from oil and gas': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Memo: International aviation': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Memo: International navigation': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Production of minerals': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Cement production': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Lime production': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Production of chemicals': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Production of metals': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Production of pulp/paper/food/drink': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Production of halocarbons and SF6': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Refrigeration and Air Conditioning': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Foam Blowing': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Fire Extinguishers': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Aerosols': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - F-gas as Solvent': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Semiconductor/Electronics Manufacture': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Electrical Equipment': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Other F-gas use': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Non-energy use of lubricants/waxes (CO2)': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Solvent and other product use: paint': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Solvent and other product use: degrease': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Solvent and other product use: chemicals': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Solvent and other product use: other': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Enteric fermentation': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Manure management': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Rice cultivation': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Direct soil emissions': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Manure in pasture/range/paddock': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Indirect N2O from agriculture': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Other direct soil emissions': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Savanna burning': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Agricultural waste burning': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Forest fires': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Grassland fires': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Decay of wetlands/peatlands': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Other vegetation fires': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Forest Fires-Post burn decay': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Solid waste disposal on land': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Wastewater handling': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Waste incineration': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Other waste handling': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Fossil fuel fires': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Indirect N2O from non-agricultural NOx': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Indirect N2O from non-agricultural NH3': GWPs['Carbon dioxide'],
            'I-GHG-CO2 emissions (Gg) - Other sources': GWPs['Carbon dioxide'],
            'I-GHG-CH4 emissions (Gg) - Public electricity and heat production': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Other Energy Industries': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Manufacturing Industries and Construction': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Domestic aviation': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Road transportation': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Rail transportation': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Inland navigation': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Other transportation': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Residential and other sectors': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Fugitive emissions from solid fuels': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Fugitive emissions from oil and gas': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Memo: International aviation': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Memo: International navigation': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Production of minerals': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Cement production': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Lime production': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Production of chemicals': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Production of metals': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Production of pulp/paper/food/drink': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Production of halocarbons and SF6': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Refrigeration and Air Conditioning': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Foam Blowing': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Fire Extinguishers': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Aerosols': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - F-gas as Solvent': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Semiconductor/Electronics Manufacture': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Electrical Equipment': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Other F-gas use': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Non-energy use of lubricants/waxes (CO2)': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Solvent and other product use: paint': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Solvent and other product use: degrease': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Solvent and other product use: chemicals': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Solvent and other product use: other': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Enteric fermentation': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Manure management': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Rice cultivation': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Direct soil emissions': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Manure in pasture/range/paddock': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Indirect N2O from agriculture': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Other direct soil emissions': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Savanna burning': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Agricultural waste burning': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Forest fires': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Grassland fires': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Decay of wetlands/peatlands': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Other vegetation fires': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Forest Fires-Post burn decay': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Solid waste disposal on land': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Wastewater handling': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Waste incineration': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Other waste handling': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Fossil fuel fires': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Indirect N2O from non-agricultural NOx': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Indirect N2O from non-agricultural NH3': GWPs['Methane - fossil'],
            'I-GHG-CH4 emissions (Gg) - Other sources': GWPs['Methane - fossil'],
            'I-GHG-N2O emissions (Gg) - Public electricity and heat production': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Other Energy Industries': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Manufacturing Industries and Construction': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Domestic aviation': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Road transportation': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Rail transportation': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Inland navigation': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Other transportation': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Residential and other sectors': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Fugitive emissions from solid fuels': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Fugitive emissions from oil and gas': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Memo: International aviation': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Memo: International navigation': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Production of minerals': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Cement production': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Lime production': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Production of chemicals': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Production of metals': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Production of pulp/paper/food/drink': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Production of halocarbons and SF6': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Refrigeration and Air Conditioning': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Foam Blowing': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Fire Extinguishers': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Aerosols': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - F-gas as Solvent': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Semiconductor/Electronics Manufacture': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Electrical Equipment': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Other F-gas use': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Non-energy use of lubricants/waxes (CO2)': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Solvent and other product use: paint': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Solvent and other product use: degrease': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Solvent and other product use: chemicals': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Solvent and other product use: other': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Enteric fermentation': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Manure management': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Rice cultivation': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Direct soil emissions': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Manure in pasture/range/paddock': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Indirect N2O from agriculture': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Other direct soil emissions': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Savanna burning': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Agricultural waste burning': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Forest fires': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Grassland fires': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Decay of wetlands/peatlands': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Other vegetation fires': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Forest Fires-Post burn decay': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Solid waste disposal on land': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Wastewater handling': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Waste incineration': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Other waste handling': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Fossil fuel fires': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Indirect N2O from non-agricultural NOx': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Indirect N2O from non-agricultural NH3': GWPs['Nitrous oxide'],
            'I-GHG-N2O emissions (Gg) - Other sources': GWPs['Nitrous oxide'],        
        },
    },
    "adb": {
        "match": "adb",
        "unit": "Gigagrams of Carbon Dioxide equivalent (Gg of CO2e)",
        "gwp": {
            'GHG | Total by substance': GWPs['GHG'],
        }
    },

    "gloria": {
        "match": "gloria",
        "unit": "kg CO2eq",
        "gwp": {
            "Emissions (EDGAR) | 'co2_excl_short_cycle_org_c_total_EDGAR_consistent'": GWPs['Carbon dioxide'],
            "Emissions (EDGAR) | 'ch4_total_EDGAR_consistent'": GWPs['Methane - fossil'],
            "Emissions (EDGAR) | 'n2o_total_EDGAR_consistent'": GWPs['Nitrous oxide'],
        },
    },
    "emerging": {
        "match": "emerging",
        "unit": "Mt CO2eq",
        "gwp": {
            "Coal": GWPs['GHG'],
            "Natural gas": GWPs['GHG'],
            "Oil products": GWPs['GHG'],
            "Crude, NGL, Ref Feeds.": GWPs['GHG'],
            "Oil shale & oil sands": GWPs['GHG'],
            "Peat & Peat products": GWPs['GHG'],
            "Other": GWPs['GHG'],
        },
    },
}


def register_ghg_profile(name: str, match, gwp: GWPMapping,
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


def _resolve_profile_gwp(
    gwp: GWPMapping,
    time_horizon: int = 100,
    ipcc_report: str = "AR6",
) -> Dict[str, GWPScalar]:
    """Resolve a profile GWP mapping into flat scalar factors."""
    report = str(ipcc_report).strip().upper()
    resolved: Dict[str, GWPScalar] = {}

    for account, factor in gwp.items():
        if not isinstance(factor, dict):
            resolved[account] = factor
            continue

        if time_horizon not in factor:
            available_horizons = ", ".join(map(str, sorted(factor)))
            raise ValueError(
                f"Time horizon {time_horizon} is not available for '{account}'. "
                f"Available horizons: {available_horizons}."
            )

        report_factors = factor[time_horizon]
        if report not in report_factors:
            available_reports = ", ".join(sorted(report_factors))
            raise ValueError(
                f"IPCC report '{report}' is not available for '{account}' "
                f"at time horizon {time_horizon}. Available reports: "
                f"{available_reports}."
            )

        resolved[account] = report_factors[report]

    return resolved


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


def _ghg_row(matrix: pd.DataFrame, gwp: Dict[str, GWPScalar],
             label: str, match_mode: str = "exact") -> pd.Series:
    """Multiply each ghg row by its GWP and return their sum as a Series
    indexed by ``matrix.columns`` and named ``label``.

    With ``match_mode='prefix'`` every row whose index label starts with a
    gwp key is weighted by that key's factor (multiple rows per key allowed).
    """
    _matched_ghg_labels(matrix.index, gwp, match_mode=match_mode)
    if matrix.shape[1] == 0:
        return pd.Series(index=matrix.columns, dtype=float, name=label)
    weights = pd.Series(0.0, index=matrix.index)
    if match_mode == "prefix":
        for prefix, factor in gwp.items():
            weights.loc[matrix.index.astype(str).str.startswith(prefix)] += factor
    else:
        for account, factor in gwp.items():
            if account in weights.index:
                weights.loc[account] = factor

    # An account with GWP=0 contributes zero even when its multiplier is NaN.
    selected = weights != 0
    if not selected.any():
        return pd.Series(0.0, index=matrix.columns, name=label)
    sub = matrix.loc[selected]
    values = weights.loc[selected].to_numpy(dtype=float)
    if all(isinstance(t, pd.SparseDtype) and t.fill_value == 0 for t in sub.dtypes):
        from scipy import sparse

        weighted = sparse.diags(values) @ sub.sparse.to_coo().tocsr()
        result = np.asarray(weighted.sum(axis=0)).ravel()
    else:
        # Only selected gas rows are materialized, never the economic system.
        result = values @ sub.to_numpy(dtype=float)
    return pd.Series(result, index=matrix.columns, name=label)


def _append_ghg_row(matrix, gwp, label, matched_labels, *, match_mode, block_name):
    """Extend one stored linear satellite block while preserving its storage."""
    if not isinstance(matrix, pd.DataFrame):
        raise ValueError(f"Satellite block {block_name!r} must be a pandas DataFrame.")
    if isinstance(matrix.index, pd.MultiIndex) or not matrix.index.is_unique:
        raise ValueError(
            f"Satellite block {block_name!r} must have one unique row per account."
        )
    missing = pd.Index(matched_labels).difference(matrix.index)
    if len(missing):
        raise ValueError(f"Satellite block {block_name!r} is missing GHG accounts: {missing.tolist()!r}.")
    if label in matrix.index:
        raise ValueError(f"Satellite account {label!r} already exists in block {block_name!r}.")
    row = _ghg_row(matrix, gwp, label, match_mode=match_mode)
    row_index = pd.Index([label], name=matrix.index.name)
    if matrix.shape[1] and all(
        isinstance(t, pd.SparseDtype) and t.fill_value == 0 for t in matrix.dtypes
    ):
        from scipy import sparse

        # Pandas concatenation otherwise appends separately to every column's
        # SparseArray. Native SUTs have tens of thousands of these columns.
        result = pd.DataFrame.sparse.from_spmatrix(
            sparse.vstack([
                matrix.sparse.to_coo().tocsr(),
                sparse.csr_matrix(row.to_numpy().reshape(1, -1)),
            ], format="csc"),
            index=matrix.index.append(row_index), columns=matrix.columns,
        )
    else:
        extension = pd.DataFrame([row.to_numpy()], index=row_index, columns=matrix.columns)
        result = pd.concat([matrix, extension], axis=0)
    # In particular, retain diagnostics attached to partial multiplier results.
    result.attrs = copy.deepcopy(matrix.attrs)
    return result


def _append_ghg_account(target, gwp, label, resolved_unit, matched_labels, *, match_mode):
    """Stage a characterization across scenarios without resolving any matrices."""
    satellite_blocks = {
        name for name in available_matrix_names(target.table_type)
        if get_matrix_spec(target.table_type, name).axes.rows == (SATELLITE,)
    }
    matrices = {}
    for scenario, blocks in target.matrices.items():
        updated = dict(blocks)
        affected = set(blocks).intersection(satellite_blocks)
        if not affected:
            raise ValueError(f"Scenario {scenario!r} has no stored satellite blocks to characterize.")
        for name in affected:
            updated[name] = _append_ghg_row(
                blocks[name], gwp, label, matched_labels,
                match_mode=match_mode, block_name=f"{scenario}/{name}",
            )
        _invalidate_dependent_operators(target, updated, affected)
        matrices[scenario] = updated

    indexes = copy.deepcopy(target._indeces["k"])
    indexes["main"] = list(indexes["main"]) + [label]
    units = target.units[SATELLITE]
    if label in units.index:
        raise ValueError(f"Satellite account {label!r} already exists in the units table.")
    unit_column = "unit" if "unit" in units.columns else units.columns[0]
    new_units = pd.concat([
        units,
        pd.DataFrame({unit_column: [resolved_unit]}, index=pd.Index([label], name=units.index.name)),
    ])
    # Commit only after every scenario and its metadata have been validated.
    target.matrices = matrices
    target._indeces["k"] = indexes
    target.units[SATELLITE] = new_units
    target.meta._add_history(
        f"GHG satellite account {label!r} added using {gwp!r} across {len(matrices)} scenario(s)."
    )


def _matched_ghg_labels(index: pd.Index, gwp: Dict[str, GWPScalar],
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


def _default_ghg_label(ipcc_report: str, time_horizon: int, explicit_gwp: bool) -> str:
    """Compose the default satellite-account label for the aggregated GHG row.

    Built-in profiles resolve their GWPs from one IPCC report and time horizon,
    so the label encodes both, e.g. ``"GHG AR6 GWP-100"``. Custom ``gwp=...``
    mappings ignore those arguments, so the plain ``"GHG"`` label is used.
    """
    if explicit_gwp:
        return "GHG"
    return f"GHG {str(ipcc_report).strip().upper()} GWP-{int(time_horizon)}"


def calc_ghg(
    db,
    profile: Optional[str] = None,
    gwp: Optional[Dict[str, GWPScalar]] = None,
    label: Optional[str] = None,
    unit: Optional[str] = None,
    time_horizon: int = 100,
    ipcc_report: str = "AR6",
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
        Satellite-account label used for the aggregated row. When omitted, the
        label is derived from the GWP basis: built-in profiles yield
        ``"GHG {ipcc_report} GWP-{time_horizon}"`` (e.g. ``"GHG AR6 GWP-100"``),
        while custom ``gwp=...`` mappings yield ``"GHG"``.
    unit:
        Optional unit override. When omitted, MARIO reuses the shared unit of
        the aggregated satellite accounts and raises when those units differ.
    time_horizon:
        Time horizon used to resolve built-in profile GWPs when profiles store
        multiple horizons. Ignored when ``gwp=...`` is provided.
    ipcc_report:
        IPCC assessment report used to resolve built-in profile GWPs when
        profiles store multiple report variants. Ignored when ``gwp=...`` is
        provided.
    inplace:
        When ``True`` mutate the current database. When ``False`` return a
        modified copy.

    Returns
    -------
    Database | None
        Modified database when ``inplace=False``, otherwise ``None``.

    Notes
    -----
    Characterizes stored environmental blocks in every scenario, including
    native SUT ``Ea``, ``Ec`` and ``EY``. Existing coefficients, multipliers
    and footprints receive the same weighted row without new linear solves.
    Missing matrices are left for on-demand resolution. Economic matrices,
    scenarios and sparse storage are preserved. Cached custom operators
    depending on changed environmental blocks are invalidated.
    """
    if not isinstance(inplace, bool):
        raise ValueError("inplace must be True or False.")
    target = db if inplace else db.copy()
    explicit_gwp = gwp is not None

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
        try:
            time_horizon = int(time_horizon)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid time horizon '{time_horizon}'. Expected an integer."
            ) from exc

        gwp = _resolve_profile_gwp(
            spec["gwp"],
            time_horizon=time_horizon,
            ipcc_report=ipcc_report,
        )
        match_mode = spec.get("match_mode", "exact")
    else:
        match_mode = "exact"

    if not isinstance(gwp, dict) or any(
        not isinstance(factor, Real) or not np.isfinite(factor) for factor in gwp.values()
    ):
        raise ValueError("gwp must map satellite account labels to finite numeric factors.")

    if label is None:
        label = _default_ghg_label(ipcc_report, time_horizon, explicit_gwp)

    if label in target.get_index("Satellite account"):
        raise ValueError(
            f"Satellite account '{label}' already exists in the database."
        )

    matched_labels = _matched_ghg_labels(
        pd.Index(target.get_index(SATELLITE)), gwp, match_mode=match_mode
    )
    resolved_unit = _resolve_ghg_unit(target, matched_labels, unit)
    _append_ghg_account(
        target, gwp, label, resolved_unit, matched_labels, match_mode=match_mode,
    )

    if not inplace:
        return target
