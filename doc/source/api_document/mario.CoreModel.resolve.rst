mario.CoreModel.resolve
=======================

.. currentmodule:: mario

``resolve`` returns one block and stores it in the selected scenario. It uses
existing blocks and computes missing dependencies as needed; an already stored
target is reused unless ``force_rewrite=True``.

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="industry-based")
   fc = db.resolve("fc")

This computes commodity-side environmental multipliers:

.. math::

   f_c=(e_as+e_c)(I-us)^{-1}.

The result has satellite accounts on rows and commodity production nodes on
columns. See :doc:`the block formulas <../reference/api_resolvable_matrices>`
for the SUT quadrants and the equivalent linear-system form.

.. automethod:: CoreModel.resolve

For NAM, the same method name resolves its own account totals, coefficients
and accounting views. The SUT formula above does not apply to NAM. See
:doc:`the NAM interface </reference/api_nam_database>` for its signature and
:doc:`NAM calculations </reference/api_nam_calculations>` for its equations.
