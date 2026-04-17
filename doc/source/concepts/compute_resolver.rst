Compute Resolver
================

MARIO no longer relies on a single hardcoded chain for every matrix. It uses a
resolver-based compute layer.

Core idea
---------

Each public matrix is described in a central compute catalog. For a given
target, the catalog may know several valid ways to obtain it:

* read it directly if it was parsed or already stored;
* extract it from a larger matrix;
* concatenate smaller matrices into a unified view;
* compute it through a mathematical formula;
* apply an operator-like transformation.

The resolver inspects what is currently available and chooses a valid path.

Main components
---------------

The compute layer is organized around three roles:

* the catalog describes matrices and available strategies;
* the planner ranks viable strategies;
* the resolver executes the chosen path and caches the result.

This architecture makes the system more flexible than a fixed formula tree.
The same matrix can be rebuilt differently depending on the available matrices
and the runtime settings.

Strategy types
--------------

The most important strategy families are:

* parsed: the matrix already exists in the database store;
* extract: the target is a sub-matrix of another matrix;
* concat: the target is a unified view built from smaller matrices;
* formula: the target must be computed from other matrices.

From a user point of view, attribute access such as ``db.f`` or ``db.Z`` can
therefore trigger very different internal paths while keeping the public API
simple.

Runtime options
---------------

Some targets have more than one meaningful formula family. For these cases,
MARIO also uses runtime preferences such as:

* ``compute_method`` with values ``auto``, ``inverse`` or ``solve``;
* ``linear_strategy`` with values ``auto``, ``direct`` or ``iterative``.

These settings do not affect every matrix. They only matter when the catalog
actually offers alternative compute paths for the requested target.

Why this architecture matters
-----------------------------

The resolver-based design is what makes recent MARIO improvements possible:

* large-database paths can avoid explicit inverse matrices;
* SUT split matrices and unified views can coexist cleanly;
* new public matrices can be added without rewriting the whole compute layer;
* formulas can become sparse-aware without exposing that complexity in the
  high-level API.
