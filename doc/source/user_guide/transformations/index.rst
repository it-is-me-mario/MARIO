:summary: Change a model’s structure or inputs and inspect the resulting scenario.

Transformations and scenarios
==============================

These guides change the structure of a *database* or add *scenarios* to it:
aggregation, new extensions and sectors, shocks, and conversions between table
formats.

These transformation workflows apply to IOT/SUT. NAM currently supports
cloning a scenario and replacing native flow blocks with ``set_block``;
see :doc:`NAM scenarios </get_started/scenarios>` and the
:doc:`NAM database reference </reference/api_nam_database>`.
NAM aggregation, shock propagation and conversion to SUT are not implemented.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - I want to
     - Guide
   * - Group regions, sectors or other sets with my own mapping
     - :doc:`Aggregate a database <aggregate>`
   * - Prepare groups from NACE or CPA hierarchies
     - :doc:`Aggregate by classification <classification_aggregation>`
   * - Add environmental or other satellite accounts
     - :doc:`Add extensions <add_extensions>`
   * - Apply changes and compare scenarios
     - :doc:`Apply shocks <apply_shocks>`
   * - Add or split productive sectors
     - :doc:`Add and split sectors <add_sectors>`
   * - Convert a SUT into an IOT
     - :doc:`SUT to IOT <sut_to_iot>`
   * - Extract one or several regions
     - :doc:`MRIO to SRIO <mrio_to_srio>`
   * - Change the SUT trade representation
     - :doc:`Isard to Chenery-Moses <to_chenery_moses>`
   * - Update electricity generation or trade shares
     - :doc:`Update electricity mixes <../advanced/electricity_mix>`

.. toctree::
   :hidden:

   aggregate
   classification_aggregation
   classification_mapping
   add_extensions
   apply_shocks
   add_sectors
   sut_to_iot
   mrio_to_srio
   to_chenery_moses
   ../advanced/electricity_mix
