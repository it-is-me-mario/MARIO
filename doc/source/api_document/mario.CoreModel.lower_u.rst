db.u
====

For the standalone function, see :func:`mario.calc_u`.

Calculate commodity-by-activity use coefficients from use flows and activity production.

.. math::

   u=U\operatorname{diag}(X_a)^{-1}

Inputs
------

``U``: use flows, with commodity rows and activity columns.

``Xa``: activity production, indexed like the columns of ``U``.

Result
------

Commodity nodes on rows and activity nodes on columns. Each column
is expressed per unit of output of its activity.

Calculation details
-------------------

The same formula applies under IT and PT. A zero entry in ``Xa``
has inverse zero and sets the corresponding coefficient column to zero.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("u")
   # Dotted access requests the same block:
   result = db.u

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
