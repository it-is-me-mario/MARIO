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
from pathlib import Path
from runpy import run_path
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
except ImportError:  # pragma: no cover - docs fallback when Plotly is absent
    pio = None


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
release = run_path(str(Path(__file__).resolve().parents[2] / "mario" / "version.py"))["__version__"]


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
    "prefixes": ["notebooks/parsers/", "user_guide/advanced/", "user_guide/examples/"],
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
    "user_guide/inspection/custom_labels.ipynb",
    "user_guide/advanced/change_settings.ipynb",
    "user_guide/advanced/large_database_workflows.ipynb",
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
html_baseurl = os.environ.get("MARIO_DOCS_BASEURL") or os.environ.get("READTHEDOCS_CANONICAL_URL", "")
html_permalinks_icon = "#"
html_show_sourcelink = False
html_copy_source = False

html_static_path = ["_static"]
html_css_files = ["heatmap-background.css", "benchmarks.css"]
html_js_files = [
    # Reproducible frontend; dashed marker outlines require this Plotly.js version.
    "https://cdn.plot.ly/plotly-3.6.0.min.js",
    "external-links.js",
    "terminology-tables.js",
]

# Long signatures get one parameter per line.
python_maximum_signature_line_length = 88

mario_site = {
    "github": "https://github.com/it-is-me-mario/MARIO",
    "pypi": "https://pypi.org/project/mariopy/",
    "install": "pip install mariopy",
    # Transparency notice on AI-assisted content (EU AI Act, Regulation (EU) 2024/1689), shown in every footer.
    "ai_notice": (
        "<strong>AI disclosure.</strong> This documentation and its database explorer were written and built "
        "with AI agents, then reviewed by the MARIO team, who remain responsible for their content. "
        'Spotted an error? <a href="https://github.com/it-is-me-mario/MARIO/issues">Tell us on GitHub Issues</a>.'
    ),
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
            "prefixes": ["user_guide/", "notebooks/", "reference/", "api_document/", "changelog"],
            "sidebar": True,
            "hero": {
                "title": "Everything MARIO <mark>can do</mark>",
                "text": (
                    "Parse a database, inspect and transform it, run advanced workflows, "
                    "look up every method in the API reference and see what changed in each release."
                ),
            },
            "navigation_style": "sidebar",
            "tabs": [
                {
                    "key": "parsers",
                    "icon": "parsers",
                    "label": "Data sources",
                    "doc": "user_guide/parsers/index",
                    "prefixes": [
                        "user_guide/parsers/",
                        "notebooks/parsers/"
                    ],
                    "pages": [
                        "user_guide/advanced/database_profiles"
                    ],
                    "toc": {
                        "doc": "user_guide/parsers/index",
                        "show_caption": True
                    },
                    "summary": "Choose a source, import its tables and understand its metadata."
                },
                {
                    "key": "inspection",
                    "icon": "inspection",
                    "label": "Working with a database",
                    "doc": "user_guide/inspection/index",
                    "prefixes": [
                        "user_guide/inspection/"
                    ],
                    "toc": {
                        "doc": "user_guide/inspection/index"
                    },
                    "summary": "Explore sets and matrices, find classification codes and export data."
                },
                {
                    "key": "analysis",
                    "icon": "chart",
                    "label": "Calculations and analysis",
                    "doc": "user_guide/analysis/index",
                    "prefixes": [
                        "user_guide/analysis/"
                    ],
                    "pages": [
                        "user_guide/inspection/compute_matrices",
                        "user_guide/inspection/visualization"
                    ],
                    "toc": {
                        "doc": "user_guide/analysis/index"
                    },
                    "summary": "Calculate matrices, characterize emissions and interpret results."
                },
                {
                    "key": "transformations",
                    "icon": "transformations",
                    "label": "Transformations and scenarios",
                    "doc": "user_guide/transformations/index",
                    "prefixes": [
                        "user_guide/transformations/"
                    ],
                    "pages": [
                        "user_guide/advanced/electricity_mix"
                    ],
                    "toc": {
                        "doc": "user_guide/transformations/index"
                    },
                    "summary": "Aggregate or convert a table, extend its accounts and build scenarios."
                },
                {
                    "key": "configuration",
                    "icon": "advanced",
                    "label": "Configuration",
                    "doc": "user_guide/configuration/index",
                    "prefixes": [
                        "user_guide/configuration/"
                    ],
                    "pages": [
                        "user_guide/advanced/compute_settings",
                        "user_guide/inspection/custom_labels_and_aliases"
                    ],
                    "toc": {
                        "doc": "user_guide/configuration/index"
                    },
                    "summary": "Choose computation settings and customize your Python session."
                },
                {
                    "key": "examples",
                    "icon": "paths",
                    "label": "Examples",
                    "doc": "user_guide/examples/index",
                    "prefixes": [
                        "user_guide/examples/"
                    ],
                    "pages": [
                        "user_guide/advanced/supply_chain_analyses",
                        "user_guide/advanced/structural_path_analysis"
                    ],
                    "toc": {
                        "doc": "user_guide/examples/index"
                    },
                    "summary": "Follow complete analyses with downloadable notebooks."
                },
                {
                    "key": "api",
                    "icon": "api",
                    "label": "API reference",
                    "doc": "reference/api_library",
                    "prefixes": [
                        "reference/",
                        "api_document/"
                    ],
                    "toc": {
                        "doc": "reference/api_library",
                        "max_depth": 1
                    },
                    "summary": "Look up signatures, parameters, returned values and equations."
                }
            ],
        },
        {
            "key": "resources",
            "home_label": "Resources",
            "home_summary": "Explore databases, applications and learning material.",
            "label": "Resources",
            "landing": "resources/data-explorer/scope",
            "prefixes": ["resources/"],
            "hero": {
                "title": "Everything <mark>around</mark> MARIO",
                "text": "Database explorer, projects and publications, teaching and downloadable material.",
            },
            "tabs": [
                {"label": "Database explorer", "doc": "resources/data-explorer/scope", "featured": True, "summary": "Compare classifications, explore indicators and read analyses.", "prefixes": ["resources/data-explorer/"], "children": [
                    {"label": "Classifications", "doc": "resources/data-explorer/scope"},
                    {"label": "Compare databases", "doc": "resources/data-explorer/compare"},
                    {"label": "Analyses", "doc": "resources/data-explorer/analyses", "prefixes": ["resources/data-explorer/electricity_"]},
                ]},
                {"label": "Projects & Publications", "doc": "resources/projects_publications", "summary": "Discover the research built with MARIO."},
                {"label": "Teaching", "doc": "resources/teaching", "summary": "Learn through courses and guided examples."},
                {"label": "Downloadable material", "doc": "resources/material", "summary": "Download notebooks, set lists and reference sheets."},
            ],
        },
    ],
    # Large closing line at the end of a page, outside its tab panels.
    "closings": {
        **{page: {"text": "Learn how to <mark>use</mark> these databases", "doc": "user_guide/parsers/index"}
           for page in ("resources/data-explorer/scope", "resources/data-explorer/compare")},
        # Opens a contact dialog that drafts an email in the visitor's own mail app; nothing is sent by the site.
        "resources/teaching": {
            "text": "Would you be interested in a <mark>MARIO course</mark>? Let us know!",
            "dialog": {
                "title": "A MARIO course for you or your team",
                "intro": (
                    "We don't run scheduled courses yet, but if you or your team are interested "
                    "in a course, we can work out the format together."
                ),
                "subject": "MARIO course enquiry",
                # Split so no address appears whole in the page source.
                "recipients": [("lorenzo.rinaldi", "polimi.it"), ("nicolo.golinucci", "enextgen.it")],
            },
        },
    },
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
        "notebooks/parsers/bonsai/walkthrough_bonsai": "user_guide/parsers/bonsai",
        "user_guide/advanced/greenhouse_gas_calculations": "user_guide/analysis/greenhouse_gases",
        "user_guide/advanced/index": "user_guide/index",
        "user_guide/parsers/bonsai_methods": "get_started/nomenclature#regional-classifications",
        "resources/publications": "resources/projects_publications",
        "resources/data-explorer": "resources/data-explorer/scope",
        "resources/data-explorer/browsers": "resources/data-explorer/compare",
        "resources/changelog": "changelog",
    },
}

bibtex_bibfiles = ["publications/mario.bib"]

# copy btn settings
copybutton_prompt_text = "<AxesSubplot:>"
