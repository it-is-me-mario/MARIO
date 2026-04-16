OECD
====

MARIO supports local parsing of the OECD ICIO 2025 edition flat CSV bundles.

Relevant source links
---------------------

* official OECD dataset page:
  `OECD ICIO dataset page <https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_oecd(...) <../api_document/mario.parse_oecd>`

The current backend supports the OECD ICIO ``IOT`` workflow.

Key arguments
-------------

The key public arguments are:

* ``path``:
  one yearly OECD ICIO csv file or one directory containing multiple yearly
  files;
* ``year``:
  use it when the selected directory contains more than one year;
* ``name``:
  optional metadata label override;
* ``calc_all``:
  optional eager computation of derived blocks after parsing.

Download workflow
-----------------

Automatic OECD ICIO download is intentionally not supported.

In practice, the workflow is:

1. download the yearly OECD ICIO csv file manually from the official dataset
   page;
2. keep one local ``<year>.csv`` file, or a directory containing multiple
   yearly csv files;
3. pass that file or directory to ``mario.parse_oecd(...)``.

Tutorial
--------

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the OECD notebook <../notebooks/parsers/oecd/tutorial.ipynb>`

Load MARIO first:

.. code-block:: python

   import mario

Parse one explicit yearly file:

.. code-block:: python

   db = mario.parse_oecd(
       path="/path/to/ICIO2021_2018.csv",
   )

Parse from a directory and select one year:

.. code-block:: python

   db = mario.parse_oecd(
       path="/path/to/oecd_directory",
       year=2018,
   )

Inspect the parsed database:

.. code-block:: python

   db

Caveats
-------

* OECD parsing currently supports the local ``IOT`` csv bundle workflow;
* automatic MARIO download is intentionally not supported;
* when ``path`` points to a directory containing more than one year, pass
  ``year=`` explicitly.
