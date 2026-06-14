****************
Release History
****************

v1.0.2
------

Packaging and installation
~~~~~~~~~~~~~~~~~~~~~~~~~~

* Installed Parquet support by default by shipping the package with the
  required dependency out of the box, refreshed the installation guidance,
  refined optional-dependency messaging, and added package-metadata regression
  coverage. Resolved issue `#142 <https://github.com/it-is-me-mario/MARIO/issues/142>`_.

SUT scenarios and native matrix workflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Extended SUT scenario updates so unified ``Z``, ``Y`` and ``E`` inputs are
  accepted directly and normalized through the shared ordering logic, with
  dedicated regression tests for the new update paths. Resolved issue
  `#144 <https://github.com/it-is-me-mario/MARIO/issues/144>`_.
* Switched SUT export and parser roundtrips to native SUT blocks instead of
  legacy unified IOT-style matrices, while preserving backward-compatible
  parsing of historical TXT, Parquet and Excel layouts. Resolved issue
  `#146 <https://github.com/it-is-me-mario/MARIO/issues/146>`_.

v1.0.1
------

Core calculations and regional subsets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Added exploded price-contribution accessors for the price index workflow:
  ``p_ex`` / ``p_ex_all`` for IOT databases and ``pa_ex`` / ``pa_ex_all`` plus
  ``pc_ex`` / ``pc_ex_all`` for SUT activity- and commodity-side
  contributions.
* Expanded ``Database.to_region_subset(...)`` and ``to_single_region(...)``
  with sectorized external-trade layouts via
  ``externalized_trade_layout="sectorized"`` and the shorthand trade modes
  ``"by_sector"`` and ``"by_region_and_sector"``.
* Fixed IOT sectorized subset export so ``to_excel(...)`` writes a coherent
  explicit special-layout workbook, including aligned ``VY`` rows and public
  ``Region/Sector`` plus ``Region/Consumption category`` axes without legacy
  ``Level`` markers.
* Added an explicit ``NotImplementable`` guard for SUT
  ``to_region_subset(...)`` calls that request custom ``trade_mode`` or
  non-legacy externalized-trade layouts, while preserving the standard legacy
  subset workflow for SUT tables.

Parquet and packaging
~~~~~~~~~~~~~~~~~~~~~

* Made ``pyarrow>=17`` an explicit optional dependency for Parquet parsing,
  export and storage workflows, added clearer runtime guidance when Parquet
  support is unavailable, and exposed a dedicated ``mariopy[parquet]`` extra.
* Hardened PyPI packaging metadata by sanitizing ``README.rst`` raw-directive
  blocks before publishing it as the package long description and by declaring
  the ``text/x-rst`` content type explicitly in ``setup.py``.

Documentation
~~~~~~~~~~~~~

* Added installation guidance for optional Parquet support and refreshed the
  README setup instructions.
* Reworked API-reference navigation and expanded the shock-workflow and
  transformation documentation, including doc-build warning fixes and notebook
  metadata cleanup for the published docs.

v1.0.0
------

Architecture and public API
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Reorganized MARIO around clearer ``api``, ``compute``, ``ops``, ``parsers``,
  ``views``, ``storage`` and ``internal`` modules.
* Moved most legacy logic out of ``core`` and ``tools`` and consolidated the
  public surface around ``Database``.
* Added support for renamed baseline scenarios, more ergonomic matrix/index
  inspection helpers, and template-based custom database authoring workflows.
* Added a unified ``Database.plot(...)`` workflow backed by Plotly Express and
  kept the historical plotting helpers as deprecated compatibility wrappers.
* Added exploded multiplier and footprint accessors on ``CoreModel`` through
  ``f_ex``, ``fa_ex``, ``fc_ex``, ``m_ex``, ``ma_ex``, ``mc_ex`` and the
  corresponding ``*_all`` convenience properties.
* Added a more explicit compute layer with planner, resolver, primitives,
  formula modules and dependency graph utilities.
* Added trade-analysis APIs, trade-content plotting, parser-based scenario
  import workflows, and default shock clusters with automatic region mapping.
* Configured MARIO to default to ``INFO`` logging on import while preserving
  explicit ``set_log_verbosity(...)`` overrides.

Parsing and export
~~~~~~~~~~~~~~~~~~

* Added ``matrix_layout`` as a backward-compatible alias for
  ``matrix_layouts`` in Excel parsing entry points and reject ambiguous calls
  that pass both names at once.

* Unified Excel, TXT and Parquet parsing through a shared parser-state flow.
* Added native flat TXT/Parquet export and matching re-import support.
* Introduced ``matrix_layouts`` support for richer IOT and SUT layouts,
  including cases where ``V`` and ``E`` carry additional ``Region`` and
  ``Sector``/``Activity`` levels.
* Preserved legacy public axes for historical workbooks while allowing newer
  explicit layouts without forcing ``Level`` markers back into exports.
* Added structural ``tech_assumption`` support for SUT parsing with
  ``industry-based`` / ``product-based`` modes, including automatic fallback to
  ``industry-based`` for non-square SUT tables.
* Expanded direct parser coverage with BEA supply-use, CEADS, CEPALSTAT,
  USEEIO and GLORIA support, and improved parser robustness for FIGARO,
  OECD ICIO, EMERGING bundles and zip-based imports.

Add sectors and structural operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Refactored ``add_sectors`` around a workbook-driven workflow with a single
  template format.
* Added CVXLab-backed ``split=True`` support for IOT workflows, including a
  packaged ``Split_sectors`` model template.
* Improved ``add_sectors`` compatibility with explicit IOT layouts where
  ``V``/``E`` do not follow the old ``Region/Level/Item`` convention.
* Added overwrite protection to ``get_add_sectors_excel(...)`` and
  ``get_inventory_sheets(...)`` so existing files and inventory sheets are not
  replaced unless ``overwrite=True`` is passed explicitly.

Aggregation and transforms
~~~~~~~~~~~~~~~~~~~~~~~~~~

* Made aggregation robust to layout-aware ``V`` and ``E`` blocks without
  breaking the legacy public surface.
* Changed ``aggregate(...)`` to default to ``calc_all=False`` and hardened
  sparse export paths, including a fix for sparse ``to_parquet(...)`` output.
* Added a default ``zero_output_epsilon`` fallback during aggregation so
  zero-output items with non-zero stored coefficients do not lose their
  reconstructed ``z``/``v``/``e`` columns after aggregation.
* Added ``VY`` as a first-class factor-of-production final-demand block across
  MARIO.
* Kept transformation utilities in the new ``ops`` layout and aligned them with
  the refactored parser/database flow.
* Added SUT-native structural assumption management, including a public
  ``change_assumption(...)`` workflow and table-aware reset operations that now
  preserve split SUT blocks instead of rebuilding unified placeholders first.

Compute and SUT semantics
~~~~~~~~~~~~~~~~~~~~~~~~~

* Added product-based SUT support to the compute layer, including the public
  matrix ``c`` and the corresponding supply-side formulas alongside the
  historical industry-based path.
* Made SUT technology assumptions a first-class database property that is
  stored in metadata, shown in database summaries, preserved by test fixtures,
  and cleared when transforming SUT databases into IOT form.
* Added ``Database.calc_ghg(...)`` with built-in EXIOBASE, EORA, GLORIA and
  EMERGING profiles, plus improved metadata matching and satellite-account
  aggregation.
* Added SUT-specific Ghosh formulas alongside the refactored supply-side
  compute path.
* Introduced sparse-aware helper routines for shared compute operations such as
  row/column sums, matrix-matrix products, and matrix-vector products, and
  routed more IOT/SUT formulas through those helpers instead of direct
  pandas/NumPy calls.

Parsers and downloaders
~~~~~~~~~~~~~~~~~~~~~~~

* Added or rewrote direct parsers for Eurostat SDMX, FIGARO, OECD ICIO, WIOD,
  ADB MRIO, EMERGING, EORA, GTAP, StatCan and EXIOBASE IOT/SUT/hybrid data.
* Separated raw-data download utilities from parser-side logic and exposed a
  cleaner downloader surface.

Testing and documentation
~~~~~~~~~~~~~~~~~~~~~~~~~

* Greatly expanded the automated test suite across compute, parser, export,
  downloader and add-sectors workflows.
* Added focused regression coverage and API reference pages for exploded
  matrices and the new plotting workflow.
* Added vendored real-data workbook fixtures for IOT and SUT plus aggregation
  templates, with roundtrip tests for Excel, TXT and Parquet exports.
* Added pandas 3 compatibility fixes, parser coverage reporting, and broader
  parser/developer documentation refreshes across the user guide and README.
* Added a visualization user-guide notebook for ``db.plot(...)`` and updated
  notebook resolution so published docs persist HTML Plotly output instead of
  unsupported ``application/vnd.plotly.v1+json`` payloads.
* Removed GTAP and CEPALSTAT pages from the published documentation while
  keeping their parser implementations in the package.
* Rewrote and expanded developer-facing documentation, tutorials and parser
  development guidance.


v 0.3.4
-------

Parsing functions error fixed
~~~~~~~~
Recent pandas versions have changed the way they interpret "None" in DataFrames indices and values, which are currently interpreted it as NaN. 
This mario update fixes the issue by replacing NaN with the string "None" when parsing excel files.

Deprecated functions
~~~~~~~~
Parser for old-fashioned Eurostat SUTs is deprecated. This function relied on peculiarly structured SUTs formats.
In case you need to parse such SUTs, please rearrange them into the standard MARIO format.
You can check the MARIO format from 'test_SUT_standard.xlsx' file in the mario/test/tables directory in this repository.


v 0.3.3
-------

Settings
~~~~~~~~
to_excel function bug in flow mode fixed.


v 0.3.0
-------

Settings
~~~~~~~~

New functionalities are provided to allow the user to change some naming convensions in mario indexing and input-output nomenclature convensions in mario.

Isard to Chenery-Moses Transformation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The transformation implies moving from trades accounted in the USE matrix to trades accounted in the SUPPLY matrix.

Data Templates
~~~~~~~~~~~~~~

New functionalities are added to create an enpty IO/SU tables  from tabular data.

Figaro Parser
~~~~~~~~~~~~~

New download and parsing functionalities are added to parser figaro database.


Table Downloader
~~~~~~~~~~~~~~~~

Donwload functions are added to the software. Some of the download functions are using pymrio database download functionalities, and some other databases are mario exclusive.

Deprecated functions
~~~~~~~~~~~~~~~~~~~~

is_productive and backup methods are deprecated.

Improvements
~~~~~~~~~~~~

* The add_sector function imprvements are implemented to make the code faster.
* Updating dependencies versioning (specifically pandas, numpy and xlsxwriter) 


Documentation
~~~~~~~~~~~~~

* The tutorials are updated to improve the readiblity and quality of the juputer notebook functionalities.
* New templates for the readthedocs.
