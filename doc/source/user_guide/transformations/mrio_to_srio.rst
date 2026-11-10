:page-type: Guide
:summary: Keep selected regions and represent their exchanges with the remaining economy.

Extract a region or subset
==========================

.. container:: mario-companion

   :download:`Download notebook <mrio_to_srio.ipynb>`

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      regional = db.to_single_region("Reg1", inplace=False)
      regional.regions

   .. container:: mario-result

      **Result** · A database for the retained region, with external exchanges
      represented in value-added and final-demand accounts.

Keep several regions
--------------------

.. code-block:: python

   regions_to_keep = db.regions[:-1]
   subset = db.to_region_subset(regions_to_keep, inplace=False)

Select fewer than all source regions. The packaged two-region example retains
one; on a larger MRIO, ``regions_to_keep`` can contain several regions.

External trade accounts
-----------------------

.. code-block:: python

   regional.factors
   regional.consumption_categories
   regional.Z

This operation changes the model boundary. Inspect the new trade accounts
before interpreting regional value added or final demand.

Keep SUT imports by product or producer
---------------------------------------

On a monetary SUT, select the classification of the imported flows explicitly:

.. code-block:: python

   sut = mario.load_test("SUT")
   region = sut.regions[0]
   products = sut.to_single_region(
       region, imports_by="product", inplace=False,
   )
   producers = sut.to_single_region(
       region, imports_by="activity", inplace=False,
   )

``"product"`` keeps one import account per commodity, such as
``"imports of Electricity"``. ``"activity"`` uses the **foreign producing
activity**, rather than the domestic purchaser, with labels such as
``"imports by Electricity production"``. Use-side product imports are allocated
to producers using each source commodity's shares in ``S``. This is a
proportional sourcing assumption; the SUT does not observe each buyer's choice
between activities supplying the same commodity. A nonzero import with zero
net supply raises an error because that allocation is undefined. Direct
activity final demand is allocated to products using the activity's commodity
output mix when ``imports_by="product"``.

The retained products, activities, factors of production and original
final-demand categories are kept separately. Only foreign partner regions are
summed by default. To retain those partners too, combine the classification
with ``trade_mode="by_region"``; both methods accept the same options:

.. code-block:: python

   subset = sut.to_region_subset(
       [region], imports_by="product", trade_mode="by_region", inplace=False,
   )

The native accounting blocks remain available:

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Block
     - Retained flows
   * - ``S``, ``U``
     - Supply and use between retained economic nodes.
   * - ``Ya``, ``Yc``
     - Original domestic final-demand columns plus exports to excluded regions.
   * - ``Va``
     - Original activity-side factors plus use-side import accounts.
   * - ``Vc``
     - Original commodity-side factors plus supply-side import accounts,
       including trade carried in ``S`` by Chenery-Moses SUTs.
   * - ``VY``
     - Original direct final-demand factors plus imported final uses,
       classified like the import accounts in ``Va`` and ``Vc``.
   * - ``Ea``, ``Ec``, ``EY``
     - Original direct environmental accounts on the retained columns.

Imports are exogenous monetary inputs, not domestic value added, even though
their accounts share the factor matrices. Their upstream foreign emissions
are not added to the domestic environmental accounts.

With ``imports_by=None``, the legacy layout retains aggregate import accounts.
``trade_mode="by_sector"`` selects product imports and a single ``Export``
category per retained region; ``"by_region_and_sector"`` retains partner
detail as well. SUT productive axes keep their native ``Region/Level/Item``
structure. Imports on the default SUT path now also retain imported final
demand in ``VY``.

See :doc:`db.to_single_region() <../../api_document/mario.Database.to_single_region>`
and :doc:`db.to_region_subset() <../../api_document/mario.Database.to_region_subset>`.
