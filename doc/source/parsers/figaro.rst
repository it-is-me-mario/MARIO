FIGARO
======

MARIO supports local parsing of FIGARO flat files in both:

* SUT form;
* IOT form.

Relevant source links
---------------------

The current parser is based on the public CIRCABC FIGARO libraries referenced
by MARIO:

* supply files:
  `CIRCABC supply library <https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/library/651e74b4-ff35-445b-9427-5b3ed9ec5ca9?p=1&n=10&sort=name_ASC>`_;
* use files:
  `CIRCABC use library <https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/library/093bfbed-142f-47c8-a151-d9fd3f95a507?p=1&n=10&sort=name_ASC>`_;
* product-by-product IOT files:
  `CIRCABC pxp IOT library <https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/library/93e9d3f7-54ab-47e9-8b40-ae4ac6faf7b5?p=1&n=10&sort=modified_DESC>`_;
* industry-by-industry IOT files:
  `CIRCABC ixi IOT library <https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/library/50d2f89f-ea50-4c8d-969e-cf3ad6b43750?p=1&n=10&sort=modified_DESC>`_.

Unlike EXIOBASE, the FIGARO workflow is intentionally file-based: download the
files yourself, keep them in one local directory, and then point MARIO to that
directory.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_figaro(...) <../api_document/mario.parse_figaro>`

This is enough for the FIGARO variants covered by the current parser.

Key arguments
-------------

The key public arguments are:

* ``path``:
  local directory containing the FIGARO flat files;
* ``table``:
  choose ``"SUT"`` or ``"IOT"``;
* ``year``:
  use this when the selected directory contains more than one FIGARO year;
* ``iot_mode``:
  only relevant for ``table="IOT"``. Use ``"auto"``, ``"product"`` or
  ``"industry"``.

Download workflow
-----------------

Automatic FIGARO download is intentionally not supported.

In practice, the workflow is:

1. download the relevant FIGARO flat files from CIRCABC;
2. place the ``.zip`` bundles or extracted ``.csv`` files in one local folder;
3. pass that folder to ``mario.parse_figaro(...)``.

For ``table="SUT"``, MARIO looks for the supply/use files.
For ``table="IOT"``, MARIO looks for the pxp and/or ixi IOT files.

Local layout expectation
------------------------

MARIO expects one local directory containing the relevant FIGARO flat files,
either as:

* ``.zip`` bundles;
* extracted ``.csv`` files.

The parser inspects that directory and resolves the correct files from the
available year and table type.

Tutorial
--------

This page is the practical walkthrough for FIGARO. It covers:

* where to get the source files;
* what local layout MARIO expects;
* how to parse a FIGARO SUT;
* how to parse a FIGARO IOT;
* how to choose the IOT mode when needed.

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the FIGARO notebook <../notebooks/parsers/figaro/tutorial.ipynb>`

Load MARIO first:

.. code-block:: python

   import mario

Parse a FIGARO SUT
------------------

SUT:

.. code-block:: python

   db = mario.parse_figaro(
       path="/path/to/figaro_directory",
       table="SUT",
   )

Parse a FIGARO IOT
------------------

For IOT parsing, ``iot_mode`` can be:

* ``"auto"``
* ``"product"``
* ``"industry"``

When both IOT variants are present and ``iot_mode="auto"``, MARIO defaults to
the product-by-product file.

.. code-block:: python

   db = mario.parse_figaro(
       path="/path/to/figaro_directory",
       table="IOT",
       iot_mode="auto",
   )

Inspect the parsed database
---------------------------

Once parsed, the result is a standard MARIO database. A simple first check is:

.. code-block:: python

   db

You can then inspect the available labels as usual:

.. code-block:: python

   db.region[:5]
   db.activity[:5]
   db.commodity[:5]

Caveats
-------

* the parser expects a local directory, not a remote URL;
* for IOT parsing, ``iot_mode`` can be ``auto``, ``product``, or ``industry``;
* when both IOT variants are present and ``iot_mode="auto"``, MARIO defaults
  to the product-by-product file.
