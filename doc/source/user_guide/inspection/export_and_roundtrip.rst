:page-type: Guide
:summary: Save model tables for inspection or for a later MARIO session.

Export a database
=================

.. container:: mario-companion

   :download:`Run the notebook <export_and_roundtrip.ipynb>`

Choose a format by what you plan to do next.

.. mario-cards::
   :columns: 2

   .. mario-card:: Excel
      :icon: table-search

      Inspect and edit a workbook. Convenient for small tables and manual review.

   .. mario-card:: CSV or Parquet
      :icon: export

      Exchange tables with scripts. Flat layouts reduce the number of files
      and support parsing back into MARIO.

Save and reload
---------------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      db.to_parquet(path="iot_export", flows=True, flat=True)
      restored = mario.parse_from_parquet(
          path="iot_export", table="IOT", mode="flows", flat=True,
      )

   .. container:: mario-result

      **Result** · Exported flow and unit files, then a new database constructed
      from them. This exports model tables, rather than a Python session.

.. mario-details:: Excel export

   .. code-block:: python

      db.to_excel(path="iot_export.xlsx", flows=True, coefficients=True)

   See :doc:`the Excel parser <../../notebooks/parsers/custom_database/from_excel>`
   for the required blocks and import options.

.. mario-details:: CSV export

   .. code-block:: python

      db.to_txt(path="iot_export_csv", flows=True, _format="csv", flat=True)
      restored = mario.parse_from_txt(
          path="iot_export_csv", table="IOT", mode="flows",
          _format="csv", flat=True,
      )

   Keep the unit file with the data file. The :doc:`TXT, CSV and Parquet guide
   <../../notebooks/parsers/custom_database/from_txt>` explains flat and matrix layouts.
