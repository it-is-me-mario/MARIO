"""Render one committed catalogue in parser cards, guides and comparisons.

No database parsing, workbook generation or external API access happens in Sphinx.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
import posixpath
import re

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.util import logging

logger = logging.getLogger(__name__)
COMPARISONS = "resources/data-explorer/scope"
CATALOGUE = "_static/data/database_profiles.json"
EXTERNAL_PROFILES = "_static/data/external_profiles.json"
LICENCES = "_static/data/database_licences.json"


class database_profile_summary(nodes.General, nodes.Element):
    pass


class database_profile_catalogue(nodes.General, nodes.Element):
    pass


class database_geographic_coverage(nodes.General, nodes.Element):
    pass


class DatabaseProfiles(Directive):
    def run(self):
        return [database_profile_catalogue("")]


class GeographicCoverage(Directive):
    def run(self):
        return [database_geographic_coverage("")]


def coverage_groups(profiles):
    """Group only identical geographic AND economic native sets; counts alone cannot prove equivalence."""
    groups = {}
    for profile in profiles:
        signatures = profile.get("coverage_signatures", {})
        key = (profile.get("source", ""), signatures.get("geography", profile["id"]), signatures.get("economic", profile["id"]))
        groups.setdefault(key, []).append(profile)
    return list(groups.values())


def _note_dependency(app, doctree):
    # Register while reading, before Sphinx pickles its environment. Registering
    # only in doctree-resolved is too late for the next incremental build.
    if (app.env.docname.startswith("notebooks/parsers/")
            or any(doctree.findall(database_profile_summary))
            or any(doctree.findall(database_profile_catalogue))
            or any(doctree.findall(database_geographic_coverage))):
        app.env.note_dependency(str(Path(app.srcdir) / CATALOGUE))
        app.env.note_dependency(str(Path(app.srcdir) / LICENCES))
        external_path=Path(app.srcdir) / EXTERNAL_PROFILES
        if external_path.is_file():
            app.env.note_dependency(str(external_path))


def _load(app, docname):
    path = Path(app.srcdir) / CATALOGUE
    app.env.dependencies[docname].add(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported database profile catalogue schema")
    external_path=Path(app.srcdir) / EXTERNAL_PROFILES
    if external_path.is_file():
        app.env.dependencies[docname].add(external_path)
        external=json.loads(external_path.read_text(encoding="utf-8"))
        if external.get("schema_version")!=1:
            raise ValueError("Unsupported external profile catalogue schema")
        data["profiles"].extend(external["profiles"])
    return data


def _release_key(value):
    """Numeric release components: 3.11.2 > 3.10.1 > 3.9.6 > 3.8.2."""
    return tuple((1, int(part)) if part.isdigit() else (0, part.casefold())
                 for part in re.findall(r"\d+|[^\d]+", str(value or "")))


def _ordered_profiles(profiles):
    # Keep systems and set changes stable within each release, newest first.
    system_order = {"ixi": 0, "pxp": 1, "SUT": 2}
    ordered = sorted(profiles, key=lambda p: (
        system_order.get(p.get("provenance", {}).get("options", {}).get("system") or p.get("table"), 3),
        -int(p.get("year") or 0), p["id"]))
    return sorted(ordered, key=lambda p: _release_key(p.get("release")), reverse=True)


def geographic_groups(profiles):
    """Ignore years and economic formats only for the shared geographic heading."""
    groups = {}
    for profile in _ordered_profiles(profiles):
        signature = profile.get("coverage_signatures", {}).get("geography", profile["id"])
        groups.setdefault((profile.get("source", ""), signature), []).append(profile)
    return list(groups.values())


def _version_title(group):
    releases = sorted({p.get("release") for p in group if p.get("release")}, key=_release_key, reverse=True)
    guide = group[0]["guide"]
    prefix = {"exiobase-monetary": "Monetary", "exiobase-hybrid": "Hybrid"}.get(guide, "")
    if guide == "wiod":
        return " · ".join([" / ".join(releases), " / ".join(sorted({p["table"] for p in group})), " / ".join(sorted({p.get("price_basis", "Current prices") for p in group}))])
    if guide == "figaro":
        return " / ".join(sorted({p["table"] for p in group}))
    return " · ".join(filter(None, (prefix, " / ".join(releases)))) or group[0]["label"]


def _economic_metrics(group):
    labels = {"Sector": "sectors", "Activity": "activities", "Commodity": "commodities"}
    items = []
    economic_groups = coverage_groups(group)
    for equivalent in economic_groups:
        profile = max(equivalent, key=lambda p: int(p.get("year") or 0))
        options = profile.get("provenance", {}).get("options", {})
        variant = options.get("system", "") or {"product": "pxp", "industry": "ixi"}.get(options.get("iot_mode"), "")
        if not variant and len({p.get("release") for p in group}) > 1:
            releases = sorted({p.get("release") for p in equivalent if p.get("release")}, key=_release_key, reverse=True)
            variant = " / ".join(releases)
        for dimension, label in labels.items():
            if dimension in profile["counts"]:
                item = (profile["counts"][dimension], label, variant)
                if item not in items:
                    items.append(item)
    return items


def _metrics_html(group, *, tiles=False):
    metrics = [(group[0]["counts"].get("Region", 0), "regions", "")] + _economic_metrics(group)
    singular = {"regions": "region", "sectors": "sector", "activities": "activity", "commodities": "commodity"}
    metrics = [(count, singular.get(label, label) if count == 1 else label, variant)
               for count, label, variant in metrics]
    if tiles:
        return '<dl class="database-coverage-metrics">' + ''.join(
            f'<div><dt>{html.escape(label)}{f" ({html.escape(variant)})" if variant else ""}</dt><dd>{count:,}</dd></div>'
            for count, label, variant in metrics) + '</dl>'
    return ' · '.join(f'<span><strong>{count:,}</strong> {html.escape(label)}{f" ({html.escape(variant)})" if variant else ""}</span>'
                      for count, label, variant in metrics)


def _workbook_url(app, docname, profile):
    if profile.get("workbook_allowed") is False or profile.get("guide") == "eora":
        return None  # No permission to redistribute the complete source inventory.
    if not (Path(app.srcdir) / profile["workbook"]).is_file():
        logger.warning("Database profile %s has no workbook", profile["id"], location=docname)
        return None
    ascent = posixpath.dirname(app.builder.get_relative_uri(docname, app.config.root_doc))
    return ((ascent + "/") if ascent else "") + profile["workbook"]


def _year_periods(years):
    """Preserve gaps in local verified years instead of implying continuity."""
    verified = sorted({int(year) for year in years})
    if not verified:
        return ""
    periods = []
    start = last = verified[0]
    for year in verified[1:] + [None]:
        if year is not None and year == last + 1:
            last = year
            continue
        periods.append(str(start) if start == last else f"{start}–{last}")
        start = last = year
    return ", ".join(periods)


def _download_html(app, docname, group):
    links = []
    years = [p.get("year") for p in group]
    for profile in _ordered_profiles(group):
        url = _workbook_url(app, docname, profile)
        if not url:
            continue
        label = str(profile.get("year") or "Excel")
        if profile.get("years"):
            options = profile.get("provenance", {}).get("options", {})
            variant = options.get("system") or {"product": "pxp", "industry": "ixi"}.get(options.get("iot_mode")) or profile["table"]
            label = " · ".join(filter(None, (profile.get("release"), variant, _year_periods(profile["years"]))))
        elif years.count(profile.get("year")) > 1:
            variant = profile.get("provenance", {}).get("options", {}).get("system")
            label += " · " + (variant or profile["label"])
        links.append(f'<a class="database-profile-download" href="{html.escape(url)}" download title="{html.escape(profile["label"])}" data-profile-id="{html.escape(profile["id"])}">{html.escape(label)}</a>')
    if not links:
        publisher_links = []
        for profile in group:
            url = profile.get('source_structure_url') or profile.get('source_url')
            if not url:
                continue
            label = 'Source structure Excel ↗' if profile.get('source_structure_url') else 'Publisher metadata ↗'
            note = profile.get('scope_note', '')
            link = f'<a href="{html.escape(url)}" title="{html.escape(note)}">{label}</a>'
            if link not in publisher_links:
                publisher_links.append(link)
        if publisher_links:
            return ' · '.join(publisher_links)
        if any(p.get('guide') == 'eora' for p in group):
            return '<a href="https://new.worldmrio.com/documentation/">Publisher metadata ↗</a>'
    content = '<span class="database-excel-links">' + ''.join(links) + '</span>'
    if len(links) > 4:
        content = f'<details class="database-excel-years"><summary>Excel · {len(links)} files</summary>{content}</details>'
    return content


def _profile_years(profiles):
    return sorted({int(year) for p in profiles
                   for year in (p.get("years") or [p.get("year")]) if year})


def _guide_economic_counts(profile):
    """Expose economic roles without changing MARIO's native IOT Sector set."""
    counts = {key: count for key, count in profile["counts"].items()
              if key in {"Region", "Sector", "Activity", "Commodity"}}
    options = profile.get("provenance", {}).get("options", {})
    system = options.get("system") or {"industry": "ixi", "product": "pxp"}.get(options.get("iot_mode"))
    if "Sector" in counts and system in {"ixi", "pxp"}:
        counts["Activity" if system == "ixi" else "Commodity"] = counts.pop("Sector")
    return counts


def _count_label(values):
    values = sorted(set(values))
    if not values:
        return "—"
    if len(values) == 1:
        return f"{values[0]:,}"
    return f"{values[0]:,}–{values[-1]:,}"


def _sheet_rows(profiles):
    """Combine years and systems, then merge formats with the same year coverage."""
    variants = {}
    for profile in _ordered_profiles(profiles):
        key = (profile.get("release", ""), profile["table"], profile.get("price_basis", ""))
        variants.setdefault(key, []).append(profile)
    rows = {}
    for (release, table, price), group in variants.items():
        key = (release, price, tuple(_profile_years(group)))
        row = rows.setdefault(key, {"release": release, "price": price, "years": key[2], "formats": [], "profiles": []})
        row["formats"].append(table)
        row["formats"].sort()
        row["profiles"].extend(group)
    return list(rows.values())


def _sheet_count_html(profiles):
    labels = {"Region": "regions", "Activity": "activities", "Commodity": "commodities", "Sector": "IOT sectors"}
    metrics = []
    for key, label in labels.items():
        values = [p[key] for profile in profiles if key in (p := _guide_economic_counts(profile))]
        if not values:
            continue
        hint = ""
        if key == "Region":
            geography = {(p.get("geography", {}).get("individual_countries"), p.get("geography", {}).get("aggregate_count")) for p in profiles}
            if len(geography) == 1:
                individual, aggregate = next(iter(geography))
                if individual is not None and aggregate is not None and individual + aggregate == values[0]:
                    hint = f"{individual} individual · {aggregate} aggregate"
        elif key == "Sector":
            regional = [row["count"] for profile in profiles
                        for row in profile.get("region_counts", []) if row["set"] == key]
            if len(set(regional)) > 1:
                hint = f"Varies by region; {_count_label(values)} distinct sector labels overall."
                values = regional
        metrics.append(f'<div><dt>{html.escape(label)}</dt><dd>{_count_label(values)}</dd>{f"<small>{hint}</small>" if hint else ""}</div>')
    return '<dl class="database-sheet__metrics">' + ''.join(metrics) + '</dl>'


def _other_sets_html(profiles):
    dimensions = {"Factor of production": "Factors of production", "Satellite account": "Satellite accounts", "Consumption category": "Consumption categories"}
    dimensions = {key: label for key, label in dimensions.items() if any(key in p["counts"] for p in profiles)}
    if not dimensions:
        return ""
    parts = ['<details class="database-sheet__sets"><summary>Other sets</summary><dl class="database-sheet__facts">']
    varying = []
    for key, label in dimensions.items():
        values = {p["counts"][key] for p in profiles if key in p["counts"]}
        value = "Not loaded" if values == {0} and key == "Satellite account" else _count_label(values)
        parts.append(f'<div><dt>{label}</dt><dd>{value}</dd></div>')
        if len(values) > 1:
            varying.append(key)
    parts.append('</dl>')
    if varying:
        # One row per release/format, never one per year or ixi/pxp inventory file.
        groups = {}
        for profile in _ordered_profiles(profiles):
            key = (profile.get("release", ""), profile["table"], profile.get("price_basis", ""))
            groups.setdefault(key, []).append(profile)
        parts.append('<div class="database-sheet__table" tabindex="0" role="region" aria-label="Set counts by table"><table><thead><tr><th scope="col">Table</th>')
        parts.extend(f'<th scope="col">{dimensions[key]}</th>' for key in varying)
        parts.append('</tr></thead><tbody>')
        for (release, table, price), group in groups.items():
            label = ' · '.join(filter(None, (release, table, price)))
            parts.append(f'<tr><th scope="row">{html.escape(label)}</th>')
            for key in varying:
                values = [p["counts"][key] for p in group if key in p["counts"]]
                parts.append(f'<td>{_count_label(values)}</td>')
            parts.append('</tr>')
        parts.append('</tbody></table></div>')
    parts.append('<p class="database-sheet__note">Counts refer to the inventories listed here. Optional extensions and the reference year can change the satellite set; Excel inventories give the exact lists.</p></details>')
    return ''.join(parts)


def _guide_sheet_html(app, docname, guide, profiles, metadata):
    rights = _licence_html(guide, metadata) if metadata else ""
    if not profiles and not rights:
        return ""
    catalogue_guide = next((g for g in (metadata or {}).get("catalogue_guides", []) if g["id"] == guide), {})
    label = catalogue_guide.get("label") or (profiles[0].get("source") if profiles else "Source database")
    label = {"exiobase-monetary": "EXIOBASE · Monetary", "exiobase-hybrid": "EXIOBASE · Hybrid", "oecd": "OECD ICIO" if profiles else "OECD", "adb": "ADB"}.get(guide, label)
    compare = app.builder.get_relative_uri(docname, COMPARISONS)
    parts = [f'<aside class="database-sheet" aria-label="Database profile"><div class="database-sheet__header"><div><span>Database profile</span><strong>{html.escape(label)}</strong></div><a href="{html.escape(compare)}">Classifications ↗</a></div><div class="database-sheet__body">']
    if profiles:
        rows = _sheet_rows(profiles)
        releases = list(dict.fromkeys(p.get("release", "") for p in _ordered_profiles(profiles)))
        formats = sorted({p["table"] for p in profiles})
        systems = sorted({system for p in profiles if (system := (p.get("provenance", {}).get("options", {}).get("system") or {"industry": "ixi", "product": "pxp"}.get(p.get("provenance", {}).get("options", {}).get("iot_mode"))))})
        units = sorted({unit for p in profiles if (unit := p.get("provenance", {}).get("options", {}).get("unit"))})
        format_varies = len({tuple(row["formats"]) for row in rows}) > 1
        price_varies = len({row["price"] for row in rows}) > 1
        parts.append(_sheet_count_html(profiles))
        if systems:
            roles = []
            if "ixi" in systems: roles.append("ixi: activities")
            if "pxp" in systems: roles.append("pxp: commodities")
            parts.append(f'<p class="database-sheet__note">IOT systems: {" · ".join(roles)}. MARIO stores IOT categories in the Sector set.</p>')
        facts = []
        if len(releases) == 1 and releases[0]: facts.append(("Version", releases[0]))
        if units and not all(unit.casefold() in label.casefold() for unit in units):
            facts.append(("Units", " / ".join(units)))
        if not format_varies: facts.append(("Table format" if len(formats) == 1 else "Table formats", " / ".join(formats)))
        if len(rows) == 1: facts.append(("Available local years" if any(p.get("year_evidence") for p in profiles) else "Verified years", _year_periods(rows[0]["years"])))
        publisher = next((p.get("source_coverage") for p in profiles if p.get("source_coverage")), None)
        if publisher:
            span = f"{publisher['first_year']}–{publisher['last_year']}"
            forecast = publisher.get("forecast_from")
            facts.append(("Publisher series", span + (f" · {forecast}–{publisher['last_year']} forecasts" if forecast else "")))
        if not price_varies and rows[0]["price"]: facts.append(("Price basis", rows[0]["price"]))
        if facts:
            parts.append('<dl class="database-sheet__facts">' + ''.join(f'<div><dt>{name}</dt><dd>{html.escape(value)}</dd></div>' for name, value in facts) + '</dl>')
        if len(rows) > 1:
            version_varies = len(releases) > 1
            changing = [key for key in ("Region", "Activity", "Commodity", "Sector")
                        if len({counts[key] for p in profiles if key in (counts := _guide_economic_counts(p))}) > 1]
            coverage_labels = {"Region": "regions", "Activity": "activities", "Commodity": "commodities", "Sector": "sectors"}
            parts.append('<div class="database-sheet__table" tabindex="0" role="region" aria-label="Versions and verified years"><table><thead><tr>')
            headers = (["Version"] if version_varies else []) + (["Table format"] if format_varies else []) + (["Price basis"] if price_varies else []) + ["Verified years"] + (["Coverage"] if changing else [])
            parts.extend(f'<th scope="col">{name}</th>' for name in headers)
            parts.append('</tr></thead><tbody>')
            for row in rows:
                cells = ([row["release"]] if version_varies else []) + ([" / ".join(row["formats"])] if format_varies else []) + ([row["price"]] if price_varies else []) + [_year_periods(row["years"])]
                if changing:
                    coverage = []
                    for key in changing:
                        values = [counts[key] for p in row["profiles"] if key in (counts := _guide_economic_counts(p))]
                        if values: coverage.append(f'{_count_label(values)} {coverage_labels[key]}')
                    cells.append(" · ".join(coverage))
                parts.append('<tr>')
                for i, value in enumerate(cells):
                    tag = 'th scope="row"' if i == 0 else 'td'
                    closing = 'th' if i == 0 else 'td'
                    parts.append(f'<{tag}>{html.escape(value)}</{closing}>')
                parts.append('</tr>')
            parts.append('</tbody></table></div>')
        evidence_notes = list(dict.fromkeys(p.get("year_evidence", {}).get("note") for p in profiles if p.get("year_evidence", {}).get("note")))
        parts.append('<p class="database-sheet__note">' + (html.escape(" ".join(evidence_notes)) if evidence_notes else "Years and counts describe the verified inventories in this documentation.") + "</p>")
        parts.append(_other_sets_html(profiles))
    parts.append(rights)
    if profiles:
        source = profiles[0].get("source", "")
        family = "ADB" if source == "Asian Development Bank" else source
        anchor = "database-sets-" + re.sub(r"[^a-z0-9]+", "-", family.lower()).strip("-")
        material = app.builder.get_relative_uri(docname, "resources/material") + "#" + anchor
        label = "Excel set lists ↗" if any(p.get("workbook_allowed", True) and p.get("guide") != "eora" for p in profiles) else "Source set information ↗"
        parts.append(f'<div class="database-sheet__links"><a href="{html.escape(material)}">{label}</a></div>')
    parts.append('</div></aside>')
    return ''.join(parts)


def _summary_html(app, docname, guide, profiles, *, compact=False, metadata=None):
    verified = [p for p in profiles if p.get("status") in {"parsed", "source_verified"} and p.get("parser_supported", True) and p["guide"] == guide]
    if compact:
        if not verified:
            return ""
        return '<div class="database-profile-summary">' + ''.join(
            f'<div class="database-card-coverage"><p class="database-card-version">{html.escape(_version_title(group))}</p><p class="database-card-metrics">{_metrics_html(group)}</p></div>'
            for group in geographic_groups(verified)) + '</div>'
    return _guide_sheet_html(app, docname, guide, verified, metadata)


def _catalogue_html(app, docname, profiles):
    if not profiles:
        return '<p class="database-profile-empty">Database set lists will appear as inventories are added.</p>'
    parts = ['<div class="database-profile-catalogue" tabindex="0" role="region" aria-label="Database set downloads"><table class="database-download-table"><thead><tr><th scope="col">Database</th><th scope="col">Version / format</th><th scope="col">Coverage</th><th scope="col">Excel</th></tr></thead>']
    for source in sorted({p["source"] for p in profiles}):
        label = "ADB" if source == "Asian Development Bank" else source
        anchor = "database-sets-" + re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        groups = geographic_groups([p for p in profiles if p["source"] == source])
        parts.append(f'<tbody class="database-family" id="{anchor}">')
        for i, group in enumerate(groups):
            parts.append('<tr>')
            if i == 0:
                parts.append(f'<th scope="rowgroup" rowspan="{len(groups)}">{html.escape(label)}</th>')
            formats = " / ".join(dict.fromkeys(p["table"] for p in group))
            parts.append(f'<td><strong class="database-download-version">{html.escape(_version_title(group))}</strong><small>{html.escape(formats)}</small></td><td class="database-download-coverage">{_metrics_html(group)}</td><td>{_download_html(app, docname, group)}</td></tr>')
        parts.append('</tbody>')
    parts.append('</table></div>')
    return ''.join(parts)


def _insert_guide_summary(top, panel):
    """Leave the existing introduction before the overview, including its lists."""
    section = next((i for i, child in enumerate(top.children) if isinstance(child, nodes.section)), len(top.children))
    top.insert(section, panel)


def _licence_html(guide, metadata):
    """Compact source rights near the introduction; do not infer missing licences."""
    entries=metadata['guides'].get(guide,[])
    if not entries:
        return ''
    parts=['<div class="database-sheet__licence"><strong>Source licence</strong>']
    for entry in entries:
        label=html.escape(entry['label'])
        if entry.get('url'):
            label=f'<a href="{html.escape(entry["url"])}">{label} ↗</a>'
        scope = f'<span>{html.escape(entry["scope"])}</span> · ' if len(entries) > 1 else ''
        parts.append(f'<p>{scope}{label}</p>')
    parts.append('<details><summary>Reuse &amp; attribution</summary>')
    for entry in entries:
        sources=' · '.join(f'<a href="{html.escape(url)}">Source {i+1} ↗</a>' for i,url in enumerate(entry.get('sources',[])))
        parts.append(f'<p>{html.escape(entry["note"])}{(" "+sources) if sources else ""}</p>')
    parts.append('</details></div>')
    return ''.join(parts)


def _render(app, doctree, docname):
    summaries = list(doctree.findall(database_profile_summary))
    catalogues = list(doctree.findall(database_profile_catalogue))
    geographic = list(doctree.findall(database_geographic_coverage))
    if not summaries and not catalogues and not geographic and not docname.startswith("notebooks/parsers/"):
        return
    data = _load(app, docname)
    guides = {guide["id"]: guide for guide in data["guides"]}
    for summary in summaries:
        key = summary["guide"]
        if key not in guides:
            raise ValueError(f"Unknown database guide {key}")
        summary.replace_self(nodes.raw("", _summary_html(app, docname, key, data["profiles"], compact=True), format="html"))
    guide = next((g for g in guides.values() if g["doc"] == docname), None)
    if guide and not any(doctree.findall(lambda node: isinstance(node, nodes.container) and "database-guide-summary" in node.get("classes", []))):
        top = next(iter(doctree.findall(nodes.section)), None)
        if top is not None:
            metadata = json.loads((Path(app.srcdir) / LICENCES).read_text())
            if metadata.get("schema_version") != 1:
                raise ValueError("Unsupported database licence metadata")
            metadata["catalogue_guides"] = data["guides"]
            content = _summary_html(app, docname, guide["id"], data["profiles"], metadata=metadata)
            if content:
                panel = nodes.container(classes=["database-guide-summary"])
                panel += nodes.raw("", content, format="html")
                _insert_guide_summary(top, panel)
    for catalogue in catalogues:
        profiles = [p for p in data["profiles"] if p.get("status") in {"parsed", "source_verified"}]
        catalogue.replace_self(nodes.raw("", _catalogue_html(app, docname, profiles), format="html"))
    for marker in geographic:
        profiles = [p for p in data["profiles"] if p.get("status") in {"parsed", "source_verified"}]
        ascent = posixpath.dirname(app.builder.get_relative_uri(docname, app.config.root_doc))
        root = (ascent + "/") if ascent else ""
        lightweight = [{key: p[key] for key in ("id", "source", "guide", "label", "release", "year", "table", "counts", "geography", "workbook", "coverage_signatures")}
                       for p in profiles if len({r.get("iso3") or r.get("label") for r in p.get("geography", {}).get("regions", [])
                                                 if r.get("kind") == "country"}) > 1]
        for profile in lightweight:
            original = next(p for p in profiles if p["id"] == profile["id"])
            profile["years"] = original.get("years", [original.get("year")])
            profile["status"] = original["status"]
            profile["parser_supported"] = original.get("parser_supported", True)
            profile["source_url"] = original.get("source_url") or original.get("provenance", {}).get("source_url")
            profile["guide_url"] = (app.builder.get_relative_uri(docname, guides[profile["guide"]]["doc"])
                                    if profile["guide"] in guides else profile["source_url"])
        payload = json.dumps(lightweight, ensure_ascii=False).replace("<", "\\u003c")
        content = f'''<div class="coverage-explorer" data-database-comparisons data-root="{html.escape(root)}">
          <script type="application/json" data-comparison-profiles>{payload}</script>
          <p data-comparison-loading>Loading the country explorer…</p>
          <noscript>Enable JavaScript to explore the map. Original set lists are available in <a href="{html.escape(root)}resources/material.html#database-set-downloads">Downloadable material</a>.</noscript>
        </div>'''
        marker.replace_self(nodes.raw("", content, format="html"))


def setup(app):
    app.add_node(database_profile_summary)
    app.add_node(database_profile_catalogue)
    app.add_node(database_geographic_coverage)
    app.add_directive("mario-database-profiles", DatabaseProfiles)
    app.add_directive("mario-geographic-coverage", GeographicCoverage)
    app.add_js_file("database-comparisons.js", defer="defer")
    app.connect("doctree-read", _note_dependency)
    app.connect("doctree-resolved", _render)
    return {"version": "1.3", "parallel_read_safe": True, "parallel_write_safe": True}
