:page-type: Database guide
:summary: Read matrix files or a flat table together with their units.

TXT, CSV and Parquet
====================

.. container:: mario-companion

   :download:`Download notebook <from_txt.ipynb>`

Match flat and matrix layouts to the export you have. Keep the units file with the data; choose flows or coefficients explicitly.

This custom-file reader supports IOT/SUT. For FIGARO's published NAM CSV,
use :func:`mario.parse_figaro` with ``table="NAM"`` and an explicit country;
see :doc:`the FIGARO guide <../figaro/walkthrough_figaro>`. MARIO native NAM
round trips use :doc:`Excel <from_excel>`.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_from_txt(
          path="iot_export_csv", table="IOT", mode="flows", _format="csv", flat=True,
      )

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Key arguments and directory layout

   Use ``mario.parse_from_txt(...)`` for TXT or CSV payloads and ``mario.parse_from_parquet(...)`` for Parquet payloads.

   Key arguments:

   - ``path``: directory containing the files to parse;
   - ``table``: choose ``"IOT"`` or ``"SUT"``;
   - ``mode``: choose ``"flows"`` or ``"coefficients"``;
   - ``flat``: set ``True`` for long-format payloads;
   - ``sep`` and ``_format``: TXT or CSV only;
   - ``matrix_layouts``: optional semantic declaration for non-standard matrix layouts;
   - ``tech_assumption``: optional ``SUT`` selector for ``IT`` or ``PT``.

   Matrix-per-file payloads look like:

   .. code:: text

      custom_txt_database/
      ├── Z.csv
      ├── Y.csv
      ├── V.csv
      ├── E.csv
      ├── EY.csv
      └── units.csv

   Flat payloads can use one combined ``data`` file plus ``units``, or one flat file per matrix plus ``units``. The same directory logic applies to Parquet.

.. mario-details:: Packaged example directories

   The parser examples below use exported database folders bundled with the documentation:

   - `CSV export archive <../../../_static/data/supporting_files/iot_export_csv.zip>`__
   - `Parquet export archive <../../../_static/data/supporting_files/iot_export_parquet.zip>`__

   Extract each archive locally and point ``path`` to the inner ``flows`` or ``coefficients`` directory shown in the code examples below.

   .. code:: python

      import mario

.. mario-details:: Matrix-per-file TXT or CSV

   Use ``flat=False`` for the historical matrix-per-file layout.

   .. code:: python

      db = mario.parse_from_txt(
          path="/path/to/iot_export_csv/flows",
          table="IOT",
          mode="flows",
          _format="csv",
          flat=False,
      )

.. mario-details:: Flat TXT or CSV

   Use ``flat=True`` for long-format payloads. MARIO accepts either one combined ``data`` file or separate flat files per matrix, as long as ``units`` is present.

   .. code:: python

      db = mario.parse_from_txt(
          path="/path/to/iot_export_csv",
          table="IOT",
          mode="coefficients",
          _format="csv",
          flat=True,
      )

.. mario-details:: Flat Parquet

   The same logic applies to Parquet exports.

   .. code:: python

      db = mario.parse_from_parquet(
          path="/path/to/iot_export_parquet",
          table="IOT",
          mode="flows",
          flat=True,
      )

.. mario-details:: Reference notes and caveats

   These parsers are directory-based. ``path`` must point to one directory, not to one individual file.

   Use ``flat=True`` for long-format payloads. For TXT or CSV parsing, ``_format`` and ``sep`` matter; for Parquet parsing they do not.

   The same semantic rules used for custom Excel parsing also apply here: if one IOT layout carries extra semantic levels, declare them through ``matrix_layouts=`` instead of relying on filename conventions alone.

   These formats are usually preferable to Excel when the data already comes from a MARIO export or from an automated preprocessing workflow.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
