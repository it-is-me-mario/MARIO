"""Sphinx configuration for the MARIO Model Gallery."""

from datetime import datetime
import os
from pathlib import Path
import sys

frontend = Path(__file__).resolve().parents[1] / "source"
sys.path.insert(0, str(frontend / "_ext"))

from mario_resources import TEACHING_CLOSING

project = "MARIO Model Gallery"
author = "Lorenzo Rinaldi, Mohammad Amin Tahavori, Nicolo Golinucci"
copyright = f"{datetime.now().year}, {author}"

extensions = [
    "mario_site", "mario_versions", "sphinx_copybutton",
    "sphinx.ext.autodoc", "sphinx.ext.napoleon",
]
html_theme = "mario"
html_theme_path = [str(frontend / "_themes")]
html_baseurl = os.environ.get("MARIO_DOCS_BASEURL", "")
html_favicon = str(frontend / "_static/images/mario-favicon.ico")
html_css_files = ["heatmap-background.css", "model-gallery.css"]
html_js_files = ["external-links.js"]
html_show_sourcelink = False
html_copy_source = False
html_static_path = ["_static"]

site = os.environ.get("MARIO_DOCS_SITE_ROOT", "https://www.marioproject.com").rstrip("/")
gallery = f"{site}/en/model_gallery/"
setup_doc = "user_guide/configuration/model_setups"
rst_epilog = f"""
.. _Research model setups: {gallery}{setup_doc}.html
.. _PV-HLCA guide in the Model Gallery: {gallery}models/pv-hlca.html
"""

mario_site = {
    "changelog_url": "https://github.com/it-is-me-mario/MARIO/releases",
    "github": "https://github.com/it-is-me-mario/MARIO",
    "pypi": "https://pypi.org/project/mariopy/",
    "browser_assets": False,
    "closings": {"resources/teaching": TEACHING_CLOSING},
    "home_hero": {
        "title": "Model Gallery",
        "text": "Research models built with MARIO.",
    },
    "sections": [
        {
            "key": "get_started", "label": "Get started",
            "landing": gallery + setup_doc + ".html#install-a-model",
            "tabs": [
                {"label": "Installation", "doc": gallery + setup_doc + ".html#install-a-model"},
                {"label": "Open a project", "doc": gallery + setup_doc + ".html#open-a-project"},
            ],
        },
        {
            "key": "docs", "label": "Docs", "landing": "user_guide/index",
            "prefixes": ["models/", "user_guide/", "api_document/", "reference/"],
            "navigation_style": "sidebar", "sidebar_label": "Model Gallery",
            "breadcrumb_label": "Docs",
            "tabs": [
                {"key": "models", "label": "Model guides", "doc": "index",
                 "prefixes": ["models/"], "toc": {"doc": "index", "caption": "Models", "max_depth": 1}},
                {"key": "configuration", "label": "Configuration", "doc": setup_doc},
                {"key": "api", "label": "API reference", "doc": "reference/api_model_methods",
                 "prefixes": ["api_document/", "reference/"],
                 "toc": {"doc": "reference/api_model_methods", "max_depth": 1}},
            ],
        },
        {
            "key": "explorer", "label": "Explorer",
            "landing": "https://explorer.marioproject.com/",
            "tabs": [
                {"label": "Indicators", "doc": "https://explorer.marioproject.com/resources/data-explorer/compare.html"},
                {"label": "Classifications", "doc": "https://explorer.marioproject.com/resources/data-explorer/scope.html"},
                {"label": "Analyses", "doc": "https://explorer.marioproject.com/resources/data-explorer/analyses.html"},
            ],
        },
        {
            "key": "resources", "label": "Resources", "landing": "resources/index",
            "prefixes": ["resources/"],
            "hero": {"title": "Resources"},
            "tabs": [
                {"label": "Tutorials", "doc": "https://tutorials.marioproject.com/"},
                {"label": "Model Gallery", "doc": "index"},
                {"label": "Teaching", "doc": "resources/teaching"},
                {"label": "Projects & Publications", "doc": "resources/projects_publications"},
                {"label": "Downloadable material", "doc": "resources/material"},
            ],
        },
    ],
}
