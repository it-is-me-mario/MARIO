db.bu
=====

For the standalone function, see :func:`mario.calc_bu`.

Calculate commodity-by-activity direct-output coefficients from use flows.

.. math::

   b_u=\operatorname{diag}(X_c)^{-1}U

Inputs
------

``U``: commodity-by-activity use flows.

``Xc``: commodity production, indexed like ``U.index``.

Result
------

Commodity nodes on rows and activity nodes on columns.

Calculation details
-------------------

This normalizes rows by commodity production, whereas ``u``
normalizes columns by activity production. Zero production gives a zero row.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("bu")
   # Dotted access requests the same block:
   result = db.bu

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
