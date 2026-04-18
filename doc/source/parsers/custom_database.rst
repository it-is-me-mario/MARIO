Custom Parsers
==============

This group covers user-provided databases and bridges from generic external
formats into MARIO's canonical database structure.

Use these parsers when you already have the matrices and units available in one
of the supported storage formats and you do not need a source-specific parser
such as EXIOBASE, WIOD, or FIGARO.

The custom surface is split into four entry points:

* :doc:`From Excel <from_excel>`
* :doc:`From TXT <from_txt>`
* :doc:`From Parquet <from_parquet>`
* :doc:`From pymrio <from_pymrio>`

Choose the parser based on the shape of the input:

* use ``from_excel`` for one manually prepared workbook;
* use ``from_txt`` for one directory of text files;
* use ``from_parquet`` for one directory of parquet files;
* use ``from_pymrio`` when the source is already a live ``pymrio.IOSystem``.

Common concepts
---------------

For the file-based custom parsers, the main structural choices are the same:

* ``table="IOT"`` or ``table="SUT"``;
* ``mode="flows"`` or ``mode="coefficients"``;
* optional ``matrix_layouts=...`` for non-standard IOT-side layouts;
* optional ``tech_assumption=...`` for SUT parsing.

These parsers do not infer the semantic model automatically. You should pass
the table kind and the mode that actually match the files you prepared.

Notebook
--------

If you prefer to run a generic custom-database walkthrough locally, you can
still download the shared notebook:

* :download:`Download the custom-parser notebook <../notebooks/parsers/custom_database/tutorial.ipynb>`
