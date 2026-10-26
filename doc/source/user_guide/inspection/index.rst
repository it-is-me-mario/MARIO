:summary: Explore a parsed model, retrieve its data and save your work.

Working with a database
=======================

Use these guides once you have imported a database. For the meaning of
regions, activities, commodities and sectors, see
:doc:`Table formats <../../get_started/table_formats>`.

For NAM, follow the dedicated sections in :doc:`basic_inspections`,
:doc:`compute_matrices` and :doc:`export_and_roundtrip`. Clusters,
classification concordances and source profiles below currently apply to
IOT/SUT. The :doc:`NAM database reference </reference/api_nam_database>` lists
the supported operations.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - I want to
     - Guide
   * - Find sets, scenarios, labels and matrix values
     - :doc:`Inspect and query a database <basic_inspections>`
   * - Find NACE, CPA, ISIC, CPC or HS codes for native items
     - :doc:`Classification concordances <concordances>`
   * - Save and reuse named groups of labels
     - :doc:`Work with clusters <clusters>`
   * - Save a model to Excel, CSV or Parquet
     - :doc:`Export a database <export_and_roundtrip>`

To create matrices that have not been calculated yet, continue to
:doc:`Calculations and analysis <../analysis/index>`.
For GHG definitions, compute preferences and available classifications for a
source, inspect its :doc:`database profile <../advanced/database_profiles>`.

.. toctree::
   :hidden:

   basic_inspections
   clusters
   concordances
   export_and_roundtrip
