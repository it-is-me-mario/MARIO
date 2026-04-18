from __future__ import annotations

import json
from html import escape
from pathlib import Path

import country_converter as coco
import pandas as pd

try:
    import pycountry
except ModuleNotFoundError:  # pragma: no cover - optional fallback dependency
    pycountry = None


DOC_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = DOC_ROOT / "source" / "_static" / "data" / "Country_coverage.xlsx"
OUTPUT_DIR = DOC_ROOT / "source" / "parsers" / "_generated"
JSON_OUTPUT = DOC_ROOT / "source" / "_static" / "data" / "parser_coverage.json"

SOURCE_CODE_OVERRIDES = {
    ("OECD", "CN1"): ("CHN", "China"),
    ("OECD", "CN2"): ("CHN", "China"),
    ("OECD", "MX1"): ("MEX", "Mexico"),
    ("OECD", "MX2"): ("MEX", "Mexico"),
    # Keep the Eora code visible until its meaning is clarified in the source workbook.
    ("EORA1", "USR"): ("", "USR"),
}

NON_STANDARD_ISO3_NAMES = {
    "ANT": "Netherlands Antilles",
    "DYE": "South Yemen",
    "SUN": "Soviet Union",
    "BA1": "BA1",
    "CHI": "CHI",
    "EAT": "EAT",
    "EAZ": "EAZ",
}

SOURCE_PAGE_SLUGS = {
    "ADB": "adb",
    "CEPALSTAT": "cepalstat",
    "EMERGING": "emerging",
    "EORA1": "eora",
    "EUROSTAT": "eurostat",
    "EXIOBASE": "exiobase",
    "FIGARO": "figaro",
    "GLORIA": "gloria",
    "ISTAT": "istat",
    "OECD": "oecd",
    "StatCan": "statcan",
    "USEEIO": "useeio",
    "WIOD": "wiod",
}


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def load_concordance() -> dict[str, dict[str, str]]:
    concordance = pd.read_excel(WORKBOOK, sheet_name="concordance", header=1)
    concordance = concordance.rename(columns={concordance.columns[0]: "ISO3"})
    mappings: dict[str, dict[str, str]] = {}
    for source in concordance.columns:
        if source == "ISO3":
            continue
        source_map: dict[str, str] = {}
        for _, row in concordance[["ISO3", source]].dropna().iterrows():
            iso3 = normalize_text(row["ISO3"])
            source_code = normalize_text(row[source])
            if iso3 and source_code:
                source_map.setdefault(source_code, iso3)
        mappings[source] = source_map
    return mappings


def convert_country_name(iso3: str, converter) -> str:
    converted = converter.convert(names=iso3, to="name_short", not_found="__NF__")
    if converted != "__NF__":
        return str(converted)
    if pycountry is not None:
        match = pycountry.countries.get(alpha_3=iso3)
        if match is not None:
            return str(match.name)
    return iso3


def country_name_for(iso3: str, source: str, source_code: str, converter) -> str:
    override = SOURCE_CODE_OVERRIDES.get((source, source_code))
    if override is not None:
        return override[1]
    if not iso3:
        return source_code
    if iso3 in NON_STANDARD_ISO3_NAMES:
        if source_code != iso3:
            return source_code
        return NON_STANDARD_ISO3_NAMES[iso3]
    converted = convert_country_name(iso3, converter)
    if converted == iso3:
        return source_code if source_code and source_code != iso3 else iso3
    return converted


def iso3_for(source: str, source_code: str, mappings: dict[str, dict[str, str]]) -> str:
    override = SOURCE_CODE_OVERRIDES.get((source, source_code))
    if override is not None:
        return override[0]
    return mappings.get(source, {}).get(source_code, "")


def expand_years(years: str) -> list[str]:
    values: list[str] = []
    for token in [part.strip() for part in str(years).split(",") if part.strip()]:
        if token.isdigit() and len(token) == 4:
            values.append(token)
            continue
        if "-" in token:
            bounds = [part.strip() for part in token.split("-", 1)]
            if len(bounds) == 2 and all(bound.isdigit() and len(bound) == 4 for bound in bounds):
                start, end = (int(bounds[0]), int(bounds[1]))
                if start <= end and end - start <= 100:
                    values.extend(str(year) for year in range(start, end + 1))
                    continue
        values.append(token)
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)


def normalize_coverage_rows() -> list[dict[str, str]]:
    coverage = pd.read_excel(WORKBOOK, sheet_name="coverage")
    concordance = load_concordance()
    converter = coco.CountryConverter()

    rows: list[dict[str, str]] = []
    country_columns = list(coverage.columns[7:])
    for _, row in coverage.iterrows():
        source = normalize_text(row["Source"])
        parser = normalize_text(row["parser"])
        table = normalize_text(row["Table"])
        years = normalize_text(row["Year"])
        version = normalize_text(row["Version"])
        notes = normalize_text(row["Other notes"])
        region_scope = normalize_text(row["Region"])

        for column in country_columns:
            source_code = normalize_text(row[column])
            if not source_code:
                continue
            iso3 = iso3_for(source, source_code, concordance)
            country = country_name_for(iso3, source, source_code, converter)
            rows.append(
                {
                    "source": source,
                    "parser": parser,
                    "parser_page": SOURCE_PAGE_SLUGS.get(source, ""),
                    "table": table,
                    "years": years,
                    "year_values": expand_years(years),
                    "version": version,
                    "scope": region_scope,
                    "country": country,
                    "iso3": iso3,
                    "source_code": source_code,
                    "notes": notes,
                }
            )

    rows.sort(
        key=lambda values: (
            values["source"],
            values["country"],
            values["table"],
            values["years"],
            values["version"],
            values["source_code"],
        )
    )
    return rows


def render_query(json_payload: str) -> str:
    html = []
    html.append('<div id="parser-coverage-query" class="parser-coverage-query">')
    html.append('  <form class="parser-coverage-form">')
    html.append('    <div class="parser-coverage-controls">')
    html.append('      <label class="parser-coverage-field">')
    html.append('        <span>Country</span>')
    html.append('        <select name="country">')
    html.append('          <option value="">All countries</option>')
    html.append('        </select>')
    html.append("      </label>")
    html.append('      <label class="parser-coverage-field">')
    html.append('        <span>Year</span>')
    html.append('        <select name="year">')
    html.append('          <option value="">All years</option>')
    html.append('        </select>')
    html.append("      </label>")
    html.append('      <div class="parser-coverage-actions">')
    html.append('        <button type="submit" class="btn btn-primary btn-sm">Query</button>')
    html.append('        <button type="button" class="btn btn-secondary btn-sm" data-action="reset">Reset</button>')
    html.append("      </div>")
    html.append("    </div>")
    html.append("  </form>")
    html.append(
        '  <p class="parser-coverage-help">'
        "Select a country, a year, or both. The other selector narrows itself automatically. "
        "After you submit, only matching rows are rendered."
        "</p>"
    )
    html.append('  <p class="parser-coverage-message">No query submitted yet.</p>')
    html.append('  <script type="application/json" class="parser-coverage-data">')
    html.append(json_payload.replace("</", "<\\/"))
    html.append("  </script>")
    html.append('  <div class="parser-coverage-results" hidden>')
    html.append('    <p class="parser-coverage-summary"></p>')
    html.append('    <div class="terminology-table-wrapper">')
    html.append('      <table class="terminology-table parser-coverage-results-table">')
    html.append("        <thead>")
    html.append("          <tr>")
    for header in [
        "Source",
        "Parser",
        "Table",
        "Available years",
        "Version",
        "Scope",
        "Country",
        "ISO3",
        "Source code",
        "Notes",
    ]:
        html.append(f"            <th>{escape(header)}</th>")
    html.append("          </tr>")
    html.append("        </thead>")
    html.append("        <tbody></tbody>")
    html.append("      </table>")
    html.append("    </div>")
    html.append("  </div>")
    html.append("</div>")
    return "\n".join(html) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = normalize_coverage_rows()
    json_payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    JSON_OUTPUT.write_text(
        json_payload,
        encoding="utf-8",
    )
    (OUTPUT_DIR / "coverage_query.html").write_text(
        render_query(json_payload),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
