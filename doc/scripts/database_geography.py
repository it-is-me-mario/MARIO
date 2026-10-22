"""Resolve explicitly reviewed native regions; never infer aggregate membership."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

DOC = Path(__file__).resolve().parents[1]
MAP = DOC / "source/_static/data/world-country-map.json"

# Source-specific ADB abbreviations, as recorded in the workbook's region axis.
# These are exact aliases, not fuzzy matches or assumptions about RoW membership.
ADB_ALIASES = {
    "SWI": "CHE", "PRC": "CHN", "GER": "DEU", "DEN": "DNK", "SPA": "ESP", "UKG": "GBR",
    "INO": "IDN", "IRE": "IRL", "NET": "NLD", "POR": "PRT", "ROM": "ROU", "TAP": "TWN",
    "BAN": "BGD", "MAL": "MYS", "PHI": "PHL", "VIE": "VNM", "MON": "MNG", "SRI": "LKA",
    "FIJ": "FJI", "BRU": "BRN", "BHU": "BTN", "CAM": "KHM", "MLD": "MDV", "NEP": "NPL",
    "SIN": "SGP", "KUW": "KWT", "UAE": "ARE", "TAJ": "TJK", "PAR": "PRY",
}
EORA_ALIASES = {"SDS": "SSD", "SUD": "SDN"}
EORA_HISTORICAL = {"ANT": "Netherlands Antilles (historical grouping)",
                   "USR": "Soviet Union (former; historical grouping)"}
# The author workbook has exactly the same 245 native identifiers as the
# parsed V2.2 / 2023 reading. SER is labelled Serbia/Montenegro, not Serbia alone.
EMERGING22_HISTORICAL = {"ANT": "Netherlands Antilles (historical grouping)",
                         "SER": "Serbia / Montenegro (historical grouping)"}
# UNSD M49 records TMP -> TLS as a name/code change for the same country.
EMERGING22_ALIASES = {"TMP": "TLS"}
EMERGING22_NOMENCLATURE = {
    "name": "EMERGING author country nomenclature; matching 245 native region identifiers",
    "url": "https://zenodo.org/records/14258422/files/EMERGING2.5_Sector%26Country%20list.xlsx?download=1",
    "md5": "a1366e9c3afb2d843eb98439097b3bf9",
    "validated_reading": "EMERGING V2.2 / 2023",
    "validated_geography_sha256": "76f9fb1b3f82d12897a6d60b3b2a7f43cc3f91bb3d66dc447f897338421f4dc3",
    "historical_code_reference": "https://unstats.un.org/unsd/methodology/m49/",
    "note": "ANT and SER retain historical grouping labels without inferred current membership; TMP maps to TLS.",
}
NAME_ALIASES = {
    "GR": "GRC", "EL": "GRC", "GB": "GBR", "UK": "GBR",
    "Cote dIvoire": "CIV", "Cote d'Ivoire": "CIV", "Côte d’Ivoire": "CIV",
    "Congo": "COG", "DR Congo": "COD", "Democratic Republic of Congo": "COD",
    "Lao PDR": "LAO", "Korea, Republic of": "KOR", "Korea, Democratic People's Republic of": "PRK",
    "Viet Nam": "VNM", "Former USSR": None,
}
EXIO_AGGREGATES = {"WA": "RoW Asia and Pacific", "WL": "RoW America", "WE": "RoW Europe",
                   "WF": "RoW Africa", "WM": "RoW Middle East"}
EXIO_MONETARY_REGIONS = set("AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK GB US JP CN CA KR BR IN MX RU AU CH TR TW NO ID ZA WA WL WE WF WM".split())


def resolve_geography(profile, countries):
    by_code = {c["iso3"]: c for c in countries}
    exact = {}
    for country in countries:
        for field in ("iso3", "iso2", "name", "official_name"):
            if isinstance(country.get(field), str):
                exact[country[field].casefold()] = country["iso3"]
    regions = []
    native_signature = hashlib.sha256(json.dumps(sorted(set(profile["sets"]["Region"])),
                                                  ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    emerging_reviewed = (profile["guide"] == "emerging" and (
        (profile.get("release") == "2.2" and profile.get("year") == 2023)
        or (profile.get("release") in {"1.0", "2.0", "2.2", "E"}
            and native_signature == EMERGING22_NOMENCLATURE["validated_geography_sha256"])))
    historical = EORA_HISTORICAL if profile["guide"] == "eora" else EMERGING22_HISTORICAL if emerging_reviewed else {}
    for label in profile["sets"]["Region"]:
        text = str(label)
        if text in historical:
            regions.append({"label": label, "name": historical[text], "kind": "aggregate", "members": [],
                            "membership_status": "not_mapped", "historical": True})
            continue
        if profile["source"] in {"EXIOBASE", "BONSAI"} and text in EXIO_AGGREGATES:
            regions.append({"label": label, "name": EXIO_AGGREGATES[text], "kind": "aggregate", "members": [],
                            "membership_status": "not_mapped"})
            continue
        if profile["source"] == "BONSAI" and text == "Global":
            regions.append({"label": label, "name": "Global processes", "kind": "aggregate", "members": [],
                            "membership_status": "not_mapped", "note": "Native global process block, not a World total or an additional country."})
            continue
        # The 71-economy source Legend explicitly labels RoLAC as Rest of LAC.
        if profile["guide"] == "adb" and text == "RoLAC":
            regions.append({"label": label, "name": "Rest of Latin America and the Caribbean", "kind": "aggregate", "members": [],
                            "membership_status": "not_mapped"})
            continue
        if text.casefold() in {"row", "rest of world", "rest of the world"}:
            regions.append({"label": label, "name": "Rest of the world", "kind": "aggregate", "members": [],
                            "membership_status": "not_mapped"})
            continue
        code = ADB_ALIASES.get(text) if profile["guide"] == "adb" else None
        if profile["guide"] == "eora":
            code = EORA_ALIASES.get(text)
        if emerging_reviewed:
            code = EMERGING22_ALIASES.get(text)
        code = code or NAME_ALIASES.get(text) or exact.get(text.casefold())
        if code in by_code:
            regions.append({"label": label, "name": by_code[code]["name"], "kind": "country", "iso3": code})
        else:
            regions.append({"label": label, "name": text, "kind": "unresolved"})
    result = {"status": "reviewed_individual_regions", "regions": regions,
            "country_memberships": [], "individual_countries": len({r["iso3"] for r in regions if r["kind"] == "country"}),
            "aggregate_count": sum(r["kind"] == "aggregate" for r in regions),
            "unresolved_count": sum(r["kind"] == "unresolved" for r in regions),
            "method": "Exact ISO identifiers and country names, plus explicit source aliases. Aggregate memberships are not inferred."}
    if emerging_reviewed:
        result["region_mapping_sources"] = [{**EMERGING22_NOMENCLATURE,
            "applicable_reading": f'EMERGING {profile.get("release")} / {profile.get("year")}',
            "native_geography_sha256": native_signature}]
    return result


def add_geography(profile, path=MAP):
    if Path(path).is_file():
        data = json.loads(Path(path).read_text())
        profile["geography"] = resolve_geography(profile, data["countries"])
        concordance_path = DOC / "source/_static/data/geography-concordances.json"
        if concordance_path.is_file():
            concordances = json.loads(concordance_path.read_text())
            profile["geography"]["scope"] = "global" if profile["source"] in concordances["global_families"] else "national"
            exio = concordances["exiobase"]
            if profile["source"] == "EXIOBASE" and sorted(profile["sets"]["Region"]) == exio["native_regions"]:
                direct = {r["iso3"] for r in profile["geography"]["regions"] if r["kind"] == "country"}
                members = [code for group in exio["members"].values() for code in group]
                if len(members) != len(set(members)) or set(members) & direct:
                    raise ValueError("EXIOBASE concordance conflicts with individual regions")
                for region in profile["geography"]["regions"]:
                    if region["label"] in exio["members"]:
                        region["members"] = exio["members"][region["label"]]
                        region["membership_status"] = "reviewed_source_concordance"
                profile["geography"]["country_memberships"] = [
                    {"iso3": member, "region": region, "kind": "aggregate"}
                    for region, members in exio["members"].items() for member in members]
                profile["geography"]["aggregate_mapping_source"] = exio["source"]
    return profile
