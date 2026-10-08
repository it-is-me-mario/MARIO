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
COMPARISONS = "resources/database_coverage"
CATALOGUE = "_static/data/database_profiles.json"


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


def _load(app, docname):
    path = Path(app.srcdir) / CATALOGUE
    app.env.dependencies[docname].add(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported database profile catalogue schema")
    return data


def geographic_groups(profiles):
    """Ignore years and economic formats only for the shared geographic heading."""
    groups = {}
    for profile in sorted(profiles, key=lambda p: (-int(p.get("year") or 0), p["id"])):
        signature = profile.get("coverage_signatures", {}).get("geography", profile["id"])
        groups.setdefault((profile.get("source", ""), signature), []).append(profile)
    return list(groups.values())


def _version_title(group):
    releases = list(dict.fromkeys(p.get("release") for p in group if p.get("release")))
    guide = group[0]["guide"]
    prefix = {"exiobase-monetary": "Monetary", "exiobase-hybrid": "Hybrid"}.get(guide, "")
    if guide == "figaro":
        return "Eurostat snapshot"
    return " · ".join(filter(None, (prefix, " / ".join(releases)))) or group[0]["label"]


def _economic_metrics(group):
    labels = {"Sector": "sectors", "Activity": "activities", "Commodity": "commodities"}
    items = []
    distinct = [sorted(g, key=lambda p: int(p.get("year") or 0), reverse=True)[0]
                for g in coverage_groups(group)]
    for profile in distinct:
        variant = profile.get("provenance", {}).get("options", {}).get("system", "")
        if not variant and len({p.get("release") for p in distinct}) > 1:
            variant = profile.get("release", "")
        for dimension, label in labels.items():
            if dimension in profile["counts"]:
                item = (profile["counts"][dimension], label, variant)
                if item not in items:
                    items.append(item)
    return items


def _metrics_html(group, *, tiles=False):
    metrics = [(group[0]["counts"].get("Region", 0), "regions", "")] + _economic_metrics(group)
    if tiles:
        return '<dl class="database-coverage-metrics">' + ''.join(
            f'<div><dt>{html.escape(label)}{f" ({html.escape(variant)})" if variant else ""}</dt><dd>{count:,}</dd></div>'
            for count, label, variant in metrics) + '</dl>'
    return ' · '.join(f'<span><strong>{count:,}</strong> {html.escape(label)}{f" ({html.escape(variant)})" if variant else ""}</span>'
                      for count, label, variant in metrics)


def _workbook_url(app, docname, profile):
    if not (Path(app.srcdir) / profile["workbook"]).is_file():
        logger.warning("Database profile %s has no workbook", profile["id"], location=docname)
        return None
    ascent = posixpath.dirname(app.builder.get_relative_uri(docname, app.config.root_doc))
    return ((ascent + "/") if ascent else "") + profile["workbook"]


def _download_html(app, docname, group):
    links = []
    years = [p.get("year") for p in group]
    for profile in group:
        url = _workbook_url(app, docname, profile)
        if not url:
            continue
        label = str(profile.get("year") or "Excel")
        if years.count(profile.get("year")) > 1:
            variant = profile.get("provenance", {}).get("options", {}).get("system")
            label += " · " + (variant or profile["label"])
        links.append(f'<a class="database-profile-download" href="{html.escape(url)}" download title="{html.escape(profile["label"])}" data-profile-id="{html.escape(profile["id"])}">{html.escape(label)}</a>')
    content = '<span class="database-excel-links">' + ''.join(links) + '</span>'
    if len(links) > 4:
        content = f'<details class="database-excel-years"><summary>Excel · {len(links)} files</summary>{content}</details>'
    return content


def _summary_html(app, docname, guide, profiles, *, compact=False):
    verified = [p for p in profiles if p.get("status") == "parsed" and p["guide"] == guide]
    if not verified:
        return ""
    groups = geographic_groups(verified)
    if compact:
        return '<div class="database-profile-summary">' + ''.join(
            f'<div class="database-card-coverage"><p class="database-card-version">{html.escape(_version_title(group))}</p><p class="database-card-metrics">{_metrics_html(group)}</p></div>'
            for group in groups) + '</div>'
    compare = app.builder.get_relative_uri(docname, COMPARISONS)
    parts = [f'<div class="database-guide-coverage"><div class="database-guide-coverage__header"><strong>Database coverage</strong><a href="{html.escape(compare)}">Compare databases</a></div>']
    for group in groups:
        years = sorted({str(p["year"]) for p in group if p.get("year")}, reverse=True)
        year_label = ", ".join(years) if len(years) <= 5 else f"{len(years)} years"
        parts.append(f'<section class="database-guide-version"><div class="database-guide-version__heading"><p>{html.escape(_version_title(group))}</p><span>Set lists: {html.escape(year_label)}</span></div>{_metrics_html(group, tiles=True)}<div class="database-guide-downloads"><span>All sets · Excel</span>{_download_html(app, docname, group)}</div></section>')
    parts.append('</div>')
    return ''.join(parts)


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
            content = _summary_html(app, docname, guide["id"], data["profiles"])
            if content:
                panel = nodes.container(classes=["database-guide-summary"])
                panel += nodes.raw("", content, format="html")
                _insert_guide_summary(top, panel)
    for catalogue in catalogues:
        profiles = [p for p in data["profiles"] if p.get("status") == "parsed"]
        catalogue.replace_self(nodes.raw("", _catalogue_html(app, docname, profiles), format="html"))
    for marker in geographic:
        profiles = [p for p in data["profiles"] if p.get("status") == "parsed"]
        ascent = posixpath.dirname(app.builder.get_relative_uri(docname, app.config.root_doc))
        root = (ascent + "/") if ascent else ""
        lightweight = [{key: p[key] for key in ("id", "source", "guide", "label", "release", "year", "table", "counts", "geography", "workbook", "coverage_signatures")}
                       for p in profiles if p.get("geography", {}).get("regions")]
        for profile in lightweight:
            profile["guide_url"] = app.builder.get_relative_uri(docname, guides[profile["guide"]]["doc"])
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
    return {"version": "1.1", "parallel_read_safe": True, "parallel_write_safe": True}
