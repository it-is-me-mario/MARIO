Built-in Parsers
================

MARIO exposes two parser families.

Generic parsers
---------------

These are used when your data is already close to MARIO's internal block model:

* ``parse_from_excel(...)``
* ``parse_from_txt(...)``
* ``parse_from_parquet(...)``
* ``parse_from_pymrio(...)``

Source-specific parsers
-----------------------

These are used when MARIO already knows how to import a specific data source:

* Eurostat
* FIGARO
* EXIOBASE
* EORA
* OECD ICIO
* WIOD
* ADB
* GTAP
* GLORIA
* ISTAT
* StatCan
* EMERGING

If you need to add a new source, the main developer entry point is described in
:doc:`../contribute/parser_development`.
