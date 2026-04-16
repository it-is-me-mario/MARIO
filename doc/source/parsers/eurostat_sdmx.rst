Eurostat SDMX
=============

MARIO supports direct parsing of Eurostat national SUT and IOT tables from the
official SDMX API.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_eurostat(...) <../api_document/mario.parse_eurostat>`

Use this entry point for both Eurostat SUT and IOT tables.

Download workflow
-----------------

Two patterns are supported:

* direct API parsing through ``mario.parse_eurostat(...)``;
* explicit raw-file download through ``mario.download_eurostat(...)``.

Direct API parsing is the simplest path.

Typical usage
-------------

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the Eurostat notebook <../notebooks/parsers/eurostat_sdmx/tutorial.ipynb>`

Load MARIO first:

.. code-block:: python

   import mario

Parse a Eurostat SUT directly from SDMX:

.. code-block:: python

   db = mario.parse_eurostat(
       country="IT",
       year=2022,
       table="SUT",
   )

Parse a Eurostat IOT:

.. code-block:: python

   db = mario.parse_eurostat(
       country="IT",
       year=2022,
       table="IOT",
       iot_mode="product",
   )

Download the raw slice explicitly first:

.. code-block:: python

   mario.download_eurostat(
       path="/path/to/eurostat_cache",
       country="IT",
       year=2022,
       table="SUT",
   )

Or ask the parser to download and reuse the local raw file:

.. code-block:: python

   db = mario.parse_eurostat(
       country="IT",
       year=2022,
       table="SUT",
       path="/path/to/eurostat_cache",
       download=True,
   )

Supported options
-----------------

Key parser options are:

* ``table="SUT"`` or ``table="IOT"``
* ``iot_mode="product"`` or ``"industry"`` for IOT
* ``unit="MIO_EUR"`` or ``"MIO_NAC"``

Caveats
-------

* this parser targets national Eurostat SDMX tables, not arbitrary local
  spreadsheets;
* ``iot_mode`` matters only for ``table="IOT"``;
* ``download=True`` is the right choice when you want reproducible local raw
  files in addition to the parsed database.
