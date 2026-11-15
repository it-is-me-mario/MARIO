"""Add a Preview choice to an already-built local documentation preview."""

import argparse
import json
from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from build_versioned_docs import PageAnchors


def add_preview(output, preview_url, latest_url, dev_url, catalogue_path=None):
    """Reuse the shared selector without changing the published channel refs."""
    theme = Path(__file__).parents[1] / "source/_themes/mario"
    template = Environment(
        loader=FileSystemLoader(theme), autoescape=select_autoescape(["html"])
    ).get_template("partials/versions.html")
    catalogue = json.loads(catalogue_path.read_text()) if catalogue_path else {"versions": {}}
    for key, url in (("latest", latest_url), ("dev", dev_url)):
        catalogue["versions"].setdefault(key, {"documents": {}})["url"] = url.rstrip("/") + "/"

    pages = {}
    for path in sorted(output.rglob("*.html")):
        if "_static" in path.relative_to(output).parts:
            continue
        content = path.read_text()
        if "mario-layout-" not in content:
            continue  # Keep compatibility redirects and standalone assets intact.
        document = path.relative_to(output).with_suffix("").as_posix()
        anchors = PageAnchors()
        anchors.feed(content)
        pages[document] = (path, content, anchors.ids)
    if not pages:
        raise ValueError("No rendered MARIO pages found in the preview directory")
    catalogue["versions"]["preview"] = {
        "label": "Preview", "url": preview_url.rstrip("/") + "/",
        "documents": {document: item[2] for document, item in pages.items()},
    }
    pattern = re.compile(r'<details\b[^>]*\bdata-docs-versions\b[^>]*>.*?</details>', re.S)
    for document, (path, content, _) in pages.items():
        depth = len(path.relative_to(output).parts) - 1
        selector = template.render(mario_versions={
            "current": "preview", "label": "Preview", "document": document,
            "catalogue": "../" * depth + "_static/docs-versions.json",
            "choices": [
                {"key": key, "label": label, "url": catalogue["versions"][key]["url"]}
                for key, label in (("latest", "Latest"), ("dev", "Dev"), ("preview", "Preview"))
            ],
        })
        if pattern.search(content):
            content = pattern.sub(lambda match: selector, content, count=1)
        else:
            content = content.replace("</body>", selector + "\n</body>", 1)
        path.write_text(content)
    (output / "_static/docs-versions.json").write_text(json.dumps(catalogue, separators=(",", ":")) + "\n")
    print(f"PASS: Preview selector on {len(pages)} pages in {output.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview-url", required=True)
    parser.add_argument("--latest-url", required=True)
    parser.add_argument("--dev-url", required=True)
    parser.add_argument("--catalogue", type=Path, help="Published docs-versions.json, to retain page/anchor matching")
    args = parser.parse_args()
    add_preview(args.output.resolve(), args.preview_url, args.latest_url, args.dev_url, args.catalogue)
