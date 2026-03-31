How to Parse Data
=================

The main parsing entry points are:

* ``parse_from_excel(...)``
* ``parse_from_txt(...)``
* ``parse_from_parquet(...)``
* source-specific parsers such as ``parse_eurostat(...)`` or ``parse_exiobase(...)``

Choose the right path
---------------------

If you already have a MARIO-shaped workbook
   Use ``parse_from_excel(...)``.

If you have canonical flat files
   Use ``parse_from_txt(...)`` or ``parse_from_parquet(...)``.

If you are importing a supported external dataset
   Use the source-specific parser exposed by ``mario``.

If you are working with richer layouts
   Use ``matrix_layouts`` to declare how ``V`` and ``E`` are structured.

Related pages
-------------

* :doc:`../tutorials/parsing`
* :doc:`../concepts/parser_model`
* :doc:`../concepts/matrix_layouts`
* :doc:`../reference/parsers`
