Custom Databases
================

This is the main parser guide for user-provided databases.

Recommended Entry Points
------------------------

For ordinary workflows, the public entry points are:

* :doc:`mario.parse_from_excel(...) <../api_document/mario.parse_from_excel>`
* :doc:`mario.parse_from_txt(...) <../api_document/mario.parse_from_txt>`
* :doc:`mario.parse_from_parquet(...) <../api_document/mario.parse_from_parquet>`

Use these parsers when your data is already close to MARIO's canonical block
model and does not need a source-specific parser such as EXIOBASE or WIOD.

Choose the storage format
-------------------------

Use Excel when:

* you are building the dataset manually;
* you want one workbook with both data and units;
* you need the easiest first custom-parser workflow.

Use TXT or Parquet when:

* the data already lives as files on disk;
* you want matrix-per-file workflows;
* you want to roundtrip a canonical flat MARIO export.

Use Parquet instead of TXT when the payload is large and you want a more robust
binary storage format.

Choose the semantic model
-------------------------

MARIO custom parsers work on the same structural distinction as the rest of the
package:

* ``table="IOT"`` for input-output tables with sector-based blocks;
* ``table="SUT"`` for supply-use tables with distinct activity and commodity
  blocks.

You also choose whether the input blocks are:

* ``mode="flows"``
* ``mode="coefficients"``

The parser surface does not infer this automatically. You should pass the one
that matches the files you prepared.

Excel workflow
--------------

Key arguments for ``parse_from_excel(...)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most relevant arguments are:

* ``path``:
  one workbook to parse;
* ``table``:
  ``"IOT"`` or ``"SUT"``;
* ``mode``:
  ``"flows"`` or ``"coefficients"``;
* ``data_sheet``:
  optional data-sheet selector when the data is not in the first sheet;
* ``unit_sheet``:
  optional units-sheet selector when it is not called ``units``;
* ``matrix_layouts``:
  optional semantic declaration for non-standard IOT blocks;
* ``tech_assumption``:
  optional SUT-only selector for ``IT`` / ``PT`` behavior.

``parse_from_excel(...)`` expects one workbook with:

* one data sheet;
* one ``units`` sheet.

Typical usage:

.. code-block:: python

   import mario

   db = mario.parse_from_excel(
       path="/path/to/custom_iot.xlsx",
       table="IOT",
       mode="flows",
   )

Or for a SUT:

.. code-block:: python

   db = mario.parse_from_excel(
       path="/path/to/custom_sut.xlsx",
       table="SUT",
       mode="flows",
   )

If you want a concrete example of the expected workbook structure, the easiest
starting point is still:

.. code-block:: python

   import mario

   mario.load_test("IOT").to_excel("test_iot.xlsx")
   mario.load_test("SUT").to_excel("test_sut.xlsx")

TXT and Parquet workflows
-------------------------

Key arguments for ``parse_from_txt(...)`` and ``parse_from_parquet(...)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most relevant arguments are:

* ``path``:
  one directory containing the files to parse;
* ``table``:
  ``"IOT"`` or ``"SUT"``;
* ``mode``:
  ``"flows"`` or ``"coefficients"``;
* ``flat``:
  set this to ``True`` when parsing canonical MARIO flat exports;
* ``matrix_layouts``:
  optional semantic declaration for non-standard IOT blocks;
* ``tech_assumption``:
  optional SUT-only selector for ``IT`` / ``PT`` behavior.

TXT and Parquet support two families of layouts:

* historical matrix-per-file layouts;
* canonical flat exports.

Typical TXT parse:

.. code-block:: python

   db = mario.parse_from_txt(
       path="/path/to/txt_directory",
       table="IOT",
       mode="flows",
   )

Typical Parquet parse:

.. code-block:: python

   db = mario.parse_from_parquet(
       path="/path/to/parquet_directory",
       table="SUT",
       mode="coefficients",
   )

If you are parsing the canonical flat exports instead of one file per matrix,
use ``flat=True``.

Matrix layouts
--------------

For richer IOT layouts, MARIO accepts ``matrix_layouts=...`` to declare the
semantic shape of selected matrices such as ``V`` and ``E``.

Example:

.. code-block:: python

   db = mario.parse_from_excel(
       path="/path/to/custom_iot.xlsx",
       table="IOT",
       mode="flows",
       matrix_layouts={
           "V": "Region",
           "E": ("Region", "Sector"),
       },
   )

Only canonical MARIO set names are accepted in ``matrix_layouts``. See also:

* :doc:`../concepts/matrix_layouts`
* :doc:`../workflows/work_with_matrix_layouts`

SUT-specific options
--------------------

SUT parsers accept ``tech_assumption=...``:

* ``industry-based`` or ``IT``
* ``product-based`` or ``PT``

Example:

.. code-block:: python

   db = mario.parse_from_excel(
       path="/path/to/custom_sut.xlsx",
       table="SUT",
       mode="flows",
       tech_assumption="PT",
   )

If a product-based assumption is requested for a non-square SUT, MARIO falls
back to the industry-based assumption instead of failing the parse.

Canonical set names and aliases
-------------------------------

Inside parser inputs and layout declarations, use the canonical MARIO set
names:

* ``Region``
* ``Sector``
* ``Activity``
* ``Commodity``
* ``Consumption category``
* ``Factor of production``
* ``Satellite account``

Alias-based set resolution is a convenience of the public API. It is useful
for calls such as ``db.search("industry", ...)`` or ``db.product``, but it is
not a replacement for canonical labels inside parser inputs.

Notebook
--------

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the custom-database notebook <../notebooks/parsers/custom_database/tutorial.ipynb>`

Caveats
-------

* the parser does not infer ``flows`` versus ``coefficients`` automatically;
* ``matrix_layouts`` is the right tool for non-standard IOT block layouts;
* Excel is the easiest place to start, but flat TXT/Parquet is usually the
  better choice for roundtrip and large-file workflows.
