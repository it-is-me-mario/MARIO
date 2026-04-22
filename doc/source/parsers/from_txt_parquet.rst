From TXT, CSV and PARQUET
=========================

MARIO supports custom parsing from TXT, CSV and PARQUET files.
These files are preferable for large datasets and are not usually generated manually, but they are generally produced by a MARIO export operation.


Recommended Entry Points
------------------------

For normal user workflows, the public entry points are:

* :doc:`mario.parse_from_txt(...) <../api_document/mario.parse_from_txt>`
* :doc:`mario.parse_from_parquet(...) <../api_document/mario.parse_from_parquet>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  **directory** containing the files to parse
* ``table``:
  choose ``"IOT"`` or ``"SUT"``
* ``mode``:
  choose ``"flows"`` or ``"coefficients"``
* ``sep``:
  field separator for the text files (not required in ``mario.parse_from_parquet``)
* ``_format``:
  format of the files to parse, choose between ``"txt"``, ``"csv"`` (not required in ``mario.parse_from_parquet``)
* ``flat``:
  use ``True`` for if the database is in long-format
* ``matrix_layouts``:
  optional per-matrix semantic declarations for non-standard IOT layouts. Check the guide on special layouts :ref:`here <special_layout>` for more details
* ``tech_assumption``:
  optional SUT-only selector for ``IT`` / ``PT`` behaviour



Recommended usage
-----------------

These parsing methods supports both flat and "matricial" data shapes:
Use ``flat=True`` in the second case.

Parse from TXT/CSV:

.. code-block:: python

   import mario

   db = mario.parse_from_txt(
       path="/path/to/txt_directory",  # must be a directory, not a single file
       table="IOT",           # or "SUT"
       mode="flows",
       _format="txt",         # or "csv". "txt" is the default
       flat = False,          # set to True if the data is in long format. False is the default,
       matrix_layouts = None, # or specify the desired extra indices for E and V matrices. None is default
   )

Parse from PARQUET:

.. code-block:: python

   import mario

   db = mario.parse_from_parquet(
       path="/path/to/parquet_directory",  # must be a directory, not a single file
       table="IOT",  # or "SUT"
       mode="flows",
       flat = False,  # set to True if the data is in long format. False is the default
       matrix_layouts = None, # or specify the desired extra indices for E and V matrices. None is default
   )

