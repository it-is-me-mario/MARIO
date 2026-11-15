"""Build both documentation channels into one verified GitHub Pages artifact."""

import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import subprocess
import sys


class PageAnchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        value = dict(attrs).get("id")
        if value:
            self.ids.append(value)


def build(sources, output, site_root):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a fresh output directory for the versioned site")
    output.mkdir(parents=True, exist_ok=True)
    definitions = json.loads((Path(__file__).parents[1] / "versions.json").read_text())
    catalogue = {"versions": {}}
    for channel, source in sources.items():
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
        subprocess.run([
            sys.executable, "-m", "sphinx", "-b", "html", "-W", "--keep-going",
            str(source / "doc/source"), str(destination),
        ], cwd=source, env=env, check=True)
        subprocess.run([
            sys.executable, str(source / "doc/scripts/check_documentation.py"), str(destination),
        ], cwd=source, env=env, check=True)
        documents = {}
        for path in sorted(destination.rglob("*.html")):
            parser = PageAnchors()
            parser.feed(path.read_text())
            documents[path.relative_to(destination).with_suffix("").as_posix()] = parser.ids
        catalogue["versions"][channel] = {
            **definitions[channel], "commit": revision, "url": base_url, "documents": documents,
        }
    payload = json.dumps(catalogue, separators=(",", ":")) + "\n"
    for channel in sources:
        (output / "en" / channel / "_static/docs-versions.json").write_text(payload)
    (output / "docs-versions.json").write_text(payload)
    (output / ".nojekyll").touch()
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="0;url=en/latest/">'
        '<title>MARIO documentation</title></head><body>'
        '<a href="en/latest/">MARIO documentation</a></body></html>'
    )
    print("PASS versioned documentation and source catalogue", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latest-source", type=Path, required=True)
    parser.add_argument("--dev-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--site-root", default="https://www.marioproject.com")
    args = parser.parse_args()
    build({"latest": args.latest_source.resolve(), "dev": args.dev_source.resolve()},
          args.output.resolve(), args.site_root)
