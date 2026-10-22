db.gac
======

For the standalone function, see :func:`mario.calc_gac`.

Calculate the activity-to-commodity quadrant of the SUT Ghosh inverse.

.. math::

   g_{ac}=g_{aa}b_s

Inputs
------

``gaa``: activity Ghosh quadrant.

``bs``: activity-by-commodity direct-output coefficients.

Result
------

Activity nodes on rows and commodity nodes on columns.

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
   result = db.resolve("gac")
   # Dotted access requests the same block:
   result = db.gac

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
