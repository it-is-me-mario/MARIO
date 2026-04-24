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

Relevant source links
---------------------

* official ISTAT tag page:
  `ISTAT sistema input-output <https://www.istat.it/tag/sistema-input-output/>`_.

Recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_istat(...) <../../api_document/mario.parse_istat>`

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

Expected path structure
-----------------------

``path`` can point to one official workbook, one extracted ISTAT release
directory, one official release zip, or to the cache directory used with
``download=True``:

.. code-block:: text

   ISTAT/
   ├── input_output_2015_2020.zip
   ├── input_output_2020_2022.zip
   └── extracted_release/
       ├── *.xlsx
       └── *.xls

For local parsing, the file names and workbook sheets must come from the
official ISTAT release. For download-based parsing, ``path`` is the directory
where MARIO stores the downloaded archive and extracted files.


Notebook walkthrough
--------------------

Automatic download is available:

* ``mario.download_istat_io(...)``

Or you can ask the parser to download and parse the official release in one
step with ``download=True``.


Once downloaded, use the notebook below as the main parser guide:

* :doc:`ISTAT parser walkthrough <../../notebooks/parsers/istat/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the ISTAT notebook <../../notebooks/parsers/istat/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/parsers/istat/walkthrough


Caveats
-------

* The parser targets the official ISTAT release workbooks and release zips, not
  arbitrary spreadsheets;
* ``download=True`` is often the cleanest workflow because it leaves a
  reproducible local archive in addition to the parsed database;
* The ``SUT`` workflow has more structural selectors than the ``IOT`` workflow,
  so be explicit about ``level``, ``price``, and ``valuation`` when needed;
* For ``IOT``, ``iot_mode=`` decides whether you parse the product-by-product
  or industry-by-industry release.
