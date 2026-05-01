Adding New Matrices
===================

Adding a matrix to MARIO means more than writing one formula. A matrix becomes
part of the compute contract only when its semantics, axes, resolution
strategies, tests, and user-facing naming all line up.

For the current codebase, the main moving parts are:

* ``mario.compute.catalog`` for the authoritative matrix spec;
* ``mario.compute.iot_formulas`` or ``mario.compute.sut_formulas`` for numeric
  builders;
* ``mario.compute.views`` when the new block is only an extracted or
  concatenated view;
* resolver and catalog tests that prove the block can actually be materialized.


Start With Semantics
--------------------

Before touching code, decide four things explicitly:

* whether the matrix belongs to ``IOT``, ``SUT``, or both;
* whether it is a flow block, coefficient block, extracted view, or concat view;
* its canonical public name, following the nomenclature already used in
  :doc:`../concepts/nomenclature`;
* the semantic row and column axes the block is supposed to expose.

That step matters because MARIO now derives the public matrix surface from the
compute catalog. If the semantics are fuzzy, the implementation will also stay
fuzzy.


Register the Matrix in the Compute Catalog
------------------------------------------

The authoritative registration point is ``mario.compute.catalog``.

Add one ``_spec(...)`` entry under the relevant table kind with:

* the matrix name;
* its migration status (``KEEP`` for historical blocks, ``ADD`` for newly
  introduced ones);
* the expected axis labels;
* one or more strategies describing how the resolver may obtain it.

The common helpers are:

* ``_parsed(...)`` for blocks that must already exist in storage;
* ``_formula(...)`` for blocks built from other matrices;
* ``_extract(...)`` for split or unified views derived from one source block;
* ``_concat(...)`` for blocks assembled from already resolved pieces.

In practice, the catalog entry is the source of truth. ``available_matrices(...)``
and downstream resolver behaviour read from it rather than from a separate hand
maintained registry.


Implement the Builder in the Owning Module
------------------------------------------

Once the catalog entry exists, implement the named builder it refers to.

Use the module that matches the semantics of the block:

* ``mario.compute.iot_formulas`` for IOT algebra;
* ``mario.compute.sut_formulas`` for SUT algebra;
* ``mario.compute.views`` for extracted/reshaped blocks;
* ``mario.compute.operators`` only when the logic is better modeled as a shared
  reusable operator.

Keep the function name exactly aligned with the name referenced in the catalog.
The resolver locates builders by that string.

For SUT work, check ordering assumptions carefully. Unified blocks depend on
the activity/commodity ordering policy, so a correct formula can still look
wrong if the builder and expected ordering disagree.


Think About Parsed Versus Demand-Driven Blocks
----------------------------------------------

Not every matrix should be eagerly materialized by parsers.

If a block is truly part of the parsed source payload, register it with a
parsed strategy and make sure the parser emits it under the canonical MARIO
name. If it is cheaper or clearer to derive on demand, prefer a formula or view
strategy and let the resolver materialize it when requested through
``db.query(...)``, ``db.resolve(...)`` or ``db.calc_all(...)``.

The current codebase intentionally keeps some blocks demand-driven even when
they could be computed immediately, because that keeps parser state smaller and
makes dependencies explicit.


Required Tests
--------------

A new matrix normally needs coverage at three levels.

Catalog tests
   Update or extend ``tests/test_compute_catalog.py`` so the new matrix has the
   expected table kind, axes, and strategies.

Resolver tests
   Add a resolver-level test in ``tests/test_resolver.py`` when the new block
   introduces a new dependency path, runtime option interaction, or SUT
   ordering edge case.

Formula or view tests
   Add focused numeric tests in ``tests/test_iot_formulas.py``,
   ``tests/test_sut_formulas.py``, or ``tests/test_compute_views.py`` depending
   on where the implementation lives.

As a rule, test the semantics closest to where they can fail. Pure algebra goes
in formula tests; dependency selection and materialization behaviour go in
resolver tests.


Documentation Follow-Through
----------------------------

If the matrix is user-facing, update the docs in the same change:

* the nomenclature workbook in ``mario/settings/Terminology.xlsx``;
* the generated terminology tables via ``python doc/scripts/generate_terminology_tables.py``;
* any user guide or API reference pages that should show the new block.

This avoids a common failure mode where the code accepts a matrix that the docs
do not acknowledge, or the docs mention a block that the resolver cannot build.


Practical Checklist
-------------------

Before considering the work done, verify all of the following:

* the matrix appears in ``available_matrices()`` for the right table kind;
* ``db.resolve(...)`` or ``db.calc_all(...)`` can materialize it from a realistic test fixture;
* axes and labels match the catalog spec;
* tests cover both the happy path and the main failure mode;
* user-facing nomenclature and docs mention the new block if it is public.
