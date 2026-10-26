:page-type: Database guide
:summary: Read model flows or coefficients from a MARIO-layout workbook.

Excel tables
============

.. container:: mario-companion

   :download:`Download notebook <from_excel.ipynb>`

Prepare tables, labels and units in the expected layout. Use the custom-table template guide when starting from scratch.

Choose the reader for the workbook you have. The IOT/SUT examples below use
MARIO table layouts. A MARIO native NAM workbook uses a separate registry-based
layout; a FIGARO source workbook must go through :func:`mario.parse_figaro`.
Set inventories on this page describe the packaged IOT/SUT examples.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_from_excel(path="custom_iot.xlsx", table="IOT", mode="flows")

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Native NAM workbooks
--------------------

Read a workbook produced by ``nam.to_excel`` or
:func:`mario.write_parse_template` with ``table="NAM"``:

.. code-block:: python

   nam = mario.parse_from_excel("nam_native.xlsx", table="NAM", mode="flows")
   nam.get_index("all")
   nam.units

NAM reads its embedded ``metadata``, ``accounts``, ``descriptors``,
``matrix_layouts`` and ``flows`` sheets. It retains every scenario and each
block's observed, declared-zero or unavailable state. Derived coefficients
can be requested after loading; they are not workbook inputs.
``data_sheet``, ``unit_sheet`` and layout overrides belong to the IOT/SUT
workflows; NAM uses the native sheets and embedded layouts. ``mode="flows"``
is required and no SUT technology assumption applies.

The native contract requires version 2. Reparse the original source or create
a new template for an older workbook; it is not silently reclassified. See
:doc:`Import your own tables </user_guide/parsers/provide_your_database>`
and the :doc:`NAM database reference </reference/api_nam_database>`.

Inputs and options
------------------

The following options describe IOT/SUT workbook layouts.

.. mario-details:: Example workbooks

   The examples use these packaged workbooks:

   - ``test_IOT_standard.xlsx``: standard IOT layout;
   - ``test_IOT_special.xlsx``: IOT layout with extra semantic levels on ``V`` and ``E``;
   - ``test_SUT_standard.xlsx``: standard SUT layout;
   - ``test_SUT_special.xlsx``: SUT layout with extra semantic levels on satellite extensions.

   The code below uses paths relative to this notebook source location in the MARIO repository. If you run the notebook elsewhere, replace the path strings with the location of your local Excel files.

.. mario-details:: Main entry point and key arguments

   Use ``mario.parse_from_excel(...)`` when ``path`` points to one completed MARIO-readable workbook.

   Key arguments:

   - ``path``: workbook to parse;
   - ``table``: choose ``"IOT"`` or ``"SUT"``;
   - ``mode``: choose ``"flows"`` or ``"coefficients"``;
   - ``data_sheet``: optional sheet selector for the table payload;
   - ``unit_sheet``: optional sheet selector for the units sheet;
   - ``matrix_layouts``: optional semantic declaration for non-standard matrix layouts;
   - ``tech_assumption``: optional ``SUT`` selector for ``IT`` or ``PT``.

.. mario-details:: Workbook structure and packaged examples

   ``path`` must point to one Excel workbook.

   .. code:: text

      custom_database.xlsx
      ├── data sheet
      └── units sheet

   The data sheet can use the canonical MARIO matrix layout exported by MARIO or a flat template generated with ``mario.write_parse_template(...)``. The units sheet must contain the units for the labels used by sectors, activities, commodities, factors, final demand, and satellites.

   Packaged example workbooks used in this notebook:

   - `test_IOT_standard.xlsx <../../../_static/data/test_tables/test_IOT_standard.xlsx>`__
   - `test_IOT_special.xlsx <../../../_static/data/test_tables/test_IOT_special.xlsx>`__
   - `test_SUT_standard.xlsx <../../../_static/data/test_tables/test_SUT_standard.xlsx>`__
   - `test_SUT_special.xlsx <../../../_static/data/test_tables/test_SUT_special.xlsx>`__

.. mario-details:: Standard and special layouts

   In the standard workbook layout, the table uses three index levels on both rows and columns: region, level name, and level label. Use ``mode="flows"`` or ``mode="coefficients"`` to tell MARIO how to interpret the numbers.

   For non-standard layouts, use ``matrix_layouts=`` to declare extra semantic layers, especially on ``V`` and ``E``. ``VY`` and ``EY`` inherit the same extra layout as ``V`` and ``E``, so you do not declare them separately.

   .. code:: python

      import mario

.. mario-details:: Parse a standard IOT workbook

   For a standard IOT workbook, only the file path, table kind and mode are required.

   .. code:: python

      iot = mario.parse_from_excel(
          path="/path/to/test_IOT_standard.xlsx",
          table="IOT",
          mode="flows",
      )

   .. code:: python

      iot.meta.table

   .. code:: python

      iot.get_index("Region")

   .. code:: python

      iot.get_index("Sector")

   .. code:: python

      iot.V

.. mario-details:: Parse an IOT workbook with custom matrix layouts

   Use ``matrix_layouts`` when specific matrices carry extra semantic levels beyond the default layout. In this example, ``V`` is indexed by region and sector, while ``E`` is indexed by region.

   .. code:: python

      iot_special = mario.parse_from_excel(
          path="/path/to/test_IOT_special.xlsx",
          table="IOT",
          mode="flows",
          matrix_layouts={
              "V": ("Region", "Sector"),
              "E": "Region",
          },
      )

   .. code:: python

      iot_special.V

.. mario-details:: Parse a standard SUT workbook

   For SUT workbooks, pass the table kind as ``"SUT"``. You can also pass ``tech_assumption=`` when you want MARIO to record the technology assumption used downstream.

   .. code:: python

      sut = mario.parse_from_excel(
          path="/path/to/test_SUT_standard.xlsx",
          table="SUT",
          mode="flows",
          tech_assumption="IT",
      )

   .. code:: python

      sut.meta.table

   .. code:: python

      sorted(sut["baseline"].keys())

   .. code:: python

      sut.E

.. mario-details:: Parse a SUT workbook with custom matrix layouts

   The same ``matrix_layouts`` mechanism applies to SUT workbooks. Here, the satellite-account matrices are declared with region and commodity detail.

   .. code:: python

      sut_special = mario.parse_from_excel(
          path="/path/to/test_SUT_special.xlsx",
          table="SUT",
          mode="flows",
          tech_assumption="IT",
          matrix_layouts={
              "E": ("Region", "Commodity"),
          },
      )

   .. code:: python

      sut_special.E

.. mario-details:: Practical notes

   - ``mode="flows"`` reads flow matrices; use ``mode="coefficients"`` only for coefficient workbooks.
   - ``matrix_layouts`` must use MARIO semantic index names, such as ``Region``, ``Sector``, ``Activity``, ``Commodity``, ``Factor of production``, ``Final demand``, and ``Satellite account``.
   - Fully empty matrices are accepted and filled with zeros; partially empty matrices are treated as invalid input.

.. mario-details:: Layout notes and caveats

   An IOT/SUT workbook has at least a data sheet and a units sheet.

   In the standard layout, rows and columns use three index levels: region, level name, and level label. The units sheet lists the units for sectors or activities or commodities, factors of production, and satellite accounts used by the workbook. If the sheet names are not the defaults, use ``data_sheet=`` and ``unit_sheet=`` explicitly.

   For non-standard layouts, ``matrix_layouts=`` declares the extra semantic levels carried by matrices such as ``V`` and ``E``. When extra levels are defined for ``V`` or ``E``, MARIO applies the same logic to ``VY`` and ``EY``, so they do not need separate declarations.

   Practical caveats:

   - Excel is usually the easiest custom entry point, but it is not the best format for large roundtrip workflows.
   - ``mode=`` is never inferred automatically: choose ``"flows"`` or ``"coefficients"`` explicitly.
   - When you define extra indices for ``E`` or ``V``, provide the complete label set under those indices, not only the labels visible in one sub-block.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
