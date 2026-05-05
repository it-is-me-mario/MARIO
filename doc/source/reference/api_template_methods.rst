Templates and Workbooks
=======================

These methods create empty or helper workbooks that users fill before parsing,
aggregation, shocks, extensions or sector-addition workflows.
``Database.get_aggregation_excel(...)`` can also prefill the ``Region`` sheet
through ``region_aggregation`` when you want to combine automatic regional
grouping with manual edits on the other sets.

Custom Database Templates
-------------------------

.. toctree::
   :maxdepth: 1

   ../api_document/mario.write_template_definition
   ../api_document/mario.write_parse_template


Workflow Helper Workbooks
-------------------------

.. toctree::
   :maxdepth: 1

   ../api_document/mario.Database.get_aggregation_excel
   ../api_document/mario.Database.get_extensions_excel
   ../api_document/mario.Database.get_add_sectors_excel
   ../api_document/mario.Database.get_shock_excel
