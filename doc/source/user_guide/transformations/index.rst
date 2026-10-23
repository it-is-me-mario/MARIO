Transformations
===============

These guides change the structure of a *database* or add *scenarios* to it:
aggregation, new extensions and sectors, shocks, and conversions between table
formats.

.. mario-cards::
   :columns: 2
   :links:

   .. mario-card:: :doc:`Aggregation <aggregate>`
      :kicker: db.aggregate
      :icon: merge

      Group regions, sectors and other sets with an Excel workbook or a Region
      preset.

   .. mario-card:: :doc:`Aggregating by classification <classification_aggregation>`
      :kicker: db.get_aggregation
      :icon: merge

      Prepare NACE or CPA hierarchy groups, review unresolved items and
      apply the mapping to a copy of the database.

   .. mario-card:: :doc:`Add extensions <add_extensions>`
      :kicker: db.add_extensions
      :icon: add-rows

      Add satellite accounts to a database from an Excel workbook.

   .. mario-card:: :doc:`Shock analyses <apply_shocks>`
      :kicker: db.shock_calc
      :icon: bolt

      Apply shocks through the Excel template and store the result as a new
      scenario.

   .. mario-card:: :doc:`Adding and splitting sectors <add_sectors>`
      :kicker: db.add_sectors
      :icon: split

      Extend a database with new sectors, or split existing ones, through the
      Excel workflow.

   .. mario-card:: :doc:`SUT to IOT <sut_to_iot>`
      :kicker: db.to_iot
      :icon: convert

      Turn a supply-use table into an input-output table with one of the
      transformation models A, B, C or D.

   .. mario-card:: :doc:`MRIO to SRIO <mrio_to_srio>`
      :kicker: db.to_single_region
      :icon: pin

      Extract a single-region table, or a subset of regions, from a
      multi-regional table.

   .. mario-card:: :doc:`Isard to Chenery-Moses <to_chenery_moses>`
      :kicker: db.to_chenery_moses
      :icon: swap

      Convert a supply-use table from the Isard to the Chenery-Moses format.

.. toctree::
   :hidden:

   aggregate
   classification_aggregation
   add_extensions
   apply_shocks
   add_sectors
   sut_to_iot
   mrio_to_srio
   to_chenery_moses
