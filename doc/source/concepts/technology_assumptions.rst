Technology Assumptions
======================

Technology assumptions are a SUT-specific concept in MARIO. They describe how
the supply-side coefficient structure should be interpreted and rebuilt.

Two assumptions
---------------

MARIO supports two structural assumptions for SUT databases:

* ``industry-based``;
* ``product-based``.

At the API level, the short aliases ``IT`` and ``PT`` are also accepted.

These assumptions do not change the meaning of every SUT block. They mainly
affect the supply-side coefficient logic.

Structural property, not runtime option
---------------------------------------

``tech_assumption`` is stored as a property of the database. It is not treated
like a temporary compute preference such as ``compute_method``.

This is important because the assumption changes the mathematical relationship
between some public matrices. Two databases with the same flows but different
technology assumptions should be understood as structurally different SUT
states.

Industry-based and product-based logic
--------------------------------------

Under the industry-based assumption, the usual public supply coefficient matrix
is ``s``.

Under the product-based assumption, MARIO also exposes a public matrix ``c``.
Conceptually:

* ``c`` is built from ``S`` and ``Xa``;
* ``s`` is recovered as the inverse of ``c``;
* rebuilding ``S`` from coefficients uses the product-based inverse relation,
  not the industry-based one.

This is why ``c`` is public: it makes the product-based representation easier
to inspect and reason about directly.

Changing the assumption
-----------------------

For SUT databases, the assumption can be changed after parsing. When this
happens, MARIO resets scenarios to flow blocks first and then rebuilds the
affected coefficient-side structure under the new assumption.

This avoids mixing coefficients computed under different structural rules.

Square-table requirement
------------------------

Product-based logic requires a square SUT in the relevant commodity/activity
sense. If a user requests ``PT`` on a non-square SUT, MARIO does not fail the
import. It falls back to ``industry-based`` instead.

This fallback is intentional:

* it keeps parsing robust;
* it avoids pretending that the product-based system is valid when the required
  structure is not present.
