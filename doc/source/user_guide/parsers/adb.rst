Asian Development Bank (ADB)
============================

MARIO supports local parsing of the Asian Development Bank (ADB) Input-Output tables
distributed on the official ADB website.

ADB currently provides ``IOT`` tables, but the parser works with both:

* ``Multi-Region Input-Output (MRIO)`` workbooks, typically one workbook per release year;
* ``Single-Region Input-Output (SRIO)`` workbooks, where one workbook contains multiple yearly sheets;
* optional ADB air-emissions workbooks imported through ``add_extensions=...``.


Relevant source links
---------------------

* `official ADB website <https://kidb.adb.org/globalization/current>`_
* `official ADB air-emissions extensions page <https://kidb.adb.org/globalization/adb_environmentally_extended_multiregional_inputoutput_tables>`_

Recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_adb(...) <../../api_document/mario.parse_adb>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  one ADB workbook or one directory containing multiple ADB workbooks;
* ``table``:
  optional, only ``"IOT"`` is available
* ``year``:
  use it when one directory contains more than one yearly MRIO release.
  For SRIO workbooks this is mandatory, because one file contains multiple
  yearly sheets
* ``economies``:
  ADB provdes different variants of MRIO tables, with 62, 71, 72 or 74 regions. 
  Use this argument when your path contains multiple workbook variants for the same
  year, for example ``62``, ``71``, ``72`` or ``74``
* ``add_extensions``:
  optional path to the ADB air-emissions workbook. When passed, MARIO imports
  the environmental extension matrix ``E`` and keeps ``EY`` zero-filled.
  Works for both MRIO and SRIO workbooks.

Expected path structure
-----------------------

``path`` can point either to one workbook or to a directory containing several
ADB workbooks.

For MRIO releases, a directory is typically organized by regional coverage:

.. code-block:: text

   ADB/
   ├── 62 economies/
   │   └── ADB-MRIO-2024_*.xlsx
   ├── 72 economies/
   │   └── ADB-MRIO72-2024_*.xlsx
   └── CO2/
       └── 2023 EE-MRIOT (Air Emissions).xlsx

For SRIO releases, ``path`` usually points to one country workbook:

.. code-block:: text

   ADB/SRIO/
   └── CAN IOT 2000, 2007-2024.xlsx

When ``path`` is a directory, use ``year=`` and, when needed, ``economies=``
to disambiguate the workbook. When parsing SRIO workbooks, ``year=`` is
required because one workbook contains multiple yearly sheets.


Notebook walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`ADB parser walkthrough <../../notebooks/parsers/adb/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the ADB notebook <../../notebooks/parsers/adb/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/parsers/adb/walkthrough


Caveats
-------

* The parser is local-file based: there is no automatic MARIO downloader
* ``economies=`` is useful to specify which file to target when your path
  contains more than one workbook variant for the same year
* For SRIO workbooks, ``year=`` is required
* When ``add_extensions`` is used, MARIO warns if the emissions workbook year
  does not match the economic table year
* When ``add_extensions`` is used, MARIO warns if the emissions workbook does
  not cover all regions present in the economic table (e.g. 2 countries in the
  74 economies variant are missing in the emissions workbook)
