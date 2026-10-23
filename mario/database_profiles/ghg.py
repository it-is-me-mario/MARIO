"""Native GHG row identities and characterisation profiles by database.

This module stores metadata only; calculations live in mario.ops.ghg.
"""
from typing import Dict, Optional, Union

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
            'AR6': 27.0,
            'AR5': 28,
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
    # ---------------- BONSAI Balanced HSUT / native b2 HIOT ------------
    # Names and compartments are the parser's readable satellite labels.
    # Biogenic CO2 is retained separately, consistently with the existing
    # EXIOBASE/GLORIA profiles; this is not a net biogenic carbon balance.
    # N2O is "Dinitrogen monoxide", distinct from NOx ("Nitrogen oxides").
    # GWP100: IPCC AR6 Table 7.15; AR5/AR4 variants follow the shared factors.
    # https://ghgprotocol.org/sites/default/files/2024-08/Global-Warming-Potential-Values%20(August%202024).pdf
    # Accelerated CO2 is a BONSAI-specific flow, characterized separately in
    # its LCIA.xlsx and load_climate_factors/calculate_ghg_footprint routines.
    # Only the checked AR6/GWP100 factor is supplied; do not extrapolate it.
    "bonsai": {
        "match": "bonsai",
        # Also accept disambiguating suffixes and the older unit/UUID labels.
        "match_mode": "prefix",
        "unit": "tonnes CO2eq",
        "gwp": {
            "Carbon dioxide, fossil | Air": GWPs['Carbon dioxide'],
            "Carbon dioxide, non-fossil | Air": 0,
            "Methane, fossil | Air": GWPs['Methane - fossil'],
            "Methane, non-fossil | Air": GWPs['Methane - non fossil'],
            "Dinitrogen monoxide | Air": GWPs['Nitrous oxide'],
            "Accelerated CO2, Air | Air": {100: {"AR6": 0.00772}},
        },
    },
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



def autodetect_profile(db) -> Optional[str]:
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
