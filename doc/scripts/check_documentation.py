"""Check a built HTML site's guides, navigation and notebook downloads offline.

Run after a strict Sphinx build; see doc/maintenance/verification.rst.
Uses only the Python standard library and never executes notebook code.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit


SOURCE = Path(__file__).resolve().parents[1] / "source"


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.ids = set()
        self.current_links = []
        self.sidebar = False
        self.headings = 0
        self.notebook_cells = False
        self.redirect = False
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("name"):
            self.ids.add(attrs["name"])
        if tag == "aside" and "mario-sidebar" in classes:
            self.sidebar = True
        if tag == "a" and attrs.get("href") is not None:
            self.links.append(attrs["href"])
            if self.sidebar and attrs.get("aria-current") == "page":
                self.current_links.append(attrs["href"])
        self.headings += tag == "h1"
        self.notebook_cells |= bool(classes & {"nbinput", "nboutput"})
        if tag == "meta" and (attrs.get("http-equiv") or "").lower() == "refresh":
            self.redirect = True

    def handle_endtag(self, tag):
        if tag == "aside":
            self.sidebar = False


def excluded_patterns(source):
    """Read the literal exclusion list without importing Sphinx configuration."""
    tree = ast.parse((source / "conf.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "exclude_patterns"
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError("No literal exclude_patterns found in conf.py")


def local_target(href, origin, site):
    parts = urlsplit(href)
    if parts.scheme or parts.netloc:
        return None
    path = unquote(parts.path)
    target = (site / path.lstrip("/") if path.startswith("/") else
              origin.parent / path if path else origin).resolve()
    if target.is_dir():
        target /= "index.html"
    return target, unquote(parts.fragment)


def audit(site, source=SOURCE):
    site, source = site.resolve(), source.resolve()
    errors, cache, notebook_links = [], {}, {}
    checks = 0
    patterns = excluded_patterns(source)
    pages = sorted(
        path.relative_to(source).with_suffix(".html")
        for folder in ("user_guide", "notebooks/parsers")
        for path in (source / folder).rglob("*.rst")
        if not any(fnmatch.fnmatchcase(path.relative_to(source).as_posix(), pattern)
                   for pattern in patterns)
    )
    pages.append(Path("resources/material.html"))

    def read(path):
        if path not in cache:
            cache[path] = Page(path)
        return cache[path]

    for relative in pages:
        path = site / relative
        if not path.is_file():
            errors.append(f"{relative}: built page missing")
            continue
        page = read(path)
        if page.headings != 1:
            errors.append(f"{relative}: expected one h1, found {page.headings}")
        if page.notebook_cells:
            errors.append(f"{relative}: notebook cells rendered as a web page")
        if relative.parts[0] in {"user_guide", "notebooks"} and not any(
            local_target(href, path, site) == (path, "") for href in page.current_links
        ):
            errors.append(f"{relative}: missing current-page link in topic sidebar")
        notebook_links[path] = set()
        for href in page.links:
            destination = local_target(href, path, site)
            if destination is None:
                continue
            target, fragment = destination
            checks += 1
            if not target.is_relative_to(site) or not target.is_file():
                errors.append(f"{relative}: missing local target {href}")
                continue
            if fragment and target.suffix == ".html":
                linked = read(target)
                if fragment not in linked.ids and not linked.redirect:
                    errors.append(f"{relative}: missing anchor {href}")
            if target.suffix == ".ipynb":
                notebook_links[path].add(target)

    expected_downloads = set()
    for notebook in sorted(source.rglob("*.ipynb")):
        relative = notebook.relative_to(source)
        if not notebook.with_suffix(".rst").is_file():
            errors.append(f"{relative}: notebook has no RST companion page")
            continue
        guide = site / relative.with_suffix(".html")
        matches = {path for path in notebook_links.get(guide, set())
                   if path.name == notebook.name}
        if not matches:
            errors.append(f"{relative}: companion missing from its built guide")
        expected_downloads.update(matches)

    gallery = notebook_links.get(site / "resources/material.html", set())
    for missing in sorted(expected_downloads - gallery):
        errors.append(f"Downloadable material: missing {missing.relative_to(site)}")
    for extra in sorted(gallery - expected_downloads):
        errors.append(f"Downloadable material: unpaired notebook {extra.relative_to(site)}")

    downloads = set().union(*notebook_links.values())
    for download in sorted(downloads):
        try:
            notebook = json.loads(download.read_text(encoding="utf-8"))
            cells = notebook["cells"]
            if any(cell.get("outputs") or cell.get("execution_count") is not None
                   for cell in cells if cell["cell_type"] == "code"):
                errors.append(f"{download.relative_to(site)}: saved execution results")
            if "Source databases keep their own licences" not in json.dumps(notebook):
                errors.append(f"{download.relative_to(site)}: source notice missing")
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(f"{download.relative_to(site)}: invalid notebook ({exc})")
    for raw in sorted((site / "_sources").rglob("*.ipynb")):
        errors.append(f"{raw.relative_to(site)}: raw notebook source published")
    return errors, len(pages), checks, len(downloads)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path, help="HTML output directory from Sphinx")
    args = parser.parse_args()
    if not (args.site / "index.html").is_file():
        parser.error("site must contain the built index.html")
    errors, pages, links, downloads = audit(args.site)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PASS: {pages} pages, {links} local links/anchors, "
          f"{downloads} notebook downloads; sidebar and companion checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
