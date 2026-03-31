IOT vs SUT
==========

MARIO supports both Input-Output Tables (IOTs) and Supply and Use Tables (SUTs).

IOT
---

IOT workflows revolve around unified productive blocks such as:

* ``Z`` for intersectoral flows;
* ``Y`` for final demand;
* ``V`` for factor-of-production rows;
* ``E`` for satellite-account rows.

SUT
---

SUT workflows distinguish supply and use structure and may also carry split
activity and commodity blocks:

* ``U`` and ``S``;
* ``Ya`` and ``Yc``;
* ``Va`` and ``Vc``;
* ``Ea`` and ``Ec``;
* ``EY`` and ``VY``.

Why this matters
----------------

Some operations are common to both table types, but others depend strongly on
the underlying structure. Parsing, aggregation and transforms therefore need to
know whether a database is IOT or SUT.
