:page-type: Guide
:summary: Save model tables for inspection or for a later MARIO session.

Export a database
=================

.. container:: mario-companion

   :download:`Download notebook <export_and_roundtrip.ipynb>`

Choose a format by what you plan to do next.

NAM currently uses its versioned native Excel format: ``nam.to_excel(...)``
followed by ``mario.parse_from_excel(..., table="NAM", mode="flows")``.
It preserves block states, native layouts and scenarios. The CSV/Parquet and
coefficient options below apply to IOT/SUT; see :doc:`the NAM workflow
</get_started/table_formats/nam>` for its template and supported operations.

.. code-block:: python

   # nam is an already parsed NAM database.
   import mario

   nam.to_excel("nam_native.xlsx")
   restored = mario.parse_from_excel("nam_native.xlsx", table="NAM", mode="flows")
   restored.resolve("cf_d")

Totals, coefficients, ``T`` and ``B9_d``/``B9_f`` are calculated outputs;
they are not additional workbook payments. Reload recomputes them from
available flows. Keep the workbook's registry and metadata sheets with its
values. The NAM format is distinct from FIGARO's source workbook and from
the IOT/SUT Excel layouts below. See :doc:`/reference/api_nam_database`.

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
