Documentation change map
========================

Paths below are relative to the repository root. Start with the canonical
source, then review its dependent pages. This is a map of responsibilities,
not a second copy of API definitions or database metadata.

Page ownership
--------------

.. list-table::
   :header-rows: 1
   :widths: 27 43 30

   * - Topic
     - Main web pages under ``doc/source/``
     - Also review
   * - Data sources and imports
     - ``user_guide/parsers/index.rst`` and source guides in
       ``notebooks/parsers/``; BONSAI uses ``user_guide/parsers/bonsai.rst``
     - Parser API, companion, source profile and catalogue
   * - Inspecting, querying and exporting
     - ``user_guide/inspection/`` and its ``index.rst``
     - API, paired notebook and file-format examples
   * - Matrices and GHG calculations
     - ``user_guide/analysis/index.rst``, ``analysis/greenhouse_gases.rst``,
       ``analysis/ghg_characterization.rst``, ``inspection/compute_matrices.rst``
     - Matrix catalogue, calculation API, GHG profiles and examples
   * - Trade, paths and production mixes
     - ``user_guide/analysis/supply_chains.rst``, ``structural_paths.rst`` and
       ``production_mix.rst`` in the same directory
     - Corresponding API; worked examples in ``user_guide/advanced/``
   * - Transformations and scenarios
     - ``user_guide/transformations/``; electricity updates use
       ``user_guide/advanced/electricity_mix.rst``
     - API, paired notebook and transformation index
   * - Database profiles and classifications
     - ``user_guide/advanced/database_profiles.rst``,
       ``inspection/concordances.rst``,
       ``transformations/classification_aggregation.rst`` and
       ``transformations/classification_mapping.rst`` under ``user_guide/``
     - Profile, concordance and aggregation APIs; explorer classifications
   * - Configuration
     - ``user_guide/configuration/index.rst``,
       ``advanced/compute_settings.rst`` and
       ``inspection/custom_labels_and_aliases.rst`` under ``user_guide/``
     - Settings API, install guidance and affected database guides
   * - Complete analyses
     - ``user_guide/examples/index.rst`` and linked case pages
     - Topic guide, notebook, scientific assumptions and figure captions
   * - API reference
     - ``api_document/`` for individual symbols; ``reference/`` for indexes
     - Implementation docstrings, task guide and public-symbol coverage tests

Navigation and layout
---------------------

``doc/source/conf.py`` owns topic membership through
``mario_site["sections"]`` and compatibility URLs through
``mario_site["redirects"]``. Each topic index also owns its toctree and visible
task links. Update both when adding or moving a page; do not infer membership
from a legacy ``advanced/`` or ``notebooks/`` path. Search navigation is generated
as ``_static/mario-nav.json`` in the build output, not edited by hand.

For a public feature, connect **guide <-> API**, and **guide <-> worked example**
when an example exists. Check the feature from the topic menu as well as from
search. Adding a page only to Examples leaves the operation undiscoverable.

Components live in ``doc/source/_ext/mario_site.py``; styling in
``doc/source/_static/docs-workflows.css`` and ``doc/source/_themes/mario/``.
Changes there require representative desktop and narrow-screen checks, including
navigation, code blocks, disclosure links and keyboard interaction.

Notebook companions
-------------------

Keep ``name.rst`` and ``name.ipynb`` together and put a ``:download:`` link inside
a ``mario-companion`` container on the guide. The companion registry in
``conf.py`` discovers these pairs; ``resources/material.rst`` renders the shared
download list. All database parser/test notebooks must remain downloadable.

BONSAI's shared companion is ``user_guide/examples/bonsai.ipynb``: both its source
guide and its example link to it. A second copy is unnecessary.

When a call, selector, input or scientific assumption changes, review the page
and the complete notebook. ``doc/source/_ext/mario_downloads.py`` cleans only
published copies. Do not rely on saved outputs as evidence of a current run.
See `download generation instructions <../scripts/downloads.rst>`_ for notices
and other downloadable assets.

Shared metadata and generated assets
------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 26 40 34

   * - Change
     - Canonical source / generator
     - Dependent material to review
   * - Runtime database identity, GHG or compute defaults
     - ``mario/database_profiles/registry.py``, ``ghg.py``, ``compute.py``;
       session settings in ``mario/settings/``
     - Profile guide, GHG/compute guides, affected parser guides and API;
       optional solver installation instructions
   * - Classification coverage or hierarchy
     - ``doc/classifications/sectoral/`` and
       ``doc/scripts/build_sectoral_scope.py``;
       ``doc/scripts/build_runtime_concordances.py`` packages runtime bundles
     - Explorer, concordance downloads, packaged bundles under
       ``mario/database_profiles/data/concordances/`` and aggregation behaviour
   * - A parsed database release or its sets
     - ``doc/scripts/database_catalogue.py``;
       ``doc/source/_static/data/database_profiles.json`` is the summary
     - Parser cards and guide panels, explorer coverage, native-set downloads
       and source notices
   * - Explorer indicators
     - Source-specific scripts in ``doc/scripts/`` and their saved provenance
     - Indicator definitions, units, characterization, reference year,
       update date, plots and exports
   * - Release or installation behaviour
     - Package version/dependencies and ``CHANGELOG.rst``
     - README, Get started installation and affected feature guides

Use `catalogue instructions <../scripts/database_catalogue.rst>`_,
`classification instructions <../classifications/sectoral/README.md>`_ and
`economy browser instructions <../scripts/economy_browser.rst>`_ for the specific
pipeline. Regenerate from the relevant source; do not patch generated counts or
compiled concordance bundles by hand. Updating prose alone does not require
parsing a database or refreshing external data.

Distinguish runtime profiles from parsed-release inventories: they serve
different purposes. Keep source release, observation year, update date and
classification edition explicit where they affect interpretation. For BONSAI,
regional sector counts vary; a global label count is not a uniform regional
dimension. GHG comparisons must identify the characterization used in each
result rather than inheriting a notebook's default silently.
