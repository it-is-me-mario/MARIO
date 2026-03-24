Developer Guide
===============

This page is the working map of the MARIO codebase for developers. It is meant
to answer four practical questions:

* what the main runtime layers are;
* where each responsibility lives in the repository;
* which file to edit for a given type of change;
* which modules are current architecture, compatibility shims, or legacy paths.

The guide is intentionally broad, but each file description is kept short. The
goal is orientation, not line-by-line commentary.


Reading Order
-------------

If you are new to the project, read the codebase in this order:

1. ``mario/__init__.py`` to see the public surface.
2. ``mario/api/core_model.py`` and ``mario/api/database.py`` to understand the
   public object model.
3. ``mario/compute/`` to understand how matrices are resolved.
4. ``mario/parsers/`` to understand how raw data becomes a ``Database``.
5. ``mario/ops/`` to understand mutations, export, aggregation and transforms.
6. ``mario/internal/`` and ``mario/storage/`` if you need the newer block-state
   substrate or alternative storage backends.


Repository Map
--------------

At the repository root, the main folders and files are:

``README.rst``
   User-facing project overview.

``CHANGELOG.rst``
   Release notes and change history.

``setup.py``, ``pyproject.toml``, ``requirements.txt``, ``requirements.yml``
   Packaging and dependency definitions.

``doc/``
   Sphinx documentation source and built tutorial assets.

``mario/``
   The library itself.

``tests/``
   Test suite for runtime behavior, parser coverage and compute correctness.

``Output/``
   Local output artifacts used in tests/examples. Not core source code.

``dummy/`` and ``mariopy.egg-info/``
   Local/dev packaging artifacts. Not part of the core architecture.

``test.py``
   Ad hoc local script; not part of the packaged API.


Runtime Architecture
--------------------

MARIO currently has one public runtime object family and one internal
implementation substrate:

``mario.Database``
   The public object that users parse, query, transform, aggregate, export and
   mutate.

``mario.internal.ModelState``
   The internal block-oriented state model used by the newer parser/storage
   architecture. It is an implementation layer, not a second user API.

The codebase is organized around that split:

``mario.api``
   Public object model.

``mario.compute``
   Catalog-driven matrix resolution.

``mario.parsers``
   Raw-data parsing and parser infrastructure.

``mario.ops``
   Mutating and export operations.

``mario.views``
   Presentation helpers.

``mario.model``
   Shared conventions, labels and empty builders.

``mario.internal`` and ``mario.storage``
   Internal state/storage abstractions introduced by the newer architecture.


Top-Level Package Files
-----------------------

``mario/__init__.py``
   Public import surface. Re-exports ``Database``, ``CoreModel``, parser
   entrypoints, matrix primitives, settings helpers, plotting helpers and test
   loaders.

``mario/version.py``
   Package version constant.

``mario/utils.py``
   Shared low-level helpers that do not fit cleanly elsewhere. This is still a
   mixed utility module, so changes here should be conservative.

``mario/download.py``
   Downloader helpers for some historical data sources. Useful as convenience,
   but not the architectural center of current parser work.


``mario/api/``
--------------

This folder contains the public object model.

``mario/api/__init__.py``
   Canonical exports for the API layer.

``mario/api/core_model.py``
   Shared base class for database-like objects. Owns:

   * matrix and scenario storage;
   * ``calc_all(...)``, ``resolve(...)``, ``query(...)``, ``get_data(...)``;
   * block access adapters;
   * scenario reset logic;
   * a large part of the public read/update contract.

   If a change is about matrix lifecycle rather than a specific operation, it
   usually belongs here.

``mario/api/database.py``
   User-facing ``Database`` implementation. Adds higher-level workflows on top
   of ``CoreModel``:

   * aggregation;
   * SUT/IOT transforms;
   * exports;
   * shocks;
   * plotting;
   * add-sectors and split/CVXLab integration;
   * single-region extraction.

   If a method is explicitly exposed to users, this is usually where the public
   wrapper lives.

``mario/api/metadata.py``
   ``MARIOMetaData`` container used by ``Database.meta``. Handles metadata,
   persistence and history log entries.


``mario/compute/``
------------------

This folder is the computational core. The current compute path is catalog
driven.

``mario/compute/__init__.py``
   Public exports for the compute layer.

``mario/compute/catalog.py``
   Authoritative description of all matrix blocks known by MARIO. Each block
   declares:

   * its axes;
   * whether it is parsed, extracted, concatenated or formula-based;
   * which dependencies or strategies exist.

   If you add a new canonical matrix, start here.

``mario/compute/types.py``
   Typed metadata objects for catalog/planner/resolver internals:
   ``MatrixSpec``, strategy classes, axis specs and planning context types.

``mario/compute/planner.py``
   Converts catalog declarations into an ordered plan of candidate strategies
   for a requested matrix.

``mario/compute/resolver.py``
   Executes the selected plan, resolves dependencies and materializes results
   back into the current dataset state.

``mario/compute/helpers.py``
   Shared numerical helpers used by formulas.

``mario/compute/primitives.py``
   Public numerical wrappers such as ``calc_Z``, ``calc_X`` and related helper
   functions exposed from ``mario`` top level.

``mario/compute/iot_formulas.py``
   Numerical implementations specific to IOT formulas.

``mario/compute/sut_formulas.py``
   Numerical implementations specific to SUT formulas.

``mario/compute/ghosh_formulas.py``
   Ghosh-side formulas and related operator calculations.

``mario/compute/views.py``
   Cheap extract/concat builders for split and unified views, especially on
   SUTs. This is where many “derived without recomputing” blocks live.

``mario/compute/ordering.py``
   SUT ordering policy logic that defines how unified and split SUT blocks are
   aligned and concatenated.

``mario/compute/graph.py``
   Dependency graph rendering and explanation helpers used for introspection.


``mario/internal/``
-------------------

This folder contains the newer internal state model. It matters mainly for
developers working on parsers, storage and the long-term move away from a pure
``dict[str, DataFrame]`` mindset.

``mario/internal/__init__.py``
   Internal state exports.

``mario/internal/state.py``
   ``ModelState`` implementation: scenarios, blocks, indexes, units, repository
   access and resolver integration.

``mario/internal/scenario.py``
   ``ScenarioState`` container for locally owned blocks and provenance.

``mario/internal/block.py``
   ``StoredBlock`` metadata record for one persisted block.

``mario/internal/metadata.py``
   ``ModelStateMetadata`` container used by internal parser/state flows.

``mario/internal/access.py``
   Access adapters that convert a stored block to pandas, a tabular backend or
   a numeric matrix backend. This is the main seam for future non-pandas
   storage.


``mario/log_exc/``
------------------

Cross-cutting exceptions and logging helpers.

``mario/log_exc/__init__.py``
   Namespace marker.

``mario/log_exc/exceptions.py``
   Custom exception classes used across the library.

``mario/log_exc/logger.py``
   Shared logging helpers, verbosity setup and warning suppression.


``mario/model/``
----------------

This folder contains domain-level conventions that should stay stable across
parsers and operations.

``mario/model/__init__.py``
   Lazy exports for builders, labels and enums.

``mario/model/conventions.py``
   Core structural conventions:

   * table kinds;
   * matrix titles;
   * canonical index/column layouts;
   * configured nomenclature aliases.

``mario/model/labels.py``
   Cached human-readable labels derived from settings. Used heavily by the new
   compute/core code.

``mario/model/enums.py``
   Lightweight enums such as ``TableKind`` and ``BlockRole``.

``mario/model/builders.py``
   Empty matrix builders and ``DataTemplate``. Useful for tests, examples and
   minimal user-created databases.


``mario/ops/``
--------------

This folder holds business operations that mutate databases or export them.
When an algorithm is not “core matrix resolution” and not “raw parsing”, it
usually belongs here.

``mario/ops/__init__.py``
   Exports for the operations layer.

``mario/ops/aggregation.py``
   Public aggregation wrapper used by ``Database.aggregate(...)``.

``mario/ops/aggregation_engine.py``
   Lower-level aggregation logic over matrices, indexes and units.

``mario/ops/transforms.py``
   Public wrappers for scenario cloning and SUT/IOT transforms.

``mario/ops/transform_engine.py``
   Numerical implementation of SUT-to-IOT and Isard-to-Chenery-Moses logic.

``mario/ops/shocks.py``
   Shock application helpers used by ``Database.shock_calc(...)``.

``mario/ops/export.py``
   Main export entrypoints for Excel, TXT, Parquet and pymrio.

``mario/ops/excel.py``
   Historical Excel/TXT layout writers and workbook-specific helpers.

``mario/ops/export_specs.py``
   Shared export schemas, especially for flat/tidy exports.

``mario/ops/workbook_specs.py``
   Workbook layout constants for shock and add-sector spreadsheets.

``mario/ops/sectoradd.py``
   Legacy/simple add-sector helpers that still support parts of the add-sector
   workflow and backward-compatible utilities.

``mario/ops/add_sector_specs.py``
   Canonical constants for the current workbook-driven add-sector workflow.

``mario/ops/add_sector_workbook.py``
   Workbook writer/reader for add-sectors templates, clusters, inventories and
   split sheets.

``mario/ops/add_sector_engine.py``
   Current non-split add-sectors engine. Handles parent copy, updates,
   percentage rules, clusters, units, final demand, factors and satellites.

``mario/ops/add_sector_split.py``
   Deterministic pre-optimization split logic and validation for
   ``split=True``.

``mario/ops/cvxlab_bridge.py``
   Integration layer between MARIO and CVXLab. Prepares model directories,
   writes input data, calls CVXLab and parses optimization results back into
   MARIO scenarios.

``mario/ops/cvxlab_models/``
   Packaged model assets owned by MARIO and copied into CVXLab runs.


``mario/parsers/``
------------------

This folder contains both dataset-specific parsers and the generic parser
infrastructure. The current direction is:

* parser authors read raw files;
* build canonical MARIO blocks, indexes and units;
* use the parser API helpers to build a state or database.

Infrastructure files
~~~~~~~~~~~~~~~~~~~~

``mario/parsers/__init__.py``
   Lazy parser exports.

``mario/parsers/api.py``
   Developer-facing parser helpers. This is the preferred landing surface for
   new parser code.

``mario/parsers/base.py``
   Minimal parser protocol for internal state-based parsers.

``mario/parsers/registry.py``
   Pluggable parser registry used by the state-based parser layer.

``mario/parsers/helpers.py``
   Adapters between normalized parser output and ``ModelState``.

``mario/parsers/specs.py``
   Parser constants, dataset-specific source metadata and small naming catalogs.

``mario/parsers/identifiers.py``
   Static layouts for older parser paths, especially generic txt/excel layouts.

``mario/parsers/tabular.py``
   Historical generic parsing helpers still used by dataframe/excel/txt and
   pymrio compatibility flows.

``mario/parsers/entrypoints.py``
   Public ``parse_*`` functions that return ``Database`` objects.

``mario/parsers/excel.py``, ``mario/parsers/txt.py``, ``mario/parsers/parquet.py``
   Generic state-based parsers for MARIO-native exports.

Dataset parsers
~~~~~~~~~~~~~~~

``mario/parsers/adb.py``
   ADB MRIO Excel parser.

``mario/parsers/emerging.py``
   EMERGING MATLAB/HDF5 parser.

``mario/parsers/eora.py``
   EORA single-region and Eora26 parser.

``mario/parsers/eurostat_sdmx.py``
   Eurostat SDMX-backed SUT/IOT parser.

``mario/parsers/exiobase.py``
   Internal EXIOBASE compatibility/state helpers.

``mario/parsers/exiobase_iot.py``
   EXIOBASE monetary IOT parser and lightweight extension reader.

``mario/parsers/exiobase_sut.py``
   EXIOBASE monetary SUT parser, including optional extension import from IOT.

``mario/parsers/exiobase_hybrid.py``
   EXIOBASE hybrid SUT and HIOT parser.

``mario/parsers/figaro.py``
   FIGARO local flat-file parser for SUT and IOT.

``mario/parsers/gloria.py``
   GLORIA SUT parser, including caching and optional satellite filtering.

``mario/parsers/oecd_icio.py``
   OECD ICIO local CSV parser.

``mario/parsers/statcan_wds.py``
   StatCan WDS-backed SUT/IOT parser.

``mario/parsers/wiod.py``
   WIOD 2016 multiregional workbook parser.

Compatibility and resources
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``mario/parsers/handshake.py``
   Small compatibility shim. Today it mainly keeps an EXIOBASE entrypoint alias
   alive.

``mario/parsers/figaro_metadata.csv``
   Packaged metadata lookup used by the FIGARO parser.


``mario/settings/``
-------------------

This folder defines configurable labels and nomenclature.

``mario/settings/settings.py``
   Loader/validator for current settings plus upload/reset helpers.

``mario/settings/settings.yaml``
   Active settings used by the package.

``mario/settings/original_settings.yaml``
   Packaged fallback/default settings.


``mario/storage/``
------------------

This folder is the storage abstraction layer used mainly by the internal
state-based architecture.

``mario/storage/__init__.py``
   Storage exports.

``mario/storage/base.py``
   Abstract repository contract.

``mario/storage/repository.py``
   In-memory repository implementation.

``mario/storage/parquet.py``
   Parquet-backed repository implementation for pandas blocks.

``mario/storage/duckdb.py``
   Optional helper for future DuckDB-backed storage/query work. Intentionally
   thin for now.


``mario/views/``
----------------

Presentation helpers live here.

``mario/views/__init__.py``
   View exports.

``mario/views/tabular.py``
   Historical single-dataframe view builder.

``mario/views/plots.py``
   Plot construction logic.

``mario/views/plot_specs.py``
   Plot/filter layout configuration and palette helpers.


``mario/test/``
---------------

This folder contains packaged fixtures that ship with the library itself.

``mario/test/mario_test.py``
   Loader helpers for packaged example/test databases.

``mario/test/IOT.xlsx``, ``mario/test/SUT.xlsx``, ``mario/test/IOT_dummy.xlsx``
   Packaged fixtures used by examples and tests.


``tests/``
----------

This is the external test suite. It is organized mostly by subsystem or data
source.

``tests/test_coremodel.py``
   CoreModel contract and scenario behavior.

``tests/test_database_api.py``
   Public ``Database`` behavior and high-level query paths.

``tests/test_dataset_model.py``
   Internal ``ModelState`` and dataset-like behavior.

``tests/test_compute_catalog.py``
   Coverage and invariants for the compute catalog.

``tests/test_compute_views.py``
   Split/unified view builders.

``tests/test_iot_formulas.py`` and ``tests/test_sut_formulas.py``
   Formula-level regression tests.

``tests/test_resolver.py``
   Resolver and dependency behavior.

``tests/test_iomath.py``
   Low-level IO math regressions.

``tests/test_ops.py``
   Operational flows that cross multiple modules.

``tests/test_utils.py``
   Generic utility behavior.

``tests/test_settings.py``
   Settings loading and validation.

``tests/test_logging.py``
   Logging/warning behavior.

``tests/test_attrdata.py``
   Legacy-style attribute/dataframe behavior and exports.

``tests/test_isard_to_chenery.py``
   Chenery-Moses transform behavior.

``tests/test_addsector.py``
   Add-sectors workbook, engine and split/CVXLab integration.

Parser coverage is split by source:

* ``tests/test_parsers.py`` for generic excel/txt/parquet parser roundtrips;
* ``tests/test_exiobase_iot_parser.py`` and ``tests/test_exiobase_sut_parser.py``;
* ``tests/test_hybrid_exiobase.py``;
* ``tests/test_eurostat_sdmx_parser.py``;
* ``tests/test_eora_parser.py``;
* ``tests/test_figaro_parser.py``;
* ``tests/test_gloria_parser.py``;
* ``tests/test_oecd_parser.py``;
* ``tests/test_statcan_parser.py``;
* ``tests/test_wiod_parser.py``;
* ``tests/test_adb_parser.py``;
* ``tests/test_emerging_parser.py``.


``doc/source/``
---------------

The documentation source is Sphinx-based.

``doc/source/index.rst``
   Main docs entrypoint.

``doc/source/intro.rst``, ``terminology.rst``, ``settings.rst``
   User-facing conceptual docs.

``doc/source/developer_guide.rst``
   This page.

``doc/source/parser_development.rst``
   Focused guide for writing new parsers.

``doc/source/add_sector_refactor.rst``
   Design note for the workbook-driven add-sector workflow.

``doc/source/tutorials.rst`` and ``doc/source/tutorials/*.ipynb``
   Notebook-based tutorials.

``doc/source/examples.rst`` and ``doc/source/htmls/``
   Example material and historical rendered tutorial assets.

``doc/source/api_document/``
   One stub page per public API symbol.

``doc/source/conf.py``
   Sphinx configuration.


Main Runtime Flows
------------------

Parser flow
~~~~~~~~~~~

The intended modern parser flow is:

1. Read raw files in a dataset-specific parser.
2. Build canonical matrices, indexes and units.
3. Call ``mario.parsers.api.build_parser_state(...)`` or
   ``build_database_from_parser_output(...)``.
4. Let ``Database`` initialize from parser payload.

The key modules are:

* dataset parser in ``mario/parsers/*.py``;
* ``mario/parsers/helpers.py`` for state adaptation;
* ``mario/parsers/entrypoints.py`` for public wrappers.

Compute flow
~~~~~~~~~~~~

When a block is missing and a user asks for it:

1. ``CoreModel`` validates the request.
2. ``mario.compute.catalog`` declares legal strategies.
3. ``mario.compute.planner`` orders candidate strategies.
4. ``mario.compute.resolver`` executes them.
5. The resolved block is stored back into the scenario.

If you add or change a canonical matrix, the normal touchpoints are:

* ``mario/model/conventions.py``;
* ``mario/compute/catalog.py``;
* one of ``iot_formulas.py``, ``sut_formulas.py`` or ``views.py``.

Operational mutation flow
~~~~~~~~~~~~~~~~~~~~~~~~~

Most high-level mutations follow the same pattern:

1. ``Database`` method in ``mario/api/database.py`` validates the public call.
2. The implementation is delegated to ``mario/ops``.
3. Resulting matrices, units and indexes are written back into the database.
4. Metadata history is updated.

This applies to aggregation, transforms, exports, shocks and add-sectors.

Add-sectors and split flow
~~~~~~~~~~~~~~~~~~~~~~~~~~

The current add-sectors path is workbook-driven:

1. ``Database.get_add_sectors_excel(...)`` writes a workbook.
2. ``read_add_sectors_excel(...)`` reads metadata sheets.
3. ``read_inventory_sheets(...)`` attaches inventories.
4. ``run_add_sector_engine(...)`` applies the non-split insertion.
5. If ``split=True``:

   * ``add_sector_split.py`` prepares deterministic split data;
   * ``cvxlab_bridge.py`` writes CVXLab input data or runs optimization;
   * optimized results are imported into a dedicated scenario.


Where To Edit What
------------------

Use this quick routing table when deciding where to work:

* New parser: start in ``mario/parsers/`` and use ``mario/parsers/api.py``.
* New canonical matrix: update ``mario/model/conventions.py`` and
  ``mario/compute/catalog.py`` first.
* New compute formula: implement it in ``mario/compute/*_formulas.py`` and wire
  it in the catalog.
* New extraction/concat view: implement it in ``mario/compute/views.py``.
* Public API behavior change: usually ``mario/api/core_model.py`` or
  ``mario/api/database.py``.
* Export/import layout change: ``mario/ops/export.py``, ``mario/ops/excel.py``,
  ``mario/parsers/txt.py`` and ``mario/parsers/parquet.py``.
* Add-sectors workbook change: ``mario/ops/add_sector_specs.py`` and
  ``mario/ops/add_sector_workbook.py``.
* Add-sectors algorithm change: ``mario/ops/add_sector_engine.py``.
* Split/CVXLab integration change: ``mario/ops/add_sector_split.py`` and
  ``mario/ops/cvxlab_bridge.py``.
* New storage backend: ``mario/storage/`` plus ``mario/internal/access.py``.
* Plot/filter behavior: ``mario/views/plots.py`` and
  ``mario/views/plot_specs.py``.


What Is Current vs Transitional
-------------------------------

The codebase is partly modernized and partly transitional. The practical split
is:

Current architecture
~~~~~~~~~~~~~~~~~~~~

* catalog-driven compute in ``mario.compute``;
* state-based parser infrastructure in ``mario.parsers.api`` and
  ``mario.internal``;
* workbook-driven add-sectors flow in ``mario.ops.add_sector_*``;
* flat txt/parquet import/export;
* direct dataset parsers for EXIOBASE, Eurostat, FIGARO, WIOD, ADB, EMERGING,
  GLORIA, OECD, EORA and StatCan.

Transitional or compatibility-heavy areas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``mario/parsers/tabular.py`` and parts of ``mario/ops/excel.py``;
* ``mario/ops/sectoradd.py`` legacy helpers still used by compatibility paths;
* downloader helpers in ``mario/download.py``;
* historical single-sheet dataframe views and older workbook conventions.

When touching transitional modules, prefer small, well-contained changes unless
you are explicitly refactoring that area.


Developer Advice
----------------

Three patterns make the codebase easier to extend safely:

1. Keep canonical MARIO blocks authoritative.
   Raw dataset structure can vary wildly, but parsers should normalize early.

2. Prefer central seams over one-off fixes.
   If a change affects many parsers or exports, first look at:

   * ``mario/model/conventions.py``
   * ``mario/parsers/helpers.py``
   * ``mario/ops/export.py``
   * ``mario/api/core_model.py``

3. Treat ``Database`` as the stable user facade.
   Internal storage or execution backends may evolve, but public workflows
   should stay centered on the same object and method names.


See Also
--------

* :doc:`parser_development`
* :doc:`add_sector_refactor`
