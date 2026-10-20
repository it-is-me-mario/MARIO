db.bs
=====

For the standalone function, see :func:`mario.calc_bs`.

Calculate activity-by-commodity direct-output coefficients from supply flows.

.. math::

   b_s=\operatorname{diag}(X_a)^{-1}S

Inputs
------

``S``: activity-by-commodity supply flows.

``Xa``: activity production, indexed like ``S.index``.

Result
------

Activity nodes on rows and commodity nodes on columns.

Calculation details
-------------------

This normalizes rows by activity production. It differs from
the supply coefficient matrix ``s``. Zero production gives a zero row.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("bs")
   # Dotted access requests the same block:
   result = db.bs

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
