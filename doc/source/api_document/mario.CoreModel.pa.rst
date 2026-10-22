db.pa
=====

For the standalone function, see :func:`mario.calc_pa`.

Calculate the activity-side price index from activity and commodity value-added coefficients.

.. math::

   p_a=w_{aa}^{\mathsf{T}}v_a^{\mathsf{T}}\mathbf{1}
   +w_{ca}^{\mathsf{T}}v_c^{\mathsf{T}}\mathbf{1}

Inputs
------

``va`` and ``vc``: direct value-added coefficients. Factor rows
are summed first. The inverse branch uses ``waa`` and ``wca``;
the solve branch uses ``s`` and ``u``.

Result
------

Activity nodes on rows and one column named ``price index``.

Calculation details
-------------------

The equivalent solve is
:math:`(I-su)^{\mathsf{T}}p_a=v_a^{\mathsf{T}}\mathbf{1}+u^{\mathsf{T}}v_c^{\mathsf{T}}\mathbf{1}`.
Both direct value-added sides contribute; ``pa_ex`` decomposes this index
by contributor.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("pa")
   # Dotted access requests the same block:
   result = db.pa

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
