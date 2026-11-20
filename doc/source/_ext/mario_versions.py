"""Supply the channel, source revision and native links for versioned docs."""

import json
import os
from pathlib import Path


DEFINITIONS = json.loads((Path(__file__).resolve().parents[2] / "versions.json").read_text())


def page_context(app, pagename, templatename, context, doctree):
    channel = os.environ.get("MARIO_DOCS_CHANNEL")
    if channel not in DEFINITIONS:
        return
    root = os.environ["MARIO_DOCS_SITE_ROOT"].rstrip("/")
    revision = os.environ["MARIO_DOCS_REVISION"]
    context["mario_versions"] = {
        "current": channel,
        "label": DEFINITIONS[channel]["label"],
        "document": pagename,
        "catalogue": app.builder.get_relative_uri(pagename, "index").removesuffix("index.html") + "_static/docs-versions.json",
        "revision": revision[:7],
        "source_url": "https://github.com/it-is-me-mario/MARIO/tree/" + revision,
        "choices": [{"key": key, "label": item["label"], "url": f"{root}/en/{key}/"}
                    for key, item in DEFINITIONS.items()],
    }


def setup(app):
    app.add_css_file("docs-versions.css")
    app.add_js_file("docs-versions.js", defer="defer")
    app.connect("html-page-context", page_context, priority=900)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
