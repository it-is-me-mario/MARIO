db.waa
======

For the standalone function, see :func:`mario.calc_waa`.

Calculate the activity-to-activity quadrant of the SUT Leontief inverse.

.. math::

   w_{aa}=(I-su)^{-1}

Inputs
------

``u``: commodity-by-activity use coefficients.

``s``: activity-by-commodity supply coefficients.

Result
------

Activity nodes on both axes.

Calculation details
-------------------

The subscript ``a`` denotes activities and ``c`` commodities.
The equivalent linear system is :math:`(I-su)w_{aa}=I`. Compute settings
select an inverse or solve path; an existing unified ``w`` can also
supply this quadrant. In the explicit inverse path, a singular system
falls back to the Moore-Penrose pseudoinverse.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("waa")
   # Dotted access requests the same block:
   result = db.waa

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
