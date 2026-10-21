"""Publish BONSAI explorer assets from a local, verified frozen HIOT audit.

python doc/scripts/build_bonsai_explorer.py /path/to/bonsai_equivalence_20261021 \
    --classification /path/to/Balanced/20260615/classification.csv

Requires the audit's cached mario_selected_f.pkl. No inverse or network access
is required. Source matrices and local paths are never published.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

DOC = Path(__file__).resolve().parents[1]
DATA = DOC / "source/_static/data"
sys.path.insert(0, str(DOC.parent))
import mario
from database_catalogue import prepare, extract_profile, export_workbook, write_json
from build_economy_browser import publish
from economy_browser import aggregate

ID = "bonsai-b2-2016-hiot-20261021"
LABEL = "GHG BONSAI GWP100"
CF = {
    "Carbon dioxide, fossil | Air": 1,
    "Methane, fossil | Air": 29.8,
    "Methane, non-fossil | Air": 27,
    "Dinitrogen monoxide | Air": 273,
    "Accelerated CO2, Air | Air": 0.00772,
}
TECH = {
    "POWB": "Biomass and waste",
    "POWC": "Coal",
    "POWG": "Natural Gas",
    "POWH": "Hydro",
    "POWM": "Geothermal",
    "POWN": "Nuclear",
    "POWO": "Tide and wave",
    "POWP": "Oil",
    "POWS": "Solar",
    "POWW": "Wind",
}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def compact(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        + "\n"
    )


def main(audit, classification):
    report = json.loads((audit / "report.json").read_text())
    assert (
        report["source_matrix_preserved_exactly"] and not report["partial_solve_used"]
    )
    assert report["indicators"]["GWP100"]["allclose_rtol_1e-7_atol_1e-10"]
    for name, entry in report["inputs"].items():
        assert (
            digest(audit / "inputs" / name) == entry["sha256"]
        ), f"Changed frozen input: {name}"
    workbook = pd.read_excel(audit / "inputs/GWPs/LCIA.xlsx").dropna(subset=["GWP100"])
    actual_cf = workbook.set_index("Exio substance")["GWP100"].to_dict()
    assert actual_cf == {
        "Carbon dioxide, fossil": 1,
        "Methane, fossil": 29.8,
        "Methane, biogenic": 27,
        "Dinitrogen monoxide": 273,
        "Accelerated CO2, Air": 0.00772,
    }
    manifest = prepare()

    def native_iot(r):
        if r["guide"] != "bonsai":
            return False
        notebook = json.loads((DOC / r["notebook"]).read_text())
        tree = ast.parse("".join(notebook["cells"][r["cell"]]["source"]))
        return any(
            isinstance(n, ast.Call)
            and any(
                k.arg == "table"
                and isinstance(k.value, ast.Constant)
                and k.value.value == "IOT"
                for k in n.keywords
            )
            for n in ast.walk(tree)
        )

    recipe = next(r for r in manifest["recipes"] if native_iot(r))
    db = mario.parse_bonsai(audit / "inputs", table="IOT")
    assert db.meta.year == 2016
    profile = extract_profile(
        db,
        job={
            "id": ID,
            "label": "BONSAI · native b2 HIOT · inputs 21 Oct 2026",
            "source": "BONSAI",
            "release": "b2 · 2026-10-21",
            "year": 2016,
        },
        recipe=recipe,
        parameters={"table": "IOT", "unit": "Hybrid"},
    )
    counts = [r["count"] for r in profile["region_counts"] if r["set"] == "Sector"]
    count = next(
        r["count"]
        for r in profile["region_counts"]
        if r["set"] == "Sector" and r["region"] == "Global"
    )
    note = f"Point shows the native Global block ({count} sectors). Classification size varies by region ({min(counts):,}–{max(counts):,}); native memberships are retained."
    updated = datetime.fromtimestamp(
        max(v["source_mtime_ns"] for v in report["inputs"].values()) / 1e9,
        ZoneInfo("Europe/Rome"),
    ).isoformat()
    profile.update(
        scope_counts={"Sector": {"count": count, "region": "Global", "note": note}},
        inputs_updated_at=updated,
        source_url="https://bonsai.uno/",
        attribution="BONSAI; parsed with MARIO",
        scope_note=note,
        environmental=True,
    )
    profile["set_flags"]["Factor of production"] = {
        "placeholder_labels": profile["sets"]["Factor of production"],
        "status": "not_provided",
    }
    profile["counts"]["Factor of production"] = 0
    profile["geography"]["scope"] = "global"
    profile["input_files"] = report["inputs"]
    root = DATA / "database_profiles"
    compact(root / f"{ID}.json", profile)
    export_workbook(profile, root / f"{ID}.xlsx")
    profile["workbook"] = f"_static/data/database_profiles/{ID}.xlsx"
    profile["detail"] = f"_static/data/database_profiles/{ID}.json"
    summary = {
        k: v
        for k, v in profile.items()
        if k not in {"sets", "axes", "units", "region_items"}
    }
    cat = json.loads((DATA / "database_profiles.json").read_text())
    cat["profiles"] = [p for p in cat["profiles"] if p["id"] != ID] + [summary]
    cat["profiles"].sort(key=lambda p: (p["guide"], p["label"]))
    compact(DATA / "database_profiles.json", cat)

    db.calc_ghg(gwp=CF, label=LABEL)
    f = pd.read_pickle(audit / "mario_selected_f.pkl")
    assert f.columns.equals(db.E.columns)
    np.testing.assert_allclose(
        f.loc[list(CF)].mul(pd.Series(CF), axis=0).sum(),
        f.loc[LABEL],
        rtol=1e-12,
        atol=1e-10,
    )
    direct = db.E.loc[LABEL].astype(float).div(db.X.iloc[:, 0])
    production = pd.DataFrame(db.info["bonsai"]["reference_products"])
    with classification.open() as stream:
        descriptions = {r["name"]: r["description"] for r in csv.DictReader(stream)}
    countries = {
        r["label"] for r in profile["geography"]["regions"] if r["kind"] == "country"
    }
    benchmark = json.loads(
        (DATA / "benchmarks/electricity-technology.json").read_text()
    )
    records, mapping = [], []
    for code, technology in TECH.items():
        product, activity = "C_elec_" + code, "A_" + code
        description = descriptions[activity]
        # Keep a reviewed, explicit mapping: e.g. POWP=petroleum and POWO=ocean.
        mapping.append(
            {
                "product": product,
                "activity": activity,
                "description": description,
                "technology": technology,
            }
        )
        for row in production[production["product"].eq(product)].to_dict("records"):
            assert row["activity"] == activity and row["unit"] == "TJ"
            if row["location"] not in countries:
                continue
            key = (row["location"], "Sector", product)
            for flow, series in [("lifecycle", f.loc[LABEL]), ("direct", direct)]:
                value = float(series.loc[key]) * 3.6
                assert np.isfinite(value)
                records.append(
                    {
                        "flow": flow,
                        "tech": technology,
                        "source": "BONSAI",
                        "value": value,
                        "clean": technology in benchmark["clean"],
                        "approx": False,
                        "region": row["location"],
                        "year": 2016,
                        "product": product,
                        "activity": activity,
                    }
                )
    metadata = {
        "label": "BONSAI",
        "model": "Native b2 HIOT",
        "reference_year": 2016,
        "inputs_updated_at": updated,
        "input_directory_label": "20260615",
        "characterisation": "BONSAI GWP100; AR6 factors plus Accelerated CO2",
        "characterisation_factors": CF,
        "native_unit": "tonnes CO2eq/TJ",
        "unit": "g CO2eq/kWh",
        "unit_conversion_factor": 3.6,
        "input_files": report["inputs"],
        "mario_commit": report["mario_commit"],
        "cached_f_sha256": digest(audit / "mario_selected_f.pkl"),
        "equivalence_check": report["indicators"]["GWP100"],
        "classification_sha256": digest(classification),
        "technology_mapping": mapping,
        "sample": "Available individual-country generation nodes; RoW and Global excluded. No absent country/technology node is filled.",
        "attribution": "BONSAI native b2 HIOT; calculated with MARIO",
    }
    write_json(
        DATA / "benchmarks/bonsai-electricity-technology-2016.json",
        {"source": metadata, "records": records},
    )

    native_regions = profile["geography"]["regions"]
    economic = {
        "id": ID,
        "label": "BONSAI b2 HIOT · inputs 21 Oct 2026",
        "source": "BONSAI",
        "release": profile["release"],
        "year": 2016,
        "table": "IOT",
        "dimension": "Native HIOT",
        "native_units": "Hybrid",
        "currency": None,
        "parser": "parse_bonsai",
        "parser_options": {"table": "IOT"},
        "parser_guide": "notebooks/parsers/bonsai/walkthrough_bonsai.html",
        "mario_revision": report["mario_commit"],
        "regions": native_regions,
        "sectors": ["All native production activities"],
        "value_added_available": False,
        "value_added_rows": [],
        "gdp_bridge_verified": False,
        "gdp_basis": "Unavailable: no GDP accounts",
        "value_added_basis": "Unavailable: no value-added accounts",
        "ghg_factors": CF,
        "expected_units": {"Satellite account": {name: "tonnes" for name in CF}},
        "ghg_usable": True,
        "final_demand_emissions_loaded": False,
        "world_total_available": True,
        "gwp_basis": metadata["characterisation"],
        "gwp_horizon": 100,
        "ghg_method": "Characterised native E, aggregated by producer region; BONSAI GWP100 with supplied iLUC",
        "ghg_basis": "Producer emissions only; BONSAI GWP100 including supplied iLUC and Accelerated CO2",
        "ghg_note": "BONSAI: producer accounts only; separate direct final-demand emissions are unavailable. Uses AR6 GWP100 factors with Accelerated CO2 0.00772. No common GWP basis with the AR5 reference is claimed. Native Global is a global process block, not a World total; all native regions enter World once. GDP and value added are unavailable.",
        "scope_note": "Reference year 2016; inputs updated 21 Oct 2026. " + note,
        "source_url": "https://bonsai.uno/",
        "license_url": "https://bonsai.uno/",
        "attribution": metadata["attribution"],
    }
    regions = aggregate(db, economic)
    assert len(regions) == profile["counts"]["Region"] and all(
        r["gdp"] is None and r["value_added"] is None for r in regions
    )
    publish(
        economic,
        regions,
        {"input_files": report["inputs"], "inputs_updated_at": updated},
        DATA / "economy",
    )
    # Country lookup preserves the actual heterogeneous native memberships.
    scope = json.loads((DATA / "economy/country-scope.json").read_text())
    memberships = {}
    for item in profile["region_items"]:
        if item["set"] == "Sector":
            memberships.setdefault(item["region"], {}).setdefault("Sector", []).append(
                item["label"]
            )
    entry = {
        "id": ID,
        "family": "BONSAI",
        "release": profile["release"],
        "units": "Hybrid",
        "format": "IOT",
        "system": "Native HIOT",
        "price_basis": "",
        "years": [2016],
        "counts": profile["counts"],
        "scope_counts": profile["scope_counts"],
        "region_counts": profile["region_counts"],
        "regions": native_regions,
        "memberships": memberships,
        "sets": {k: v for k, v in profile["sets"].items() if k != "Region"},
        "set_flags": profile["set_flags"],
        "reading_ids": [ID],
        "reading_years": {ID: 2016},
        "indicator_flags": {ID: {"gdp_proxy": False, "ghg_proxy": False}},
        "availability": {ID: {"gdp": False, "value_added": False, "ghg": True}},
        "status": "parsed",
        "parser_supported": True,
        "native_codes": {},
        "source_url": economic["source_url"],
        "scope_note": economic["scope_note"],
        "license_url": economic["license_url"],
        "attribution": economic["attribution"],
        "workbook": profile["workbook"],
        "guide": economic["parser_guide"],
        "mapping": None,
        "mapping_ids": [],
        "signature": profile["coverage_signatures"],
        "environmental": True,
    }
    scope["profiles"] = [p for p in scope["profiles"] if p["id"] != ID] + [entry]
    compact(DATA / "economy/country-scope.json", scope)
    # Both native axes are available; fine concordances require a separate review.
    sectoral = json.loads((DATA / "economy/sectoral-scope.json").read_text())
    for kind, field in [("activity", "activity"), ("commodity", "product")]:
        native = sorted(set(production.loc[production.location.eq("Global"), field]))
        column = {
            "id": "bonsai-hybrid-" + kind,
            "family": "BONSAI",
            "label": "BONSAI · Global",
            "units": "Hybrid",
            "kind": kind,
            "native_count": len(native),
            "namespace": "BONSAI-b2",
            "native": [
                {"code": n, "name": descriptions.get(n, n), "links": {}} for n in native
            ],
            "profile_ids": [ID],
            "source_url": economic["source_url"],
            "status": "unverified",
            "scope_note": note,
        }
        sectoral["columns"][kind] = [
            c for c in sectoral["columns"][kind] if c["family"] != "BONSAI"
        ] + [column]
    compact(DATA / "economy/sectoral-scope.json", sectoral)
    print(
        json.dumps(
            {
                "counts": profile["counts"],
                "scope_count": count,
                "regional_range": [min(counts), max(counts)],
                "technology_observations": len(records),
                "satellites": profile["sets"]["Satellite account"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit", type=Path)
    parser.add_argument("--classification", type=Path, required=True)
    args = parser.parse_args()
    main(args.audit, args.classification)
