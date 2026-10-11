"""Compute one browser snapshot at a time using the documentation parser recipe.

Requires local, legitimately obtained database inputs. This command never
downloads MRIO files or evicts OneDrive files. Release each local input after
validating its snapshot, before moving to the next database.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

DOC = Path(__file__).resolve().parents[1]
STATIC = DOC / "source/_static"
sys.path.insert(0, str(DOC.parent))
sys.path.insert(0, str(STATIC / "reproduce"))
from economy_browser import annotate_ghg_method, aggregate, final_demand_taxes, load_database


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


def publish(recipe, regions, provenance, output):
    """Publish only aggregated indicators and their explicit recipe."""
    annotate_ghg_method(recipe)
    output = Path(output)
    if recipe["source"] == "EXIOBASE" and recipe.get("tax_bridge") and regions:
        # An absolute EUR threshold would misclassify tiny rounding entries as
        # an economic tax bridge. Require an explicit recipe review and a
        # non-negligible tax share; magnitude alone never grants verification.
        va_total = sum(abs(v) for r in regions for v in r["value_added"])
        tax_total = sum(abs(r["net_product_taxes"]) for r in regions)
        recipe["gdp_bridge_verified"] = bool(recipe.get("gdp_bridge_verified")) and tax_total > va_total * 1e-6
        if recipe["gdp_bridge_verified"] and recipe["tax_bridge"] == "source_activity_taxes":
            pass  # The reviewed recipe states its own basis: the source has no final-use tax row.
        elif recipe["gdp_bridge_verified"]:
            recipe["gdp_basis"] = "GDP reconstructed with the source product-tax bridge"
            recipe["gdp_note"] = "Value added plus source net product taxes on intermediate and final uses. The published tax bridge is retained; source vintages, balancing and accounting boundaries may differ from World Bank national accounts."
        else:
            recipe["gdp_basis"] = "GDP estimate; unverified market-price bridge"
            recipe["gdp_note"] = "This reading has negligible product-tax entries and a zero final-demand tax bridge. The income aggregate is a GDP estimate; market-price equivalence is not independently verified."
    snapshot = {"schema_version": 1, "recipe": recipe, "regions": regions,
                "generated_at": datetime.now(timezone.utc).isoformat(), "provenance": provenance}
    write(output / f"{recipe['id']}.json", snapshot)
    path = output / "manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {"schema_version": 1, "datasets": []}
    manifest["datasets"] = [p for p in manifest["datasets"] if p["id"] != recipe["id"]]
    entry = {k: recipe[k] for k in ("id", "label", "source", "year", "dimension", "currency", "gdp_bridge_verified") if k in recipe}
    if manifest.get("templates") is not None:
        keys = ['source', 'release', 'dimension', 'parser_options', 'sectors', 'ghg_method', 'ghg_basis', 'gdp_basis', 'value_added_basis', 'source_url', 'license_url', 'parser_guide', 'ghg_factors', 'attribution', 'value_added_note', 'gdp_note', 'gdp_identity_status', 'gdp_quality_note', 'table', 'gdp_proxy', 'ghg_proxy', 'ghg_note', 'gwp_basis', 'gwp_horizon', 'final_demand_emissions_loaded', 'ghg_sectors', 'ghg_usable', 'ghg_unavailable_reason', 'ghg_quality_status', 'ghg_quality_sources', 'world_total_available', 'scope_note']
        metadata = {k: recipe[k] for k in keys if k in recipe}
        geography = [{k: r[k] for k in ("code", "name", "iso3", "kind")} for r in regions]
        key = hashlib.sha256(json.dumps([metadata, geography], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
        manifest["templates"][key] = {"recipe": metadata, "regions": geography}
        entry.update(template=key, availability={metric: (metric != "ghg" or recipe.get("ghg_usable") is not False) and all(r.get(metric) is not None for r in regions) for metric in ("gdp", "value_added", "ghg")})
    manifest["datasets"].append(entry)
    manifest["datasets"].sort(key=lambda r: (-r["year"], r["label"]))
    manifest["world_bank_sha256"] = hashlib.sha256((output / "world-bank.json").read_bytes()).hexdigest()
    write(path, manifest)
    return snapshot


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--id", required=True)
    cli.add_argument("--path", required=True, type=Path)
    cli.add_argument("--output", type=Path, default=STATIC / "data/economy")
    cli.add_argument("--extensions-path", type=Path, help="Matching same-year IOT for monetary EXIOBASE SUT")
    args = cli.parse_args()
    recipe = next(r for r in json.loads((DOC / "economy_browser.recipes.json").read_text())["recipes"] if r["id"] == args.id)
    if args.extensions_path:
        recipe["parser_options"]["add_extensions"] = str(args.extensions_path)
    import mario
    database = load_database(recipe, args.path)
    regions = aggregate(database, recipe, final_demand_taxes(args.path, recipe))
    # Never scan a directory recursively: GLORIA and cloud folders may contain
    # many unselected years. Hash a single-file source; directory provenance
    # is limited explicitly to parser parameters, labels and unit checks.
    inputs = [] if args.path.is_dir() else [args.path]
    checksums = {}
    for file in inputs:
        if not file.is_file():
            continue
        digest = hashlib.sha256()
        with file.open("rb") as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(block)
        name = str(file.relative_to(args.path)) if args.path.is_dir() else file.name
        checksums[name] = digest.hexdigest()
    provenance = {"mario_version": mario.__version__, "mario_revision": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=DOC.parent, text=True).strip(), "source_sha256": checksums}
    if recipe.get("parser_options", {}).get("add_extensions"):
        recipe["parser_options"]["add_extensions"] = "/path/to/corresponding-IOT"
    publish(recipe, regions, provenance, args.output)
    print(f"Published {args.id}: {len(regions)} regions, {len(recipe['sectors'])} industries")
