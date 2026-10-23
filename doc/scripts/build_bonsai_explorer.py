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
BONSAI_CF = {
    "Carbon dioxide, fossil | Air": 1,
    "Methane, fossil | Air": 29.8,
    "Methane, non-fossil | Air": 27,
    "Dinitrogen monoxide | Air": 273,
    "Accelerated CO2, Air | Air": 0.00772,
}
# The explorer follows EDGAR's AR5 convention (28 for both methane origins).
# Accelerated CO2 has no verified AR5 factor: omit it explicitly, never reuse
# its BONSAI AR6 factor or imply that an omitted flow has zero climate impact.
CF = {
    "Carbon dioxide, fossil | Air": 1,
    "Methane, fossil | Air": 28,
    "Methane, non-fossil | Air": 28,
    "Dinitrogen monoxide | Air": 265,
}
AR5_BASIS = "IPCC AR5 GWP100 (EDGAR CH4=28); CO2, CH4 and N2O subtotal"
AR5_COVERAGE = (
    "Includes the supplied iLUC contributions to these gases. Accelerated CO2 "
    "is excluded because no AR5 factor has been verified; F-gases are not "
    "characterised. This is not the official BONSAI AR6 indicator."
)
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


def characterise(frame, factors):
    """Recharacterise physical gas rows, including cached gas multipliers."""
    selected = frame.loc[list(factors)].astype(float)
    if not np.isfinite(selected.to_numpy()).all():
        raise ValueError("Non-finite native gas values")
    return selected.mul(pd.Series(factors), axis=0).sum(axis=0)


def main(audit, classification, *, indicators_only=False):
    report = json.loads((audit / "report.json").read_text())
    assert (
        report["source_matrix_preserved_exactly"] and not report["partial_solve_used"]
    )
    assert report["indicators"]["GWP100"]["allclose_rtol_1e-7_atol_1e-10"]
    current_inputs = {}
    for name, entry in report["inputs"].items():
        actual_hash = digest(audit / "inputs" / name)
        # AR5 uses no LCIA workbook. Still verify its five official GWP100
        # factors below and disclose any byte change independently of the
        # unchanged T/E/Y inputs on which the cached solve depends.
        if name != "GWPs/LCIA.xlsx":
            assert actual_hash == entry["sha256"], f"Changed frozen input: {name}"
        current_inputs[name] = {**entry, "sha256": actual_hash}
    lcia_provenance = {
        "used_for_ar5": False,
        "audit_sha256": report["inputs"]["GWPs/LCIA.xlsx"]["sha256"],
        "current_sha256": current_inputs["GWPs/LCIA.xlsx"]["sha256"],
        "official_gwp100_factors_unchanged": True,
    }
    workbook = pd.read_excel(audit / "inputs/GWPs/LCIA.xlsx").dropna(subset=["GWP100"])
    actual_cf = workbook.set_index("Exio substance")["GWP100"].to_dict()
    assert actual_cf == {
        "Carbon dioxide, fossil": 1,
        "Methane, fossil": 29.8,
        "Methane, biogenic": 27,
        "Dinitrogen monoxide": 273,
        "Accelerated CO2, Air": 0.00772,
    }
    db = mario.parse_bonsai(audit / "inputs", table="IOT")
    assert db.meta.year == 2016
    if indicators_only:
        profile = json.loads((DATA / "database_profiles" / f"{ID}.json").read_text())
        assert profile["input_files"] == report["inputs"]
        count = profile["scope_counts"]["Sector"]["count"]
        counts = [r["count"] for r in profile["region_counts"] if r["set"] == "Sector"]
        note, updated = profile["scope_note"], profile["inputs_updated_at"]
    else:
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

    f = pd.read_pickle(audit / "mario_selected_f.pkl")
    assert f.columns.equals(db.E.columns)
    np.testing.assert_allclose(
        characterise(f, BONSAI_CF),
        f.loc[LABEL],
        rtol=1e-12,
        atol=1e-10,
    )
    # Characterisation is linear. Reuse the verified gas multipliers, avoiding
    # another solve and retaining the original official-AR6 audit unchanged.
    lifecycle = characterise(f, CF)
    direct = characterise(db.E, CF).div(db.X.iloc[:, 0])
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
            for flow, series in [("lifecycle", lifecycle), ("direct", direct)]:
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
        "characterisation": AR5_BASIS,
        "characterisation_factors": CF,
        "characterisation_note": AR5_COVERAGE,
        "excluded_climate_flows": ["Accelerated CO2, Air | Air"],
        "native_unit": "tonnes CO2eq/TJ",
        "unit": "g CO2eq/kWh",
        "unit_conversion_factor": 3.6,
        "input_files": current_inputs,
        "lcia_workbook": lcia_provenance,
        "mario_commit": report["mario_commit"],
        "cached_f_sha256": digest(audit / "mario_selected_f.pkl"),
        "official_ar6_equivalence_check": report["indicators"]["GWP100"],
        "recharacterisation": "AR5 linear combination of verified native gas multipliers; official AR6 audit retained separately",
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
        "parser_guide": "user_guide/parsers/bonsai.html",
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
        "ghg_method": "Native CO2, CH4 and N2O recharacterised with EDGAR-compatible AR5 GWP100 and aggregated by producer region",
        "ghg_basis": "Producer emissions only; " + AR5_BASIS,
        "ghg_note": "BONSAI: producer accounts only; separate direct final-demand emissions are unavailable. " + AR5_COVERAGE + " Production and EDGAR territorial boundaries differ, including land-use coverage. Native Global is a global process block, not a World total; all native regions enter World once. GDP and value added are unavailable.",
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
        {"input_files": current_inputs, "inputs_updated_at": updated,
         "lcia_workbook": lcia_provenance},
        DATA / "economy",
    )
    if not indicators_only:
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
        # One classification compiler owns heatmaps and country lookup. The
        # snapshot validates the full observed HIOT vocabulary, including markets;
        # the Global block alone cannot represent its regional classifications.
        from build_sectoral_scope import build, enrich_country_scope, gtap_power

        sectoral = build(DOC / "classifications/sectoral", scope)
        visible = {**sectoral, "columns": {
            kind: [c for c in columns if not gtap_power(c)]
            for kind, columns in sectoral["columns"].items()
        }}
        compact(DATA / "economy/sectoral-scope.json", visible)
        compact(DATA / "economy/country-scope.json", enrich_country_scope(scope, sectoral))
        for filename in ["bonsai-current-reviews.json", "bonsai-native-correspondences.json"]:
            compact(DATA / "economy" / filename,
                    json.loads((DOC / "classifications/sectoral" / filename).read_text()))
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
    parser.add_argument("--indicators-only", action="store_true",
                        help="Reuse the published native profile; refresh indicators without rewriting classification workbooks")
    args = parser.parse_args()
    main(args.audit, args.classification, indicators_only=args.indicators_only)
