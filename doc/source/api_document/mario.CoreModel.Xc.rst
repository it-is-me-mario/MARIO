db.Xc
=====

For the standalone function, see :func:`mario.calc_Xc`.

Calculate total commodity production from use flows or the commodity-side coefficient system.

.. math::

   X_c=U\mathbf{1}+Y_c\mathbf{1},\qquad
   (I-us)X_c=Y_c\mathbf{1},\qquad X_c=w_{cc}(Y_c\mathbf{1})

Inputs
------

The flow branch uses ``U`` and ``Yc``. The solve branch uses ``u``,
``s`` and ``Yc``. An existing ``wcc`` can be multiplied by commodity
final-demand totals; a stored unified ``X`` can supply the commodity slice.

Result
------

Commodity nodes on rows and one column named ``production``.

Calculation details
-------------------

Final demand is summed across its columns first. The selected
branch depends on available inputs and compute settings; the solve branch
does not need a materialized ``wcc``.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("Xc")
   # Dotted access requests the same block:
   result = db.Xc

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
