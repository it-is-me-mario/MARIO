StatCan
=======

MARIO supports Statistics Canada supply-use and symmetric I-O tables through
the official WDS API.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_statcan(...) <../api_document/mario.parse_statcan>`

Key arguments
-------------

The key public arguments are:

* ``year``:
  reference year to download and parse;
* ``table``:
  choose ``"SUT"`` or ``"IOT"``;
* ``level``:
  choose ``summary``, ``detail`` or ``link1997`` when supported;
* ``geo``:
  geography label such as ``Canada`` or one province/territory;
* ``valuation``:
  IOT price-system selector, usually ``basic`` or ``purchaser``;
* ``satellite_account``:
  optional extra bundle selector such as ``openio_canada`` when supported;
* ``path``:
  optional cache directory for local raw files;
* ``download``:
  when ``True``, MARIO stores the raw CSV locally before parsing it.

Download workflow
-----------------

Two download helpers are available:

* ``mario.download_statcan(...)`` for raw WDS table files;
* ``mario.download_statcan_openio_canada(...)`` for the OpenIO-Canada
  emission-factor workbook used by the ``openio_canada`` satellite path.

You can also parse directly from the API without a prior explicit download.

Supported workflows
-------------------

StatCan parsing supports both:

* ``table="SUT"``
* ``table="IOT"``

Supported ``level`` values are:

* ``summary``
* ``detail``
* ``link1997`` only for ``SUT``

For IOT parsing, ``valuation`` can be:

* ``basic``
* ``purchaser``

Tutorial
--------

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the StatCan notebook <../notebooks/parsers/statcan/tutorial.ipynb>`

Load MARIO first:

.. code-block:: python

   import mario

Parse a StatCan SUT directly from WDS:

.. code-block:: python

   db = mario.parse_statcan(
       year=2022,
       table="SUT",
       level="summary",
       geo="Canada",
   )

Parse a StatCan IOT:

.. code-block:: python

   db = mario.parse_statcan(
       year=2022,
       table="IOT",
       level="detail",
       valuation="basic",
   )

Keep the raw CSV locally while parsing:

.. code-block:: python

   db = mario.parse_statcan(
       year=2022,
       table="SUT",
       level="detail",
       path="/path/to/statcan_cache",
       download=True,
   )

Use the OpenIO-Canada satellite bundle when supported:

.. code-block:: python

   db = mario.parse_statcan(
       year=2022,
       table="SUT",
       level="detail",
       geo="Ontario",
       satellite_account="openio_canada",
       path="/path/to/statcan_cache",
       download=True,
   )

Caveats
-------

* ``satellite_account="openio_canada"`` is currently supported only for the
  documented subset of the StatCan SUT workflow;
* ``download=True`` is the right choice when you want a local raw-file cache in
  addition to the parsed database;
* the StatCan parser is API-driven, so a stable network connection matters more
  than for local-file parsers.
