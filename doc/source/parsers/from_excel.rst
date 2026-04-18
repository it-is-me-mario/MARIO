From Excel
==========

MARIO supports custom parsing from one Excel workbook when the database is
already organized close to MARIO's canonical matrix structure.

This is usually the easiest entry point when you are assembling a custom
database manually or when you want one human-readable file containing both data
and units.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_from_excel(...) <../api_document/mario.parse_from_excel>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  path to the workbook to parse;
* ``table``:
  choose ``"IOT"`` or ``"SUT"``;
* ``mode``:
  choose ``"flows"`` or ``"coefficients"``;
* ``data_sheet``:
  optional selector when the matrix payload is not in the first sheet;
* ``unit_sheet``:
  optional selector when the units sheet is not called ``units``;
* ``matrix_layouts``:
  optional per-matrix semantic declarations for non-standard IOT layouts;
* ``tech_assumption``:
  optional SUT-only selector for ``IT`` / ``PT`` behavior.

Expected workbook layout
------------------------

``parse_from_excel(...)`` expects:

* one data sheet containing the MARIO matrices;
* one units sheet.

The workbook is not a generic spreadsheet importer. It expects matrices and
index labels to follow MARIO's canonical structure.

Typical usage
-------------

Parse one custom IOT workbook:

.. code-block:: python

   import mario

   db = mario.parse_from_excel(
       path="/path/to/custom_iot.xlsx",
       table="IOT",
       mode="flows",
   )

Parse one custom SUT workbook:

.. code-block:: python

   import mario

   db = mario.parse_from_excel(
       path="/path/to/custom_sut.xlsx",
       table="SUT",
       mode="flows",
       tech_assumption="PT",
   )

Scaffold a valid starting workbook from MARIO itself:

.. code-block:: python

   import mario

   mario.load_test("IOT").to_excel("test_iot.xlsx")
   mario.load_test("SUT").to_excel("test_sut.xlsx")

Caveats
-------

* this parser does not infer ``flows`` versus ``coefficients`` automatically;
* ``matrix_layouts`` should be used only when your IOT matrices are valid but
  not in the default semantic layout;
* Excel is usually the simplest way to start, but it is not the most robust
  format for large roundtrip workflows.
