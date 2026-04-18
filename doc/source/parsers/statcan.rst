StatCan
=======

MARIO supports Statistics Canada supply-use and symmetric I-O tables through
the official WDS API.

The parser currently supports:

* ``SUT`` tables at ``summary``, ``detail``, and ``link1997`` level;
* ``IOT`` tables at ``summary`` and ``detail`` level;
* direct online parsing from WDS;
* optional local caching of the raw CSV downloads.

For this source, the most useful documentation format is a notebook-driven one:
this landing page stays short, while one practical notebook covers where the
tables come from, direct online parsing, local caching, the difference between
``SUT`` and ``IOT`` workflows, ``geo=``, ``level=``, and ``valuation=``.

Relevant source links
---------------------

* official StatCan SUT catalogue:
  `Supply and use tables <https://www150.statcan.gc.ca/n1/en/catalogue/36100478>`_;
* official StatCan IOT catalogue:
  `Symmetric input-output tables <https://www150.statcan.gc.ca/n1/en/catalogue/36100001>`_;
* official StatCan WDS guide:
  `StatCan WDS user guide <https://www.statcan.gc.ca/en/developers/wds/user-guide>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

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
* ``path``:
  optional cache directory for local raw files;
* ``download``:
  when ``True``, MARIO stores the raw CSV locally before parsing it.

Download workflow
-----------------

Automatic raw download is available:

* ``mario.download_statcan(...)``

You can also parse directly from WDS without a prior explicit download.

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

Typical usage
-------------

Parse a StatCan SUT directly from WDS:

.. code-block:: python

   import mario

   db = mario.parse_statcan(
       year=2022,
       table="SUT",
       level="summary",
       geo="Canada",
   )

Parse a provincial detail SUT:

.. code-block:: python

   import mario

   db = mario.parse_statcan(
       year=2022,
       table="SUT",
       level="detail",
       geo="Ontario",
   )

Parse a StatCan IOT:

.. code-block:: python

   import mario

   db = mario.parse_statcan(
       year=2022,
       table="IOT",
       level="detail",
       valuation="basic",
   )

Cache the raw CSV locally while parsing:

.. code-block:: python

   import mario

   db = mario.parse_statcan(
       year=2022,
       table="SUT",
       level="detail",
       path="/path/to/statcan_cache",
       download=True,
   )

Caveats
-------

* the parser is API-driven, so network availability matters more than for
  local-file parsers;
* ``download=True`` is the right choice when you want a reusable local raw-file
  cache in addition to the parsed database;
* this guide focuses on the economic StatCan tables only. Environmental
  extensions are intentionally left out here.

Notebook Walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`StatCan parser walkthrough <../notebooks/parsers/statcan/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the StatCan notebook <../notebooks/parsers/statcan/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/statcan/walkthrough
