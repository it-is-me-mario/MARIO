Developer Guide
===============

This page is a guided tour of the MARIO codebase.

It is written for developers, but not only for experts. The goal is to help a
new contributor answer simple questions quickly:

* what the main parts of the project are;
* where each kind of logic lives;
* which file to open first when something needs to change;
* which areas are the “current” design and which ones still carry older logic.

This is not a line-by-line explanation of the code. Think of it as a map of the
repository with short notes for each important folder and file.


Start Here
----------

If you are opening the project for the first time, this is a good reading
order:

1. ``mario/__init__.py`` to see what MARIO exposes publicly.
2. ``mario/api/core_model.py`` and ``mario/api/database.py`` to understand the
   main user-facing object.
3. ``mario/compute/`` to see how matrices are calculated when they are missing.
4. ``mario/parsers/`` to see how external datasets become a ``Database``.
5. ``mario/ops/`` to see how MARIO applies changes such as aggregation,
   transforms, exports, shocks and add-sectors.
6. ``mario/internal/`` and ``mario/storage/`` only if you need the newer
   internal state and storage layer.

If you just want to fix a bug or add a small feature, you usually do not need
to understand everything in one pass.


Big Picture
-----------

MARIO revolves around one main public object:

``mario.Database``
   This is the object users work with. They parse data into it, query it,
   calculate matrices, aggregate it, export it, transform it and modify it.

There is also a newer internal layer:

``mario.internal.ModelState``
   This is not a second public API. It is the lower-level structure used by the
   newer parser and storage design.

In plain words:

* ``Database`` is the main thing users see.
* ``ModelState`` is one of the main things developers may work on behind the
  scenes.


Repository Map
--------------

At the repository root, the most important files and folders are:

``README.rst``
   General project introduction for users.

``CHANGELOG.rst``
   Release history.

``setup.py``, ``pyproject.toml``, ``requirements.txt``, ``requirements.yml``
   Packaging and dependency files.

``doc/``
   Documentation source.

``mario/``
   The library code.

``tests/``
   The test suite.

``Output/``
   Local output files used in examples or tests. Not part of the core library.

``dummy/`` and ``mariopy.egg-info/``
   Local or packaging artifacts. They are not part of MARIO's real structure.

``test.py``
   A local helper script, not part of the public package.


Top-Level Files in ``mario/``
-----------------------------

``mario/__init__.py``
   The public import surface. If you want to know what users can import
   directly from ``mario``, start here.

``mario/version.py``
   Stores the package version.

``mario/utils.py``
   A shared utility module. It contains helpers used in different parts of the
   project. It is useful, but also a place where unrelated helpers can
   accumulate, so edits here should stay focused.

``mario/download.py``
   Convenience download helpers for some historical data sources. Useful in a
   few cases, but not the center of the current parser design.


The Main Packages
-----------------

The codebase is easier to understand if you think in layers:

``mario.api``
   Public objects and methods.

``mario.compute``
   Matrix calculation logic.

``mario.parsers``
   Dataset parsers and parser infrastructure.

``mario.ops``
   Operations that change or export a database.

``mario.views``
   Tabular views and plots.

``mario.model``
   Shared labels, conventions and empty templates.

``mario.internal``
   Newer internal state objects.

``mario.storage``
   Storage backends used by the internal state.

``mario.settings``
   Configurable labels and nomenclature.

``mario.log_exc``
   Exceptions and logging helpers.


``mario/api/``
--------------

This is the most important folder for understanding how MARIO looks from the
outside.

``mario/api/__init__.py``
   Re-exports the main API layer.

``mario/api/core_model.py``
   The shared base class behind database-like objects. It handles:

   * scenarios;
   * matrix storage;
   * block access;
   * ``calc_all(...)`` and ``resolve(...)``;
   * ``query(...)`` and ``get_data(...)``;
   * reset logic;
   * several checks on table structure.

   If the question is “how does MARIO store or retrieve a matrix?”, this file
   is usually the right place to look.

``mario/api/database.py``
   The main user-facing class. It builds on ``CoreModel`` and adds the higher
   level workflows users usually call:

   * aggregation;
   * SUT/IOT transforms;
   * exports;
   * shocks;
   * plotting;
   * add-sectors;
   * split/CVXLab integration;
   * single-region extraction.

   If a public method is visible to the user, the wrapper usually lives here.

``mario/api/metadata.py``
   Defines ``MARIOMetaData``, which stores metadata and history notes attached
   to a database.


``mario/compute/``
------------------

This is where MARIO decides how to build matrices that are not already stored.

The important idea is simple: MARIO does not hard-code every calculation in one
place. Instead, it has a catalog that says what each matrix is and how it can
be obtained.

``mario/compute/__init__.py``
   Exports the compute layer.

``mario/compute/catalog.py``
   The central map of MARIO matrices. If you add a new standard matrix, this is
   usually the first file to update.

``mario/compute/types.py``
   Small data structures used by the compute layer.

``mario/compute/planner.py``
   Chooses a sensible route for building a requested matrix.

``mario/compute/resolver.py``
   Actually performs the steps chosen by the planner and stores the result back
   into the database or state.

``mario/compute/helpers.py``
   Shared helper functions used by formulas.

``mario/compute/primitives.py``
   Public low-level calculation helpers such as ``calc_Z`` and ``calc_X``.

``mario/compute/iot_formulas.py``
   Formulas specific to IOTs.

``mario/compute/sut_formulas.py``
   Formulas specific to SUTs.

``mario/compute/ghosh_formulas.py``
   Ghosh-side formulas.

``mario/compute/views.py``
   Builds matrices that are better seen as views, combinations, or simple
   rearrangements of existing blocks.

``mario/compute/ordering.py``
   Keeps SUT ordering rules consistent when matrices are combined or split.

``mario/compute/graph.py``
   Developer tools for understanding dependency chains between matrices.

Rule of thumb:

* if you are adding a new standard matrix, start with ``catalog.py``;
* if you are changing a formula, look in one of the ``*_formulas.py`` files;
* if the matrix is mainly a recombination of existing blocks, look in
  ``views.py``.


``mario/internal/``
-------------------

This folder contains the newer internal state model. You do not need it for
every change, but it matters for parser, storage and future backend work.

``mario/internal/__init__.py``
   Exports the internal state layer.

``mario/internal/state.py``
   Defines ``ModelState``, the internal object that stores blocks, scenarios,
   indexes and units in a more explicit way.

``mario/internal/scenario.py``
   Scenario container used by ``ModelState``.

``mario/internal/block.py``
   Small record describing one stored block.

``mario/internal/metadata.py``
   Metadata container for the internal state layer.

``mario/internal/access.py``
   Adapters that turn a stored block into a pandas object, a tabular object, or
   a numeric matrix. This file is especially important for future work that
   tries not to assume everything is always a pandas ``DataFrame`` in memory.


``mario/log_exc/``
------------------

This folder contains cross-cutting support code.

``mario/log_exc/__init__.py``
   Namespace marker.

``mario/log_exc/exceptions.py``
   Custom exception classes.

``mario/log_exc/logger.py``
   Logging helpers and warning filters.


``mario/model/``
----------------

This folder contains concepts that should stay stable across parsers, compute
and operations.

``mario/model/__init__.py``
   Exports the model layer.

``mario/model/conventions.py``
   Shared structural rules such as table kinds, matrix names, index layouts and
   nomenclature aliases. If several modules disagree on a matrix name or axis,
   this is one of the first files to check.

``mario/model/labels.py``
   Human-readable labels derived from settings.

``mario/model/enums.py``
   Small enums used across the codebase.

``mario/model/builders.py``
   Empty templates and builders useful for tests, examples and manual database
   creation.


``mario/ops/``
--------------

This is where MARIO puts most “do something with the database” logic.

If the code is not raw parsing and not core matrix resolution, it often belongs
here.

``mario/ops/__init__.py``
   Exports the operations layer.

``mario/ops/aggregation.py``
   Public wrapper for aggregation.

``mario/ops/aggregation_engine.py``
   Main aggregation logic.

``mario/ops/transforms.py``
   Public wrappers for major transforms such as SUT to IOT.

``mario/ops/transform_engine.py``
   The lower-level implementation of those transforms.

``mario/ops/shocks.py``
   Shock logic.

``mario/ops/export.py``
   Main export entry points.

``mario/ops/excel.py``
   Helpers for Excel-style layouts and some older export paths.

``mario/ops/export_specs.py``
   Shared export schemas, especially for the flat long-format exports.

``mario/ops/workbook_specs.py``
   Shared layout constants for workbook-based workflows.

``mario/ops/sectoradd.py``
   Older add-sector helpers that still support some compatibility paths.

``mario/ops/add_sector_specs.py``
   Constants for the current add-sectors workbook.

``mario/ops/add_sector_workbook.py``
   Reads and writes the add-sectors workbook.

``mario/ops/add_sector_engine.py``
   Applies the main non-split add-sectors logic.

``mario/ops/add_sector_split.py``
   Handles preparation and checks for the ``split=True`` path.

``mario/ops/cvxlab_bridge.py``
   The bridge between MARIO and CVXLab. It prepares input data, launches the
   optimization workflow and reads results back into MARIO.

``mario/ops/cvxlab_models/``
   Packaged model files that MARIO copies into CVXLab runs.


``mario/parsers/``
------------------

This folder contains both the actual dataset parsers and the small framework
used to write new ones.

The modern parser idea is:

1. read the raw files;
2. convert them into standard MARIO matrices, indexes and units;
3. use helper functions to turn that normalized result into a ``Database`` or
   internal state.

Infrastructure files
~~~~~~~~~~~~~~~~~~~~

``mario/parsers/__init__.py``
   Exports parser functions.

``mario/parsers/api.py``
   The main helper module for parser authors. If you are writing a new parser,
   start here before touching lower-level parser infrastructure.

``mario/parsers/base.py``
   Small base protocol for the internal state-based parser layer.

``mario/parsers/registry.py``
   Registry used by the newer parser layer.

``mario/parsers/helpers.py``
   Adapters between normalized parser output and internal state objects.

``mario/parsers/specs.py``
   Parser constants and source metadata.

``mario/parsers/identifiers.py``
   Static layouts used mainly by older generic parser paths.

``mario/parsers/tabular.py``
   Historical generic parsing logic. Still important, but also one of the more
   transitional parts of the codebase.

``mario/parsers/entrypoints.py``
   Public ``parse_*`` functions that users call.

``mario/parsers/excel.py``, ``mario/parsers/txt.py``, ``mario/parsers/parquet.py``
   Generic parsers for MARIO-native export formats.

Dataset parsers
~~~~~~~~~~~~~~~

``mario/parsers/adb.py``
   Parser for ADB MRIO workbooks.

``mario/parsers/emerging.py``
   Parser for EMERGING MATLAB/HDF5 bundles.

``mario/parsers/eora.py``
   Parser for EORA and Eora26.

``mario/parsers/eurostat_sdmx.py``
   Parser for Eurostat SUT/IOT data via SDMX.

``mario/parsers/exiobase.py``
   Internal EXIOBASE compatibility helpers.

``mario/parsers/exiobase_iot.py``
   Parser for EXIOBASE monetary IOT.

``mario/parsers/exiobase_sut.py``
   Parser for EXIOBASE monetary SUT.

``mario/parsers/exiobase_hybrid.py``
   Parser for EXIOBASE hybrid SUT and HIOT.

``mario/parsers/figaro.py``
   Parser for FIGARO SUT and IOT flat files.

``mario/parsers/gloria.py``
   Parser for GLORIA SUT, including cache and satellite filtering.

``mario/parsers/oecd_icio.py``
   Parser for OECD ICIO CSV files.

``mario/parsers/statcan_wds.py``
   Parser for StatCan SUT/IOT through WDS.

``mario/parsers/wiod.py``
   Parser for WIOD 2016 multiregional workbooks.

Compatibility and resources
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``mario/parsers/handshake.py``
   Small compatibility shim. It is not the preferred place for new parser
   work.

``mario/parsers/figaro_metadata.csv``
   Metadata lookup file used by the FIGARO parser.


``mario/settings/``
-------------------

This folder holds the configurable labels and nomenclature used across MARIO.

``mario/settings/settings.py``
   Loads, validates, resets and updates settings.

``mario/settings/settings.yaml``
   Active settings file.

``mario/settings/original_settings.yaml``
   Default packaged settings.


``mario/storage/``
------------------

This folder is mostly relevant for the internal state layer.

``mario/storage/__init__.py``
   Exports storage helpers.

``mario/storage/base.py``
   Base repository contract.

``mario/storage/repository.py``
   In-memory repository.

``mario/storage/parquet.py``
   Parquet-backed repository.

``mario/storage/duckdb.py``
   Thin helper for future DuckDB-backed work.


``mario/views/``
----------------

This folder contains presentation helpers.

``mario/views/__init__.py``
   Exports views.

``mario/views/tabular.py``
   Builds the historical single-dataframe view.

``mario/views/plots.py``
   Plot logic.

``mario/views/plot_specs.py``
   Plot options, filters and related configuration.


``mario/test/``
---------------

This folder contains packaged fixtures that ship with MARIO itself.

``mario/test/mario_test.py``
   Helper functions that load packaged example databases.

``mario/test/IOT.xlsx``, ``mario/test/SUT.xlsx``, ``mario/test/IOT_dummy.xlsx``
   Packaged test/example files.


``tests/``
----------

This is the external test suite. When you change behavior, this folder tells
you which area you are likely to affect.

``tests/test_coremodel.py``
   CoreModel behavior.

``tests/test_database_api.py``
   Main public ``Database`` behavior.

``tests/test_dataset_model.py``
   Internal ``ModelState`` behavior.

``tests/test_compute_catalog.py``
   Compute catalog checks.

``tests/test_compute_views.py``
   View-building logic.

``tests/test_iot_formulas.py`` and ``tests/test_sut_formulas.py``
   Formula regression tests.

``tests/test_resolver.py``
   Resolver behavior.

``tests/test_iomath.py``
   Low-level IO math.

``tests/test_ops.py``
   Operations that touch several modules at once.

``tests/test_utils.py``
   Utility helpers.

``tests/test_settings.py``
   Settings logic.

``tests/test_logging.py``
   Logging and warnings.

``tests/test_attrdata.py``
   Older dataframe-style behavior and exports.

``tests/test_isard_to_chenery.py``
   Chenery-Moses transform checks.

``tests/test_addsector.py``
   Add-sectors and split/CVXLab flow.

Parser tests are mostly split by source:

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

This is the documentation source used by Sphinx.

``doc/source/index.rst``
   Main documentation entry page.

``doc/source/intro.rst``, ``terminology.rst``, ``settings.rst``
   User-facing background pages.

``doc/source/developer_guide.rst``
   This page.

``doc/source/parser_development.rst``
   Guide for writing new parsers.

``doc/source/add_sector_refactor.rst``
   Design note for add-sectors.

``doc/source/tutorials.rst`` and ``doc/source/tutorials/*.ipynb``
   Tutorial notebooks.

``doc/source/examples.rst`` and ``doc/source/htmls/``
   Example material and historical rendered tutorial assets.

``doc/source/api_document/``
   One documentation stub per public API symbol.

``doc/source/conf.py``
   Sphinx configuration.


Main Runtime Flows
------------------

The code becomes much easier to follow if you keep a few common flows in mind.

Parser flow
~~~~~~~~~~~

When MARIO reads an external dataset, the usual path is:

1. a dataset parser reads raw files;
2. it builds standard MARIO matrices, indexes and units;
3. helper functions turn that result into a ``Database`` or ``ModelState``;
4. the user receives a normal MARIO object.

In practice, the usual files involved are:

* a dataset-specific parser in ``mario/parsers/*.py``;
* ``mario/parsers/api.py``;
* ``mario/parsers/helpers.py``;
* ``mario/parsers/entrypoints.py``.

Compute flow
~~~~~~~~~~~~

When a matrix is missing and the user asks for it:

1. ``CoreModel`` accepts the request;
2. the compute catalog says which routes are allowed;
3. the planner chooses a route;
4. the resolver runs it;
5. the result is stored back into the current scenario.

The key files are:

* ``mario/compute/catalog.py``;
* ``mario/compute/planner.py``;
* ``mario/compute/resolver.py``;
* one of the formula or view modules.

Operations flow
~~~~~~~~~~~~~~~

Most high-level operations follow the same pattern:

1. the user calls a method on ``Database``;
2. ``database.py`` validates the public arguments;
3. the real logic is delegated to ``mario/ops``;
4. the resulting matrices are written back into the database.

This is how aggregation, transforms, exports, shocks and add-sectors work.

Add-sectors flow
~~~~~~~~~~~~~~~~

The current add-sectors workflow is workbook-based:

1. ``get_add_sectors_excel(...)`` creates a workbook;
2. ``read_add_sectors_excel(...)`` reads its setup sheets;
3. ``read_inventory_sheets(...)`` reads the inventory sheets;
4. ``add_sector_engine.py`` applies the main logic;
5. if ``split=True``, MARIO also uses ``add_sector_split.py`` and
   ``cvxlab_bridge.py``.


Where To Edit What
------------------

If you are not sure where to start, use this shortcut list:

* New parser: start in ``mario/parsers/`` and use ``mario/parsers/api.py``.
* New standard matrix: start with ``mario/model/conventions.py`` and
  ``mario/compute/catalog.py``.
* New formula: go to one of the ``mario/compute/*_formulas.py`` files.
* New matrix view or recombination: ``mario/compute/views.py``.
* Public API change: usually ``mario/api/core_model.py`` or
  ``mario/api/database.py``.
* Export/import layout change: ``mario/ops/export.py``, ``mario/ops/excel.py``,
  ``mario/parsers/txt.py`` and ``mario/parsers/parquet.py``.
* Add-sectors workbook change: ``mario/ops/add_sector_specs.py`` and
  ``mario/ops/add_sector_workbook.py``.
* Add-sectors logic change: ``mario/ops/add_sector_engine.py``.
* Split/CVXLab change: ``mario/ops/add_sector_split.py`` and
  ``mario/ops/cvxlab_bridge.py``.
* Storage backend work: ``mario/storage/`` and ``mario/internal/access.py``.
* Plot behavior: ``mario/views/plots.py`` and ``mario/views/plot_specs.py``.


Current Areas and Older Areas
-----------------------------

Not all parts of the codebase are equally “new”.

Current design
~~~~~~~~~~~~~~

These are the areas that best reflect the current direction of the project:

* catalog-driven compute in ``mario.compute``;
* state-based parser helpers in ``mario.parsers.api`` and ``mario.internal``;
* workbook-driven add-sectors flow in ``mario.ops.add_sector_*``;
* flat txt/parquet import/export;
* direct parsers for datasets such as EXIOBASE, Eurostat, FIGARO, WIOD, ADB,
  EMERGING, GLORIA, OECD, EORA and StatCan.

Older or more transitional areas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These parts still matter, but they carry more historical logic:

* ``mario/parsers/tabular.py``;
* parts of ``mario/ops/excel.py``;
* ``mario/ops/sectoradd.py``;
* ``mario/download.py``;
* the older single-dataframe views.

When editing these areas, it is usually better to make small, careful changes
unless you are deliberately refactoring that subsystem.


Practical Advice
----------------

Three habits make work on MARIO easier:

1. Normalize early.
   Dataset files all look different, but once inside MARIO they should be
   turned into standard MARIO matrices as soon as possible.

2. Prefer one central fix over many local fixes.
   If the same problem appears in several parsers or exports, first check:

   * ``mario/model/conventions.py``;
   * ``mario/parsers/helpers.py``;
   * ``mario/ops/export.py``;
   * ``mario/api/core_model.py``.

3. Keep ``Database`` as the stable public face.
   Internal storage and execution details may change over time, but the user
   should still feel that they are working with the same main object and the
   same family of methods.


See Also
--------

* :doc:`parser_development`
* :doc:`add_sector_refactor`
