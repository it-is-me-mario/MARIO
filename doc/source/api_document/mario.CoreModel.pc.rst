db.pc
=====

For the standalone function, see :func:`mario.calc_pc`.

Calculate the commodity-side price index from activity and commodity value-added coefficients.

.. math::

   p_c=w_{ac}^{\mathsf{T}}v_a^{\mathsf{T}}\mathbf{1}
   +w_{cc}^{\mathsf{T}}v_c^{\mathsf{T}}\mathbf{1}

Inputs
------

``va`` and ``vc``: direct value-added coefficients. Factor rows
are summed first. The inverse branch uses ``wac`` and ``wcc``;
the solve branch uses ``s`` and ``u``.

Result
------

Commodity nodes on rows and one column named ``price index``.

Calculation details
-------------------

The equivalent solve is
:math:`(I-us)^{\mathsf{T}}p_c=s^{\mathsf{T}}v_a^{\mathsf{T}}\mathbf{1}+v_c^{\mathsf{T}}\mathbf{1}`.
Both direct value-added sides contribute; ``pc_ex`` decomposes this index
by contributor.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("pc")
   # Dotted access requests the same block:
   result = db.pc

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
