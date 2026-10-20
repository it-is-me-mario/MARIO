mario.CoreModel.explain
=======================

.. currentmodule:: mario

Inspect the dependency plan before requesting a result:

.. code-block:: python

   import mario

   db = mario.load_test("IOT")
   print(db.explain("f"))

The returned text identifies stored dependencies and the planned formula
functions. It does not perform the calculation. For the equations represented
by those functions, see :doc:`../reference/api_calculation_methods` and
:doc:`../reference/api_resolvable_matrices`.

If the target is already stored, the explanation reports it as materialized;
it does not reconstruct the formula used to create that value.

.. automethod:: CoreModel.explain
