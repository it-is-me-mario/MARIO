EUROSTAT
========

MARIO supports direct parsing of Eurostat national supply-use and symmetric
input-output tables from the official SDMX API.

The parser currently supports:

* ``SUT`` through Eurostat tables ``T1500`` and ``T1600``;
* ``IOT`` through Eurostat symmetric tables in both product-by-product and
  industry-by-industry form;
* direct online parsing from the official API;
* optional local caching of the raw SDMX-CSV slices.

Relevant source links
---------------------

* official Eurostat SUIOT information page:
  `ESA supply, use and input-output tables <https://ec.europa.eu/eurostat/web/esa-supply-use-input-tables>`_;
* official Eurostat metadata for national SUIOTs:
  `naio_10_n metadata <https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_n_esms.htm>`_;
* official Eurostat API guide:
  `Eurostat data access API <https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction>`_.

Recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_eurostat(...) <../api_document/mario.parse_eurostat>`

Key arguments
-------------

The key public arguments are:

* ``country``:
  Eurostat geo code such as ``IT`` or ``DE``;
* ``year``:
  reference year to download and parse;
* ``table``:
  choose ``"SUT"`` or ``"IOT"``;
* ``iot_mode``:
  IOT-only selector, either ``"product"`` or ``"industry"``;
* ``unit``:
  choose ``"MIO_EUR"`` or ``"MIO_NAC"``;
* ``path``:
  optional local cache directory for raw SDMX files;
* ``download``:
  when ``True``, MARIO stores the raw CSV locally before parsing it.

Expected path structure
-----------------------

EUROSTAT parsing is API-driven. ``path`` is optional and, when provided, is a
cache directory for raw SDMX-CSV slices:

.. code-block:: text

   EUROSTAT/
   └── cache/
       ├── NAIO_10_CP15_*.csv
       ├── NAIO_10_CP16_*.csv
       ├── NAIO_10_CP1700_*.csv
       └── NAIO_10_CP1750_*.csv

If ``download=False``, MARIO reads directly from the Eurostat API. If
``download=True``, MARIO stores the downloaded slices under ``path`` before
building the database.

Available years
---------------

Year availability is not uniform across all countries.

The official Eurostat metadata states that:

* national ``SUT`` annual tables are published from reference year ``2010``
  onward;
* national ``IOT`` tables are also published from reference year ``2010``
  onward;
* however, ``IOT`` transmission is mandatory only for years ending in ``0`` or
  ``5``, while additional years depend on voluntary country transmission.

On the live official API, checked on ``18 April 2026`` with ``Italy (IT)`` as
one concrete example, MARIO currently finds:

* ``SUT``: ``2010`` to ``2022``;
* ``IOT``: ``2010`` and then ``2015`` to ``2022``.

So the practical rule is:

* for ``SUT``, expect a broadly annual series from ``2010`` onward, but not
  the most recent ``T-2`` or ``T-1`` years unless Eurostat has already
  published them for the specific country;
* for ``IOT``, treat ``2010``, ``2015``, ``2020`` as the core mandatory years
  and any extra years as country-specific.

Caveats
-------

* this parser targets national Eurostat SDMX tables, not arbitrary local
  spreadsheets;
* ``iot_mode`` matters only for ``table="IOT"``;
* year availability is country-dependent, especially for ``IOT``;
* ``download=True`` is the right choice when you want reproducible local raw
  files in addition to the parsed database.

Notebook walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`EUROSTAT parser walkthrough <../notebooks/parsers/eurostat/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the EUROSTAT notebook <../notebooks/parsers/eurostat/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/eurostat/walkthrough
