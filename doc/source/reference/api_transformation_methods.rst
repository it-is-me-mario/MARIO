Transformations and Scenarios
=============================

These methods change the structure or scenario state of a database.
``Database.aggregate(...)`` now also supports workbook-free Region
aggregation through ``region_aggregation`` presets or explicit mappings.
``Database.ras(...)`` rebalances the ``Z`` block of an IOT scenario to target
row and column margins with the biproportional RAS algorithm.

Database Transformations
------------------------

.. toctree::
   :maxdepth: 1

   ../api_document/mario.Database.aggregate
   ../api_document/mario.Database.add_extensions
   ../api_document/mario.Database.add_sectors
   ../api_document/mario.Database.ras
   ../api_document/mario.Database.to_iot
   ../api_document/mario.Database.to_region_subset
   ../api_document/mario.Database.to_single_region
   ../api_document/mario.Database.to_chenery_moses
   ../api_document/mario.Database.pool_trade
   ../api_document/mario.Database.change_assumption


Supply and Trade Mixes
----------------------

Scenario-level redistribution of one regional bundle preserving the selected
column totals: technology/market shares with ``update_supply_mix`` and
regional sourcing with ``update_trade_mix``. See
:doc:`../user_guide/advanced/electricity_mix` for the end-to-end workflow
(EMBER supply mix, ENTSO-E trade mix, ``pool_trade`` and the data-provider
API keys). ``update_supply_mix_iot`` and ``update_mix_iot`` are kept as
IOT-only backward-compatible aliases of ``update_supply_mix``.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.Database.update_supply_mix
   ../api_document/mario.Database.update_trade_mix
   ../api_document/mario.Database.get_mix
   ../api_document/mario.Database.update_supply_mix_iot
   ../api_document/mario.Database.update_mix_iot


Scenario Operations
-------------------

For workbook-free manual shocks and programmatic scenario edits, see
:doc:`../user_guide/transformations/apply_shocks`.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.Database.clone_scenario
   ../api_document/mario.Database.rename_scenario
   ../api_document/mario.Database.rename_baseline_scenario
   ../api_document/mario.Database.update_scenarios
   ../api_document/mario.Database.shock_calc
   ../api_document/mario.Database.reset_to_flows
   ../api_document/mario.Database.reset_to_coefficients


Clusters and Helper Mutations
-----------------------------

.. toctree::
   :maxdepth: 1

   ../api_document/mario.Database.set_clusters
   ../api_document/mario.Database.add_cluster
   ../api_document/mario.Database.clear_clusters
   ../api_document/mario.Database.replace_units_name
   ../api_document/mario.Database.build_new_instance
