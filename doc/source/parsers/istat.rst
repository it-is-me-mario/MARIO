ISTAT
=====

MARIO supports official ISTAT input-output releases from local files or from a
downloaded release zip.

Relevant source links
---------------------

* official ISTAT tag page:
  `ISTAT sistema input-output <https://www.istat.it/tag/sistema-input-output/>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_istat(...) <../api_document/mario.parse_istat>`

Download workflow
-----------------

Automatic download is available:

* ``mario.download_istat_io(...)``

Or you can ask the parser to download and parse the official release in one
step with ``download=True``.

Supported workflows
-------------------

The parser supports both:

* ``table="IOT"``
* ``table="SUT"``

For IOT parsing, choose:

* ``iot_mode="product"``
* ``iot_mode="industry"``

For SUT parsing, the relevant selectors are:

* ``level="63"`` or ``"20"``
* ``price="current"`` or ``"pyp"``
* ``valuation="basic"`` or ``"purchaser"``

Tutorial
--------

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the ISTAT notebook <../notebooks/parsers/istat/tutorial.ipynb>`

Load MARIO first:

.. code-block:: python

   import mario

Parse one local ISTAT IOT workbook:

.. code-block:: python

   db = mario.parse_istat(
       path="/path/to/istat_release",
       year=2022,
       table="IOT",
       iot_mode="product",
   )

Parse one ISTAT SUT:

.. code-block:: python

   db = mario.parse_istat(
       path="/path/to/istat_release",
       year=2022,
       table="SUT",
       level="63",
       price="current",
       valuation="basic",
   )

Download and parse in one step:

.. code-block:: python

   db = mario.parse_istat(
       path="/path/to/istat_cache",
       year=2022,
       table="IOT",
       iot_mode="product",
       download=True,
       edition="latest",
   )

Caveats
-------

* the parser targets the official ISTAT release workbooks and release zips, not
  arbitrary spreadsheets;
* ``download=True`` is often the cleanest workflow because it leaves a
  reproducible local archive in addition to the parsed database;
* the SUT workflow has more structural options than the IOT workflow, so be
  explicit about ``level``, ``price`` and ``valuation`` when needed.
