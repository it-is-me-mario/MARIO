:page-type: Guide
:summary: Save model tables and current sets for inspection or a later MARIO session.

Export a database
=================

.. container:: mario-companion

   :download:`Download notebook <export_and_roundtrip.ipynb>`

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

Export the current sets
-----------------------

Use :meth:`db.export_sets() <mario.Database.export_sets>` to write the current
classifications separately from the matrices:

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("SUT")
      sets_path = db.export_sets(path="exports/sets.xlsx")

   .. container:: mario-result

      **Result** · One workbook with Activity, Commodity, Factor of production,
      Satellite account, Consumption category and Region sheets, plus Scenario.
      Each sheet has a column with the same MARIO set name and its current members.

Run the export after selecting regions, aggregating classifications or filtering
extensions so the lists describe the transformed database. IOT databases export
Sector instead of Activity and Commodity. Pass ``include_scenarios=False`` to
export only the sets listed by :attr:`db.sets <mario.CoreModel.sets>`.

When a classification differs between regions, its sheet contains ``Region``
and set-name columns with only the observed region/member pairs. Common sets
remain single-column lists. The method preserves MARIO names and label order;
it does not apply CVXLab mappings. The downloadable companion includes the same
call. Full arguments are in the :meth:`API reference <mario.Database.export_sets>`.

To populate a CVXLab model's set and input workbooks with its own names and
coordinates, follow :doc:`to_cvxlab`.

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
