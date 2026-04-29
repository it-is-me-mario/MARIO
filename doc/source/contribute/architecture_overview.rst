Architecture Overview
=====================

MARIO is organized around a small number of layers with fairly clear
responsibilities. For an advanced reader, the useful mental model is:

1. parse or build a database into a normalized internal state;
2. expose that state through ``Database`` and ``CoreModel``;
3. resolve matrices and derived views through the compute layer;
4. run structural operations and exports in ``mario.ops``;
5. render user-facing tables and figures in ``mario.views``.

The important design choice is that MARIO is not only a collection of matrix
formulas. It is also a stateful container for scenarios, metadata, units,
index conventions, and parser-specific assumptions. Most modules are easier to
understand once they are read in terms of that lifecycle instead of as isolated
functions.

Reading the package top-down
----------------------------

For most expert users, the best reading order is:

* ``mario.__init__`` to see the public surface exported by the package;
* ``mario.api.database`` to understand the main object users interact with;
* ``mario.api.core_model`` for the lower-level matrix and index helpers shared
  by ``Database``;
* ``mario.compute`` to see how derived matrices are specified and resolved;
* ``mario.parsers`` for the ingestion path and source-specific readers;
* ``mario.ops`` and ``mario.views`` for transformations, exports, and
  visualization.

Main package map
----------------

``mario.api``
   The public surface centered on ``Database`` and ``CoreModel``. This is the
   layer that translates internal storage and compute concepts into methods
   such as ``calc_all(...)``, ``aggregate(...)``, ``plot(...)`` or
   ``to_excel(...)``.

``mario.compute``
   The authoritative catalog of matrix definitions plus the planner, resolver,
   formulas, operators, and ordering policies needed to materialize derived
   blocks. This is the main place to look when asking "where does matrix X come
   from?".

``mario.parsers``
   Parser entry points, parser validation helpers, and source-specific readers.
   Its job is to normalize many external data layouts into one MARIO state that
   can instantiate a ``Database``.

``mario.ops``
   Structural operations, exports, aggregation, transformations, shocks, and
   add-sector workflows. In practice this is where most state-changing
   operations live once a database already exists.

``mario.views``
   Plotting and tabular views. This layer is intentionally downstream of the
   data model: it expects already normalized matrices or dataframes and focuses
   on presentation.

``mario.internal`` and ``mario.storage``
   Supporting layers for newer state/storage work. These packages matter most
   when tracing how parsed material is stored or serialized, but they are not
   usually the first stop for understanding user-facing workflows.

Core runtime objects
--------------------

``Database``
   The main user-facing object. It owns scenarios, metadata, clustering state,
   transformation methods, exports, plotting entry points, and higher-level
   convenience APIs.

``CoreModel``
   The lower-level shared implementation for matrix access, index management,
   scenario bookkeeping, and many calculation helpers. When a ``Database``
   method feels thin, the controlling logic is often here.

Scenario state
   MARIO does not only store one table. It stores scenario-keyed matrices,
   indices, units, metadata, and auxiliary settings. That is why many helpers
   accept a scenario name and why operations often create or update scenario
   snapshots rather than overwriting one bare dataframe.

Conventions and labels
   The naming layer in ``mario.model`` and ``mario.settings`` is central.
   Matrix names, axis labels, aliases, and table-dependent set names are not
   incidental strings spread around the package; they are part of the public
   model contract.

Typical end-to-end flow
-----------------------

The most common runtime path is:

* a parser entry point, direct dataframe constructor, or test fixture builds a
  ``Database``;
* parsed matrices and indices are normalized into the database state;
* compute helpers resolve missing matrices lazily or via ``calc_all(...)``;
* user operations in ``mario.ops`` create transformed scenarios or exported
  artifacts;
* ``mario.views`` and ``Database.plot(...)`` flatten or reshape data for human
  inspection.

This separation is useful when debugging. If a result is wrong, the first
question is usually whether the issue belongs to ingestion, state normalization,
matrix resolution, structural transformation, or presentation.

What changed in the recent restructure
--------------------------------------

The current package layout reflects an explicit move away from a monolithic
``core`` + ``tools`` organization. The newer structure tries to make the owning
abstraction obvious:

* public object behaviour lives under ``mario.api``;
* matrix semantics and dependency logic live under ``mario.compute``;
* source normalization lives under ``mario.parsers``;
* transformations and exports live under ``mario.ops``;
* presentation lives under ``mario.views``.

That split is worth keeping in mind while reading the repository, because many
files still implement historical workflows but now do so under a more explicit
package boundary.
