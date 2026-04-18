ADB
===

MARIO supports local parsing of the Asian Development Bank Excel workbooks
distributed on the official ADB globalization page.

Relevant source links
---------------------

* official ADB MRIO and SRIO page:
  `ADB globalization portal <https://kidb.adb.org/globalization/current>`_.
* official ADB air-emissions extensions page:
  `ADB environmentally extended MRIOT <https://kidb.adb.org/globalization/adb_environmentally_extended_multiregional_inputoutput_tables>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_adb(...) <../api_document/mario.parse_adb>`

The parser currently supports only ``IOT`` tables, but it works with both:

* ADB ``MRIO`` workbooks, typically one workbook per release year;
* ADB ``SRIO`` workbooks, where one workbook contains multiple yearly sheets.

Key arguments
-------------

The key public arguments are:

* ``path``:
  one ADB workbook or one directory containing multiple ADB workbooks;
* ``table``:
  currently only ``"IOT"`` is supported;
* ``year``:
  use it when one directory contains more than one yearly MRIO release.
  For SRIO workbooks this is mandatory, because one file contains multiple
  yearly sheets;
* ``economies``:
  use it when one directory contains multiple workbook variants for the same
  year, for example ``62``, ``72`` or ``74``;
* ``add_extensions``:
  optional path to the ADB air-emissions workbook. When passed, MARIO imports
  the environmental extension matrix ``E`` and keeps ``EY`` zero-filled.

Download workflow
-----------------

Automatic ADB download is intentionally not supported.

In practice, the workflow is:

1. download the desired ADB economic workbook manually from the official page;
2. optionally download the matching ADB air-emissions workbook;
3. keep the ``.xlsx`` files locally, or place several ADB workbooks in one
   directory;
4. pass the economic workbook to ``mario.parse_adb(...)``, optionally with
   ``add_extensions=...``.

Local layout expectation
------------------------

MARIO expects either:

* one local ADB ``MRIO`` ``.xlsx`` workbook;
* one local ADB ``SRIO`` ``.xlsx`` workbook;
* or one directory containing one or more ADB workbooks.

When a directory contains multiple MRIO candidates, use ``year=`` and/or
``economies=`` to disambiguate the target workbook. For SRIO workbooks,
``year=`` selects the annual sheet inside the workbook.

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
   )

Parse from a directory containing multiple releases:

.. code-block:: python

   db = mario.parse_adb(
       path="/path/to/adb_directory",
       year=2024,
       economies=74,
   )

Parse one SRIO workbook. Here ``year=`` is mandatory because the workbook
contains one sheet per year:

.. code-block:: python

   db = mario.parse_adb(
       path="/path/to/CAN IOT 2000, 2007-2024.xlsx",
       year=2024,
   )

Import the matching ADB air-emissions extensions:

.. code-block:: python

   db = mario.parse_adb(
       path="/path/to/ADB_MRIO_2024_74.xlsx",
       add_extensions="/path/to/2024 EE-MRIOT (Air Emissions).xlsx",
   )

The same ``add_extensions=...`` argument also works for SRIO workbooks:

.. code-block:: python

   db = mario.parse_adb(
       path="/path/to/CAN IOT 2000, 2007-2024.xlsx",
       year=2024,
       add_extensions="/path/to/2024 EE-MRIOT (Air Emissions).xlsx",
   )

Inspect the parsed database:

.. code-block:: python

   db

Caveats
-------

* ADB parsing currently supports only ``IOT`` tables;
* the parser is local-file based; there is no automatic MARIO downloader;
* ``economies=`` is useful only when a directory contains more than one
  workbook variant for the same year;
* for SRIO workbooks, ``year=`` is required;
* when ``add_extensions`` is used, MARIO warns if the emissions workbook year
  does not match the economic table year;
* when ``add_extensions`` is used, MARIO warns if the emissions workbook does
  not cover all regions present in the economic table.
