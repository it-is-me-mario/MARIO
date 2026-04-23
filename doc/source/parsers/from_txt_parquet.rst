From TXT, CSV, and Parquet
==========================

MARIO supports custom parsing from TXT, CSV, and Parquet files.
These files are preferable for large datasets and are usually produced by a
MARIO export operation rather than assembled manually.

Recommended entry points
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
  use ``True`` if the database is in long format
* ``matrix_layouts``:
  optional per-matrix semantic declarations for non-standard IOT layouts. Check the guide on special layouts :ref:`here <special_layout>` for more details
* ``tech_assumption``:
  optional SUT-only selector for ``IT`` / ``PT`` behaviour

Flat and matrix layouts
-----------------------

Both parsing methods support:

* matrix-per-file payloads;
* flat long-format payloads.

Use ``flat=True`` for long-format payloads.

When parsing from TXT/CSV, MARIO accepts either:

* one combined ``data`` file plus one ``units`` file;
* or one ``units`` file plus separate flat files per matrix.

The same logic also applies to flat Parquet payloads.

Notebook walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`TXT, CSV and Parquet parser walkthrough <../notebooks/parsers/custom_database/from_txt>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the TXT and Parquet notebook <../notebooks/parsers/custom_database/from_txt.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/custom_database/from_txt

Caveats
-------

* ``path`` must always point to a directory, not to one single file.
* ``flat=True`` is required for long-format payloads.
* ``_format`` matters only for TXT/CSV parsing, not for Parquet parsing.
