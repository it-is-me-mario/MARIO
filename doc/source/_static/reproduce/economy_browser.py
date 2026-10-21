"""Reproduce a MARIO Economy & emissions browser selection from local inputs.

Install the MARIO revision specified in CONFIG['mario_revision'], then run:
    python reproduce.py --path /path/to/licensed/database

The same indicator aggregation code generates the documentation snapshots.
No MRIO source matrices or coefficients are embedded in this script.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

# The browser replaces this assignment with the selected recipe and filters.
CONFIG = None  # BROWSER_CONFIG


def strict_sum(frame, rows):
    """Reject unknown/duplicated labels and missing values instead of guessing."""
    if not rows or len(rows) != len(set(rows)) or not frame.index.is_unique:
        raise ValueError("Expected non-empty, unique indicator rows")
    selected = frame.loc[rows]
    if not np.isfinite(selected.to_numpy(dtype=float)).all():
        raise ValueError("Indicator inputs contain missing or non-finite values")
    return selected.astype(float).sum(axis=0)


def characterise(frame, factors):
    selected = frame.loc[list(factors)]
    if not selected.index.is_unique or not np.isfinite(selected.to_numpy(dtype=float)).all():
        raise ValueError("Invalid GHG rows")
    # Factors include native mass -> tonnes conversion. Already characterised
    # CO2eq rows are scaled once; no second GWP is applied.
    return selected.mul(pd.Series(factors), axis=0).sum(axis=0)


def annotate_source_quality(recipe):
    """Withhold reviewed defective readings, never impute or rescale the source.

    Independently reread original F/F_Y and verified their CRC/SHA256 against
    the extraction. These are explicit release/year exclusions, not an
    automatic outlier threshold. Keep raw aggregate vectors for audit only.
    """
    if recipe.get("source") != "EXIOBASE" or recipe.get("parser_options", {}).get("unit") == "Hybrid":
        return recipe
    release, year = str(recipe.get("release", "")), recipe.get("year")
    if (release == "3.10.1" and year in (2022, 2023, 2024)) or (release == "3.10.2" and year in (2023, 2024)):
        problems = []
        if release == "3.10.1":
            problems.append("anomalous non-combustion source extensions (corrected in release 3.10.2)")
        if year in (2023, 2024):
            problems.append("all combustion rows and direct final-demand combustion accounts are zero in the source")
        recipe.update(ghg_usable=False, ghg_quality_status="withheld_source_error",
            ghg_unavailable_reason=f"EXIOBASE {release}, {year}: GHG total withheld; " + "; ".join(problems) + ". No replacement year or release is used.",
            ghg_quality_sources=["https://zenodo.org/records/20051562", "https://github.com/EXIOBASE/exiobase-bugs-public/issues/1"])
    return recipe


def annotate_ghg_method(recipe):
    """Retain reviewed source methods; disclose mixed characterisation."""
    annotate_source_quality(recipe)
    if not recipe.get("ghg_factors"): return recipe
    source=recipe.get("source")
    recipe["ghg_method"] = recipe.get("ghg_method", "").replace("direct household emissions reported separately", "direct final-demand emissions calculated separately and included once in Whole economy").replace("Direct final-demand emissions kept separately", "Direct final-demand emissions stored separately and included once in Whole economy")
    if source == "EXIOBASE":
        recipe["gwp_basis"] = "AR5 (EDGAR CH4=28); source HFC/PFC CO2eq retained" if recipe.get("parser_options", {}).get("unit") != "Hybrid" else "AR5 (CO2, CH4, N2O only; mixed CH4 origins)"
        recipe["gwp_horizon"] = 100
        recipe["ghg_note"] = "EXIOBASE: mass-reported gases use EDGAR-compatible AR5 GWP100 (CH4=28). HFC/PFC already in source CO2eq retain their original characterisation; its IPCC basis is not independently verified. Production accounts and EDGAR territorial totals have different boundaries."
        if recipe.get("parser_options", {}).get("unit") == "Hybrid":
            recipe["ghg_note"] = "EXIOBASE Hybrid: this is a three-gas CO2/CH4/N2O subtotal, not a complete GHG inventory. F-gas rows are unavailable; mixed-origin CH4 uses EDGAR-compatible AR5 GWP100 of 28. The source has separate unregistered-waste accounts; their overlap is not independently verified."
        recipe["ghg_basis"] = "Producer accounts plus direct final-demand emissions where supplied; " + recipe["gwp_basis"]
    elif source == "GLORIA":
        recipe.update(gwp_basis='Native CO2eq; IPCC AR5 GWP100 verified for CO2, CH4, N2O, SF6 and NF3; other F-gases unverified',gwp_horizon=100,ghg_note='GLORIA retains its native EDGAR-consistent CO2eq total. Independent checks of the 2001 and 2024 gas rows recover AR5 GWP100 factors for CO2, CH4, N2O, SF6 and NF3. Individual factors for all fluorinated gases remain unverified; the 2024 cell-level gas-row fit has a relative L2 residual of about 0.15%. The EDGAR 2026 territorial boundary also differs.')
    elif source == "ADB":
        recipe.update(gwp_basis="IPCC AR5 (source-characterised)",gwp_horizon=100,
          ghg_note="ADB: source AR5 GWP100 totals are converted from Gg to tonnes once. SEEA uses residence-based accounts; EDGAR uses a territorial boundary.",
          ghg_basis="SEEA residence-based producer and direct final-demand accounts; AR5 GWP100; excludes LULUCF")
    elif source == "USEEIO":
        recipe.update(gwp_basis="Source characterisation (CH4 27.9; N2O 273)",gwp_horizon=100,
          ghg_note="USEEIO: native workbook C factors are retained, including CH4 27.9. Commodity flows include import-related emissions; direct final-demand accounts are unavailable. This is not a US territorial inventory.")
    return recipe


def aggregate(db, recipe, tax_fd=None):
    """Aggregate named V/E rows without calculating a Leontief inverse."""
    annotate_ghg_method(recipe)
    if recipe.get("value_added_available") is False:
        # Native hybrid systems can publish emissions without any income accounts.
        # Do not interpret MARIO's zero-filled factor placeholders as observations.
        ghg = characterise(db.get_block(recipe.get("emissions_block", "E")), recipe["ghg_factors"])
        totals = ghg.groupby(level="Region").sum()
        if set(totals.index) != {r["label"] for r in recipe["regions"]}:
            raise ValueError("The source geographic coverage changed; review the recipe")
        return [{"code": r["label"], "name": r["name"], "iso3": r.get("iso3"),
                 "kind": r["kind"], "gdp": None, "value_added": None,
                 "ghg": [float(totals.loc[r["label"]])]} for r in recipe["regions"]]
    block = recipe.get("value_added_block", "V")
    V = db.get_block(block)
    if not V.columns.is_unique:
        raise ValueError("Duplicated regional industry columns")
    if set(V.columns.get_level_values("Region")) != {r["label"] for r in recipe["regions"]}:
        raise ValueError("The source geographic coverage changed; review the recipe")
    weights = recipe.get("value_added_factors")
    if weights is not None and set(weights) != set(recipe["value_added_rows"]):
        raise ValueError("Value-added weights must match the reviewed rows")
    va = (characterise(V, weights) if weights is not None else strict_sum(V, recipe["value_added_rows"])) * recipe["currency_scale"]
    sector_level = recipe.get("sector_level", "Item")
    sector_names = list(recipe["sectors"])
    observed = list(dict.fromkeys(V.columns.get_level_values(sector_level)))
    if set(observed) != set(sector_names):
        raise ValueError("The source economic classification changed; review the recipe")
    ghg = None
    household = None
    ghg_sectors = recipe.get("ghg_sectors", sector_names)
    if recipe.get("ghg_factors"):
        extension = db.get_block(recipe.get("emissions_block", "E"))
        if set(extension.columns.get_level_values(sector_level)) != set(ghg_sectors):
            raise ValueError("The source emissions classification changed; review the recipe")
        ghg = characterise(extension, recipe["ghg_factors"])
        if recipe.get("final_demand_emissions_loaded", True):
            household = characterise(db.get_block("EY"), recipe["ghg_factors"]).groupby(level="Region").sum()
    taxes = None
    supply_taxes = recipe.get("tax_bridge") == "sut_supply_product_taxes"
    if recipe.get("tax_bridge") == "gloria_valuations" and tax_fd is not None:
        # Both intermediate and final-use taxes come from separate valuation
        # tables. No product-tax row is added again from basic-price Va.
        taxes = pd.Series({r["label"]: 0.0 for r in recipe["regions"]})
    elif supply_taxes:
        taxes = strict_sum(db.get_block("Vc"), recipe["product_tax_rows"]).groupby(level="Region").sum()
        tax_fd = {r["label"]: 0.0 for r in recipe["regions"]}
    elif recipe.get("product_tax_rows"):
        if recipe.get("tax_bridge") == "wiod_sut_vy" and tax_fd is None:
            tax_fd = strict_sum(db.get_block("VY"), recipe["product_tax_rows"]).groupby(level="Region").sum().to_dict()
        if tax_fd is not None:
            taxes = strict_sum(V, recipe["product_tax_rows"]).groupby(level="Region").sum()
    output = []
    for region in recipe["regions"]:
        code = region["label"]
        series = va.xs(code, level="Region").groupby(level=sector_level).sum()
        entry = {"code": code, "name": region["name"], "iso3": region.get("iso3"),
                 "kind": region["kind"], "value_added": [float(series[s]) for s in sector_names]}
        if ghg is not None:
            gas = ghg.xs(code, level="Region").groupby(level=sector_level).sum()
            entry["ghg"] = [float(gas[s]) for s in ghg_sectors]
            if household is not None:
                entry["household_ghg"] = float(household[code])
        if taxes is not None:
            if code not in tax_fd:
                raise ValueError(f"Missing final-demand tax bridge for {code}")
            entry["net_product_taxes"] = float((taxes[code] + tax_fd[code]) * recipe["currency_scale"])
            entry["gdp"] = float(series.sum() + entry["net_product_taxes"])
        elif recipe.get("gdp_proxy") == "native_value_added":
            entry["gdp"] = sum(entry["value_added"])
        output.append(entry)
    return output


def final_demand_taxes(path, recipe):
    """Read the published tax bridge that the current MARIO parsers omit."""
    kind = recipe.get("tax_bridge")
    if not kind or kind in {"sut_supply_product_taxes", "wiod_sut_vy"}:
        return None
    if kind == "gloria_valuations":
        from mario.parsers.gloria import detect_gloria_layout, _iter_csv_batches, _activity_positions
        total = None
        codes = None
        for valuation in ("taxes", "subsidies"):
            layout, metadata = detect_gloria_layout(Path(path), year=recipe["year"], valuation=valuation)
            current_codes = list(metadata.region_codes)
            if codes is not None and current_codes != codes: raise ValueError("Changed GLORIA valuation regions")
            codes = current_codes
            nr, ns, nf = len(codes), len(metadata.sector_names), len(metadata.final_demand_names)
            region_total = np.zeros(nr)
            for block, resource in (("U", layout.T_path), ("Yc", layout.Y_path)):
                columns = _activity_positions(list(range(nr)), ns) if block == "U" else np.arange(nr * nf)
                values_sum = np.zeros(len(columns)); seen = 0
                for rows, values in _iter_csv_batches(resource, columns=columns, dtype=np.dtype("float64"), batch_size=96):
                    if not np.isfinite(values).all(): raise ValueError("Invalid GLORIA product-tax values")
                    values_sum += values[rows % (2 * ns) >= ns].sum(axis=0); seen += len(rows)
                if seen != nr * ns * 2: raise ValueError("Changed GLORIA valuation axes")
                region_total += values_sum.reshape(nr, ns if block == "U" else nf).sum(axis=1)
            if valuation == "subsidies" and np.any(region_total > 1e-6): raise ValueError("Review changed GLORIA subsidy signs")
            total = region_total if total is None else total + region_total
        if set(codes) != {r["label"] for r in recipe["regions"]}: raise ValueError("Changed GLORIA tax coverage")
        return dict(zip(codes, total.tolist()))
    if kind == "source_activity_taxes":
        # The source publishes net product taxes only as a row of the value-added
        # block (EXIOBASE Hybrid). It has no final-use tax row, so none is added.
        return {region["label"]: 0.0 for region in recipe["regions"]}
    if kind == "exiobase_matching_iot":
        matching = recipe.get("parser_options", {}).get("add_extensions")
        if not matching or str(matching).startswith("/path/to/"):
            raise ValueError("Supply the exact same-year EXIOBASE IOT via --extensions-path")
        values = final_demand_taxes(matching, {**recipe, "tax_bridge": "exiobase_satellite"})
        # The paired IOT's F_Y is in million EUR; SUT Va is already EUR.
        return {region: value * 1e6 for region, value in values.items()}
    if kind == "figaro_csv":
        from mario.parsers import figaro
        opts = recipe['parser_options'];year=recipe['year']
        mode=opts.get('iot_mode','product');sut=opts.get('table',recipe.get('table'))=='SUT'
        layout=figaro.detect_figaro_sut_layout(year) if sut else figaro.detect_figaro_iot_layout(year,mode=mode)
        metadata=figaro.load_figaro_metadata()
        factor_codes,_=figaro._label_map(metadata,level='f')
        fd_codes,_=figaro._label_map(metadata,level='n')
        _,region_labels=figaro._label_map(metadata,level='r')
        cache=figaro._figaro_cache_file(path,dataflow=layout.use_dataflow if sut else layout.dataflow,year=year,unit=opts.get('unit','MIO_EUR'),row_dim='prd_ava' if sut or layout.mode=='product' else 'ind_ava',col_dim='ind_use' if sut or layout.mode=='industry' else 'prd_use',countries=opts.get('countries'),include_dom=True,factor_codes=factor_codes)
        if cache is None or not cache.is_file():raise ValueError('The exact FIGARO source cache is required for the final-demand tax bridge')
        result={};cells=set()
        for chunk in pd.read_csv(cache,chunksize=500_000):
            taxes=chunk.loc[chunk.refArea.eq('W2') & chunk.rowCode.eq('D21X31') & chunk.colCode.isin(fd_codes)]
            for row in taxes.itertuples(index=False):
                cell=(row.counterpartArea,row.colCode)
                if cell in cells or not np.isfinite(row.obsValue):raise ValueError('Duplicate or missing FIGARO final-demand tax observation')
                cells.add(cell);label=figaro._resolve_figaro_region_label(row.counterpartArea,region_labels)
                result[label]=result.get(label,0.0)+float(row.obsValue)
        expected={region['label'] for region in recipe['regions']}
        if set(result)!=expected or len(cells)!=len(expected)*len(fd_codes):raise ValueError('Incomplete FIGARO final-demand tax bridge')
        return result
    if kind == "wiod_iot":
        from mario.parsers.wiod import _read_wiod_workbook
        from mario.parsers.specs import WIOD_FINAL_DEMAND_CODES
        frame = _read_wiod_workbook(path)
        rows = frame.loc[frame.iloc[:, 0].eq("TXSP")]
        if len(rows) != 1:
            raise ValueError("Cannot identify the WIOD net product-tax row")
        values = pd.to_numeric(rows.iloc[0, 4:], errors="raise")
        result = {r["label"]: 0.0 for r in recipe["regions"]}
        for value, code, region in zip(values, frame.iloc[2, 4:], frame.iloc[4, 4:]):
            if code in WIOD_FINAL_DEMAND_CODES and region in result:
                result[region] += 0.0 if pd.isna(value) else float(value)
        return result
    if kind == "adb_excel":
        from mario.parsers.adb import detect_adb_layout, _find_header_rows
        from mario.parsers.specs import ADB_FACTOR_LABELS
        layout = detect_adb_layout(path)
        frame = pd.read_excel(layout.data_path, sheet_name=layout.sheet_name, header=None)
        _, region_row, _, sector_start, _, fd_start, fd_end = _find_header_rows(frame.iloc[:12])
        code = next(k for k, v in ADB_FACTOR_LABELS.items() if v == recipe["product_tax_rows"][0])
        rows = frame[frame.iloc[:, sector_start - 1] == code]
        if len(rows) != 1:
            raise ValueError("Cannot identify the ADB product-tax row")
        taxes = rows.iloc[0, fd_start:fd_end].astype(float)
        if not np.isfinite(taxes).all():
            raise ValueError("Missing ADB final-demand tax value")
        regions = frame.iloc[region_row, fd_start:fd_end].astype(str)
        return taxes.groupby(regions).sum().to_dict()
    if kind == "oecd_csv":
        frame = pd.read_csv(path, index_col=0)
        selected = strict_sum(frame, recipe["product_tax_rows"])
        result = {}
        for label, value in selected.items():
            if "_" not in label:
                continue
            region, item = label.split("_", 1)
            if item not in recipe["consumption_categories"]:
                continue
            region = {"CN1": "CHN", "CN2": "CHN", "MX1": "MEX", "MX2": "MEX"}.get(region, region)
            if not np.isfinite(value):
                raise ValueError("Missing final-demand tax value")
            result[region] = result.get(region, 0.0) + float(value)
        return result
    if kind in {"exiobase_factor_inputs", "exiobase_satellite"}:
        relative = ("satellite" if kind == "exiobase_satellite" else "factor_inputs") + "/F_Y.txt"
        if Path(path).is_dir():
            frame = pd.read_csv(Path(path) / relative, sep="\t", index_col=0, header=[0, 1])
        else:
            with zipfile.ZipFile(path) as archive:
                matches = [n for n in archive.namelist() if n.endswith(relative)]
                if len(matches) != 1:
                    raise ValueError("Cannot identify factor_inputs/F_Y.txt in this release")
                with archive.open(matches[0]) as stream:
                    frame = pd.read_csv(stream, sep="\t", index_col=0, header=[0, 1])
        return strict_sum(frame, recipe["product_tax_rows"]).groupby(level=0).sum().to_dict()
    raise ValueError(f"Unknown tax bridge: {kind}")


def load_database(recipe, path):
    """Parse and verify the source year, axes and measurement units."""
    import mario
    if recipe.get("tax_bridge") == "exiobase_matching_iot":
        from mario.parsers.exiobase_iot import detect_exiobase_iot_layout
        matching = recipe["parser_options"].get("add_extensions")
        if not matching or str(matching).startswith("/path/to/"):
            raise ValueError("Supply the exact same-year EXIOBASE IOT via --extensions-path")
        layout = detect_exiobase_iot_layout(matching)
        if layout.year != recipe["year"] or layout.version != recipe["release"] or layout.system != "ixi":
            raise ValueError("The SUT needs the same-release/year industry-by-industry IOT")
    database = getattr(mario, recipe["parser"])(path=str(path), calc_all=False, **recipe["parser_options"])
    year = getattr(database.meta, "year", None)
    if year is None or int(year) != recipe["year"]:
        raise ValueError(f"Expected source year {recipe['year']}, parsed {year}")
    if database.table_type != recipe["table"]:
        raise ValueError("The source table format differs from the selected recipe")
    for group, expected in recipe.get("expected_units", {}).items():
        units = database.units[group]["unit"]
        for label, unit in expected.items():
            if str(units.loc[label]) != unit:
                raise ValueError(f"Unexpected unit for {label}; expected {unit}")
    return database


def usd_factor(recipe, world_bank):
    if recipe["currency"] == "USD":
        return 1.0
    if recipe["currency"] == "EUR":
        explicit = world_bank.get("currency_rates", {}).get("EUR", {}).get("years", {}).get(str(recipe["year"]))
        if explicit is not None:
            return explicit if explicit > 0 else None
        # Before 1999 Germany reports DEM/USD, not EUR/USD. Require the
        # explicit historical EUR/ECU series rather than mislabelling DEM.
        if recipe["year"] < 1999:
            return None
        row = world_bank["countries"].get("DEU", {}).get("years", {}).get(str(recipe["year"]), {})
        rate = row.get("local_currency_per_usd")
        return 1 / rate if rate is not None and rate > 0 else None
    return None


def selected_rows(snapshot, config, wb):
    recipe = config["recipe"]
    metric = config.get("metric", "value_added")
    per_capita = config.get("per_capita", False)
    native_sectors = recipe.get("ghg_sectors", recipe["sectors"]) if metric == "ghg" else recipe["sectors"]
    sectors = config.get("sectors", native_sectors)
    if not sectors:
        raise ValueError("Select at least one industry")
    indices = [native_sectors.index(s) for s in sectors]
    if metric == "gdp" and len(indices) != len(recipe["sectors"]):
        raise ValueError("GDP is available for the whole economy only")
    if config.get("breakdown") and metric in ("value_added", "ghg"):
        yield from selected_rows(snapshot, {**config, "breakdown": False}, wb)
        for sector in sectors:
            yield from selected_rows(snapshot, {**config, "breakdown": False, "sectors": [sector], "industry_row": True}, wb)
        if metric == "ghg" and len(indices) == len(native_sectors) and recipe.get("final_demand_emissions_loaded", True):
            yield from selected_rows(snapshot, {**config, "breakdown": False, "final_demand_row": True}, wb)
        return
    rate = usd_factor(recipe, wb)
    for region in snapshot:
        if config.get("country") and region["code"] != config["country"]:
            continue
        reference = wb["countries"].get(region.get("iso3"), {}).get("years", {}).get(str(recipe["year"]), {})
        value = (sum(region[metric][i] for i in indices) if metric in ("value_added", "ghg") and metric in region
                 else region.get(metric))
        if metric == "ghg" and recipe.get("final_demand_emissions_loaded", True):
            if config.get("final_demand_row"):
                if region.get("household_ghg") is None: continue
                value = region["household_ghg"]
            elif not config.get("industry_row") and len(indices) == len(native_sectors) and value is not None:
                value += region.get("household_ghg", 0)
        if metric == "ghg" and recipe.get("ghg_usable") is False:
            value = None
        if metric in ("gdp", "value_added"):
            value = value * rate if value is not None and rate is not None else None
        if per_capita:
            population = reference.get("population")
            value = value / population if value is not None and population and population > 0 else None
        benchmark = reference.get("gdp_per_capita" if per_capita else "gdp") if metric == "gdp" and recipe.get("price_basis") != "Previous year prices" else None
        yield {"database": recipe["label"], "year": recipe["year"], "region": region["name"],
               "iso3": region.get("iso3"), "indicator": metric,
               "basis": recipe.get("gdp_basis", "GDP") if metric == "gdp" else recipe.get("ghg_basis", "Industry production accounts") if metric == "ghg" else "Industry production accounts",
               "gwp_basis": recipe.get("gwp_basis", "") if metric == "ghg" else "",
               "note": recipe.get("gdp_note", "") if metric == "gdp" else recipe.get("ghg_unavailable_reason", recipe.get("ghg_note", "")) if metric == "ghg" else "",
               "unit": ("t CO2eq" if metric == "ghg" else "previous-year US$" if recipe.get("price_basis") == "Previous year prices" else "current US$") + (" / person" if per_capita else ""),
               "value": value, "world_bank": benchmark,
               "difference_percent": 100 * (value / benchmark - 1) if value is not None and benchmark else None,
               "scope": "Direct final demand" if config.get("final_demand_row") else "Industry" if config.get("industry_row") else "Whole economy" if metric == "gdp" else "Whole economy including direct final demand" if metric == "ghg" and len(indices) == len(native_sectors) and recipe.get("final_demand_emissions_loaded", True) and "household_ghg" in region else "Selected industries total",
               "sectors": "Whole economy" if metric == "gdp" else " | ".join(sectors)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--path", required=True, help="Local input for the selected MARIO parser")
    cli.add_argument("--world-bank", type=Path, help="Optional local copy of the pinned World Bank snapshot")
    cli.add_argument("--output", type=Path, default=Path("mario-browser-selection.csv"))
    args = cli.parse_args()
    if CONFIG is None:
        cli.error("Download this script from a database selection in the MARIO browser")
    import mario
    recipe = CONFIG["recipe"]
    print("Recipe expects MARIO revision:", CONFIG["mario_revision"])
    database = load_database(recipe, args.path)
    tax_fd = final_demand_taxes(args.path, recipe)
    result = aggregate(database, recipe, tax_fd)
    if args.world_bank:
        raw = args.world_bank.read_bytes()
        if hashlib.sha256(raw).hexdigest() != CONFIG["world_bank_sha256"]:
            raise ValueError("World Bank snapshot differs from the reference used in the browser.")
        reference = json.loads(raw)
    else:
        reference = CONFIG["world_bank_reference"]
    rows = list(selected_rows(result, CONFIG, reference))
    if not rows:
        raise ValueError("No rows match the selected filters")
    with args.output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} observations to {args.output}")


if __name__ == "__main__":
    main()
