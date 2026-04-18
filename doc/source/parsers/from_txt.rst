From TXT
========

MARIO supports custom parsing from one directory of text files.

Use this parser when the database already lives as plain-text files on disk, or
when you want to roundtrip one flat MARIO export without going through Excel.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_from_txt(...) <../api_document/mario.parse_from_txt>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  directory containing the files to parse;
* ``table``:
  choose ``"IOT"`` or ``"SUT"``;
* ``mode``:
  choose ``"flows"`` or ``"coefficients"``;
* ``sep``:
  field separator for the text files;
* ``flat``:
  use ``True`` for the canonical long-format MARIO export;
* ``matrix_layouts``:
  optional per-matrix semantic declarations for non-standard IOT layouts;
* ``tech_assumption``:
  optional SUT-only selector for ``IT`` / ``PT`` behavior.

Supported layouts
-----------------

TXT parsing supports two distinct layouts:

* one file per matrix;
* one flat ``data`` file plus one flat ``units`` file.

Use ``flat=True`` only for the second case.

Typical usage
-------------

Parse a matrix-per-file custom IOT:

.. code-block:: python

   import mario

   db = mario.parse_from_txt(
       path="/path/to/txt_directory",
       table="IOT",
       mode="flows",
   )

Parse a flat custom SUT export:

.. code-block:: python

   import mario

   db = mario.parse_from_txt(
       path="/path/to/flat_txt_directory",
       table="SUT",
       mode="coefficients",
       flat=True,
   )

Caveats
-------

* use ``flat=True`` only for canonical MARIO flat exports;
* the matrix-per-file workflow still expects MARIO matrix names and canonical
  labels, not arbitrary filenames;
* TXT is easy to inspect, but it is less robust than Parquet for large payloads
  and repeated roundtrip operations.
