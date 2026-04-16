Flows vs Coefficients
=====================

Many MARIO matrices come in pairs:

* a flow block that stores quantities in levels;
* a coefficient block that stores the same structure normalized by an output
  vector.

This distinction is central to parsing, validation, export and runtime
computation.

Flows
-----

Flow blocks store actual quantities. Typical examples are:

* IOT: ``Z``, ``Y``, ``V``, ``E``;
* SUT: ``U``, ``S``, ``Ya``, ``Yc``, ``Va``, ``Vc``, ``Ea``, ``Ec``.

These matrices answer questions such as:

* how much product was supplied;
* how much input was used by a sector or activity;
* how much value added or emission is attached to an activity.

Flows are usually what users inspect first, what they compare against source
data, and what they export when they need a table in levels.

Coefficients
------------

Coefficient blocks store normalized intensities instead of levels. Examples are:

* IOT: ``z``, ``v``, ``e``;
* SUT: ``u``, ``s``, ``va``, ``vc``, ``ea``, ``ec``.

The exact normalization depends on the table type and, for some SUT blocks,
also on the active technology assumption. In the most common cases:

* ``z`` is obtained by scaling ``Z`` by sector output ``X``;
* ``u`` is obtained by scaling ``U`` by activity output ``Xa``;
* ``s`` is obtained from ``S`` using the SUT supply-side convention.

Coefficients are useful because they describe structure independently of the
absolute scale of the economy.

Why MARIO needs both
--------------------

Flows and coefficients support different tasks.

Flows are better for:

* checking the original data;
* exporting tables;
* applying changes directly in levels.

Coefficients are better for:

* structural comparisons across scenarios;
* demand-driven and solve-based computations;
* reconstructing flows from a known technical structure and output totals.

Conversions
-----------

MARIO can derive one family from the other whenever the required totals are
available.

Typical conversions are:

* ``Z`` -> ``z`` through output-based scaling;
* ``z`` + ``X`` -> ``Z`` by reversing the same scaling;
* ``U`` -> ``u`` through ``Xa``;
* ``u`` + ``Xa`` -> ``U``;
* ``S`` <-> ``s`` according to the current SUT technology assumption.

This is why a database can often be imported from either flows or coefficients
and still rebuild the missing side later.

Practical implications
----------------------

Three practical consequences matter a lot:

* exporting a database is easier to validate when you know whether you are
  looking at levels or normalized coefficients;
* scenario resets can keep either the flow-side or the coefficient-side,
  depending on the workflow;
* large-database computation often prefers coefficient-side formulas, because
  they avoid materializing very large flow blocks or inverse matrices.
