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
sys.path.insert(0, os.path.abspath("_ext"))

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
release = '1.2.0'


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
    "mario_site",
    "mario_database_profiles",
]
nbsphinx_execute = "never"
# Notebooks offered as downloads: at the bottom of their page (nbsphinx_epilog) and
# in the list on resources/material (``mario-notebook-downloads``).
mario_notebook_downloads = {
    "prefixes": ["notebooks/parsers/", "user_guide/advanced/"],
    "pages": [
        "user_guide/parsers/provide_your_database",
        "user_guide/inspection/basic_inspections",
        "user_guide/inspection/compute_matrices",
        "user_guide/inspection/visualization",
        "user_guide/inspection/custom_labels_and_aliases",
        "user_guide/inspection/export_and_roundtrip",
        "user_guide/transformations/aggregate",
        "user_guide/transformations/add_extensions",
        "user_guide/transformations/apply_shocks",
        "user_guide/transformations/add_sectors",
        "user_guide/transformations/sut_to_iot",
        "user_guide/transformations/mrio_to_srio",
        "user_guide/transformations/to_chenery_moses",
    ],
}

nbsphinx_epilog = (
    "{% set notebook_download_pages = "
    + repr(mario_notebook_downloads["pages"])
    + " %}\n{% if "
    + " or ".join(f'env.docname.startswith("{prefix}")' for prefix in mario_notebook_downloads["prefixes"])
    + r""" or env.docname in notebook_download_pages %}
.. container:: parser-notebook-download

   :download:`Download this notebook <{{ env.docname.split("/")[-1] }}.ipynb>`
{% endif %}
"""
)
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
    "resources/changelog.rst",
    # The analysis index and its dedicated pages replace the previous single page.
    "resources/benchmarks.rst",
    # Coverage comparison and benchmarking will be redesigned; kept in the repo, out of the site.
    "user_guide/parsers/country_coverage.rst",
]


# -- Options for HTML output -------------------------------------------------

# The site uses its own theme (doc/source/_themes/mario), fed by the
# ``mario_site`` extension (doc/source/_ext/mario_site.py).
html_theme = "mario"
html_theme_path = ["_themes"]
html_title = "MARIO"
html_short_title = "MARIO"
html_logo = "_static/images/mario-logo.png"
html_favicon = "_static/images/mario-favicon.ico"
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")
html_permalinks_icon = "#"
html_show_sourcelink = False
html_copy_source = False

html_static_path = ["_static"]
html_css_files = ["heatmap-background.css", "benchmarks.css"]
html_js_files = [
    (
        f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"
        if get_plotlyjs_version is not None
        else "https://cdn.plot.ly/plotly-2.32.0.min.js"
    ),
    "external-links.js",
    "terminology-tables.js",
]

# Long signatures get one parameter per line.
python_maximum_signature_line_length = 88

mario_site = {
    "github": "https://github.com/it-is-me-mario/MARIO",
    "pypi": "https://pypi.org/project/mariopy/",
    "install": "pip install mariopy",
    "home_hero": {
        "title": "Input-output analysis in <mark>Python</mark>",
        "text": (
            "Work with input-output and supply-use tables, from reading a database "
            "to building scenarios and analysing impacts across regions and sectors."
        ),
        "install": True,
        "actions": [
            {"label": "Get started", "doc": "get_started/index"},
        ],
    },
    "sections": [
        {
            "key": "get_started",
            "home_label": "Get started",
            "home_summary": "Set up MARIO and learn the essentials.",
            "label": "Get started",
            "landing": "get_started/index",
            "prefixes": ["get_started/"],
            "hero": {
                "title": "<mark>Install</mark> and <mark>discover</mark> MARIO",
                "text": "Set up your MARIO environment and learn about definitions, nomenclature and other fundamentals.",
            },
            "tabs": [
                {"label": "Installation", "doc": "get_started/index", "summary": "Install MARIO and prepare your Python environment."},
                {"label": "Nomenclature", "doc": "get_started/nomenclature", "summary": "Understand the tables, matrices and sets."},
                {"label": "Table formats", "doc": "get_started/table_formats", "summary": "Explore input-output and supply-use tables."},
                {"label": "Scenarios", "doc": "get_started/scenarios", "summary": "Organise and compare different model scenarios."},
            ],
        },
        {
            "key": "docs",
            "home_label": "Documentation",
            "home_summary": "Find a guide for every step of your workflow.",
            "label": "Docs",
            "landing": "user_guide/index",
            "prefixes": ["user_guide/", "notebooks/", "reference/", "api_document/"],
            "sidebar": True,
            "hero": {
                "title": "Everything MARIO <mark>can do</mark>",
                "text": (
                    "Parse a database, inspect and transform it, run advanced workflows, "
                    "and look up every method in the API reference."
                ),
            },
            "tabs": [
                {
                    "key": "parsers",
                    "icon": "parsers",
                    "label": "Parsers",
                    "doc": "user_guide/parsers/index",
                    "prefixes": ["user_guide/parsers/", "notebooks/parsers/"],
                    "toc": {"doc": "user_guide/parsers/index", "overview": "Overview", "show_caption": True},
                    "summary": "Read tables from EXIOBASE, EORA, FIGARO, OECD and more, or bring your own.",
                },
                {
                    "key": "inspection",
                    "icon": "inspection",
                    "label": "Inspection",
                    "doc": "user_guide/inspection/index",
                    "prefixes": ["user_guide/inspection/"],
                    "toc": {"doc": "user_guide/inspection/index", "overview": "Overview"},
                    "summary": "Look inside a database, compute its matrices, plot and export them.",
                },
                {
                    "key": "transformations",
                    "icon": "transformations",
                    "label": "Transformations",
                    "doc": "user_guide/transformations/index",
                    "prefixes": ["user_guide/transformations/"],
                    "toc": {"doc": "user_guide/transformations/index", "overview": "Overview"},
                    "summary": "Aggregate, extend, shock and convert a database.",
                },
                {
                    "key": "advanced",
                    "icon": "advanced",
                    "label": "Advanced",
                    "doc": "user_guide/advanced/index",
                    "prefixes": ["user_guide/advanced/"],
                    "toc": {"doc": "user_guide/advanced/index", "overview": "Overview"},
                    "summary": "End-to-end analyses on real databases such as EXIOBASE.",
                },
                {
                    "key": "api",
                    "icon": "api",
                    "label": "API",
                    "doc": "reference/api_library",
                    "prefixes": ["reference/", "api_document/"],
                    "toc": {"doc": "reference/api_library", "overview": "API reference", "max_depth": 0},
                    "summary": "Every public method, with its signature and parameters.",
                },
            ],
        },
        {
            "key": "resources",
            "home_label": "Resources",
            "home_summary": "Explore databases, applications and learning material.",
            "label": "Resources",
            "landing": "resources/research",
            "prefixes": ["resources/"],
            "hero": {
                "title": "Everything <mark>around</mark> MARIO",
                "text": "Database comparisons, analyses and benchmarks, projects and publications, teaching and downloadable material.",
            },
            "tabs": [
                {"label": "Database comparisons", "doc": "resources/database_coverage", "summary": "Explore geographic coverage and available sets."},
                {"label": "Analyses & benchmarks", "doc": "resources/benchmarks/index", "summary": "See how data and assumptions shape results.", "prefixes": ["resources/benchmarks/"]},
                {"label": "Projects & Publications", "doc": "resources/research", "summary": "Discover the research built with MARIO."},
                {"label": "Teaching", "doc": "resources/teaching", "summary": "Learn through courses and guided examples."},
                {"label": "Downloadable material", "doc": "resources/material", "summary": "Download notebooks, set lists and reference sheets."},
            ],
        },
    ],
    # Pages moved or removed in the 2026 redesign keep working through redirect pages.
    "redirects": {
        "setup/index": "get_started/index",
        "concepts/index": "get_started/nomenclature",
        "concepts/nomenclature": "get_started/nomenclature",
        "concepts/table_formats": "get_started/table_formats",
        "concepts/scenarios": "get_started/scenarios",
        "concepts/clusters": "get_started/nomenclature#clusters",
        "concepts/technology_assumptions": "get_started/table_formats#technology-assumptions",
        "contribute/index": "index",
        "contribute/architecture_overview": "index",
        "contribute/compute_layer": "index",
        "contribute/parsers": "index",
        "contribute/adding_new_matrices": "index",
        "contribute/testing_strategy": "index",
        "contribute/realdata_fixtures": "index",
        "contribute/documentation": "index",
        "user_guide/parsers/country_coverage": "user_guide/parsers/index",
        "resources/publications": "resources/research",
        "resources/benchmarks": "resources/benchmarks/index",
    },
}

bibtex_bibfiles = ["publications/mario.bib"]

# copy btn settings
copybutton_prompt_text = "<AxesSubplot:>"
