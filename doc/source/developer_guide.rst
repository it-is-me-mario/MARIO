Developer Guide
===============

This page documents the current internal logic of MARIO for developers working
on the package. It is intentionally focused on the code that exists today,
especially the main public APIs, the compute path, and the separation between
user-facing objects and lower-level modules.

This is not a speculative architecture note. It describes how the package
currently works.


Scope
-----

At the moment MARIO exposes two main object families:

``mario.Database``
   The main public API. This is the object normal users interact with for
   parsing, computing, querying, transforming, aggregating, exporting and
   scenario management.

``mario.Dataset``
   The newer modular object used by the new internal core. It is the cleaner
   abstraction for storage, block-level compute, repository backends and future
   parser work.

The package is intentionally arranged so that:

* the user-facing API remains centered on ``Database``;
* the compute engine is catalog-driven and lives in ``mario.compute``;
* parser logic lives in ``mario.parsers``;
* operational algorithms live in ``mario.ops``;
* display-oriented helpers live in ``mario.views``;
* shared domain conventions live in ``mario.model``.


Current Module Map
------------------

The main modules to know are:

``mario/__init__.py``
   Public import surface. Re-exports the main classes, parser entry points,
   matrix primitives, settings helpers, plotting helpers and test loaders.

``mario/api/core_model.py``
   Base class for database-like objects. Owns matrix storage, scenario logic,
   matrix validation, compute entry points, query/get_data behavior and most of
   the shared model mechanics.

``mario/api/database.py``
   User-facing ``Database`` implementation. Adds higher-level operations such as
   aggregation, exports, SUT to IOT transforms, shock calculations, sector
   addition and plotting.

``mario/compute/``
   Catalog-driven compute system. This is the current computational core.

``mario/parsers/``
   Parser layer. Contains both the current ``Database`` parsers and the newer
   pluggable ``Dataset`` parser stack.

``mario/ops/``
   Operations extracted from the old monolithic class methods. This is where
   transformation, export, shock and aggregation logic should live.

``mario/views/``
   Tabular and plotting presentation helpers.

``mario/model/``
   Domain-level conventions and shared data objects. This includes labels,
   table conventions, block objects, scenarios, metadata and the ``Dataset``
   abstraction.

``mario/storage/``
   Repository abstractions for ``Dataset`` block storage.

``mario/utils.py``
   Shared helper functions that do not belong to compute, parser or ops.


Main Public APIs
----------------

``mario.Database``
~~~~~~~~~~~~~~~~~~

``Database`` is still the main public entry point. A developer should think of
it as a rich facade over:

* matrix/scenario state from ``CoreModel``;
* compute resolution from ``mario.compute``;
* operational algorithms from ``mario.ops``;
* parser outputs from ``mario.parsers``.

The most important public behaviors are:

* construction from dataframes or parser output;
* ``calc_all(...)`` and ``resolve(...)`` for matrix materialization;
* ``query(...)`` and ``get_data(...)`` for retrieval;
* scenario mutation methods such as ``clone_scenario(...)`` and
  ``update_scenarios(...)``;
* transforms such as ``to_iot(...)`` and ``to_chenery_moses(...)``;
* export methods such as ``to_excel(...)``, ``to_txt(...)`` and
  ``to_pymrio(...)``;
* shock, plotting, aggregation, sector and extension methods.

``mario.CoreModel``
~~~~~~~~~~~~~~~~~~~

``CoreModel`` is the shared base class that owns the common model mechanics:

* matrix storage in ``self.matrices``;
* index storage in ``self._indeces``;
* unit storage in ``self.units``;
* metadata in ``self.meta``;
* scenario lifecycle and reset logic;
* compute and retrieval entry points.

If a behavior is primarily about matrix/state management rather than a concrete
business operation, it usually belongs in ``CoreModel``.

``mario.Dataset``
~~~~~~~~~~~~~~~~~

``Dataset`` is the block-oriented model introduced by the restructuring. It is
not yet the default user object, but it already matters for developers because
it expresses the architecture more cleanly:

* blocks are stored through a repository abstraction;
* scenarios are explicit objects;
* compute goes through the same resolver logic;
* optional conversions exist for pandas, Polars and sparse matrices.

Today ``Dataset`` is best understood as the new internal core and an advanced
API surface, not as the primary public surface.


How ``Database`` Is Built
-------------------------

There are two main initialization paths.

Construction from parser output
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Parsers call ``Database(..., init_by_parsers=...)``.

That payload contains:

* ``matrices`` grouped by scenario, usually with a ``baseline`` entry;
* ``_indeces``;
* ``units``.

During initialization, ``CoreModel``:

* renames matrix keys using the configured nomenclature;
* stores the parser payload into ``self.matrices``, ``self._indeces`` and
  ``self.units``;
* initializes metadata;
* optionally runs ``calc_all()`` if requested by the caller.

Construction from explicit dataframes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When users pass ``Z``, ``Y``, ``E``, ``V``, ``EY``, ``units`` and ``table``
directly, ``CoreModel`` delegates normalization to
``mario.parsers.tabular.dataframe_parser``. The parser returns canonical
matrices, indexes and units, and then initialization proceeds exactly as above.


How Matrix Computation Works
----------------------------

The current compute flow is entirely centered on the catalog-driven resolver.

High-level flow
~~~~~~~~~~~~~~~

When a user calls:

.. code-block:: python

   db.calc_all(["w", "f"], scenario="baseline")

the call path is:

1. ``Database.calc_all(...)`` is inherited from ``CoreModel``.
2. The requested matrix names are normalized.
3. The scenario is validated.
4. The matrix names are validated against the compute catalog through
   ``available_matrices(table_type)``.
5. For each missing matrix, ``_resolve_one(...)`` calls
   ``mario.compute.resolver.resolve(...)``.

At that point the new compute engine takes over.

Planner and resolver
~~~~~~~~~~~~~~~~~~~~

The compute engine is split into two responsibilities:

``mario.compute.catalog``
   Declares what each matrix means and which strategies are available for
   building it.

``mario.compute.planner``
   Selects candidate strategies and determines dependency order.

``mario.compute.resolver``
   Executes the selected strategies and materializes results into the current
   dataset/database state.

Strategy types
~~~~~~~~~~~~~~

Each matrix can be resolved through one of four strategy families:

``parsed``
   The block already exists as a source block and should simply be present.

``extract``
   The block is a view extracted from an already materialized parent block.

``concat``
   The block is assembled from already defined sub-blocks. This is especially
   important for SUT unified matrices.

``formula``
   The block is computed numerically from dependencies.

The current planner order is deliberate:

1. parsed
2. extract
3. concat
4. formula

This means MARIO prefers not to recompute data if an equivalent block can be
reused or built cheaply from existing materialized blocks.

SUT-specific behavior
~~~~~~~~~~~~~~~~~~~~~

The SUT path is intentionally different from the IOT path where needed.

The key rule is that unified SUT matrices should follow the split-block logic
defined in the catalog. For example, ``w`` in SUT is not treated as a monolithic
formula-first matrix. Instead, the resolver computes the four quadrants
(``wcc``, ``wca``, ``wac``, ``waa``) and then concatenates them.

This is important because:

* it matches the intended economic decomposition;
* it avoids unnecessary dense unified calculations for large systems;
* it keeps the compute graph explicit and inspectable.

In practice, the resolver now recursively resolves concat dependencies, so a
request for a unified SUT block automatically triggers the split computations
that the catalog declares.

Formula implementations
~~~~~~~~~~~~~~~~~~~~~~~

The formulas are distributed by concern:

``mario.compute.iot_formulas``
   IOT-specific formulas.

``mario.compute.sut_formulas``
   SUT split and unified formulas.

``mario.compute.ghosh_formulas``
   Ghosh-related formulas.

``mario.compute.views``
   Pure extract/concat view logic.

``mario.compute.ordering``
   SUT unified ordering policy used to keep concatenation and extraction
   deterministic.

Developers should add new computational logic here, not in ``Database``.


How Retrieval APIs Work
-----------------------

``query(...)``
~~~~~~~~~~~~~~

``query(...)`` is the lightweight retrieval API.

It delegates to ``get_data(...)`` with:

* ``units=False``
* ``indeces=False``
* ``format="dict"``

and then simplifies the result shape:

* one matrix + one scenario returns a dataframe/series directly;
* one matrix + many scenarios returns a scenario dictionary;
* many matrices returns a nested structure.

``get_data(...)``
~~~~~~~~~~~~~~~~~

``get_data(...)`` is the structured retrieval API.

It can:

* auto-compute missing matrices through ``auto_calc=True``;
* include units and indexes;
* return absolute or relative differences against a base scenario;
* return either dicts or lightweight namedtuple objects.

The important thing for developers is that retrieval is compute-aware. If a
requested block is missing and ``auto_calc=True``, MARIO will resolve it before
returning it.

``resolve(...)`` and ``explain(...)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are developer-useful APIs that expose the new compute engine more
directly.

``resolve(...)``
   Materializes a single matrix through the catalog-driven resolver.

``resolve_many(...)``
   Materializes several matrices.

``explain(...)``
   Builds a dependency explanation from the compute graph.

These methods are useful whenever the developer wants to inspect the compute
logic explicitly rather than just relying on ``calc_all(...)``.


How Scenario Logic Works
------------------------

Scenarios live in ``self.matrices`` at the ``Database`` level. Each scenario is
basically a dictionary of materialized matrices.

The most important operations are:

``clone_scenario(...)``
   Deep-copies an existing scenario into a new scenario name.

``update_scenarios(...)``
   Replaces selected materialized matrices in an existing scenario.

``reset_to_flows(...)``
   Drops coefficient matrices and keeps only the flow-side core.

``reset_to_coefficients(...)``
   Drops flow matrices and keeps only the coefficient-side core.

These are not passive operations. They directly change which blocks are
materialized in a scenario, and therefore they affect what the resolver sees as
already available for future computations.


How Operational Methods Are Structured
--------------------------------------

The large user-visible operations have been extracted out of ``Database`` into
dedicated modules under ``mario.ops``. ``Database`` is now mostly a facade that
delegates to them.

Current mapping:

``mario.ops.aggregation``
   High-level aggregation entry point.

``mario.ops.aggregation_engine``
   Core aggregation algorithm.

``mario.ops.transforms``
   High-level wrappers for table transformations and scenario-to-instance
   conversion.

``mario.ops.transform_engine``
   Low-level transformation algorithms.

``mario.ops.export``
   High-level export entry points.

``mario.ops.excel``
   Excel and text workbook writing helpers.

``mario.ops.shocks``
   Shock matrix algorithms.

``mario.ops.sectoradd``
   Sector extension/addition logic.

For developers, this means:

* API shape stays in ``Database``;
* algorithmic work should usually be implemented in ``mario.ops``.


How Parsing Is Structured Today
-------------------------------

There are currently two parser surfaces.

Database parsers
~~~~~~~~~~~~~~~~

The historical parser entry points such as:

* ``mario.parse_from_excel(...)``
* ``mario.parse_from_txt(...)``
* ``mario.parse_exiobase_3(...)``
* ``mario.parse_exiobase_sut(...)``
* ``mario.parse_eora(...)``

return ``Database`` objects.

These entry points live in ``mario.parsers.entrypoints`` and mostly:

1. validate the high-level input arguments;
2. delegate to lower-level parser functions in ``mario.parsers.tabular``;
3. wrap the resulting matrices/indexes/units into a ``Database``.

Dataset parsers
~~~~~~~~~~~~~~~

The newer parser stack lives in:

* ``mario.parsers.registry``
* ``mario.parsers.base``
* ``mario.parsers.excel``
* ``mario.parsers.exiobase``
* ``mario.parsers.helpers``

This stack returns ``Dataset`` objects and supports parser registration. It is
the right place for future parser restructuring work, especially once Polars
and DuckDB become more central in the parser/storage path.

Important current rule
~~~~~~~~~~~~~~~~~~~~~~

Parser refactoring should be done carefully because parser code does more than
I/O:

* it normalizes matrix names;
* it infers indexes;
* it enforces table shape conventions;
* it decides which blocks are native and which blocks are derived later.

For that reason, parser work should preserve the current domain grammar even if
the internal mechanics change substantially.


How ``Dataset`` and Storage Work
--------------------------------

``Dataset`` stores named blocks through a repository abstraction.

Current repositories:

``InMemoryBlockRepository``
   Default in-memory storage.

``ParquetBlockRepository``
   Parquet-backed persistence for pandas blocks.

Optional helpers:

``mario.storage.duckdb``
   Currently only exposes an optional import helper. DuckDB is not yet a
   primary execution backend.

``Dataset`` is therefore already useful for:

* block-oriented storage;
* explainable compute;
* alternative repositories;
* future parser/storage work.

But it is not yet the default path for everyday users.


Optional Dependencies
---------------------

Some newer dependencies are currently optional and only used in specific places.

``polars``
   Used by ``Dataset.to_polars(...)``.

``scipy``
   Used by ``Dataset.to_sparse(...)``.

``pyarrow``
   Required in practice for Parquet-backed repositories through pandas parquet
   support.

``duckdb``
   Only used in the optional DuckDB helper layer today.

This means the current core compute path of ``Database`` does not yet depend on
Polars or DuckDB directly.


Developer Rules of Thumb
------------------------

When adding or changing code, the current design intent is:

* keep ``Database`` as the main public API;
* move algorithmic logic out of ``Database`` and into ``compute``, ``ops`` or
  ``parsers``;
* keep domain labels and matrix conventions centralized in ``mario.model``;
* add new matrix logic through the compute catalog and formula/view modules;
* do not reintroduce string-based dynamic compute rules;
* treat SUT split-block logic as first-class, not as an afterthought;
* treat parser work as high-risk and convention-sensitive.


Recommended Entry Points for New Development
--------------------------------------------

If you need to add a new feature, the preferred landing zones are:

Add a new derived matrix
   Update ``mario.compute.catalog`` and implement the logic in
   ``mario.compute.views`` or one of the formula modules.

Add a new high-level database operation
   Implement it in ``mario.ops`` and keep ``Database`` as a thin facade.

Add a new parser
   Prefer the ``Dataset`` parser registry in ``mario.parsers`` unless the
   feature explicitly belongs to the current ``Database`` parser surface.

Add a new storage backend
   Implement a repository in ``mario.storage`` and keep ``Dataset`` as the
   consumer.

Add a new public convenience import
   Re-export it from ``mario/__init__.py`` only if it is genuinely part of the
   public API.


Current Status Summary
----------------------

The package has already been re-centered around:

* ``mario.api`` for public object implementations;
* ``mario.compute`` for matrix resolution;
* ``mario.ops`` for operations;
* ``mario.parsers`` for parser logic;
* ``mario.model`` for shared conventions and data abstractions.

The next major area of careful work is parser restructuring, especially if the
goal is to make Polars, DuckDB and Parquet more central in the ingestion and
storage path without changing MARIO's domain semantics.
