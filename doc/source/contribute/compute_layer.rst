Compute Layer
=============

The compute layer is the part of MARIO that answers questions such as:

* which matrices are authoritative inputs and which are derived;
* how a requested block can be reconstructed from the current scenario state;
* which implementation to use for IOT versus SUT semantics;
* how dependencies should be resolved without hard-coding one monolithic
	``calc_all`` chain.

At a high level, the compute subsystem is built around three ideas:

* a catalog that declares what each matrix means and how it may be built;
* a planner/resolver that chooses a viable strategy from the current state;
* formula and view builders that implement the actual matrix construction.

Catalog first, formulas second
------------------------------

The most important file for orientation is ``mario.compute.catalog``.

It defines the authoritative matrix catalog for IOT and SUT workflows,
including:

* the matrix name and table kind;
* the expected row and column axes;
* whether the matrix is preserved, newly added, or parsed directly;
* one or more strategies to obtain it.

This is a deliberate design choice. The project is moving away from treating
matrix formulas as scattered ad-hoc helpers. Instead, the catalog acts as the
source of truth for what a block is allowed to mean and how it can be resolved.

Strategies and resolution
-------------------------

Each matrix specification can advertise different strategies, for example:

* ``ParsedStrategy`` when the block is expected to be materialized directly;
* ``FormulaStrategy`` when the block can be computed from dependencies;
* ``ExtractStrategy`` when the block is one view extracted from a unified
	source;
* ``ConcatStrategy`` when a block is assembled from already resolved pieces.

The resolver in ``mario.compute.resolver`` is the execution engine that walks
those strategies. Its job is to:

* inspect the current dataset and scenario state;
* ask the planner for candidate strategies;
* resolve dependencies recursively;
* call the relevant formula, extract, concat, or operator implementation;
* memoize and store successful results back into the scenario.

For an advanced reader, this is the core shift in MARIO's internal model: the
package is moving toward dependency-driven resolution rather than a fixed list
of imperative calculations.

Where the actual formulas live
------------------------------

The formulas themselves are not all in one file.

* ``mario.compute.iot_formulas`` contains IOT-specific matrix builders;
* ``mario.compute.sut_formulas`` contains SUT-specific builders;
* ``mario.compute.views`` contains builders for concatenated or reshaped views;
* ``mario.compute.operators`` contains reusable operator-style implementations.

This separation is useful because not every derived block is the same kind of
operation. Some are genuine economic formulas, some are shaped views over other
blocks, and some are reusable algebraic operators.

Planner behaviour
-----------------

The planner is responsible for selecting viable strategies given the current
state. In practice that means it decides whether MARIO can derive a matrix from
what is already present, and in which order dependencies should be attempted.

This matters because the same matrix may be obtainable in multiple ways. For
example, a block may be parsed directly for one source, reconstructed from a
flow matrix and production vector in another case, or derived from already
resolved coefficients in a third.

SUT semantics and ordering
--------------------------

SUT handling adds an extra layer of complexity because MARIO needs a coherent
ordering policy for unified activity/commodity blocks. That is why the compute
layer includes ``SUTUnifiedOrderingPolicy`` and related ordering helpers.

If an SUT-derived result looks structurally odd, the issue is often not only in
the formula itself. It may also be in the block ordering expected by the view or
concat builder using that formula.

Relationship with ``calc_all(...)``
-----------------------------------

``calc_all(...)`` still exists as a practical user-facing workflow, but the
compute layer should be read as the more general underlying model.

``calc_all(...)`` is useful when a user wants a broad set of matrices
materialized eagerly. The catalog/resolver layer is useful when the question is
more precise: why does matrix ``m`` exist, where did ``F`` come from, or which
dependencies are missing for a given request.

Sparse-aware helpers and performance
------------------------------------

The recent compute work also introduced more sparse-aware shared helpers. The
goal is not only speed; it is to keep the formula implementations consistent and
to avoid rewriting low-level matrix operations in slightly different ways across
the codebase.

For that reason, performance-sensitive changes should usually be made at the
helper or operator level first, not by patching one isolated formula in place.

How to debug compute behaviour
------------------------------

When tracking a wrong matrix value or a missing derived block, a productive
sequence is:

* inspect the matrix spec in ``mario.compute.catalog``;
* identify the candidate strategies chosen by the planner;
* inspect the formula or view builder named in that strategy;
* check whether the relevant dependencies are already materialized in the
	scenario;
* only then step back to parser or API code if the inputs themselves are wrong.

That workflow usually isolates whether the issue belongs to semantics,
dependency selection, or upstream parsed state.

