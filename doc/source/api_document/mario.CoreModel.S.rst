db.S
====

Calculate activity-by-commodity supply flows from supply coefficients and production.

.. math::

   S=\begin{cases}
   s\operatorname{diag}(X_c) & \text{IT},\\
   \left(c\operatorname{diag}(X_a)\right)^{\mathsf{T}},\quad c=s^{-1} & \text{PT}.
   \end{cases}

Inputs
------

``s``: supply coefficients, with activity rows and commodity columns.

IT uses ``Xc``, indexed like ``s.columns``. PT uses ``Xa``,
indexed like ``s.index``, and can also reconstruct supply from ``c`` directly.

Result
------

Activity nodes on rows and commodity nodes on columns.

Calculation details
-------------------

The technology assumption is read from ``db.tech_assumption``.
The PT branch uses the Moore-Penrose pseudoinverse if inversion of
``s`` fails because it is singular.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("S")
   # Dotted access requests the same block:
   result = db.S

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
