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

For native import matrices, pass ``import_representation="separate"`` when
retaining one region. See :doc:`separate import accounts <import_accounts>`
for the IOT/SUT blocks, coefficients and reversible conversion.

.. code-block:: python

   regional.factors
   regional.consumption_categories
   regional.Z

This operation changes the model boundary. Inspect the new trade accounts
before interpreting regional value added or final demand.

Classify imports and choose source-region detail
------------------------------------------------

Both extraction methods accept two independent choices:

* ``imports_by="sector"`` on IOTs; ``"commodity"`` or ``"activity"`` on SUTs.
* ``trade_mode="aggregate"`` (default) sums foreign source regions, while
  ``"by_region"`` retains them as an explicit row dimension.

For example, keep one SUT region with imports by commodity and total foreign
sourcing:

.. code-block:: python

   sut = mario.load_test("SUT")
   region = sut.regions[0]
   commodities = sut.to_single_region(
       region, imports_by="commodity", trade_mode="aggregate", inplace=False,
   )
   commodities.query("Va").index.names
   # ["Commodity", "Factor of production"]

To retain source regions as well:

.. code-block:: python

   partners = sut.to_region_subset(
       [region], imports_by="commodity", trade_mode="by_region", inplace=False,
   )
   partners.query("Va").index.names
   # ["Region", "Commodity", "Factor of production"]

The Region level on import rows identifies the excluded producer or partner;
columns identify retained buyers. It does not add foreign regions back into
the endogenous system. With aggregate sourcing, new import rows have no
source-region value, including when original factor rows already have a
Region dimension.

Import classifications are matrix dimensions
--------------------------------------------

The factor label is ``"imports"``. The commodity, activity or sector code is
stored in a separate, declared ``matrix_layouts`` dimension. For example,
``Va`` and ``VY`` can have these row coordinates:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Commodity
     - Factor of production
   * - *(empty)*
     - Wages
   * - Electricity by coal
     - imports
   * - Electricity by wind
     - imports

Original factors without a commodity association retain an empty Commodity
level. Their original amounts and source row classifications are preserved.

A single Commodity aggregation maps this dimension on import rows as well as
on productive axes. No second Factor of production mapping is needed. This
packaged example combines its first two commodity labels:

.. code-block:: python

   import pandas as pd

   items = commodities.get_index("Commodity")
   mapping = pd.DataFrame({"Aggregation": items}, index=items)
   mapping.loc[items[:2], "Aggregation"] = "Combined commodities"
   commodities.aggregate(
       {"Commodity": mapping}, levels=["Commodity"], zero_output_epsilon=None,
   )

The same applies to Sector on IOTs and Activity on SUTs. Derived factor
coefficients and multipliers use the declared row layout too; they are
recomputed from the aggregated flows.

``commodities.DataFrame()`` displays the declared set dimensions together,
including empty factor levels, without changing the model's matrix indexes.

Observed import-only classifier labels and source regions can be mapped even
when they are absent from endogenous productive axes. Geographic presets also
cover retained import origins. These descriptors do not add economic nodes or
expand the endogenous region set. If source regions were collapsed, a
region-specific classifier mapping must give the same target for that item
across origins; otherwise extraction with ``trade_mode="by_region"`` is needed.

On IOTs, the analogous call is:

.. code-block:: python

   sector_imports = db.to_single_region(
       db.regions[0], imports_by="sector", trade_mode="aggregate", inplace=False,
   )

SUT producer attribution
-------------------------

``imports_by="activity"`` uses the **foreign producing activity**, rather than
the domestic purchaser. Use-side commodity imports are allocated to producers
using each source commodity's shares in ``S``. This is a proportional sourcing
assumption; the SUT does not observe each buyer's choice between activities
supplying the same commodity. A nonzero import with zero net supply raises an
error because that allocation is undefined. Direct activity final demand is
allocated to commodities using the activity's output mix for
``imports_by="commodity"``.

Retained accounting blocks
---------------------------

The retained productive classifications, original factors and final-demand
categories stay separate. Export columns are appended. The extraction retains
the baseline and discards other scenarios.

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Block
     - Retained flows
   * - ``S``, ``U``
     - Supply and use between retained SUT economic nodes.
   * - ``Ya``, ``Yc``
     - Original domestic final-demand columns plus exports to excluded regions.
   * - ``Va``
     - Original activity-side factors plus use-side import accounts.
   * - ``Vc``
     - Original commodity-side factors plus supply-side import accounts,
       including trade carried in ``S`` by Chenery-Moses SUTs.
   * - ``VY``
     - Original direct final-demand factors plus imported final uses,
       classified like the import accounts in ``Va``/``Vc`` or IOT ``V``.
   * - ``Ea``, ``Ec``, ``EY``
     - Original direct environmental accounts on the retained SUT columns.
   * - IOT ``Z``, ``Y``, ``V``, ``E``, ``EY``
     - Retained transactions, final demand with exports, factors with
       intermediate imports, and direct environmental accounts.

Imports are exogenous monetary inputs, not domestic value added, even though
their accounts share the factor matrices. Their upstream foreign emissions
are not added to domestic environmental accounts. Imported final demand is
retained in ``VY`` for both table types, including the default extraction.

With ``imports_by=None``, the legacy layout keeps imports total over items.
``trade_mode="by_sector"`` selects sector imports on IOTs or commodity imports
on SUTs, plus a single ``Export`` category per retained region;
``"by_region_and_sector"`` retains source-region detail as well. SUT productive
axes retain their native ``Region/Level/Item`` structure.

To re-import an exported workbook, pass its declared factor prefix through
``matrix_layouts``, for example ``{"V": "Commodity"}`` or
``{"V": ("Region", "Sector")}``. Empty classification levels are preserved.

See :doc:`db.to_single_region() <../../api_document/mario.Database.to_single_region>`
and :doc:`db.to_region_subset() <../../api_document/mario.Database.to_region_subset>`.
