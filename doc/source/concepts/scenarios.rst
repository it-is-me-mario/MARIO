Scenarios
=========

MARIO stores data by scenario. Even when you work with a single baseline table,
the database is already scenario-aware.

Baseline and derived scenarios
------------------------------

Every database has a ``baseline`` scenario. Additional scenarios are created
when you:

* clone an existing scenario;
* apply shocks into a new scenario;
* update stored blocks explicitly.

The main idea is simple: a scenario is another state of the same database
structure, not a different database class.

What is stored
--------------

Scenario storage is block-based. MARIO does not need to materialize every
possible matrix for every scenario.

Instead, each scenario stores the blocks that are already available or have
been explicitly computed and cached. Missing blocks can still be rebuilt on
demand by the resolver.

This matters because:

* scenarios stay lighter than a full eager copy of every matrix;
* users can choose whether to keep flows or coefficients after an operation;
* derived quantities can be recomputed consistently from the scenario state.

Common operations
-----------------

Typical scenario operations are:

* clone a scenario before applying a shock;
* update one or more blocks and keep the rest implicit;
* compare a policy scenario against the baseline;
* reset scenarios to flows or coefficients before changing structural
  settings.

The last point matters especially for SUT technology assumptions: changing the
assumption is not a small local edit, so MARIO resets scenarios to flow blocks
before rebuilding the affected coefficient-side structure.

Why scenarios are useful
------------------------

This model makes scenario workflows practical without forcing a full copy of
every matrix all the time.

In practice it means:

* baseline data stays intact;
* counterfactual states can be created incrementally;
* the same compute engine works across scenarios, because each scenario is just
  a different block store under the same table definition.
