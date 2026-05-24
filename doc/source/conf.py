# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
from copy import deepcopy
from datetime import datetime

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(".."))
sys.path.insert(0, os.path.abspath("../.."))
sys.path.insert(0, os.path.abspath("../../.."))

import mario_bibstyles
import nbsphinx

try:
    import plotly.io as pio
    from plotly.offline.offline import get_plotlyjs_version
except ImportError:  # pragma: no cover - docs fallback when Plotly is absent
    pio = None
    get_plotlyjs_version = None


_PLOTLY_MIME = "application/vnd.plotly.v1+json"
_ORIGINAL_FROM_NOTEBOOK_NODE = nbsphinx.Exporter.from_notebook_node


def _inject_plotly_html_outputs(nb):
    """Convert Plotly MIME bundles saved in notebooks to HTML for nbsphinx."""

    if pio is None:
        return nb

    notebook = deepcopy(nb)

    for cell in notebook.get("cells", []):
        for output in cell.get("outputs", []):
            data = output.get("data")
            if not isinstance(data, dict):
                continue
            if _PLOTLY_MIME not in data or "text/html" in data:
                continue

            figure_bundle = data[_PLOTLY_MIME]
            if not isinstance(figure_bundle, dict):
                continue

            figure_payload = {
                "data": figure_bundle.get("data", []),
                "layout": figure_bundle.get("layout", {}),
                "frames": figure_bundle.get("frames", []),
            }
            config = figure_bundle.get("config") or {}

            data["text/html"] = pio.to_html(
                figure_payload,
                config=config,
                auto_play=False,
                full_html=False,
                include_plotlyjs=False,
            )

    return notebook


def _patched_from_notebook_node(self, nb, resources=None, **kwargs):
    return _ORIGINAL_FROM_NOTEBOOK_NODE(
        self,
        _inject_plotly_html_outputs(nb),
        resources=resources,
        **kwargs,
    )


nbsphinx.Exporter.from_notebook_node = _patched_from_notebook_node

# -- Project information -----------------------------------------------------


project = 'MARIO'
copyright = f'{datetime.now().year}, Lorenzo Rinaldi, Mohammad Amin Tahavori, Nicolo Golinucci'
author = 'Lorenzo Rinaldi, Mohammad Amin Tahavori, Nicolo Golinucci'

# The full version, including alpha/beta/rc tags
release = '1.0.0'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "nbsphinx",
    "IPython.sphinxext.ipython_console_highlighting",
    "sphinx.ext.mathjax",
    "sphinx.ext.coverage",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    "sphinx_copybutton",
    "sphinxcontrib.bibtex",
 
]
nbsphinx_execute = "never"
nbsphinx_epilog = r"""
{% if env.docname.startswith("notebooks/parsers/") or env.docname in ["user_guide/inspection/calc_linkages", "user_guide/inspection/calculate_trades", "user_guide/inspection/supply_chain_analyses"] %}
.. container:: parser-notebook-download

   :download:`Download this notebook <{{ env.docname.split("/")[-1] }}.ipynb>`
{% endif %}
"""
source_suffix = {
    ".rst": "restructuredtext",
    ".txt": "markdown",
    ".md": "markdown",
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [
    "__pycache__",
    "__pycache__/**",
    "notebooks/parsers/*/tutorial.ipynb",
    "api_document/mario.parse_gtap.rst",
    "api_document/mario.parse_cepalstat.rst",
    "user_guide/inspection/custom_labels.ipynb",
    "user_guide/advanced/change_settings.ipynb",
    "user_guide/advanced/large_database_workflows.ipynb",
    "contribute/documentation.rst",
    "resources/changelog.rst",
]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#


html_theme = "pydata_sphinx_theme"
html_title = "MARIO"
html_logo = "_static/images/mario-logo.png"
html_theme_options = {
    "logo": {
        "text": "MARIO",
    },
    "navbar_align": "content",
    "header_links_before_dropdown": 20,
    "navigation_with_keys": True,
    "show_toc_level": 2,
    "secondary_sidebar_items": ["page-toc"],
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/it-is-me-mario/MARIO",
            "icon": "fa-brands fa-github",
        },
    ],
}
# html_theme_path = [sphinx_pdj_theme.get_html_theme_path()]
# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_js_files = [
    (
        f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"
        if get_plotlyjs_version is not None
        else "https://cdn.plot.ly/plotly-2.32.0.min.js"
    ),
    "external-links.js",
    "terminology-tables.js",
    "parser-coverage.js",
    "docs-assistant-data.js",
    "docs-assistant.js",
]
bibtex_bibfiles = ["publications/mario.bib"]

# copy btn settings
copybutton_prompt_text = "<AxesSubplot:>"
