ADB
===

MARIO supports local parsing of the Asian Development Bank MRIO Excel
workbooks distributed on the official ADB globalization page.

Relevant source links
---------------------

* official ADB MRIO page:
  `ADB globalization portal <https://kidb.adb.org/globalization/current>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_adb(...) <../api_document/mario.parse_adb>`

The current backend supports only the ADB MRIO ``IOT`` workflow.

Key arguments
-------------

The key public arguments are:

* ``path``:
  one workbook or one directory containing multiple ADB workbooks;
* ``table``:
  currently only ``"IOT"`` is supported;
* ``year``:
  use it when one directory contains more than one yearly release;
* ``economies``:
  use it when one directory contains multiple workbook variants for the same
  year, for example ``62``, ``72`` or ``74``.

Download workflow
-----------------

Automatic ADB download is intentionally not supported.

In practice, the workflow is:

1. download the desired ADB MRIO workbook manually from the official page;
2. keep the ``.xlsx`` workbook locally, or place several ADB workbooks in one
   directory;
3. pass that file or directory to ``mario.parse_adb(...)``.

Local layout expectation
------------------------

MARIO expects either:

* one local ADB MRIO ``.xlsx`` workbook;
* or one directory containing one or more ADB MRIO workbooks.

When a directory contains multiple candidates, use ``year=`` and/or
``economies=`` to disambiguate the target workbook.

Tutorial
--------

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the ADB notebook <../notebooks/parsers/adb/tutorial.ipynb>`

Load MARIO first:

.. code-block:: python

   import mario

Parse one explicit workbook:

.. code-block:: python

   db = mario.parse_adb(
       path="/path/to/ADB_MRIO_2024_74.xlsx",
       table="IOT",
   )

Parse from a directory containing multiple releases:

.. code-block:: python

   db = mario.parse_adb(
       path="/path/to/adb_directory",
       table="IOT",
       year=2024,
       economies=74,
   )

Inspect the parsed database:

.. code-block:: python

   db

Caveats
-------

* ADB parsing currently supports only ``IOT`` tables;
* the parser is local-file based; there is no automatic MARIO downloader;
* ``economies=`` is useful only when a directory contains more than one
  workbook variant for the same year.
