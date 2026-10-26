Parsing and Data Loading
========================

These pages cover parser entry points, dataset-specific parsers, and related
loading helpers.

For NAM, use :func:`mario.parse_figaro` on local FIGARO source files, or
:func:`mario.parse_from_excel` on a MARIO native NAM workbook. These are
different layouts: a FIGARO T02 workbook is not a native MARIO export.
See :doc:`the FIGARO guide </notebooks/parsers/figaro/walkthrough_figaro>`
and :doc:`the NAM database interface <api_nam_database>`.

Import Parser Data Into an Existing Database
--------------------------------------------

These in-place parser workflows apply to IOT/SUT. For NAM, import a new
database, then clone a scenario and update native blocks as needed.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.Database.parse_scenario
   ../api_document/mario.Database.parse_exiobase
   ../api_document/mario.Database.parse_from_parquet


Top-Level Parser Entrypoints
----------------------------

.. toctree::
   :maxdepth: 1

   ../api_document/mario.load_test
   ../api_document/mario.parse_from_excel
   ../api_document/mario.parse_from_txt
   ../api_document/mario.parse_from_parquet
   ../api_document/mario.parse_from_pymrio
   ../api_document/mario.parse_exiobase
   ../api_document/mario.parse_bonsai
   ../api_document/mario.parse_figaro
   ../api_document/mario.parse_gloria
   ../api_document/mario.parse_gtap
   ../api_document/mario.parse_wiod
   ../api_document/mario.parse_oecd
   ../api_document/mario.parse_eora
   ../api_document/mario.parse_emerging
   ../api_document/mario.parse_ceads
   ../api_document/mario.parse_cepalstat
   ../api_document/mario.parse_bea
   ../api_document/mario.parse_adb
   ../api_document/mario.parse_useeio
   ../api_document/mario.parse_statcan
   ../api_document/mario.parse_istat
   ../api_document/mario.parse_eurostat


EXIOBASE-Specific Loaders
-------------------------

These public helpers load monetary IOT and SUT tables directly.
Use :doc:`mario.parse_exiobase <../api_document/mario.parse_exiobase>` to
select the table format and monetary or hybrid units through one entry point.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.parse_exiobase_3
   ../api_document/mario.parse_exiobase_sut
