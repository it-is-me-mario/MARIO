"""Regenerate the documentation benchmark fragments from local snapshots.

Run from any working directory: python doc/scripts/generate_benchmark_assets.py.
No database parsing, downloads, nxbase query or API credentials are needed.
The generated fragments are committed, so Read the Docs only reads them.

Electricity data and templates are adapted from eNextHub/electricity-carbon-footprint,
blogpost/ (Citterio et al. 2026, CC BY 4.0). See benchmark_assets.rst for provenance.
"""

from __future__ import annotations

import json
from collections import defaultdict
from html import escape
from pathlib import Path


DOC = Path(__file__).resolve().parents[1]
DATA = DOC / "source" / "_static" / "data" / "benchmarks"
TEMPLATES = Path(__file__).resolve().parent / "templates"
OUTPUT = DOC / "source" / "resources" / "benchmarks" / "_generated"


def json_for_html(value):
    # An embedded data label must never close its script element.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def catalogue_profiles():
    """Coalesce identical country lists across catalogue years; retain releases.

    These are declared coverage entries from the existing workbook, not the
    region set of a parsed model. In particular, national and subnational table
    resolution must not be inferred from the length of this country list.
    """
    rows = json.loads((DOC / "source" / "_static" / "data" / "parser_coverage.json").read_text())
    releases = defaultdict(list)
    for row in rows:
        if row["scope"] == "Multi-region":
            releases[(row["source"], row["table"], row["version"], row["years"])].append(row)

    profiles = {}
    for (source, table, version, _), release in releases.items():
        entries = {
            (r["source_code"], r["country"], r["iso3"])
            for r in release
        }
        signature = (source, table, version, tuple(sorted(entries)))
        if signature not in profiles:
            profiles[signature] = {
                "source": source,
                "format": table,
                "version": version,
                "parser_page": release[0]["parser_page"],
                "years": set(),
                "geographies": [
                    {"code": code, "name": name, "iso3": iso}
                    for code, name, iso in sorted(entries, key=lambda e: (e[1], e[0]))
                ],
                "status": "catalogue",
                "regions": None,
                "sectors": None,
                "activities": None,
                "commodities": None,
                "satellite_accounts": None,
                "workbook": None,
            }
        for row in release:
            profiles[signature]["years"].update(row["year_values"])

    result = sorted(profiles.values(), key=lambda p: (p["source"], p["format"], p["version"]))
    for n, profile in enumerate(result):
        profile["id"] = f"catalogue-{n}"
        profile["years"] = sorted(profile["years"])
    return result


def render_coverage(profiles):
    # Show a useful fallback before JS runs or when it is disabled.
    sources = sorted({p["source"] for p in profiles})
    items = "".join(f"<span>{escape(source)}</span>" for source in sources)
    return f"""<div class="benchmark-coverage" data-coverage>
  <div class="benchmark-controls">
    <label>Table format <select data-coverage-format><option value="all">IOT and SUT</option><option>IOT</option><option>SUT</option></select></label>
    <label>Source <select data-coverage-source><option value="all">All sources</option></select></label>
    <label>Catalogue year <select data-coverage-year><option value="all">All years</option></select></label>
  </div>
  <p class="benchmark-catalogue-note">Initial view from MARIO's coverage catalogue. Bars count listed geographic entries;
  they are not a verified count of model regions or individually resolved countries.
  Sectoral sets and full-set workbooks will be added from parsed releases.</p>
  <div class="benchmark-coverage-layout">
    <div><p class="benchmark-chart-label">Geographic entries in the catalogue</p>
      <div class="benchmark-coverage-bars" data-coverage-bars aria-label="Select a source release">{items}</div>
      <p class="benchmark-empty" data-coverage-empty hidden>No catalogue release matches these filters.</p>
    </div>
    <div class="benchmark-profile" data-coverage-profile aria-live="polite"></div>
  </div>
  <script type="application/json" data-coverage-data>{json_for_html(profiles)}</script>
</div>
<script src="../_static/benchmark-coverage.js"></script>
"""


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    profiles = catalogue_profiles()
    (DATA / "database-coverage.json").write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n")
    (OUTPUT / "database-coverage.html").write_text(render_coverage(profiles))
    for name in ("electricity-country", "electricity-technology"):
        data = json.loads((DATA / f"{name}.json").read_text())
        for record in data["records"]:
            if not isinstance(record["value"], (int, float)):
                raise ValueError(f"Non-numeric {name} observation: {record}")
        template = (TEMPLATES / f"{name}.html").read_text()
        if template.count("__DATA__") != 1:
            raise ValueError(f"Expected exactly one data placeholder in {name}")
        (OUTPUT / f"{name}.html").write_text(template.replace("__DATA__", json_for_html(data)))
        print(f"{name}: {len(data['records'])} observations")
    print(f"database-coverage: {len(profiles)} catalogue profiles")


if __name__ == "__main__":
    main()
