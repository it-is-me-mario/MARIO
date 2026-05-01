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
from datetime import datetime

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(".."))
sys.path.insert(0, os.path.abspath("../.."))
sys.path.insert(0, os.path.abspath("../../.."))

import mario_bibstyles

# -- Project information -----------------------------------------------------


project = 'MARIO'
copyright = f'{datetime.now().year}, Lorenzo Rinaldi, Mohammad Amin Tahavori, Nicolo Golinucci'
author = 'Lorenzo Rinaldi, Mohammad Amin Tahavori, Nicolo Golinucci'

# The full version, including alpha/beta/rc tags
release = '0.3.5'


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
{% if env.docname.startswith("notebooks/parsers/") %}
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
    "user_guide/advanced/change_settings.ipynb",
    "user_guide/advanced/large_database_workflows.ipynb",
    "contribute/documentation.rst",
    "resources/changelog.rst",
    "notebooks/parsers/gtap/**",
    "notebooks/parsers/cepalstat/**",
]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#


html_theme = "pydata_sphinx_theme"
html_title = "MARIO Documentation"
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
html_js_files = ["external-links.js", "terminology-tables.js", "parser-coverage.js"]
bibtex_bibfiles = ["publications/mario.bib"]

# copy btn settings
copybutton_prompt_text = "<AxesSubplot:>"
