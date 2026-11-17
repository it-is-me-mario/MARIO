"""Build Latest, Dev and Model Gallery into one verified GitHub Pages artifact."""

import argparse
import hashlib
from html import escape
from html.parser import HTMLParser
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urljoin, urlsplit


class PageAnchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        value = dict(attrs).get("id")
        if value:
            self.ids.append(value)


def write_catalogue(output, catalogue):
    """Give every source theme the same native version choices and inventory."""
    payload = json.dumps(catalogue, separators=(",", ":")) + "\n"
    for channel, version in catalogue["versions"].items():
        destination = output / "en" / channel
        (destination / "_static/docs-versions.json").write_text(payload)
        links = "\n".join(
            f'<a href="{escape(item["url"], quote=True)}" data-docs-version="{key}"'
            + (' aria-current="page"' if key == channel else '')
            + f'>{escape(item["label"])}</a>'
            for key, item in catalogue["versions"].items()
        )
        for document in version["documents"]:
            path = destination / (document + ".html")
            content = path.read_text()
            content = re.sub(
                r'(<nav class="mario-versions__options"[^>]*>).*?(</nav>)',
                lambda match: match[1] + "\n" + links + "\n" + match[2], content, flags=re.S,
            )
            path.write_text(content)
    (output / "docs-versions.json").write_text(payload)


class PageAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.page_urls = []
        self.explorer = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        urls = [values[key] for key in ("href", "src") if values.get(key)]
        self.urls.extend(urls)
        if tag != "a" or "data-docs-version" not in values:
            self.page_urls.extend(urls)
        self.explorer |= any(key in values for key in (
            "data-economy-browser", "data-database-comparisons", "data-database-scope",
            "data-sectoral-scope", "data-extension-scope",
        ))


def check_gallery_navigation(output, version):
    """Check ordinary gallery links and assets, excluding the version selector."""
    root = output / "en/model_gallery"
    base = urlsplit(version["url"])
    for document in version["documents"]:
        page = document + ".html"
        parser = PageAssets()
        parser.feed((root / page).read_text())
        for href in parser.page_urls:
            target = urlsplit(urljoin(version["url"] + page, href))
            if target.scheme not in {"http", "https"}:
                continue
            if target.hostname in {"tutorials.marioproject.com", "explorer.marioproject.com"}:
                raise ValueError(f"Model Gallery link leaves its channel: {page} → {href}")
            if target.netloc != base.netloc:
                continue
            if not target.path.startswith(base.path):
                raise ValueError(f"Model Gallery link leaves its channel: {page} → {href}")
            relative = unquote(target.path.removeprefix(base.path))
            if relative.endswith("/") or not relative:
                relative += "index.html"
            if not (root / relative).is_file():
                raise ValueError(f"Model Gallery link has no target: {page} → {href}")
            if target.fragment and relative.endswith(".html"):
                anchors = version["documents"].get(relative.removesuffix(".html"), [])
                if unquote(target.fragment) not in anchors:
                    raise ValueError(f"Model Gallery link has no anchor: {page} → {href}")


def deduplicate_legacy_json(output, catalogue):
    """Keep frozen compatibility JSON on Latest, plus every referenced/changed file."""
    latest = output / "en/latest"
    for channel in catalogue["versions"]:
        if channel == "latest" or catalogue["versions"][channel].get("kind") == "gallery":
            continue
        destination = output / "en" / channel
        referenced = set()
        for page in destination.rglob("*.html"):
            parser = PageAssets()
            parser.feed(page.read_text())
            if parser.explorer:
                raise ValueError("Legacy Explorer widgets must be migrated before sharing frozen assets")
            for address in parser.urls:
                url = urlsplit(address)
                if not url.scheme and not url.netloc and url.path:
                    referenced.add((page.parent / unquote(url.path)).resolve())
        shared = {}
        for path in (destination / "_static/data").rglob("*.json"):
            if path.stat().st_size < 64 * 1024 or path.resolve() in referenced:
                continue
            relative = path.relative_to(destination)
            counterpart = latest / relative
            if not counterpart.is_file() or path.read_bytes() != counterpart.read_bytes():
                continue
            shared[relative.as_posix()] = {
                "url": catalogue["versions"]["latest"]["url"] + relative.as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            path.unlink()
        (destination / "legacy-data-manifest.json").write_text(json.dumps(shared, sort_keys=True) + "\n")
    for folder in output.rglob(".doctrees"):
        shutil.rmtree(folder)



def write_preview_redirects(output, catalogue):
    """Retire Preview while preserving its page URLs, query strings and anchors."""
    destinations = {}
    # Prefer Latest; a page available only in Dev keeps its working counterpart.
    for channel in ("dev", "latest"):
        version = catalogue["versions"][channel]
        for document in version["documents"]:
            destinations[document] = version["url"] + document + ".html"
    for document, target in destinations.items():
        path = output / "en/preview" / (document + ".html")
        path.parent.mkdir(parents=True, exist_ok=True)
        address = escape(target, quote=True)
        path.write_text(
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex">'
            '<title>MARIO · Page moved</title><link rel="canonical" href="' + address + '">'
            '<meta http-equiv="refresh" content="0;url=' + address + '">'
            '<script>const target = new URL(' + json.dumps(target) + ');'
            'target.search = location.search; target.hash = location.hash;'
            'location.replace(target.href);</script></head><body>'
            '<p>This page has moved. <a href="' + address + '">Continue to MARIO</a>.</p>'
            '</body></html>')


def build(sources, output, site_root):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a fresh output directory for the versioned site")
    output.mkdir(parents=True, exist_ok=True)
    publisher = Path(__file__).resolve().parents[2]
    definitions = json.loads((publisher / "doc/versions.json").read_text())
    frontend = publisher / "doc/source"
    catalogue = {"publisher_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=publisher, text=True
    ).strip(), "versions": {}}
    for channel, source in {**sources, "model_gallery": publisher}.items():
        gallery = definitions[channel].get("kind") == "gallery"
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        destination = output / "en" / channel
        base_url = f"{site_root.rstrip('/')}/en/{channel}/"
        env = {
            **os.environ,
            "PYTHONPATH": str(source),
            "MARIO_DOCS_CHANNEL": channel,
            "MARIO_DOCS_REVISION": revision,
            "MARIO_DOCS_SITE_ROOT": site_root,
            "MARIO_DOCS_BASEURL": base_url,
        }
        # Share the approved frontend without replacing a channel's library or guides.
        with tempfile.TemporaryDirectory(prefix="mario-channel-theme-") as folder:
            static = Path(folder) / "static"
            doc_source = source / "doc/source"
            assets = ["docs-versions.css", "docs-versions.js", "external-links.js"]
            if gallery:
                # Shared RST pages resolve their images from the gallery source
                # directory, including before Sphinx copies the static assets.
                staged_docs = Path(folder) / "doc"
                staged_docs.mkdir()
                (staged_docs / "source").symlink_to(frontend, target_is_directory=True)
                doc_source = staged_docs / "model_gallery"
                shutil.copytree(source / "doc/model_gallery", doc_source)
                static = doc_source / "_static"
                assets += [
                    "docs-workflows.css", "download-figure.js", "heatmap-background.css",
                    "images/heatmap-background.png", "images/heatmap-background-dark.png",
                    "images/mario-logo.png", "images/mario-favicon.ico",
                    "images/logos/github.svg", "images/logos/pymrio.png", "images/logos/cvxlab.png",
                    "images/logo_entice.svg", "images/logo_iam_compact.png", "images/logo_fulfill.png",
                ]
            for name in assets:
                target = static / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(frontend / "_static" / name, target)
            options = []
            if not gallery:
                options = [
                    "-D", "html_static_path=_static," + str(static),
                    "-D", "mario_site.install=pip install mariopy",
                ]
            subprocess.run([
                sys.executable, "-m", "sphinx", "-b", "html", "-W", "--keep-going",
                "-D", "html_theme_path=" + str(frontend / "_themes"),
                "-D", "html_context.mario_use_source_navigation=1",
                *options, str(doc_source), str(destination),
            ], cwd=source, env=env, check=True)
        documents = {}
        for path in sorted(destination.rglob("*.html")):
            parser = PageAnchors()
            parser.feed(path.read_text())
            documents[path.relative_to(destination).with_suffix("").as_posix()] = parser.ids
        catalogue["versions"][channel] = {
            **definitions[channel], "commit": revision, "url": base_url, "documents": documents,
        }
    write_catalogue(output, catalogue)
    check_gallery_navigation(output, catalogue["versions"]["model_gallery"])
    deduplicate_legacy_json(output, catalogue)
    write_preview_redirects(output, catalogue)
    size = sum(path.stat().st_size for path in output.rglob('*') if path.is_file())
    if size > 1024 ** 3:
        raise ValueError(f"The combined Pages artifact exceeds 1 GB ({size:,} bytes)")
    for channel, source in sources.items():
        subprocess.run([
            sys.executable, str(source / "doc/scripts/check_documentation.py"),
            str(output / "en" / channel),
        ], cwd=source, env={**os.environ, "PYTHONPATH": str(source)}, check=True)
    (output / ".nojekyll").touch()
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="0;url=en/latest/">'
        '<title>MARIO documentation</title></head><body>'
        '<a href="en/latest/">MARIO documentation</a></body></html>'
    )
    print(f"PASS versioned documentation and source catalogue; {size:,} bytes", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latest-source", type=Path, required=True)
    parser.add_argument("--dev-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--site-root", default="https://www.marioproject.com")
    args = parser.parse_args()
    build({"latest": args.latest_source.resolve(), "dev": args.dev_source.resolve()},
          args.output.resolve(), args.site_root)
