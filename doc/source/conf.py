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

if os.environ.get("MARIO_DOCS_CHANNEL") == "dev":
    tags.add("development")
_docs_revision = os.environ.get("MARIO_DOCS_REVISION", "main")
_development_install = (
    'python -m pip install "mariopy @ git+https://github.com/it-is-me-mario/MARIO.git@'
    + _docs_revision + '"'
)
rst_epilog = "\n.. |mario_development_install| replace:: " + _development_install + "\n"
_docs_channel = os.environ.get("MARIO_DOCS_CHANNEL", "latest")
_site_channel_path = _docs_channel + "/" if _docs_channel == "dev" else ""
_explorer_url = "https://explorer.marioproject.com/" + _site_channel_path
_tutorials_url = "https://tutorials.marioproject.com/" + _site_channel_path


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "mario_versions",
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
    "companions": {
        path.with_suffix("").relative_to(Path(__file__).parent).as_posix():
        path.relative_to(Path(__file__).parent).as_posix()
        for path in Path(__file__).parent.rglob("*.ipynb")
        if path.with_suffix(".rst").is_file()
    },
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
    # Notebooks are executable downloads; authored RST pages own the web layout.
    "**/*.ipynb",
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
html_css_files = ["heatmap-background.css", "benchmarks.css", "model-gallery.css"]
html_js_files = [
    # Reproducible frontend; dashed marker outlines require this Plotly.js version.
    "https://cdn.plot.ly/plotly-3.6.0.min.js",
    "external-links.js",
    "terminology-tables.js",
]

# Long signatures get one parameter per line.
python_maximum_signature_line_length = 88

_nomenclature_redirect = {
    "target": "get_started/table_formats",
    "anchors": {
        "nomenclature": "get_started/table_formats",
        "basic-definitions": "get_started/table_formats#format-basic-definitions",
        "default-canonical-labels": "reference/api_indices#canonical-names-and-aliases",
        "indices": "reference/api_indices",
        "regional-classifications": "reference/api_indices#regional-classifications",
        "matrices": "reference/api_resolvable_matrices#block-catalog",
        "terminology-indices-table": "reference/api_indices#terminology-indices-table",
        "terminology-matrices-table": "reference/api_resolvable_matrices#terminology-matrices-table",
        "clusters": "user_guide/inspection/clusters",
        "concept-clusters": "user_guide/inspection/clusters#concept-clusters",
    },
}

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
        "title": "Input-output analysis<br>in <mark>Python</mark>",
        "text": (
            "Work with input-output and supply-use tables, from reading a database "
            "to building scenarios and analysing impacts across regions and sectors."
        ),
        "install": True,
        "actions": [
            {"label": "Start with MARIO", "doc": "get_started/index"},
            {"label": "Explore indicators", "url": _explorer_url + "resources/data-explorer/compare.html"},
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
                "title": "Get started with MARIO",
                "text": "Install MARIO, understand your table's structure and work with scenarios.",
            },
            "tabs": [
                {"label": "Installation", "doc": "get_started/index", "summary": "Install MARIO and prepare your Python environment."},
                {"label": "Table formats", "key": "formats", "doc": "get_started/table_formats",
                 "prefixes": ["get_started/table_formats/"],
                 "summary": "Read IOT and SUT structure, indices and matrix names."},
                {"label": "Scenarios", "doc": "get_started/scenarios", "summary": "Organise and compare different model scenarios."},
            ],
        },
        {
            "key": "docs",
            "home_label": "Documentation",
            "home_summary": "Import data, calculate indicators and modify models.",
            "label": "Docs",
            "landing": "user_guide/index",
            "prefixes": ["user_guide/", "notebooks/", "reference/", "api_document/", "changelog"],
            "sidebar": True,
            "hero": {
                "title": "Documentation",
                "text": "Guides to importing data, calculating results and building scenarios, with the complete API reference.",
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
            "key": "explorer",
            "home_label": "Explorer",
            "home_summary": "Compare database classifications and explore economic and environmental indicators.",
            "label": "Explorer",
            "landing": _explorer_url,
            "prefixes": ["resources/data-explorer/"],
            "tabs": [
                {"label": "Classifications", "doc": _explorer_url + "resources/data-explorer/scope.html", "summary": "Compare geographical, sectoral and environmental coverage."},
                {"label": "Indicators", "doc": _explorer_url + "resources/data-explorer/compare.html", "summary": "Explore economic indicators, emissions and bilateral trade."},
                {"label": "Analyses", "doc": _explorer_url + "resources/data-explorer/analyses.html", "summary": "Read economic and electricity comparisons across databases."},
            ],
        },
        {
            "key": "resources",
            "home_label": "Resources",
            "home_summary": "Find tutorials, courses, applications and learning material.",
            "label": "Resources",
            "landing": _tutorials_url,
            "prefixes": ["resources/"],
            "hero": {
                "title": "Resources",
                "text": "Tutorials, teaching, projects and publications, and downloadable material.",
            },
            "tabs": [
                {"label": "Tutorials", "doc": _tutorials_url, "summary": "Follow complete exercises and download their source materials."},
                {"label": "Model gallery", "doc": "resources/model-gallery/index", "prefixes": ["resources/model-gallery/"], "summary": "Research models, publications and their code and data editions."},
                {"label": "Teaching", "doc": "resources/teaching", "summary": "Learn through courses and recorded lessons."},
                {"label": "Projects & Publications", "doc": "resources/projects_publications", "summary": "Discover the research built with MARIO."},
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
            "text": "Request a <mark>MARIO course</mark>",
            "dialog": {
                "title": "MARIO courses",
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
        "concepts/index": _nomenclature_redirect,
        "concepts/nomenclature": _nomenclature_redirect,
        "get_started/nomenclature": _nomenclature_redirect,
        "concepts/table_formats": "get_started/table_formats",
        "concepts/scenarios": "get_started/scenarios",
        "concepts/clusters": "user_guide/inspection/clusters",
        "concepts/technology_assumptions": "get_started/table_formats/sut#technology-assumptions",
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
        "user_guide/parsers/bonsai_methods": "reference/api_indices#regional-classifications",
        "resources/publications": "resources/projects_publications",
        "resources/data-explorer": "resources/data-explorer/scope",
        "resources/data-explorer/browsers": "resources/data-explorer/compare",
        "resources/changelog": "changelog",
    },
}

bibtex_bibfiles = ["publications/mario.bib"]

# copy btn settings
copybutton_prompt_text = "<AxesSubplot:>"

# The independent explorer has its own release and deployment workflow.
mario_site["external_pages"] = {
    "resources/data-explorer/" + name: _explorer_url + "resources/data-explorer/" + name + ".html"
    for name in ("scope", "compare", "analyses", "electricity_carbon_footprint", "economy_emissions")
}
