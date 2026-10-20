mario.CoreModel.calc\_all
=========================

.. currentmodule:: mario

``calc_all`` stores the requested results in the database. Use ``resolve``
instead when you also want the returned matrix, or ``resolve_many`` for a
mapping of results. The equations depend on the requested block, table kind
and SUT technology assumption; see
:doc:`the block formulas <../reference/api_resolvable_matrices>`.

.. code-block:: python

   import mario

   db = mario.load_test("IOT")
   db.calc_all(["f", "F"])
   f = db.get_block_as_pandas("f")
   F = db.get_block_as_pandas("F")

For this IOT example:

.. math::

   f=e(I-z)^{-1}, \qquad F=f\operatorname{diag}(Y\mathbf{1}).

``F`` has the same account-by-production-node axes as ``f``. Both matrices
are reused if already stored; ``force_rewrite=True`` requests recomputation
of the selected targets using the available dependencies.

.. automethod:: CoreModel.calc_all
