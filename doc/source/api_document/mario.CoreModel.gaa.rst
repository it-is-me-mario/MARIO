db.gaa
======

Calculate the activity-to-activity quadrant of the SUT Ghosh inverse.

.. math::

   g_{aa}=(I-b_s b_u)^{-1}

Inputs
------

``bs`` and ``bu``: the two direct-output coefficient blocks.

Result
------

Activity nodes on both axes.

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
   result = db.resolve("gaa")
   # Dotted access requests the same block:
   result = db.gaa

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
