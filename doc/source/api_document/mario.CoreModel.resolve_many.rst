mario.CoreModel.resolve\_many
=============================

.. currentmodule:: mario

Resolve related blocks together and receive a dictionary keyed by the names
you requested:

.. code-block:: python

   import mario

   db = mario.load_test("IOT")
   results = db.resolve_many(["f", "m", "p"])
   f = results["f"]

For IOT these results follow:

.. math::

   f=ew, \qquad m=vw, \qquad p=w^{\mathsf{T}}v^{\mathsf{T}}\mathbf{1},
   \qquad w=(I-z)^{-1}.

The equations describe the results; the runtime may use equivalent linear
solves. Dependencies and results are stored in the selected scenario.
See :doc:`the block formulas <../reference/api_resolvable_matrices>` for SUT.

.. automethod:: CoreModel.resolve_many
