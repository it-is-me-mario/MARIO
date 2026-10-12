"""Prepare notebook-derived parsing recipes and catalogue original MARIO sets.

Preparing recipes never imports MARIO, reads a database, or makes a request.
Parsing is opt-in, uses a local job file, and keeps results private until publish.
"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import gc
import hashlib
import inspect
import json
import math
from pathlib import Path
import re
import shutil
import sys
import traceback

DOC = Path(__file__).resolve().parents[1]
RECIPES = DOC / "database_catalogue.recipes.json"
CATALOGUE = DOC / "source/_static/data/database_profiles.json"
PATH_OPTIONS = {"path", "co2_path", "labels_path", "add_extensions", "indeces"}
FLOW_BLOCKS = {"Z", "U", "S", "Y", "Ya", "Yc", "V", "Va", "Vc", "E", "Ea", "Ec", "EY", "VY"}
NATIVE_BLOCKS = FLOW_BLOCKS | {name.lower() for name in FLOW_BLOCKS}
SET_SHEETS = {
    "Region": "Regions", "Sector": "Sectors", "Activity": "Activities",
    "Commodity": "Commodities", "Satellite account": "Satellite accounts",
    "Factor of production": "Factors of production",
    "Consumption category": "Consumption categories",
}
SOURCE_NAMES = {
    "adb": "Asian Development Bank", "bea": "BEA", "ceads": "CEADS",
    "cepalstat": "CEPALSTAT", "emerging": "EMERGING", "eora": "EORA",
    "eurostat": "EUROSTAT", "figaro": "FIGARO", "gloria": "GLORIA",
    "gtap": "GTAP", "istat": "ISTAT", "oecd": "OECD", "statcan": "StatCan",
    "useeio": "USEEIO", "wiod": "WIOD", "exiobase": "EXIOBASE",
    "custom_database": "Custom database",
}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def notebook_calls(path):
    """Read literal MARIO parser calls; never execute notebook source code."""
    notebook = json.loads(Path(path).read_text(encoding="utf-8"))
    result = []
    for cell_number, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell.get("source", []))
        if "mario.parse_" not in source:
            continue
        tree = ast.parse(source)
        calls = sorted((node for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "mario"
                        and node.func.attr.startswith("parse_")), key=lambda node: (node.lineno, node.col_offset))
        for node in calls:
            recipe = {"parser": node.func.attr, "cell": cell_number,
                      "fingerprint": hashlib.sha256(ast.dump(node).encode()).hexdigest()}
            try:
                if node.args or any(kw.arg is None for kw in node.keywords):
                    raise ValueError("Use explicit keyword arguments")
                recipe["parameters"] = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
                recipe["runnable"] = True
            except (ValueError, TypeError):
                recipe["parameters"] = {}
                recipe["runnable"] = False
                recipe["reason"] = "This example needs in-memory Python objects, not only file paths."
            result.append(recipe)
    return result


def prepare(doc=DOC):
    """Refresh the recipe manifest and guide registry, retaining parsed profiles."""
    doc = Path(doc)
    guides, recipes = [], []
    for path in sorted((doc / "source/notebooks/parsers").glob("*/*.ipynb")):
        family = path.parent.name
        key = family if family not in {"exiobase", "custom_database"} else f"{family}-{path.stem}".replace("_", "-")
        label = SOURCE_NAMES[family]
        if family == "exiobase":
            label += ", " + path.stem
        elif family == "custom_database":
            label = {"from_excel": "Excel custom parser", "from_txt": "TXT, CSV and Parquet custom parser",
                     "from_pymrio": "Pymrio bridge"}[path.stem]
        guide = {"id": key, "source": SOURCE_NAMES[family], "label": label,
                 "doc": path.relative_to(doc / "source").with_suffix("").as_posix()}
        guides.append(guide)
        for number, call in enumerate(notebook_calls(path), 1):
            recipes.append({"id": f"{key}--{number:02}", "guide": key,
                            "notebook": path.relative_to(doc).as_posix(), **call})
    manifest = {"schema_version": 1, "guides": guides, "recipes": recipes}
    write_json(doc / "database_catalogue.recipes.json", manifest)
    catalogue_path = doc / "source/_static/data/database_profiles.json"
    previous = json.loads(catalogue_path.read_text()) if catalogue_path.exists() else {}
    write_json(catalogue_path, {"schema_version": 1, "guides": guides, "profiles": previous.get("profiles", [])})
    return manifest


def public_parameters(parameters):
    """Keep parsing options, but never publish local paths or credential values."""
    output = {}
    for key, value in parameters.items():
        if any(word in key.lower() for word in ("password", "token", "api_key")):
            continue
        if key in PATH_OPTIONS and isinstance(value, str):
            output[key] = "local input supplied"
        else:
            output[key] = value
    return output


def axis_records(axis):
    names = [None if name is None else str(name) for name in axis.names]
    records = [list(value) if isinstance(value, tuple) else [value] for value in axis.tolist()]
    return names, records


def scalar(value):
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def enrich_profile(profile):
    """Record exact coverage identity and distinguish MARIO's empty placeholders."""
    sets = profile["sets"]
    flags = {}
    for name in ("Satellite account", "Factor of production"):
        units = [u for u in profile["units"] if u["set"] == name]
        if sets.get(name) == ["-"] and units and all(u["values"].get("unit") in {None, "None", "-", ""} for u in units):
            flags[name] = {"placeholder_labels": ["-"], "status": "not_loaded"}
    profile["set_flags"] = flags
    profile["counts"] = {name: len(set(labels) - set(flags.get(name, {}).get("placeholder_labels", [])))
                         for name, labels in sets.items()}

    def digest(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    economic = {name: sorted(set(sets[name]), key=str) for name in ("Sector", "Activity", "Commodity") if name in sets}
    memberships = sorted((i["set"], i["region"], i["label"]) for i in profile["region_items"]
                         if i["set"] in economic)
    profile["coverage_signatures"] = {
        "geography": digest(sorted(set(sets["Region"]), key=str)),
        "economic": digest({"table": profile["table"], "sets": economic, "region_items": memberships}),
    }
    from database_geography import add_geography
    add_geography(profile)
    return profile


def extract_profile(database, *, job, recipe, parameters):
    """Read original sets and stored axes without calculating/copying matrices."""
    sets = {name: [scalar(item) for item in (items if items is not None else [])]
            for name, items in database.get_index("all").items()}
    if not sets.get("Region"):
        raise ValueError("The parsed database has no model region set")
    axes, memberships = [], {}
    for matrix in database.list_matrices():
        if matrix not in NATIVE_BLOCKS:
            continue
        block = database.get_block(matrix)
        for side in ("index", "columns"):
            axis = getattr(block, side)
            names, records = axis_records(axis)
            records = [[scalar(item) for item in row] for row in records]
            axes.append({"matrix": matrix, "side": side, "names": names, "records": records})
            for row in records:
                context = dict(zip(names, row))
                region = context.get("Region")
                if region is None:
                    continue
                # Both semantic axes (Region/Sector) and legacy (Region/Level/Item).
                for name in ("Sector", "Activity", "Commodity", "Consumption category"):
                    label = context.get(name)
                    if label is None and context.get("Level") == name:
                        label = context.get("Item")
                    if label is not None:
                        memberships[(name, region, label)] = {"set": name, "region": region, "label": label}
    units = []
    for name, frame in database.units.items():
        names, labels = axis_records(frame.index)
        for label, values in zip(labels, frame.itertuples(index=False, name=None)):
            units.append({"set": name, "index_names": names, "index": [scalar(item) for item in label],
                          "values": {str(column): scalar(value) for column, value in zip(frame.columns, values)}})
    regional_labels = {}
    for item in memberships.values():
        regional_labels.setdefault((item["region"], item["set"]), set()).add(item["label"])
    region_counts = [{"region": region, "set": name, "count": len(labels)}
                     for (region, name), labels in regional_labels.items()]
    return enrich_profile({"schema_version": 1, "id": job["id"], "guide": recipe["guide"],
            "label": job["label"], "source": job.get("source", ""),
            "release": job.get("release", ""), "year": job.get("year", parameters.get("year")),
            "table": database.table_type, "status": "parsed", "scenario": "baseline",
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "provenance": {"notebook": recipe["notebook"], "cell": recipe["cell"],
                           "recipe": recipe["id"], "fingerprint": recipe["fingerprint"],
                           "parser": recipe["parser"], "options": public_parameters(parameters)},
            "counts": {name: len(set(items)) for name, items in sets.items()}, "sets": sets,
            "region_items": list(memberships.values()), "region_counts": region_counts,
            "axes": axes, "units": units,
            "geography": {"status": "native_labels", "country_memberships": []},
            "classifications": {"status": "native_labels", "mappings": []}})


def export_workbook(profile, path):
    """Write set-only Excel sheets; never export any matrix values."""
    import xlsxwriter

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with xlsxwriter.Workbook(path, {"strings_to_formulas": False, "strings_to_urls": False}) as workbook:
        _fill_workbook(profile, workbook)


def _fill_workbook(profile, workbook):
    header = workbook.add_format({"bold": True, "bg_color": "#FFF1BD", "font_color": "#211B13", "text_wrap": True})
    text = workbook.add_format({"valign": "top", "text_wrap": True})
    integer = workbook.add_format({"num_format": "#,##0"})

    def sheet(name, columns, records):
        ws = workbook.add_worksheet(name)
        ws.freeze_panes(1, 0)
        ws.write_row(0, 0, columns, header)
        for index, row in enumerate(records, 1):
            if index >= 1048576:
                raise ValueError(f"{name} exceeds Excel's row limit")
            for column, value in enumerate(row):
                fmt = integer if isinstance(value, int) and not isinstance(value, bool) else text
                if isinstance(value, str) and len(value) > 32767:
                    raise ValueError(f"{name} contains a label/coordinate longer than Excel's cell limit")
                ws.write(index, column, value, fmt)
        ws.autofilter(0, 0, max(0, len(records)), len(columns) - 1)
        ws.set_column(0, len(columns) - 1, 28)
        return ws

    provenance = profile["provenance"]
    summary = [["Database", profile["label"]], ["Source", profile["source"]], ["Release", profile["release"]], ["Reference year", profile["year"]],
               ["Table format", profile["table"]], ["Parsed at (UTC)", profile["parsed_at"]],
               ["Counts", "Distinct native labels, excluding flagged empty placeholders; not region × item combinations."],
               ["Geography", "Native model regions; ISO country and aggregate membership mapping is separate."],
               ["Extension coverage", "Only the extensions loaded by the recorded parsing options are included."]]
    geography = profile.get("geography", {})
    summary += [["Country mapping method", geography.get("method", "Not yet mapped")]]
    summary += [[f"Country mapping source {i}", json.dumps(source, ensure_ascii=False)]
                for i, source in enumerate(geography.get("region_mapping_sources", []), 1)]
    summary += [[name, count] for name, count in profile["counts"].items()]
    summary += [[f"Placeholder: {name}", "No rows loaded; MARIO's '-' placeholder is preserved in the original set sheet."]
                for name in profile.get("set_flags", {})]
    summary += [["Notebook", provenance["notebook"]], ["Cell (zero-based)", provenance["cell"]],
                ["Recipe fingerprint", provenance["fingerprint"]], ["Parser", provenance["parser"]],
                ["MARIO version", provenance.get("mario_version", "unknown")]]
    summary += [[f"Option: {key}", json.dumps(value, ensure_ascii=False)] for key, value in provenance["options"].items()]
    sheet("Profile", ["Field", "Value"], summary).set_column(1, 1, 85)
    for name, labels in profile["sets"].items():
        placeholders = profile.get("set_flags", {}).get(name, {}).get("placeholder_labels", [])
        sheet(SET_SHEETS.get(name, name[:31]), ["Position", "Original label", "Label kind"],
              [[i, label, "Empty placeholder" if label in placeholders else "Native label"] for i, label in enumerate(labels, 1)])
    if profile.get("geography", {}).get("regions"):
        sheet("Country mapping", ["Original region", "Name", "Representation", "ISO3", "Aggregate membership"],
              [[r["label"], r["name"], r["kind"], code, r.get("membership_status", "")]
               for r in profile["geography"]["regions"] for code in (r.get("members") or [r.get("iso3")])])
    sheet("Region items", ["Set", "Region", "Original label"], [[r["set"], r["region"], r["label"]] for r in profile["region_items"]])
    sheet("Regional counts", ["Region", "Set", "Native labels"], [[r["region"], r["set"], r["count"]] for r in profile["region_counts"]])
    axis_rows = [[a["matrix"], a["side"], i, json.dumps(a["names"], ensure_ascii=False), json.dumps(row, ensure_ascii=False)]
                 for a in profile["axes"] for i, row in enumerate(a["records"], 1)]
    sheet("Native axes", ["Matrix", "Side", "Position", "Axis names", "Original coordinates"], axis_rows)
    unit_rows = [[u["set"], json.dumps(u["index_names"], ensure_ascii=False), json.dumps(u["index"], ensure_ascii=False), column, value]
                 for u in profile["units"] for column, value in u["values"].items()]
    sheet("Units", ["Set", "Index names", "Original coordinates", "Field", "Value"], unit_rows)


def resolve_job(job, manifest, *, allow_network=False, doc=DOC):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", job["id"]):
        raise ValueError("Profile ids must contain lowercase letters, digits and hyphens")
    if not job.get("label"):
        raise ValueError("Every job needs a label identifying its release/year/variant")
    recipe = next(r for r in manifest["recipes"] if r["id"] == job["recipe"])
    if not recipe["runnable"]:
        raise ValueError(recipe["reason"])
    calls = notebook_calls(Path(doc) / recipe["notebook"])
    current = next((r for r in calls if r["fingerprint"] == recipe["fingerprint"]), None)
    if current is None:
        raise ValueError("The notebook example changed: review it and rerun --prepare")
    recipe = {**recipe, "cell": current["cell"]}
    parameters = {**recipe["parameters"], **job.get("parameters", {}), "calc_all": False}
    if not allow_network:
        parameters["download"] = False
        if not parameters.get("path"):
            raise ValueError("This example uses an API. Supply a local path, or opt in with --allow-network")
    for key, value in parameters.items():
        if isinstance(value, str) and value.startswith("/path/to/"):
            raise ValueError(f"Supply a real local input for {key}")
        if key in PATH_OPTIONS and isinstance(value, str):
            # Existence is checked before any parser can attempt a download.
            local = Path(value).expanduser()
            if not allow_network and not local.exists():
                raise FileNotFoundError(f"Local input missing for {key}")
            parameters[key] = str(local)
    if job.get("expected_table") and parameters.get("table") and job["expected_table"] != parameters["table"]:
        raise ValueError("expected_table conflicts with the parser's table option")
    if job.get("year") is not None and parameters.get("year") is not None and str(job["year"]) != str(parameters["year"]):
        raise ValueError("The profile year conflicts with the parser's year option")
    return recipe, parameters


def run_jobs(config, manifest, output, *, allow_network=False, parser_module=None, doc=DOC):
    """Run sequentially; record failures separately and continue other releases."""
    output = Path(output)
    jobs = config.get("jobs", [])
    if not jobs:
        raise ValueError("Supply at least one release job; no database has been read")
    ids = [job["id"] for job in jobs]
    if len(ids) != len(set(ids)):
        raise ValueError("Job ids must be unique")
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]*", identifier) for identifier in ids):
        raise ValueError("Invalid profile id")
    if parser_module is None:
        sys.path.insert(0, str(Path(doc).parent))
        import mario as parser_module
    report = {"schema_version": 1, "results": []}
    for job in jobs:
        folder = output / job["id"]
        database = profile = None
        try:
            recipe, parameters = resolve_job(job, manifest, allow_network=allow_network, doc=doc)
            function = getattr(parser_module, recipe["parser"])
            signature = inspect.signature(function)
            if "download" not in signature.parameters and "download" not in recipe["parameters"]:
                parameters.pop("download", None)
            signature.bind(**parameters)
            database = function(**parameters)
            if job.get("expected_table") and database.table_type != job["expected_table"]:
                raise ValueError("The parsed table format differs from expected_table")
            profile = extract_profile(database, job=job, recipe=recipe, parameters=parameters)
            profile["provenance"]["mario_version"] = str(getattr(parser_module, "__version__", "unknown"))
            export_workbook(profile, folder / "sets.xlsx")
            write_json(folder / "profile.json", profile)
            report["results"].append({"id": job["id"], "status": "parsed"})
            print(f"{job['id']}: parsed; {profile['counts']}", flush=True)
        except Exception as error:
            report["results"].append({"id": job["id"], "status": "failed", "error": str(error), "traceback": traceback.format_exc()})
            print(f"{job['id']}: failed (see private run-report.json)", flush=True)
        finally:
            database = profile = None
            gc.collect()
        write_json(output / "run-report.json", report)
    return report


def publish(output, *, doc=DOC):
    """Publish only successful profiles from the latest run, replacing matching ids."""
    output, doc = Path(output), Path(doc)
    report = json.loads((output / "run-report.json").read_text())
    catalogue_path = doc / "source/_static/data/database_profiles.json"
    catalogue = json.loads(catalogue_path.read_text())
    attempted = {r["id"] for r in report["results"]}
    if len(attempted) != len(report["results"]) or any(r["status"] not in {"parsed", "failed"} for r in report["results"]):
        raise ValueError("Invalid or duplicate results in run report")
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]*", identifier) for identifier in attempted):
        raise ValueError("Invalid profile id in run report")
    profiles = [p for p in catalogue["profiles"] if p["id"] not in attempted]
    target = doc / "source/_static/data/database_profiles"
    ready = {}
    for result in report["results"]:
        if result["status"] != "parsed":
            continue
        identifier = result["id"]
        folder = output / identifier
        full = json.loads((folder / "profile.json").read_text())
        if full["id"] != identifier or full["status"] != "parsed" or not (folder / "sets.xlsx").is_file():
            raise ValueError(f"Incomplete parsed output for {identifier}; public catalogue unchanged")
        if full["guide"] not in {g["id"] for g in catalogue["guides"]}:
            raise ValueError(f"Unknown guide for {identifier}; public catalogue unchanged")
        fields = ("id", "guide", "label", "source", "release", "year", "table", "status", "parsed_at", "counts", "provenance", "region_counts", "geography", "classifications")
        summary = {key: full[key] for key in fields}
        for key in ("coverage_signatures", "set_flags"):
            if key in full:
                summary[key] = full[key]
        summary["workbook"] = f"_static/data/database_profiles/{identifier}.xlsx"
        summary["detail"] = f"_static/data/database_profiles/{identifier}.json"
        ready[identifier] = summary
    for result in report["results"]:
        identifier = result["id"]
        # A failed refresh must not leave an old successful profile visible.
        for suffix in ("xlsx", "json"):
            stale = target / f"{identifier}.{suffix}"
            if stale.exists():
                stale.unlink()
        if result["status"] != "parsed":
            continue
        folder = output / identifier
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(folder / "sets.xlsx", target / f"{identifier}.xlsx")
        shutil.copyfile(folder / "profile.json", target / f"{identifier}.json")
        profiles.append(ready[identifier])
    catalogue["profiles"] = sorted(profiles, key=lambda p: (p["guide"], p["label"]))
    write_json(catalogue_path, catalogue)
    return catalogue


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true", help="Extract notebook recipes; no parsing")
    mode.add_argument("--plan", action="store_true", help="List recipes or validate supplied jobs without parsing")
    mode.add_argument("--run", action="store_true", help="Parse supplied jobs and export private sets")
    mode.add_argument("--publish", action="store_true", help="Copy successful set profiles/downloads into docs")
    cli.add_argument("--config", type=Path, default=DOC / "database_catalogue.local.json")
    cli.add_argument("--output", type=Path, default=DOC.parent / "Output/database_catalogue")
    cli.add_argument("--allow-network", action="store_true", help="Explicitly allow API/download recipes")
    args = cli.parse_args()
    if args.prepare:
        manifest = prepare()
        print(f"{len(manifest['guides'])} guides, {len(manifest['recipes'])} notebook parser examples; no database read.")
        return 0
    if args.publish:
        print(f"{len(publish(args.output)['profiles'])} parsed profiles in the documentation catalogue.")
        return 0
    manifest = json.loads(RECIPES.read_text())
    if args.plan and not args.config.exists():
        for recipe in manifest["recipes"]:
            state = "local paths needed" if recipe["runnable"] else "in-memory object needed"
            print(f"{recipe['id']}: {recipe['parser']} · {state}")
        return 0
    config = json.loads(args.config.read_text())
    if args.plan:
        for job in config.get("jobs", []):
            recipe, parameters = resolve_job(job, manifest, allow_network=args.allow_network)
            print(f"{job['id']}: inputs ready for {recipe['parser']} (not run)")
        return 0
    report = run_jobs(config, manifest, args.output, allow_network=args.allow_network)
    return int(any(item["status"] == "failed" for item in report["results"]))


if __name__ == "__main__":
    raise SystemExit(main())
