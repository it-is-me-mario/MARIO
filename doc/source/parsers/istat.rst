ISTAT
=====

MARIO supports official ISTAT input-output releases from local files or from a
downloaded official release bundle.

The parser currently supports:

* ``IOT`` workbooks in product-by-product and industry-by-industry form;
* ``SUT`` release bundles with the supported level, price, and valuation
  combinations;
* local parsing from one workbook, one extracted release directory, or one
  release zip;
* automatic download of the official release before parsing.

For this source, the most useful documentation format is a notebook-driven one:
this landing page stays short, while one practical notebook covers direct local
parsing, zip-versus-directory workflows, the release downloader, and the
selectors used for ``IOT`` and ``SUT`` parsing.

Relevant source links
---------------------

* official ISTAT tag page:
  `ISTAT sistema input-output <https://www.istat.it/tag/sistema-input-output/>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_istat(...) <../api_document/mario.parse_istat>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  local workbook, extracted release directory, release zip, or cache directory
  when ``download=True``;
* ``year``:
  reference year to select from the ISTAT release;
* ``table``:
  choose ``"IOT"`` or ``"SUT"``;
* ``iot_mode``:
  IOT-only selector, either ``"product"`` or ``"industry"``;
* ``level``:
  SUT-only selector, either ``"63"`` or ``"20"``;
* ``price``:
  SUT-only selector, either ``"current"`` or ``"pyp"``;
* ``valuation``:
  SUT-only selector, either ``"basic"`` or ``"purchaser"``;
* ``download``:
  when ``True``, MARIO downloads the official ISTAT release before parsing it;
* ``edition`` and ``page_url``:
  downloader selectors for the official release page.

Download workflow
-----------------

Automatic download is available:

* ``mario.download_istat_io(...)``

Or you can ask the parser to download and parse the official release in one
step with ``download=True``.

Typical usage
-------------

Parse one local ISTAT IOT workbook:

.. code-block:: python

   import mario

   db = mario.parse_istat(
       path="/path/to/istat_release",
       year=2022,
       table="IOT",
       iot_mode="product",
   )

Parse one ISTAT SUT release:

.. code-block:: python

   import mario

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

   import mario

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
* the ``SUT`` workflow has more structural selectors than the ``IOT`` workflow,
  so be explicit about ``level``, ``price``, and ``valuation`` when needed;
* for ``IOT``, ``iot_mode=`` decides whether you parse the product-by-product
  or industry-by-industry release.

Notebook Walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`ISTAT parser walkthrough <../notebooks/parsers/istat/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the ISTAT notebook <../notebooks/parsers/istat/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/istat/walkthrough
