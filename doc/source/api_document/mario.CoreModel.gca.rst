db.gca
======

Calculate the commodity-to-activity quadrant of the SUT Ghosh inverse.

.. math::

   g_{ca}=g_{cc}b_u

Inputs
------

``gcc``: commodity Ghosh quadrant.

``bu``: commodity-by-activity direct-output coefficients.

Result
------

Commodity nodes on rows and activity nodes on columns.

Calculation details
-------------------

The subscript ``a`` denotes activities and ``c`` commodities.
A stored unified ``g`` can also supply this quadrant. The inverse
builders for ``gcc`` and ``gaa`` fall back to the Moore-Penrose
pseudoinverse when their system is singular.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("gca")
   # Dotted access requests the same block:
   result = db.gca

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
