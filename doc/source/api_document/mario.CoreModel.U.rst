db.U
====

Calculate commodity-by-activity use flows from use coefficients and activity production.

.. math::

   U=u\operatorname{diag}(X_a)

Inputs
------

``u``: use coefficients, with commodity rows and activity columns.

``Xa``: activity production, indexed like the columns of ``u``.

Result
------

Commodity nodes on rows and activity nodes on columns. Each
coefficient column is multiplied by its activity production.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("U")
   # Dotted access requests the same block:
   result = db.U

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
