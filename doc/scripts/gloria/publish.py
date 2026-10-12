"""Stage or publish reviewed GLORIA indicators and native sets, without reparsing.

Inputs are the local MARIO extraction retained in Output/database-browser-local.
Only aggregated indicator vectors and set metadata are distributed. Source
licensing evidence and the README region/ISIC concordances sit beside this file.
"""
from pathlib import Path
import argparse
import json
import sys

HERE = Path(__file__).resolve().parent
DOC = HERE.parents[1]
sys.path.insert(0, str(DOC / "scripts"))
from build_economy_browser import publish as publish_indicators
from database_catalogue import publish as publish_sets
from product_taxes import apply as apply_gdp_bridge


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


def prepare(snapshot, profile, stage, gdp_bridge=None):
    snapshot = json.loads(Path(snapshot).read_text())
    profile = json.loads(Path(profile).read_text())
    recipe = snapshot["recipe"]
    assert recipe["id"] == profile["id"] == f"gloria-060-{recipe['year']}-sut"
    assert recipe["year"] == profile["year"] and recipe["release"] == "060"
    assert len(snapshot["regions"]) == profile["counts"]["Region"] == 164
    assert len(recipe["sectors"]) == profile["counts"]["Activity"] == 120
    evidence = json.loads((HERE / "licence.json").read_text())
    names = {row[1]: row[2] for row in json.loads((HERE / "regions.json").read_text())[1:]}
    for region in profile["geography"]["regions"]:
        if region["kind"] == "unresolved" or region["label"] in {"SDS", "DYE"}:
            region["name"] = names[region["label"]]
            if region["label"].startswith("X"):
                region["kind"] = "aggregate"
            elif region["label"] == "SDS":
                region.update(kind="country", iso3="SSD")
    geography = {r["label"]: r for r in profile["geography"]["regions"]}
    for region in snapshot["regions"]:
        native = geography[region["code"]]
        region.update(name=native["name"], kind=native["kind"], iso3=native.get("iso3"))
        assert len(region["value_added"]) == len(region["ghg"]) == 120
        assert region["household_ghg"] is not None
    profile["geography"].update(scope="global", individual_countries=sum(r["kind"] == "country" for r in geography.values()), aggregate_count=sum(r["kind"] == "aggregate" for r in geography.values()), unresolved_count=sum(r["kind"] == "unresolved" for r in geography.values()))
    profile["geography"]["region_mapping_sources"] = ["GLORIA_ReadMe_060.xlsx, Regions sheet. SDS = South Sudan (SSD); DYE is a retained historical source region. Aggregate memberships are not inferred."]
    recipe.update(
        label="GLORIA 060 · SUT", world_total_available=True,
        final_demand_emissions_loaded=True, gdp_bridge_verified=bool(recipe.get("gdp_bridge_verified")),
        license_url=evidence["license_url"], license_basis=evidence,
        value_added_basis="Value added at basic prices; six explicit source factor rows",
        ghg_basis="Native EDGAR-consistent GHG total plus direct final-demand emissions; source CO2eq characterisation retained",
        gwp_basis='Native CO2eq; IPCC AR5 GWP100 verified for CO2, CH4, N2O, SF6 and NF3; other F-gases unverified', gwp_horizon=100,
        ghg_note='GLORIA retains its native EDGAR-consistent CO2eq total. Independent checks of the 2001 and 2024 gas rows recover AR5 GWP100 factors for CO2, CH4, N2O, SF6 and NF3. Individual factors for all fluorinated gases remain unverified; the 2024 cell-level gas-row fit has a relative L2 residual of about 0.15%. The EDGAR 2026 territorial boundary also differs.',
        scope_note=f"GLORIA {recipe['year']}: economic vintage {recipe.get('economic_vintage', '20260122')}; satellite vintage {recipe.get('satellite_vintage', '20240417')}. GDP is unavailable until the full product-tax bridge is verified.",
        attribution="GLORIA v060, University of Sydney / UNEP International Resource Panel. CC BY-NC 3.0 Australia. Non-commercial MARIO research indicators: six native value-added rows summed; native GHG CO2eq converted from kilotonnes to tonnes, with direct final-demand emissions included once. Source economic and satellite vintages are recorded for each reading. No endorsement is implied.",
    )
    if gdp_bridge is not None:
        apply_gdp_bridge(snapshot, json.loads(Path(gdp_bridge).read_text()))
        recipe["attribution"] += " GDP adds source-signed product-tax and subsidy valuations on intermediate and final uses."
    recipe["regions"] = list(geography.values())
    profile.update(source_url=recipe["source_url"], license_url=recipe["license_url"], attribution=recipe["attribution"], environmental=True, scope_note=recipe["scope_note"], classifications={"Activity": "ISIC Rev. 4 sections", "Commodity": "Native commodity labels; detailed concordance unverified"})
    stage = Path(stage)
    folder = stage / recipe["id"]
    write(folder / "profile.json", profile)
    write(stage / "snapshot.json", snapshot)
    write(stage / "run-report.json", {"results": [{"id": recipe["id"], "status": "parsed"}]})
    rows = json.loads((HERE / "isic-sections.json").read_text())
    codes, labels = rows[0][1:], rows[1][1:]
    lookup = {row[0]: row[1:] for row in rows[2:] if row[0] is not None}
    entries = []
    sections = dict(zip(codes, labels))
    for i, label in enumerate(recipe["sectors"]):
        weights = lookup[label]
        assert sum(weights) >= 1 and set(weights).issubset({0, 1})
        # Other services spans S and T. Retain one combined category, rather
        # than duplicating its value or inventing an allocation between them.
        linked = [code for code, weight in zip(codes, weights) if weight]
        section = "+".join(linked)
        sections[section] = " / ".join(sections[code] for code in linked)
        entries.append({"index": i, "native_code": str(i + 1), "native_label": label, "section": section})
    write(stage / "mapping.json", {"family": "GLORIA", "dimension": "Activity", "classification": "ISIC Rev. 4", "classification_id": "isic-4", "sections": sections, "entries": entries, "source_url": recipe["source_url"], "classification_url": "https://docs.google.com/spreadsheets/d/1E0zuQFqokX_kYmU7HbhLvaYOp-wefIZp/edit", "basis": "GLORIA_ReadMe_060.xlsx, GLORIA to ISIC concordance. Exact native labels and binary assignments; each activity enters once. Other services remains combined S+T, without invented allocation weights."})
    return snapshot


def publish(stage, doc=DOC):
    stage, doc = Path(stage), Path(doc)
    snapshot = json.loads((stage / "snapshot.json").read_text())
    recipe = snapshot["recipe"]
    output = doc / "source/_static/data/economy"
    publish_indicators(recipe, snapshot["regions"], snapshot["provenance"], output)
    catalogue = publish_sets(stage, doc=doc)
    full = json.loads((stage / recipe["id"] / "profile.json").read_text())
    public = next(p for p in catalogue["profiles"] if p["id"] == recipe["id"])
    for key in ("environmental", "source_url", "license_url", "attribution", "scope_note"):
        public[key] = full[key]
    write(doc / "source/_static/data/database_profiles.json", catalogue)
    mappings = json.loads((output / "sector-sections.json").read_text())
    mappings["mappings"][recipe["id"]] = json.loads((stage / "mapping.json").read_text())
    write(output / "sector-sections.json", mappings)
    path = doc / "economy_browser.recipes.json"
    recipes = json.loads(path.read_text())
    recipes["recipes"] = [r for r in recipes["recipes"] if r["id"] != recipe["id"]] + [recipe]
    write(path, recipes)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    local = DOC.parent / "Output/database-browser-local"
    cli.add_argument("--snapshot", type=Path, default=local / "gloria-060-2024-sut.json")
    cli.add_argument("--profile", type=Path, default=local / "gloria-060-2024-sut.sets.json")
    cli.add_argument("--stage", type=Path, default=DOC.parent / "Output/gloria-browser")
    cli.add_argument("--gdp-bridge", type=Path, default=None)
    cli.add_argument("--publish", action="store_true")
    args = cli.parse_args()
    if args.publish:
        publish(args.stage)
    else:
        year = json.loads(args.snapshot.read_text())["recipe"]["year"]
        bridge = args.gdp_bridge or HERE / ("gdp-bridge.json" if year == 2024 else f"gdp-bridge-{year}.json")
        prepare(args.snapshot, args.profile, args.stage, bridge if bridge.is_file() else None)
    print("GLORIA v060: 164 regions, 120 activities; value added and GHG; GDP uses the reviewed source bridge when supplied.")
