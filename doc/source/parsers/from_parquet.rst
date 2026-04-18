From Parquet
============

MARIO supports custom parsing from one directory of parquet files.

This is the preferred custom format when the payload is large, when you want a
more robust binary representation than TXT, or when you are roundtripping
canonical MARIO exports programmatically.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_from_parquet(...) <../api_document/mario.parse_from_parquet>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  directory containing the parquet files to parse;
* ``table``:
  choose ``"IOT"`` or ``"SUT"``;
* ``mode``:
  choose ``"flows"`` or ``"coefficients"``;
* ``flat``:
  use ``True`` for the canonical long-format MARIO parquet export;
* ``matrix_layouts``:
  optional per-matrix semantic declarations for non-standard IOT layouts;
* ``tech_assumption``:
  optional SUT-only selector for ``IT`` / ``PT`` behavior.

Supported layouts
-----------------

Parquet parsing supports the same two families as TXT:

* one parquet file per matrix;
* one flat ``data.parquet`` plus one ``units.parquet`` payload.

Use ``flat=True`` only for the flat long-format export.

Typical usage
-------------

Parse a matrix-per-file custom IOT:

.. code-block:: python

   import mario

   db = mario.parse_from_parquet(
       path="/path/to/parquet_directory",
       table="IOT",
       mode="flows",
   )

Parse a flat custom SUT export:

.. code-block:: python

   import mario

   db = mario.parse_from_parquet(
       path="/path/to/flat_parquet_directory",
       table="SUT",
       mode="coefficients",
       flat=True,
   )

Caveats
-------

* the parser still expects MARIO semantics; Parquet changes the storage format,
  not the structural model;
* ``flat=True`` should be used only for canonical MARIO flat exports;
* this is usually the strongest option for large custom databases and scripted
  roundtrip workflows.
