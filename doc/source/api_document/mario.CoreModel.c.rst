db.c
====

Calculate the commodity-by-activity product-mix coefficients for product-based technology.

.. math::

   c=S^{\mathsf{T}}\operatorname{diag}(X_a)^{-1},\qquad c=s^{-1}

Inputs
------

``S``: supply flows, with activity rows and commodity columns.

``Xa``: activity production, indexed like ``S.index``. Alternatively,
the resolver can invert an already available ``s``.

Result
------

Commodity nodes on rows and activity nodes on columns. Each column
describes the commodity output mix per unit of activity production.

Calculation details
-------------------

``c`` is defined only under PT (``product-based``). Requesting it
under IT does not produce a product-mix result. Zero activity production
has inverse zero in the flow-based branch. The branch that inverts ``s``
uses the Moore-Penrose pseudoinverse if ``s`` is singular.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="PT")
   result = db.resolve("c")
   # Dotted access requests the same block:
   result = db.c

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
