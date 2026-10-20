db.gcc
======

Calculate the commodity-to-commodity quadrant of the SUT Ghosh inverse.

.. math::

   g_{cc}=(I-b_u b_s)^{-1}

Inputs
------

``bu`` and ``bs``: the two direct-output coefficient blocks.

Result
------

Commodity nodes on both axes.

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
   result = db.resolve("gcc")
   # Dotted access requests the same block:
   result = db.gcc

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
