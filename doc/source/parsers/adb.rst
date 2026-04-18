ADB
===

MARIO supports local parsing of the Asian Development Bank Excel workbooks
distributed on the official ADB globalization page.

The parser currently supports only ``IOT`` tables, but it works with both:

* ADB ``MRIO`` workbooks, typically one workbook per release year;
* ADB ``SRIO`` workbooks, where one workbook contains multiple yearly sheets;
* optional ADB air-emissions workbooks imported through ``add_extensions=...``.

For this source, the most useful documentation format is a notebook-driven one:
this landing page stays short, while one practical notebook covers direct-file
parsing, directory parsing, ``economies=``, ``add_extensions=``, parser
warnings, and the difference between ``MRIO`` and ``SRIO`` workflows.

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

Typical usage
-------------

Direct path to one MRIO workbook:

.. code-block:: python

   import mario

   db = mario.parse_adb(
       path="/path/to/ADB_MRIO_2024_74.xlsx",
   )

Directory containing multiple MRIO releases:

.. code-block:: python

   import mario

   db = mario.parse_adb(
       path="/path/to/adb_directory",
       year=2024,
       economies=74,
   )

One SRIO workbook with annual sheets:

.. code-block:: python

   import mario

   db = mario.parse_adb(
       path="/path/to/CAN IOT 2000, 2007-2024.xlsx",
       year=2024,
   )

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

Notebook Walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`ADB parser walkthrough <../notebooks/parsers/adb/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the ADB notebook <../notebooks/parsers/adb/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/adb/walkthrough
