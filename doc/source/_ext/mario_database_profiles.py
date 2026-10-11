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
    content = '<span class="database-excel-links">' + ''.join(links) + '</span>'
    if len(links) > 4:
        content = f'<details class="database-excel-years"><summary>Excel · {len(links)} files</summary>{content}</details>'
    return content


def _summary_html(app, docname, guide, profiles, *, compact=False):
    verified = [p for p in profiles if p.get("status") in {"parsed", "source_verified"} and p.get("parser_supported", True) and p["guide"] == guide]
    if not verified:
        return ""
    groups = geographic_groups(verified)
    if compact:
        return '<div class="database-profile-summary">' + ''.join(
            f'<div class="database-card-coverage"><p class="database-card-version">{html.escape(_version_title(group))}</p><p class="database-card-metrics">{_metrics_html(group)}</p></div>'
            for group in groups) + '</div>'
    compare = app.builder.get_relative_uri(docname, COMPARISONS) + "#geographical-coverage"
    parts = [f'<div class="database-guide-coverage"><div class="database-guide-coverage__header"><strong>Database coverage</strong><a href="{html.escape(compare)}">Compare databases</a></div>']
    for group in groups:
        years = sorted({str(year) for p in group for year in p.get("years", [p.get("year")]) if year}, key=int, reverse=True)
        year_label = _year_periods(years) if len(years) <= 5 else f"{len(years)} years ({_year_periods(years)})"
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


def _licence_html(guide, metadata):
    """Compact source rights near the introduction; do not infer missing licences."""
    entries=metadata['guides'].get(guide,[])
    if not entries:
        return ''
    parts=['<aside class="database-guide-licence" aria-label="Source data licence"><strong>Source licence</strong>']
    for entry in entries:
        label=html.escape(entry['label'])
        if entry.get('url'):
            label=f'<a href="{html.escape(entry["url"])}">{label} ↗</a>'
        parts.append(f'<p><span>{html.escape(entry["scope"])}</span> · {label}</p>')
    parts.append('<details><summary>Reuse &amp; attribution</summary>')
    for entry in entries:
        sources=' · '.join(f'<a href="{html.escape(url)}">Source {i+1} ↗</a>' for i,url in enumerate(entry.get('sources',[])))
        parts.append(f'<p>{html.escape(entry["note"])}{(" "+sources) if sources else ""}</p>')
    parts.append('</details></aside>')
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
    if guide and not any(doctree.findall(lambda node: isinstance(node,nodes.container) and "database-guide-rights" in node.get("classes",[]))):
        top=next(iter(doctree.findall(nodes.section)),None)
        metadata=json.loads((Path(app.srcdir)/LICENCES).read_text())
        if metadata.get('schema_version')!=1:
            raise ValueError('Unsupported database licence metadata')
        content=_licence_html(guide['id'],metadata)
        if content and top is not None:
            panel=nodes.container(classes=['database-guide-rights'])
            panel+=nodes.raw('',content,format='html')
            _insert_guide_summary(top,panel)
    if guide and not any(doctree.findall(lambda node: isinstance(node, nodes.container) and "database-guide-summary" in node.get("classes", []))):
        top = next(iter(doctree.findall(nodes.section)), None)
        if top is not None:
            content = _summary_html(app, docname, guide["id"], data["profiles"])
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
    return {"version": "1.2", "parallel_read_safe": True, "parallel_write_safe": True}
