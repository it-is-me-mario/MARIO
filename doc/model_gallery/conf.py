"""Sphinx configuration for the MARIO Model Gallery."""

from datetime import datetime
import os
from pathlib import Path
import sys

frontend = Path(__file__).resolve().parents[1] / "source"
sys.path.insert(0, str(frontend / "_ext"))

project = "MARIO Model Gallery"
author = "Lorenzo Rinaldi, Mohammad Amin Tahavori, Nicolo Golinucci"
copyright = f"{datetime.now().year}, {author}"

extensions = ["mario_site", "mario_versions", "sphinx_copybutton"]
html_theme = "mario"
html_theme_path = [str(frontend / "_themes")]
html_baseurl = os.environ.get("MARIO_DOCS_BASEURL", "")
html_favicon = str(frontend / "_static/images/mario-favicon.ico")
html_css_files = ["heatmap-background.css"]
html_js_files = ["external-links.js"]
html_show_sourcelink = False
html_copy_source = False

site = os.environ.get("MARIO_DOCS_SITE_ROOT", "https://www.marioproject.com").rstrip("/")
latest = f"{site}/en/latest/"
rst_epilog = f"\n.. _MARIO model setup guide: {latest}user_guide/configuration/model_setups.html\n"

mario_site = {
    "home_url": latest,
    "changelog_url": latest + "changelog.html",
    "github": "https://github.com/it-is-me-mario/MARIO",
    "pypi": "https://pypi.org/project/mariopy/",
    "browser_assets": False,
    "home_hero": {
        "title": "Model Gallery",
        "text": "Research models built with MARIO.",
    },
    "sections": [
        {
            "key": "get_started", "label": "Get started",
            "landing": latest + "get_started/index.html",
            "tabs": [
                {"label": "Installation", "doc": latest + "get_started/index.html"},
                {"label": "Table formats", "doc": latest + "get_started/table_formats.html"},
                {"label": "Scenarios", "doc": latest + "get_started/scenarios.html"},
            ],
        },
        {
            "key": "docs", "label": "Docs", "landing": latest + "user_guide/index.html",
            "tabs": [
                {"label": "User guide", "doc": latest + "user_guide/index.html"},
                {"label": "API reference", "doc": latest + "reference/api_library.html"},
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
            "key": "resources", "label": "Resources", "landing": "https://tutorials.marioproject.com/",
            "tabs": [
                {"label": "Tutorials", "doc": "https://tutorials.marioproject.com/"},
                {"label": "Model Gallery", "doc": "index"},
                {"label": "Projects & Publications", "doc": latest + "resources/projects_publications.html"},
                {"label": "Teaching", "doc": latest + "resources/teaching.html"},
            ],
        },
        {
            "key": "model_gallery", "label": "Model Gallery", "landing": "index",
            "prefixes": ["models/"], "navigation": False,
            "navigation_style": "sidebar", "sidebar_label": "Model Gallery",
            "breadcrumb_label": "Model Gallery",
            "tabs": [{"key": "pv-hlca", "label": "PV-HLCA", "doc": "models/pv-hlca"}],
        },
    ],
}
