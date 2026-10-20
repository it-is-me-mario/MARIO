"""Sphinx extension behind the MARIO documentation site.

It feeds the ``mario`` theme with the site structure (sections, tabs, sidebar,
hero and local table of contents), renders the filterable API index, writes
redirect pages for moved URLs and builds the navigation index used by the
Cmd+K search palette.

The structure lives in ``conf.py`` under ``mario_site``.
"""

from __future__ import annotations

import html
import importlib
import inspect
import json
import posixpath
import re
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from sphinx import addnodes
from sphinx.util import logging

logger = logging.getLogger(__name__)

_FIRST_H1 = re.compile(r"<h1>.*?</h1>\s*", re.S)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z`*])")


# --------------------------------------------------------------------------
# Toctree records: which documents each page lists, grouped by caption.
# --------------------------------------------------------------------------


def _holding_section(toctree: nodes.Node, doctree: nodes.document):
    """Section holding a toctree, unless it is the page's top section."""
    parent = toctree.parent
    while parent is not None and not isinstance(parent, nodes.section):
        parent = parent.parent
    if parent is None or parent.parent is doctree:
        return None
    return parent


def _section_heading(toctree: nodes.Node, doctree: nodes.document) -> str | None:
    """Title of the section holding a toctree, unless it is the page title."""
    section = _holding_section(toctree, doctree)
    if section is None:
        return None
    title = section.next_node(nodes.title)
    return title.astext() if title is not None else None


def _record_toctrees(app, doctree):
    env = app.env
    records = []
    for toctree in doctree.findall(addnodes.toctree):
        entries = [
            (title, ref)
            for title, ref in toctree["entries"]
            if ref in env.found_docs
        ]
        if not entries:
            continue
        section = _holding_section(toctree, doctree)
        records.append(
            {
                "caption": toctree.get("caption") or _section_heading(toctree, doctree),
                "anchor": section["ids"][0] if section is not None and section["ids"] else "",
                "entries": entries,
            }
        )
    if not hasattr(env, "mario_toctrees"):
        env.mario_toctrees = {}
    env.mario_toctrees[env.docname] = records


def _purge_doc(app, env, docname):
    getattr(env, "mario_toctrees", {}).pop(docname, None)


def _merge_info(app, env, docnames, other):
    if not hasattr(env, "mario_toctrees"):
        env.mario_toctrees = {}
    env.mario_toctrees.update(getattr(other, "mario_toctrees", {}))


def _toc_groups(env, docname, caption=None):
    groups = getattr(env, "mario_toctrees", {}).get(docname, [])
    if caption is not None:
        groups = [group for group in groups if group["caption"] == caption]
    return groups


def _doc_title(env, docname, explicit=None):
    if explicit:
        return explicit
    title = env.titles.get(docname)
    return title.astext() if title is not None else docname


# --------------------------------------------------------------------------
# Page context
# --------------------------------------------------------------------------


def _matches(pagename, doc=None, prefixes=()):
    return pagename == doc or any(pagename.startswith(prefix) for prefix in prefixes)


def _find_section(config, pagename):
    for section in config["sections"]:
        if _matches(pagename, section["landing"], section.get("prefixes", ())):
            return section
    return None


def _active_tab(section, pagename):
    for tab in section.get("tabs", []):
        if _matches(pagename, tab["doc"], tab.get("prefixes", ())):
            return tab
    return None


def _descendants(env, docname, seen=None):
    seen = set() if seen is None else seen
    for group in _toc_groups(env, docname):
        for _, ref in group["entries"]:
            if ref not in seen:
                seen.add(ref)
                _descendants(env, ref, seen)
    return seen


def _sidebar(app, pagename, tab):
    """Sidebar groups for one Docs tab: [{caption, items: [{title, url, ...}]}]."""
    env = app.env
    toc = tab.get("toc")
    if not toc:
        return []

    max_depth = toc.get("max_depth", 1)

    def item(title, ref, depth):
        open_ = ref == pagename or pagename in _descendants(env, ref)
        children = []
        if depth < max_depth and (tab.get("expand") or open_):
            for group in _toc_groups(env, ref):
                children.append(
                    {
                        "caption": group["caption"],
                        "items": [item(t, r, depth + 1) for t, r in group["entries"]],
                    }
                )
        return {
            "title": _doc_title(env, ref, title),
            "url": app.builder.get_relative_uri(pagename, ref),
            "active": ref == pagename,
            "open": open_,
            "children": children,
        }

    groups = [
        {"caption": group["caption"] if toc.get("show_caption") else None,
         "items": [item(t, r, 0) for t, r in group["entries"]]}
        for group in _toc_groups(env, toc["doc"], toc.get("caption"))
    ]
    if toc.get("overview"):
        overview = {
            "title": toc["overview"],
            "url": app.builder.get_relative_uri(pagename, toc["doc"]),
            "active": pagename == toc["doc"],
            "open": False,
            "children": [],
        }
        groups.insert(0, {"caption": None, "items": [overview]})
    return groups


def _local_toc(env, pagename, max_depth=2):
    """Headings of the page below its title: [{title, anchor, children}]."""
    toc = env.tocs.get(pagename)
    if toc is None or not len(toc):
        return []

    def entries(bullet_list, depth):
        result = []
        for list_item in bullet_list.children:
            if not isinstance(list_item, nodes.list_item):
                continue
            reference = list_item.next_node(nodes.reference)
            if reference is None:
                continue
            children = []
            if depth < max_depth:
                for child in list_item.children:
                    if isinstance(child, nodes.bullet_list):
                        children = entries(child, depth + 1)
            result.append(
                {
                    "title": reference.astext(),
                    "anchor": reference.get("anchorname") or "#",
                    "children": children,
                }
            )
        return result

    top_items = [child for child in toc.children if isinstance(child, nodes.list_item)]
    if not top_items:
        return []
    headings = []
    for child in top_items[0].children:
        if isinstance(child, nodes.bullet_list):
            headings = entries(child, 1)
    # Notebooks can hold more than one top-level heading: keep the others too.
    for extra in top_items[1:]:
        reference = extra.next_node(nodes.reference)
        if reference is not None:
            headings.append({"title": reference.astext(), "anchor": reference.get("anchorname") or "#", "children": []})
    return headings


def _page_context(app, pagename, templatename, context, doctree):
    config = app.config.mario_site
    env = app.env
    builder = app.builder

    def url(docname):
        return builder.get_relative_uri(pagename, docname)

    nav = [
        {
            "key": section["key"],
            "label": section["label"],
            "home_label": section.get("home_label", section["label"]),
            "summary": section.get("home_summary", ""),
            "url": url(section["landing"]),
            "active": _matches(pagename, section["landing"], section.get("prefixes", ())),
            "children": [
                {"label": tab["label"], "url": url(tab["doc"]), "summary": tab.get("summary", ""),
                 "featured": tab.get("featured", False),
                 "active": _matches(pagename, tab["doc"], tab.get("prefixes", ())),
                 "exact": pagename == tab["doc"]}
                for tab in section.get("tabs", [])
            ],
        }
        for section in config["sections"] if section.get("navigation", True)
    ]

    page = {
        "section_label": "",
        "nav": nav,
        "layout": "plain",
        "section_key": "",
        "group_key": "",
        "hero": {"title": context.get("title", ""), "text": "", "install": False},
        "tabs": [],
        "sidebar": [],
        "sidebar_label": "",
        "local_toc": [],
        "home_url": url(app.config.root_doc),
        "github": config.get("github", ""),
        "pypi": config.get("pypi", ""),
        "install": config.get("install", ""),
        "ai_notice": config.get("ai_notice", ""),
        "closing": None,
    }

    section = _find_section(config, pagename)
    if pagename == app.config.root_doc:
        page["layout"] = "home"
        page["hero"] = dict(config["home_hero"])
    elif section is not None:
        page["section_key"] = section["key"]
        page["section_label"] = section["label"]
        tab = _active_tab(section, pagename)
        page["tabs"] = [
            {
                "label": item["label"],
                "url": url(item["doc"]),
                "active": item is tab,
                "key": item.get("key", ""),
                "children": [{"label": child["label"], "url": url(child["doc"]),
                              "active": _matches(pagename, child["doc"], child.get("prefixes", ()))}
                             for child in item.get("children", [])],
            }
            for item in section.get("tabs", [])
        ]
        hero = dict(section.get("hero", {}))
        if section.get("sidebar") and pagename != section["landing"] and tab is not None:
            page["layout"] = "docs"
            page["group_key"] = tab.get("key", "")
            page["sidebar"] = _sidebar(app, pagename, tab)
            page["sidebar_label"] = tab["label"]
            page["hero"] = {"title": context.get("title", ""), "text": "", "install": False}
        else:
            page["layout"] = "tabs"
            page["group_key"] = (tab or {}).get("key", "")
            page["hero"] = hero
    page["hero"].setdefault("text", "")
    page["hero"].setdefault("install", False)

    if page["layout"] in {"docs", "plain", "home"} and "body" in context:
        context["body"] = _FIRST_H1.sub("", context["body"], count=1)

    if doctree is not None and page["layout"] != "home":
        page["local_toc"] = _local_toc(env, pagename)

    closing = config.get("closings", {}).get(pagename)
    if closing:
        page["closing"] = {"text": closing["text"], "url": url(closing["doc"]) if closing.get("doc") else "",
                           "dialog": closing.get("dialog")}

    context["mario_page"] = page
    if pagename in {"resources/data-explorer/compare", "resources/data-explorer/scope", "resources/data-explorer/analyses"}:
        app.add_css_file("economy-browser.css")
    if pagename == "resources/data-explorer/scope":
        app.add_css_file("database-scope.css")
        app.add_js_file("scope-tabs.js", defer="defer")
        app.add_js_file("database-scope.js", defer="defer")
        app.add_css_file("extension-scope.css")
        app.add_js_file("extension-scope.js", defer="defer")
    if pagename == "resources/data-explorer/compare":
        for script in ("economy-model.js", "economy-charts.js", "economy-browser.js"):
            app.add_js_file(script, defer="defer")


# --------------------------------------------------------------------------
# Line icons (24x24, stroke only): coloured with currentColor by the theme
# --------------------------------------------------------------------------

MARIO_ICONS = {
    # Docs groups
    "parsers": '<ellipse cx="12" cy="5" rx="7" ry="2.5"/><path d="M5 5v14c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V5"/><path d="M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5"/>',
    "inspection": '<circle cx="11" cy="11" r="6.5"/><path d="m20.5 20.5-4.9-4.9"/>',
    "transformations": '<path d="M4 7.5h14.5l-3.5-3.5"/><path d="M20 16.5H5.5l3.5 3.5"/>',
    "advanced": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><path d="M10 6.5h4.5a3 3 0 0 1 3 3V14"/>',
    "api": '<path d="m8 7-5 5 5 5"/><path d="m16 7 5 5-5 5"/><path d="m13.5 4-3 16"/>',
    "changelog": '<path d="M3 12a9 9 0 1 0 2.6-6.4L3 8"/><path d="M3 3v5h5"/><path d="M12 7.5V12l3 2"/>',
    # Inspection guides
    "table-search": '<rect x="3" y="3" width="13" height="13" rx="1.5"/><path d="M3 8h13M8 3v13"/><circle cx="17.5" cy="17.5" r="3"/><path d="m21.5 21.5-1.9-1.9"/>',
    "compute": '<rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><path d="M14.5 10h6.5M14.5 14h6.5"/>',
    "chart": '<path d="M3 21h18"/><path d="M6.5 17v-6M12 17V5M17.5 17v-9"/>',
    "tag": '<path d="M3 11.5V4a1 1 0 0 1 1-1h7.5l9.5 9.5-8.5 8.5z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    "export": '<path d="M14 3h7v7"/><path d="m21 3-9.5 9.5"/><path d="M18 14v5.5a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 3 19.5v-12A1.5 1.5 0 0 1 4.5 6H10"/>',
    # Transformation guides
    "merge": '<path d="M4 4l8 8M4 20l8-8"/><path d="M12 12h8.5"/><path d="m17 8.5 3.5 3.5-3.5 3.5"/>',
    "add-rows": '<rect x="3" y="3" width="14" height="13" rx="1.5"/><path d="M3 7.5h14M3 12h14"/><path d="M20 15.5v6M17 18.5h6"/>',
    "bolt": '<path d="M13 2 4.5 13.5h7L10.5 22 19.5 10h-7z"/>',
    "split": '<path d="M12 21.5V13"/><path d="M12 13 5.5 6.5M12 13l6.5-6.5"/><path d="M5 10.5v-4h4M19 10.5v-4h-4"/>',
    "convert": '<rect x="2.5" y="3" width="7" height="7.5" rx="1.5"/><rect x="2.5" y="13.5" width="7" height="7.5" rx="1.5"/><path d="M11.5 12h4.5"/><path d="m14 9.5 2.5 2.5-2.5 2.5"/><rect x="17.5" y="7.5" width="4" height="9" rx="1.2"/>',
    "pin": '<path d="M12 21.5s-6.5-5.8-6.5-11.5a6.5 6.5 0 0 1 13 0c0 5.7-6.5 11.5-6.5 11.5z"/><circle cx="12" cy="10" r="2.3"/>',
    "swap": '<path d="M7.5 20.5V4"/><path d="m4 7.5 3.5-3.5L11 7.5"/><path d="M16.5 3.5V20"/><path d="m13 16.5 3.5 3.5 3.5-3.5"/>',
    # Advanced guides
    "power": '<circle cx="12" cy="12" r="9"/><path d="m13 6.5-4 6.5h4.5L11 18"/>',
    "cloud": '<path d="M7 18.5h10.5a4 4 0 0 0 .3-8 6 6 0 0 0-11.6 1.6A3.5 3.5 0 0 0 7 18.5z"/>',
    "chain": '<path d="M10 14a4.2 4.2 0 0 0 6 0l3-3a4.2 4.2 0 0 0-6-6l-1 1"/><path d="M14 10a4.2 4.2 0 0 0-6 0l-3 3a4.2 4.2 0 0 0 6 6l1-1"/>',
    "paths": '<circle cx="5" cy="12" r="2.2"/><circle cx="19" cy="5" r="2.2"/><circle cx="19" cy="12" r="2.2"/><circle cx="19" cy="19" r="2.2"/><path d="M7.2 12h9.6M7 11l10-5M7 13l10 5"/>',
}


def _icon_svg(name):
    body = MARIO_ICONS.get(name)
    if body is None:
        raise ValueError(f"Unknown MARIO icon {name!r}; available: {sorted(MARIO_ICONS)}")
    return f'<svg class="mario-line-icon" viewBox="0 0 24 24" aria-hidden="true">{body}</svg>'


# --------------------------------------------------------------------------
# Cards: a grid of short, titled blocks
# --------------------------------------------------------------------------


class MarioCards(Directive):
    """Grid of ``mario-card`` blocks.

    .. code-block:: rst

       .. mario-cards::
          :columns: 2

          .. mario-card:: Database
             :kicker: mario.Database

             The object you work with.
    """

    has_content = True
    option_spec = {
        "columns": directives.positive_int,
        "links": directives.flag,
        "class": directives.class_option,
    }

    def run(self):
        grid = nodes.container(classes=["mario-cards", *self.options.get("class", [])])
        if "links" in self.options:
            grid["classes"].append("mario-cards--links")
        columns = self.options.get("columns")
        if columns:
            grid["classes"].append(f"mario-cards--{columns}")
        self.state.nested_parse(self.content, self.content_offset, grid)
        return [grid]


class MarioCard(Directive):
    """One card: a title, an optional code kicker and free content."""

    required_arguments = 1
    final_argument_whitespace = True
    has_content = True
    option_spec = {
        "kicker": directives.unchanged,
        "wide": directives.flag,
        "logo": directives.unchanged,
        "monogram": directives.unchanged,
        "database": directives.unchanged,
        "icon": directives.unchanged,
        "class": directives.class_option,
    }

    def run(self):
        card = nodes.container(classes=["mario-card", *self.options.get("class", [])])
        if "wide" in self.options:
            card["classes"].append("mario-card--wide")
        header = nodes.container(classes=["mario-card__header"])
        logo, monogram, icon = self.options.get("logo"), self.options.get("monogram"), self.options.get("icon")
        if logo or monogram or icon:
            # A logo (or a text tile when a source has none) sits beside the title.
            card["classes"].append("mario-card--logo")
            tile = nodes.container(classes=["mario-card__logo"])
            if icon:
                tile["classes"].append("is-icon")
                tile += nodes.raw("", _icon_svg(icon), format="html")
            elif logo:
                uris = logo.split()
                if len(uris) > 1:
                    tile["classes"].append("is-multi")
                for uri in uris:
                    tile += nodes.image(uri=uri, alt="")
            else:
                tile["classes"].append("is-monogram")
                tile += nodes.inline(monogram, monogram)
            header += tile
            heading = nodes.container(classes=["mario-card__heading"])
            header += heading
        else:
            heading = header
        title_nodes, messages = self.state.inline_text(self.arguments[0], self.lineno)
        heading += nodes.paragraph("", "", *title_nodes, classes=["mario-card__title"])
        kicker = self.options.get("kicker")
        if kicker:
            heading += nodes.paragraph("", "", nodes.literal(kicker, kicker), classes=["mario-card__kicker"])
        card += header
        body = nodes.container(classes=["mario-card__body"])
        self.state.nested_parse(self.content, self.content_offset, body)
        if self.options.get("database"):
            from mario_database_profiles import database_profile_summary
            summary = database_profile_summary("")
            summary["guide"] = self.options["database"]
            body += summary
        card += body
        return [card, *messages]


class MarioSteps(Directive):
    """Rows with a short label on the left and the content on the right.

    .. code-block:: rst

       .. mario-steps::

          .. mario-step:: Inspect

             Content of the row.
    """

    has_content = True

    def run(self):
        steps = nodes.container(classes=["mario-steps"])
        self.state.nested_parse(self.content, self.content_offset, steps)
        return [steps]


class MarioStep(Directive):
    required_arguments = 1
    final_argument_whitespace = True
    has_content = True

    def run(self):
        step = nodes.container(classes=["mario-step"])
        label_nodes, messages = self.state.inline_text(self.arguments[0], self.lineno)
        step += nodes.paragraph("", "", *label_nodes, classes=["mario-step__label"])
        body = nodes.container(classes=["mario-step__body"])
        self.state.nested_parse(self.content, self.content_offset, body)
        step += body
        return [step, *messages]


# --------------------------------------------------------------------------
# Switch: big buttons that show one group of sections at a time
# --------------------------------------------------------------------------

_BLOCK_FAMILY = {"Z": "core", "U": "core", "S": "core", "Y": "demand", "V": "factors", "E": "satellite"}


def _blocks_html(spec):
    """Mini block diagram: rows split by "/", cells by spaces, "." for an empty cell.

    The last cell of each row is the final-demand column and sits slightly apart.
    """
    esc = html.escape
    rows = [row.split() for row in spec.split("/")]
    width = max(len(row) for row in rows)
    cells = []
    for row in rows:
        row = row + ["."] * (width - len(row))
        for index, name in enumerate(row):
            classes = ["mario-blocks__cell"]
            if index == width - 1:
                classes.append("is-final")
            if name == ".":
                classes.append("is-empty")
                cells.append(f'<span class="{" ".join(classes)}"></span>')
            else:
                classes.append(f"is-{_BLOCK_FAMILY.get(name[0].upper(), 'core')}")
                cells.append(f'<span class="{" ".join(classes)}">{esc(name)}</span>')
    return (
        f'<span class="mario-blocks" aria-hidden="true" style="--blocks-columns: {width}">'
        + "".join(cells)
        + "</span>"
    )


def _scheme_panel_html(title, spec, col_sizes, row_sizes, coefficients=False):
    """One scheme panel: a CSS grid whose tracks keep the real block proportions."""
    esc = html.escape
    rows = [row.split() for row in spec.split("/")]
    width = max(len(row) for row in rows)
    cols = col_sizes[:width]
    units_w, units_h = sum(cols), sum(row_sizes[: len(rows)])
    cells = []
    for row in rows:
        row = row + ["."] * (width - len(row))
        families = {_BLOCK_FAMILY.get(name[0].upper(), "core") for name in row if name != "."}
        account_row = "core" not in families and "demand" not in families
        for index, name in enumerate(row):
            classes = ["mario-scheme__cell"]
            if index == width - 1 and width == len(col_sizes):
                classes.append("is-final")
            if account_row:
                classes.append("is-account")
            if name == ".":
                classes.append("is-empty")
                cells.append(f'<span class="{" ".join(classes)}"></span>')
                continue
            classes.append(f"is-{_BLOCK_FAMILY.get(name[0].upper(), 'core')}")
            cells.append(f'<span class="{" ".join(classes)}">{esc(name)}</span>')
    style = (
        f"--scheme-units: {units_w:g}; "
        f"grid-template-columns: {' '.join(f'{size:g}fr' for size in cols)}; "
        f"grid-template-rows: {' '.join(f'{size:g}fr' for size in row_sizes[: len(rows)])}; "
        f"aspect-ratio: {units_w:g} / {units_h:g}"
    )
    kind = " mario-scheme__panel--coefficients" if coefficients else ""
    return (
        f'<div class="mario-scheme__panel{kind}" style="--scheme-units: {units_w:g}">'
        f'<p class="mario-scheme__title">{esc(title)}</p>'
        f'<div class="mario-scheme__grid" style="{style}">{"".join(cells)}</div>'
        "</div>"
    )


class MarioScheme(Directive):
    """Block diagram of a table format: flows next to coefficients, drawn in HTML.

    Options use the same block syntax as ``mario-switch-option`` (rows split by
    "/", cells by spaces, "." for an empty cell). ``col-sizes`` and
    ``row-sizes`` are relative sizes of the flow grid tracks; the coefficient
    grid reuses them. The content becomes the caption.
    """

    required_arguments = 1
    final_argument_whitespace = True
    has_content = True
    option_spec = {
        "flows": directives.unchanged_required,
        "coefficients": directives.unchanged,
        "col-sizes": directives.unchanged_required,
        "row-sizes": directives.unchanged_required,
    }

    def run(self):
        esc = html.escape
        col_sizes = [float(value) for value in self.options["col-sizes"].split()]
        row_sizes = [float(value) for value in self.options["row-sizes"].split()]
        panels = [_scheme_panel_html("Flows", self.options["flows"], col_sizes, row_sizes)]
        if self.options.get("coefficients"):
            panels.append(
                _scheme_panel_html("Coefficients", self.options["coefficients"], col_sizes, row_sizes, coefficients=True)
            )
        max_units = sum(col_sizes)
        figure = nodes.container(classes=["mario-scheme"])
        figure += nodes.raw(
            "",
            f'<div class="mario-scheme__panels" role="img" aria-label="{esc(self.arguments[0])}" '
            f'style="--scheme-max-units: {max_units:g}">' + "".join(panels) + "</div>",
            format="html",
        )
        if self.content:
            caption = nodes.container(classes=["mario-scheme__caption"])
            self.state.nested_parse(self.content, self.content_offset, caption)
            figure += caption
        return [figure]


class MarioSwitchOption(Directive):
    """One big button of a ``mario-switch``; arguments are the ids it reveals."""

    required_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        "badge": directives.unchanged,
        "title": directives.unchanged_required,
        "text": directives.unchanged,
        "blocks": directives.unchanged,
        "chips": directives.unchanged,
    }

    def run(self):
        esc = html.escape
        targets = self.arguments[0].split()
        options = self.options
        chips = [chip.strip() for chip in options.get("chips", "").split(",") if chip.strip()]
        parts = ['<span class="mario-switch__copy">']
        if options.get("badge"):
            parts.append(f'<span class="mario-switch__badge">{esc(options["badge"])}</span>')
        parts.append(f'<span class="mario-switch__title">{esc(options["title"])}</span>')
        if options.get("text"):
            parts.append(f'<span class="mario-switch__text">{esc(options["text"])}</span>')
        if chips:
            parts.append(
                '<span class="mario-switch__chips">'
                + "".join(f'<span class="mario-switch__chip">{esc(chip)}</span>' for chip in chips)
                + "</span>"
            )
        parts.append("</span>")
        if options.get("blocks"):
            parts.append(_blocks_html(options["blocks"]))
        markup = (
            f'<button type="button" class="mario-switch__option" aria-pressed="false" '
            f'data-switch-targets="{esc(" ".join(targets))}">' + "".join(parts) + "</button>"
        )
        return [nodes.raw("", markup, format="html")]


class MarioSwitch(Directive):
    """Row of big buttons; each shows its own sections and hides the others.

    Without JavaScript the buttons are hidden and every section stays visible.
    """

    has_content = True
    option_spec = {"label": directives.unchanged, "hint": directives.unchanged}

    def run(self):
        esc = html.escape
        label = self.options.get("label", "Choose a section")
        hint = self.options.get("hint", "")
        wrapper = nodes.container(classes=["mario-switch"])
        wrapper += nodes.raw(
            "",
            f'<div class="mario-switch__options" role="group" aria-label="{esc(label)}" data-switch>',
            format="html",
        )
        self.state.nested_parse(self.content, self.content_offset, wrapper)
        wrapper += nodes.raw("", "</div>", format="html")
        if hint:
            wrapper += nodes.raw("", f'<p class="mario-switch__hint" data-switch-hint>{esc(hint)}</p>', format="html")
        return [wrapper]


# --------------------------------------------------------------------------
# Docs overview: one card per group, generated from the group landing pages
# --------------------------------------------------------------------------


class mario_docs_overview(nodes.General, nodes.Element):
    pass


class MarioDocsOverview(Directive):
    """Cards for the Docs groups (the Docs tabs in ``mario_site``)."""

    has_content = False
    option_spec = {"max-items": directives.positive_int}

    def run(self):
        node = mario_docs_overview("")
        node["max_items"] = self.options.get("max-items", 6)
        return [node]


def _render_docs_overview(app, doctree, fromdocname):
    placeholders = list(doctree.findall(mario_docs_overview))
    if not placeholders:
        return
    env = app.env
    esc = html.escape
    docs = next((section for section in app.config.mario_site["sections"] if section.get("sidebar")), None)
    if docs is None:
        return
    for placeholder in placeholders:
        cards = []
        for tab in docs.get("tabs", []):
            limit = placeholder["max_items"]
            root = (tab.get("toc") or {}).get("doc", tab["doc"])
            url = app.builder.get_relative_uri(fromdocname, tab["doc"])
            groups = _toc_groups(env, root)
            captioned = [group for group in groups if group["caption"]]
            if not groups:
                links = [(f"{url}{heading['anchor']}", heading["title"], None) for heading in _local_toc(env, root)]
            elif captioned:
                links = [
                    (
                        f"{url}#{group['anchor']}" if group["anchor"] else url,
                        group["caption"],
                        len(group["entries"]),
                    )
                    for group in captioned
                ]
            else:
                links = [
                    (app.builder.get_relative_uri(fromdocname, ref), _doc_title(env, ref, title), None)
                    for group in groups
                    for title, ref in group["entries"]
                ]
            if len(links) <= limit + 1:
                limit = len(links)
            more = len(links) - limit
            items = "".join(
                f'<li><a href="{esc(href)}">{esc(label)}</a>'
                + (f' <span class="mario-docs-card__count">{count}</span>' if count else "")
                + "</li>"
                for href, label, count in links[:limit]
            )
            if more > 0:
                items += f'<li class="mario-docs-card__more"><a href="{esc(url)}">and {more} more</a></li>'
            summary = tab.get("summary", "")
            cards.append(
                f'<article class="mario-docs-card" data-group="{esc(tab.get("key", ""))}">'
                f'<h2 class="mario-docs-card__title">'
                + (f'<span class="mario-docs-card__icon">{_icon_svg(tab["icon"])}</span>' if tab.get("icon") else "")
                + f'<a href="{esc(url)}">{esc(tab["label"])}</a></h2>'
                + (f'<p class="mario-docs-card__summary">{esc(summary)}</p>' if summary else "")
                + f'<ul class="mario-docs-card__list">{items}</ul>'
                + "</article>"
            )
        markup = '<div class="mario-docs-overview">' + "".join(cards) + "</div>"
        placeholder.replace_self(nodes.raw("", markup, format="html"))


# --------------------------------------------------------------------------
# Publications: citation box and publication list, read from a .bib file
# --------------------------------------------------------------------------

_LATEX_REPLACEMENTS = {r"\&": "&", "--": "–", "{": "", "}": ""}


def _bib_text(value):
    value = str(value)
    if "\\" in value:
        import codecs

        import latexcodec  # noqa: F401  (registers the "ulatex" codec; ships with pybtex)

        value = codecs.decode(value, "ulatex")
    for old, new in _LATEX_REPLACEMENTS.items():
        value = value.replace(old, new)
    return " ".join(value.split())


def _bib_people(entry):
    names = []
    for person in entry.persons.get("author", []):
        first = " ".join(person.first_names + person.middle_names)
        last = " ".join(person.prelast_names + person.last_names)
        names.append(_bib_text(f"{first} {last}".strip()))
    return names


def _bib_initials(entry):
    """APA-like author list: Last, F. M."""
    names = []
    for person in entry.persons.get("author", []):
        last = _bib_text(" ".join(person.prelast_names + person.last_names))
        initials = " ".join(f"{_bib_text(name)[0]}." for name in person.first_names + person.middle_names if _bib_text(name))
        names.append(f"{last}, {initials}".strip(", "))
    if len(names) > 1:
        return ", ".join(names[:-1]) + ", & " + names[-1]
    return names[0] if names else ""


def _bib_doi_url(entry):
    doi = _bib_text(entry.fields.get("doi", ""))
    if not doi:
        return _bib_text(entry.fields.get("url", ""))
    return doi if doi.startswith("http") else f"https://doi.org/{doi}"


def _bib_venue(entry):
    venue = _bib_text(entry.fields.get("journal", entry.fields.get("booktitle", "")))
    volume = _bib_text(entry.fields.get("volume", ""))
    issue = _bib_text(entry.fields.get("number", entry.fields.get("issue", "")))
    if volume:
        venue += f" · {volume}" + (f"({issue})" if issue else "")
    return venue


def _load_bib(directive, path):
    from pybtex.database import parse_file

    env = directive.state.document.settings.env
    rel, absolute = env.relfn2path(path, env.docname)
    env.note_dependency(rel)
    return parse_file(absolute)


class MarioCitation(Directive):
    """How to cite: formatted reference, DOI link and the BibTeX entry to copy."""

    required_arguments = 1
    option_spec = {"bib": directives.unchanged_required}

    def run(self):
        from pybtex.database import BibliographyData

        esc = html.escape
        key = self.arguments[0]
        bib = _load_bib(self, self.options["bib"])
        entry = bib.entries[key]
        url = _bib_doi_url(entry)
        reference = (
            f"{esc(_bib_initials(entry))} ({esc(_bib_text(entry.fields.get('year', '')))}). "
            f"<strong>{esc(_bib_text(entry.fields.get('title', '')))}</strong>. "
            f"<em>{esc(_bib_venue(entry))}</em>."
        )
        box = nodes.container(classes=["mario-cite"])
        box += nodes.raw(
            "",
            f'<p class="mario-cite__reference">{reference}</p>'
            f'<p class="mario-cite__actions"><a class="mario-cite__doi" href="{esc(url)}">{esc(url.replace("https://", ""))}</a></p>'
            '<details class="mario-cite__bibtex"><summary>BibTeX</summary>',
            format="html",
        )
        single = BibliographyData(entries={key: entry})
        bibtex = single.to_string("bibtex").strip()
        block = nodes.literal_block(bibtex, bibtex)
        block["language"] = "bibtex"
        box += block
        box += nodes.raw("", "</details>", format="html")
        return [box]


class MarioPublications(Directive):
    """Publications grouped by year, newest first, from a .bib file."""

    option_spec = {
        "bib": directives.unchanged_required,
        "exclude": directives.unchanged,
        "code": directives.unchanged,
        "cite": directives.unchanged,
        "count": directives.flag,
    }

    def run(self):
        esc = html.escape
        bib = _load_bib(self, self.options["bib"])
        exclude = set(self.options.get("exclude", "").split())
        citation_key = self.options.get("cite", "").strip()
        if citation_key and citation_key not in bib.entries:
            raise self.error(f"Unknown citation key: {citation_key}")
        code_links = dict(
            item.split("=", 1) for item in self.options.get("code", "").split() if "=" in item
        )
        entries = [(key, entry) for key, entry in bib.entries.items() if key not in exclude]
        if "count" in self.options:
            title = next((node for node in self.state.parent.children if isinstance(node, nodes.title)), None)
            if title is None:
                raise self.error("The count option requires a containing section title")
            title += nodes.Text(f" ({len(entries)})")

        def sort_key(item):
            fields = item[1].fields
            year = int(_bib_text(fields.get("year", "0")) or 0)
            month = int(_bib_text(fields.get("month", "0")) or 0) if _bib_text(fields.get("month", "0")).isdigit() else 0
            return (-year, -month, _bib_text(fields.get("title", "")))

        years = {}
        for key, entry in sorted(entries, key=sort_key):
            years.setdefault(_bib_text(entry.fields.get("year", "")), []).append((key, entry))

        parts = ['<div class="mario-pubs">']
        for year, items in years.items():
            parts.append(f'<section class="mario-pubs__year"><p class="mario-pubs__year-label">{esc(year)}</p><div class="mario-pubs__list">')
            for key, entry in items:
                url = _bib_doi_url(entry)
                links = [f'<a href="{esc(url)}">DOI</a>'] if url else []
                if key in code_links:
                    links.append(f'<a href="{esc(code_links[key])}">Code</a>')
                citation = (
                    '<p class="mario-pub__citation">Cite this paper when using MARIO.</p>'
                    if key == citation_key else ""
                )
                parts.append(
                    f'<article class="mario-pub" id="pub-{esc(key.lower())}">'
                    + citation
                    + f'<p class="mario-pub__venue">{esc(_bib_venue(entry))}</p>'
                    f'<p class="mario-pub__title"><a href="{esc(url)}">{esc(_bib_text(entry.fields.get("title", "")))}</a></p>'
                    f'<p class="mario-pub__authors">{esc(", ".join(_bib_people(entry)))}</p>'
                    + (f'<p class="mario-pub__links">{"".join(links)}</p>' if links else "")
                    + "</article>"
                )
            parts.append("</div></section>")
        parts.append("</div>")
        return [nodes.raw("", "".join(parts), format="html")]


# --------------------------------------------------------------------------
# Notebook downloads: every downloadable guide notebook, grouped like Docs
# --------------------------------------------------------------------------


def _notebook_title(path):
    try:
        cells = json.loads(Path(path).read_text(encoding="utf-8"))["cells"]
    except (OSError, ValueError, KeyError):
        return None
    for cell in cells:
        if cell.get("cell_type") != "markdown":
            continue
        match = re.search(r"^#\s+(.+?)\s*$", "".join(cell.get("source", [])), re.M)
        if match:
            return match.group(1).replace("`", "")
    return None


class MarioNotebookDownloads(Directive):
    """Lists the notebooks configured in ``mario_notebook_downloads``, grouped by Docs tab."""

    has_content = False

    def run(self):
        env = self.state.document.settings.env
        app = env.app
        config = app.config.mario_notebook_downloads
        prefixes = tuple(config.get("prefixes", ()))
        pages = set(config.get("pages", ()))
        docs = [
            docname
            for docname in env.found_docs
            if (docname.startswith(prefixes) or docname in pages)
            and str(env.doc2path(docname)).endswith(".ipynb")
        ]
        section = next((item for item in app.config.mario_site["sections"] if item.get("sidebar")), None)
        tabs = section.get("tabs", []) if section else []

        wrapper = nodes.container(classes=["mario-downloads"])
        for tab in tabs:
            members = [docname for docname in docs if _matches(docname, tab["doc"], tab.get("prefixes", ()))]
            if not members:
                continue
            titled = sorted(
                ((_notebook_title(env.doc2path(docname)) or docname.split("/")[-1], docname) for docname in members),
                key=lambda item: item[0].casefold(),
            )
            group = nodes.container(classes=["mario-downloads__group"])
            group["classes"].append(f"is-{tab.get('key', '')}")
            group += nodes.paragraph("", tab["label"], classes=["mario-downloads__caption"])
            items = nodes.bullet_list(classes=["mario-downloads__list"])
            items["mario_toc_doc"] = (tab.get("toc") or {}).get("doc", tab["doc"])
            for title, docname in titled:
                download = addnodes.download_reference(
                    "",
                    "",
                    nodes.inline(title, title, classes=["mario-notebook-title"]),
                    reftarget="/" + str(env.doc2path(docname, False)),
                    refdoc=env.docname,
                    refdomain="",
                    reftype="download",
                    refexplicit=True,
                )
                paragraph = nodes.paragraph("", "", download)
                item = nodes.list_item("", paragraph)
                item["mario_doc"] = docname
                items += item
            group += items
            wrapper += group
        return [wrapper]


def _finish_notebook_downloads(app, doctree, fromdocname):
    """Once every page is read: use the guide titles and the order of the Docs sidebar."""
    env = app.env
    for listing in doctree.findall(nodes.bullet_list):
        if "mario-downloads__list" not in listing["classes"]:
            continue
        order, titles = {}, {}
        for group in _toc_groups(env, listing.get("mario_toc_doc", "")):
            for title, ref in group["entries"]:
                order.setdefault(ref, len(order))
                if title:
                    titles.setdefault(ref, title)
        items = [child for child in listing.children if isinstance(child, nodes.list_item)]
        for item in items:
            docname = item.get("mario_doc")
            title = titles.get(docname) or _doc_title(env, docname)
            # Each item holds one link: the notebook download.
            link = next(iter(item.findall(addnodes.download_reference)), None)
            if link is not None:
                link.children = []
                link += nodes.inline(title, title, classes=["mario-notebook-title"])
        items.sort(key=lambda item: order.get(item.get("mario_doc"), len(order)))
        listing.children = []
        for item in items:
            listing += item


# --------------------------------------------------------------------------
# API index directive
# --------------------------------------------------------------------------


class mario_api_index(nodes.General, nodes.Element):
    pass


class MarioApiIndex(Directive):
    """Placeholder replaced by the filterable table of API entries."""

    has_content = False

    def run(self):
        return [mario_api_index("")]


def _resolve_object(dotted):
    parts = dotted.split(".")
    for split in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:split]))
        except ImportError:
            continue
        try:
            for attribute in parts[split:]:
                obj = getattr(obj, attribute)
        except AttributeError:
            return None
        return obj
    return None


def _summary(dotted):
    obj = _resolve_object(dotted)
    if obj is None:
        return ""
    if isinstance(obj, property):
        obj = obj.fget
    doc = inspect.getdoc(obj) or ""
    paragraph = doc.strip().split("\n\n", 1)[0].replace("\n", " ").strip()
    first = _SENTENCE_END.split(paragraph, 1)[0]
    return first.replace("``", "")


def _api_rows(app):
    env = app.env
    root = app.config.mario_site.get("api_root", "reference/api_library")
    rows, seen = [], set()
    categories = []
    for group in _toc_groups(env, root):
        for title, category_doc in group["entries"]:
            category = _doc_title(env, category_doc, title).split(" and ")[0].strip()
            count = 0
            for sub in _toc_groups(env, category_doc):
                for method_title, method_doc in sub["entries"]:
                    if method_doc in seen or not method_doc.startswith("api_document/"):
                        continue
                    seen.add(method_doc)
                    name = _doc_title(env, method_doc, method_title)
                    summary = _summary(name)
                    if not summary:
                        # Named matrix blocks are resolved dynamically on a
                        # database, rather than defined as class attributes.
                        paragraph = next(
                            iter(env.get_doctree(method_doc).findall(nodes.paragraph)),
                            None,
                        )
                        if paragraph is not None:
                            summary = _SENTENCE_END.split(paragraph.astext(), 1)[0]
                    rows.append(
                        {
                            "name": name,
                            "doc": method_doc,
                            "category": category,
                            "group": sub["caption"] or "",
                            "summary": summary,
                        }
                    )
                    count += 1
            categories.append((category, count))
    return rows, categories


def _render_api_index(app, doctree, fromdocname):
    placeholders = list(doctree.findall(mario_api_index))
    if not placeholders:
        return
    rows, categories = _api_rows(app)
    esc = html.escape
    chips = [
        f'<button type="button" class="mario-chip" data-category="" aria-pressed="true">All <span>{len(rows)}</span></button>'
    ] + [
        f'<button type="button" class="mario-chip" data-category="{esc(name)}" aria-pressed="false">{esc(name)} <span>{count}</span></button>'
        for name, count in categories
        if count
    ]
    body = []
    for row in rows:
        href = app.builder.get_relative_uri(fromdocname, row["doc"])
        short = row["name"].removeprefix("mario.")
        search = " ".join([row["name"], row["category"], row["group"], row["summary"]]).lower()
        body.append(
            f'<tr data-category="{esc(row["category"])}" data-search="{esc(search)}">'
            f'<td class="mario-api-table__name"><a href="{esc(href)}"><code>{esc(short)}</code></a></td>'
            f'<td class="mario-api-table__category"><span class="mario-pill">{esc(row["category"])}</span></td>'
            f'<td class="mario-api-table__summary">{esc(row["summary"])}</td></tr>'
        )
    markup = f"""
<div class="mario-api-index" data-api-index>
  <div class="mario-api-index__controls">
    <label class="mario-field">
      <span class="mario-visually-hidden">Filter API entries</span>
      <svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input type="search" placeholder="Filter entries, for example aggregate, calc or calc_u" autocomplete="off" spellcheck="false" data-api-filter>
    </label>
    <div class="mario-chips" role="group" aria-label="Filter by category">{"".join(chips)}</div>
  </div>
  <p class="mario-api-index__count" aria-live="polite" data-api-count>{len(rows)} entries</p>
  <div class="mario-scroll">
    <table class="mario-api-table">
      <thead><tr><th scope="col">API</th><th scope="col">Category</th><th scope="col">Description</th></tr></thead>
      <tbody>{"".join(body)}</tbody>
    </table>
  </div>
  <p class="mario-api-index__empty" hidden data-api-empty>No entry matches this filter.</p>
</div>
"""
    for placeholder in placeholders:
        placeholder.replace_self(nodes.raw("", markup, format="html"))


# --------------------------------------------------------------------------
# Build outputs: redirects and the search palette index
# --------------------------------------------------------------------------


def _redirect_html(target):
    target_attr = html.escape(target, quote=True)
    target_js = json.dumps(target)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>This page has moved</title>
<link rel="canonical" href="{target_attr}">
<meta http-equiv="refresh" content="0; url={target_attr}">
<script>location.replace({target_js} + ({target_js}.indexOf("#") < 0 ? location.hash : ""));</script>
</head><body><p>This page has moved to <a href="{target_attr}">{target_attr}</a>.</p></body></html>
"""


def _write_redirects(app):
    outdir = Path(app.outdir)
    for old, new in app.config.mario_site.get("redirects", {}).items():
        new_doc, _, anchor = new.partition("#")
        if old in app.env.found_docs:
            logger.warning("mario_site: redirect source %s is still a page; skipped", old)
            continue
        if new_doc not in app.env.found_docs:
            logger.warning("mario_site: redirect target %s does not exist", new_doc)
            continue
        target = posixpath.relpath(app.builder.get_target_uri(new_doc), posixpath.dirname(old) or ".")
        if anchor:
            target = f"{target}#{anchor}"
        path = outdir / f"{old}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_redirect_html(target), encoding="utf-8")


def _section_label(config, docname):
    if docname == "index":
        return "Home"
    section = _find_section(config, docname)
    if section is None:
        return ""
    tab = _active_tab(section, docname)
    if section.get("sidebar") and tab is not None:
        return f"{section['label']} · {tab['label']}"
    return section["label"]


def _write_nav_index(app):
    env = app.env
    config = app.config.mario_site
    entries = []
    for docname in sorted(env.found_docs):
        if docname not in env.titles:
            continue
        label = _section_label(config, docname)
        if not label and docname not in {"search", "genindex"}:
            continue
        uri = app.builder.get_target_uri(docname)
        title = _doc_title(env, docname)
        is_api = docname.startswith("api_document/")
        entries.append({"t": title.removeprefix("mario.") if is_api else title, "u": uri, "s": label, "k": "api" if is_api else "page"})
        if is_api:
            continue
        for heading in _local_toc(env, docname, max_depth=1):
            entries.append({"t": heading["title"], "u": uri + heading["anchor"], "s": f"{label} · {title}", "k": "section"})
    path = Path(app.outdir) / "_static" / "mario-nav.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _clean_notebook_downloads(app):
    from mario_downloads import clean_notebook
    for source, info in app.env.dlfiles.items():
        if not str(source).endswith(".ipynb"):
            continue
        path = Path(source)
        if not path.is_absolute():
            path = Path(app.srcdir) / path
        target = Path(app.outdir) / "_downloads" / info[1]
        payload = json.dumps(clean_notebook(path, app.srcdir), ensure_ascii=False, indent=1) + "\n"
        target.write_text(payload, encoding="utf-8")
        # Sphinx source copies are downloadable too; avoid a second raw notebook.
        source_copy = Path(app.outdir) / "_sources" / (str(path.relative_to(app.srcdir)) + ".txt")
        if source_copy.is_file():
            source_copy.write_text(payload, encoding="utf-8")


def _build_finished(app, exception):
    if exception is not None or app.builder.format != "html":
        return
    _write_redirects(app)
    _write_nav_index(app)
    _clean_notebook_downloads(app)
    from mario_browser_assets import write_browser_assets
    write_browser_assets(app.srcdir, app.outdir)
    restricted = Path(app.outdir) / "_static/data/database_profiles/eora26-2017-bp.xlsx"
    restricted.unlink(missing_ok=True)


def setup(app):
    app.add_js_file("mario.js", defer="defer")
    app.add_js_file("download-figure.js", defer="defer")
    app.add_config_value("mario_site", {}, "html")
    app.add_config_value("mario_notebook_downloads", {}, "env")
    app.add_node(mario_api_index)
    app.add_node(mario_docs_overview)
    app.add_directive("mario-docs-overview", MarioDocsOverview)
    app.add_directive("mario-api-index", MarioApiIndex)
    app.add_directive("mario-cards", MarioCards)
    app.add_directive("mario-card", MarioCard)
    app.add_directive("mario-steps", MarioSteps)
    app.add_directive("mario-step", MarioStep)
    app.add_directive("mario-switch", MarioSwitch)
    app.add_directive("mario-switch-option", MarioSwitchOption)
    app.add_directive("mario-scheme", MarioScheme)
    app.add_directive("mario-citation", MarioCitation)
    app.add_directive("mario-publications", MarioPublications)
    app.add_directive("mario-notebook-downloads", MarioNotebookDownloads)
    app.connect("doctree-read", _record_toctrees)
    app.connect("env-purge-doc", _purge_doc)
    app.connect("env-merge-info", _merge_info)
    app.connect("doctree-resolved", _render_api_index)
    app.connect("doctree-resolved", _render_docs_overview)
    app.connect("doctree-resolved", _finish_notebook_downloads)
    app.connect("html-page-context", _page_context)
    app.connect("build-finished", _build_finished)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
