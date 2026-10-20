db.wac
======

Calculate the activity-to-commodity quadrant of the SUT Leontief inverse.

.. math::

   w_{ac}=(I-su)^{-1}s=w_{aa}s

Inputs
------

``u``: commodity-by-activity use coefficients.

``s``: activity-by-commodity supply coefficients.

Result
------

Activity nodes on rows and commodity nodes on columns.

Calculation details
-------------------

The subscript ``a`` denotes activities and ``c`` commodities.
The equivalent linear system is :math:`(I-su)w_{ac}=s`. Compute settings
select an inverse or solve path; an existing unified ``w`` can also
supply this quadrant. In the explicit inverse path, a singular system
falls back to the Moore-Penrose pseudoinverse.

Example
-------

.. code-block:: python

   import mario

   db = mario.load_test("SUT", tech_assumption="IT")
   result = db.resolve("wac")
   # Dotted access requests the same block:
   result = db.wac

Use :doc:`resolve <mario.CoreModel.resolve>` for scenario selection and
recomputation options. Existing targets are reused. The other SUT equations
are listed in :doc:`../reference/api_resolvable_matrices`.
