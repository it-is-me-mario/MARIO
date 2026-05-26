Transformations and Scenarios
=============================

These methods change the structure or scenario state of a database.
``Database.aggregate(...)`` now also supports workbook-free Region
aggregation through ``region_aggregation`` presets or explicit mappings.

Database Transformations
------------------------

.. toctree::
   :maxdepth: 1

   ../api_document/mario.Database.aggregate
   ../api_document/mario.Database.add_extensions
   ../api_document/mario.Database.add_sectors
   ../api_document/mario.Database.to_iot
   ../api_document/mario.Database.to_region_subset
   ../api_document/mario.Database.to_single_region
   ../api_document/mario.Database.to_chenery_moses
   ../api_document/mario.Database.change_assumption


Scenario Operations
-------------------

.. toctree::
   :maxdepth: 1

   ../api_document/mario.Database.clone_scenario
   ../api_document/mario.Database.rename_scenario
   ../api_document/mario.Database.rename_baseline_scenario
   ../api_document/mario.Database.update_scenarios
   ../api_document/mario.Database.shock_calc
   ../api_document/mario.Database.reset_to_flows
   ../api_document/mario.Database.reset_to_coefficients
