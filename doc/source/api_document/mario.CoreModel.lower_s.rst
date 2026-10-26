db.s
====

For the standalone function, see :func:`mario.calc_s`.

Calculate activity-by-commodity supply coefficients using the database technology assumption.

.. math::

   s=\begin{cases}
   S\operatorname{diag}(X_c)^{-1} & \text{IT},\\
   \left(S^{\mathsf{T}}\operatorname{diag}(X_a)^{-1}\right)^{-1} & \text{PT}.
   \end{cases}

Inputs
------

``S``: supply flows, with activity rows and commodity columns.

For IT, ``Xc`` is indexed like ``S.columns``. For PT, ``Xa`` is
indexed like ``S.index``; the intermediate product-mix matrix is ``c``.

Result
------

Activity nodes on rows and commodity nodes on columns. Under IT,
``s`` is the market-share matrix. Under PT, it is the inverse of ``c``.

Calculation details
-------------------

``db.tech_assumption`` selects IT (``industry-based``) or PT
(``product-based``). PT requires square ``c``; its inverse swaps the
commodity and activity axes. If ``c`` is singular, the current inverse
builder falls back to the Moore-Penrose pseudoinverse. Under IT, zero
commodity production gives a zero coefficient column.

See :doc:`/get_started/table_formats/sut` for assumption switching and
the fallback to IT when importing a non-square SUT.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("s")
   # Dotted access requests the same block:
   result = db.s

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.


NAM convention
--------------

``nam.s`` is always native ``S`` divided columnwise by ``nam.Xc``. It
does not use an IT/PT technology assumption.
See :doc:`the NAM calculation reference <../reference/api_nam_calculations>`.
The SUT-specific formulas and zero-production conventions above remain
separate from NAM's accounting totals and signed-zero policy.
