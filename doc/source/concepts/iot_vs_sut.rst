IOT vs SUT
==========

MARIO supports both Input-Output Tables (IOTs) and Supply and Use Tables
(SUTs). They share many workflows, but they do not carry the same internal
structure.

IOT
---

IOT workflows revolve around a single productive system. The main public flow
blocks are:

* ``Z`` for intersectoral flows;
* ``Y`` for final demand;
* ``V`` for factor-of-production rows;
* ``E`` for satellite-account rows.

From these flow blocks MARIO can derive coefficient blocks such as ``z``,
``v`` and ``e``, production totals such as ``X``, and demand-driven results
such as footprints, multipliers and prices.

For IOT databases, the public view is already close to the native internal
representation. This is why IOT workflows often feel more direct.

SUT
---

SUT workflows distinguish commodity and activity structure explicitly. The
native flow blocks are split into activity-side and commodity-side pieces:

* ``U`` and ``S``;
* ``Ya`` and ``Yc``;
* ``Va`` and ``Vc``;
* ``Ea`` and ``Ec``;
* ``EY`` and ``VY``.

MARIO can also expose unified public views such as ``Z``, ``Y``, ``V`` and
``E`` on top of those split blocks. These are convenient for inspection and
some exports, but they are not the most native representation of a SUT
database.

Why this matters
----------------

Some operations are common to both table types, but others depend strongly on
the underlying structure. Parsing, aggregation and transforms therefore need to
know whether a database is IOT or SUT.

In practice, the distinction affects at least four things:

* which matrices exist natively;
* how coefficients are defined;
* which transformations are legal or meaningful;
* which compute paths are efficient on large systems.

As a rule:

* use IOT when you already have a unified interindustry system and want a
  direct analytical workflow;
* use SUT when you need to preserve supply-use structure, technology
  assumptions, or later transform the table into an IOT.
