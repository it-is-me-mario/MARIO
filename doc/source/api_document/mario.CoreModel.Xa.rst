db.Xa
=====

For the standalone function, see :func:`mario.calc_Xa`.

Calculate total activity production from available supply-side blocks.

.. math::

   X_a=S\mathbf{1}+Y_a\mathbf{1}
   \qquad\text{or}\qquad X_a=sX_c

Inputs
------

The flow branch uses ``S`` and ``Ya``. The coefficient branch uses
``s`` and ``Xc``. A stored unified ``X`` can also supply the activity slice.

Result
------

Activity nodes on rows and one column named ``production``.

Calculation details
-------------------

These are alternative resolver branches, chosen from available
inputs. ``Ya`` is activity-side final demand and is not provided by
every parser. Use ``db.explain("Xa")`` to inspect the current plan.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("Xa")
   # Dotted access requests the same block:
   result = db.Xa

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.


NAM convention
--------------

``nam.Xa`` sums all outgoing payments of activity accounts. It uses every
relevant native block, including imports, factors and taxes, rather than
the SUT supply-only formula below.
See :doc:`the NAM calculation reference <../reference/api_nam_calculations>`.
The SUT-specific formulas and zero-production conventions above remain
separate from NAM's accounting totals and signed-zero policy.
