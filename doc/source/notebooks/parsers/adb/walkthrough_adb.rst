:page-type: Database guide
:summary: Import an ADB multi-regional or national input-output workbook.

ADB
===

.. container:: mario-companion

   :download:`Download notebook <walkthrough_adb.ipynb>`

Choose a workbook with the intended economy coverage and year. Air-emission accounts are imported separately.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_adb(path="/path/to/ADB-MRIO.xlsx")

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Relevant source pages

   - Official ADB MRIO and SRIO page: `ADB globalization portal <https://kidb.adb.org/globalization/current>`__
   - Official ADB air-emissions extensions page: `ADB environmentally extended MRIOT <https://kidb.adb.org/globalization/adb_environmentally_extended_multiregional_inputoutput_tables>`__

   MARIO does not download ADB workbooks automatically. The expected workflow is to download the ``.xlsx`` files manually from those pages and then point the parser to the local files.

.. mario-details:: Key arguments

   The key public arguments are:

   - ``path``: one ADB workbook or one directory containing multiple workbooks
   - ``table``: currently only ``"IOT"`` is supported
   - ``year``: used to disambiguate MRIO releases in one directory; mandatory for SRIO workbooks because one file contains multiple yearly sheets
   - ``economies``: used when a directory contains multiple MRIO variants for the same year, such as ``62``, ``72``, or ``74`` economies
   - ``add_extensions``: optional path to the ADB air-emissions workbook; this imports industry emissions into ``E`` and direct final-demand emissions into ``EY``

.. mario-details:: Direct file path vs directory path

   Use a **direct workbook path** when you already know the exact file to parse. This is the simplest path and usually means you do not need ``year=`` or ``economies=``.

   Use a **directory path** when you keep several ADB workbooks together. In that case MARIO scans the directory, finds the candidate workbook files, and then uses ``year=`` and optionally ``economies=`` to pick the correct one.

.. mario-details:: Expected local layout and caveats

   Typical MRIO directory layout:

   .. code:: text

      ADB/
      ├── 62 economies/
      │   └── ADB-MRIO-2024_*.xlsx
      ├── 72 economies/
      │   └── ADB-MRIO72-2024_*.xlsx
      └── Air emissions/
          └── 2023 EE-MRIOT (Air Emissions).xlsx

   Typical SRIO workbook layout:

   .. code:: text

      ADB/SRIO/
      └── CAN IOT 2000, 2007-2024.xlsx

   When ``path`` is a directory, use ``year=`` and, when needed, ``economies=`` to disambiguate the workbook. For SRIO workbooks, ``year=`` is mandatory because one file contains multiple yearly sheets. When ``add_extensions=`` is used, MARIO warns if the emissions workbook year or regional coverage does not match the economic table.

   Version labels count individual economies. Native MARIO region counts also include aggregates: 62 economies have 63 regions (including RoW); 71 have 73 (including RoLAC and RoW); 72 have 73; 74 have 75. Local years are 2000 and 2007–2024 for 62, 2007/2011/2017 for 71, 2017–2024 for 72, and 2024 for 74. Every reading has 35 industries.

   .. code:: python

      import mario

.. mario-details:: Parse one explicit MRIO workbook

   Use this when you want to point MARIO to one specific ADB MRIO workbook on disk.

   .. code:: python

      db_mrio = mario.parse_adb(
          path="/path/to/ADB-MRIO-2024-August 2025.xlsx",
      )

.. mario-details:: Parse from a directory containing multiple MRIO releases

   This is the important case when one directory contains several ADB MRIO files. Typical examples are:

   - multiple years in the same folder;
   - multiple release variants for the same year, such as ``62``, ``72``, or ``74`` economies.

   In those cases, ``year=`` narrows the release year and ``economies=`` narrows the workbook variant.

   .. code:: python

      db_mrio = mario.parse_adb(
          path="/path/to/ADB",
          year=2024,
          economies=74,
      )

   If the directory contains only one MRIO workbook for the requested year, ``year=`` may be enough on its own.

   .. code:: python

      db_mrio = mario.parse_adb(
          path="/path/to/ADB",
          year=2023,
          economies=72,
      )

.. mario-details:: Parse one SRIO workbook

   ADB SRIO workbooks differ from MRIO workbooks in one key way: **one file contains multiple yearly sheets**. Because of that, ``year=`` is mandatory for SRIO parsing.

   From the user side, the parser call stays simple: you still use ``mario.parse_adb(...)``, but now ``year=`` selects the annual sheet inside the workbook.

   .. code:: python

      db_srio = mario.parse_adb(
          path="/path/to/ITA IOT 2000, 2007-2024.xlsx",
          year=2024,
      )

.. mario-details:: Add the ADB air-emissions extensions

   Use an environmental workbook from the **same year**. The local extensions cover 2017–2023 and use the 72-economy geography plus RoW. MARIO imports both industry accounts (``E``) and direct final-demand accounts (``EY``).

   They match the 72-economy MRIOTs directly. For 62 economies, MARIO sums the ten additional individual economies into the larger RoW, conserving the global industry and final-demand totals. The available extension cannot disaggregate the additional Latin American regions of the 71-economy version. No 2024 emissions workbook is available in this collection.

   The source already expresses CO₂, CH₄, N₂O and fluorinated gases in **Gg CO₂eq using AR5 GWP100**. ``GHG | Total by substance`` is the published total; applying GWP again or summing it with its component rows would double-count. ``db_mrio_ext.calc_ghg()`` uses this total directly.

   .. code:: python

      db_mrio_ext = mario.parse_adb(
          path="/path/to/72 economies/ADB-MRIO72-2023_July 2025.xlsx",
          add_extensions="/path/to/2023 EE-MRIOT (Air Emissions).xlsx",
      )

   .. code:: python

      db_mrio_ext

   .. code:: python

      db_srio_ext = mario.parse_adb(
          path="/path/to/ITA IOT 2000, 2007-2024.xlsx",
          year=2023,
          add_extensions="/path/to/2023 EE-MRIOT (Air Emissions).xlsx",
      )

.. mario-details:: Parser warnings you may see

   When ``add_extensions=`` is used, MARIO can record parser warnings in the metadata history. The two relevant cases are:

   - the emissions workbook year does not match the economic table year;
   - the emissions workbook does not cover all regions present in the economic table.

   The second case matters mainly for MRIO releases where the economic table contains regions not present in the emissions workbook. The parse still succeeds, but MARIO records the mismatch.

   When a smaller global MRIO coverage is a subset of the extension, the metadata also records which economies were aggregated into its RoW. Missing-region warnings describe incomplete accounts; do not interpret their zero-filled cells as observed zero emissions.

   A simple way to inspect those parser notes is to check the metadata history after parsing:

   .. code:: python

      db_mrio_ext.meta_history

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
