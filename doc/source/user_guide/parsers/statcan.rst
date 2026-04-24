StatCan
=======

MARIO supports Statistics Canada supply-use and symmetric I-O tables through
the official WDS API.

The parser currently supports:

* ``SUT`` tables at ``summary``, ``detail``, and ``link1997`` level;
* ``IOT`` tables at ``summary`` and ``detail`` level;
* direct online parsing from WDS;
* optional local caching of the raw CSV downloads.

Relevant source links
---------------------

* official StatCan SUT catalogue:
  `Supply and use tables <https://www150.statcan.gc.ca/n1/en/catalogue/36100478>`_;
* official StatCan IOT catalogue:
  `Symmetric input-output tables <https://www150.statcan.gc.ca/n1/en/catalogue/36100001>`_;
* official StatCan WDS guide:
  `StatCan WDS user guide <https://www.statcan.gc.ca/en/developers/wds/user-guide>`_.

Recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_statcan(...) <../../api_document/mario.parse_statcan>`

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

Expected path structure
-----------------------

StatCan parsing is API-driven. ``path`` is optional and, when provided, is a
cache directory for raw WDS CSV downloads:

.. code-block:: text

   StatCan/
   └── cache/
       ├── 36-10-0438-01_*.csv
       └── 36-10-0001-01_*.csv

If ``download=False``, MARIO reads directly from WDS and no local files are
required. If ``download=True``, MARIO stores the raw files in ``path`` and then
parses from that cache.

Download workflow
-----------------

Automatic raw download is available:

* ``mario.download_statcan(...)``

You can also parse directly from WDS without a prior explicit download.

Supported Workflows
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

Caveats
-------

* the parser is API-driven, so network availability matters more than for
  local-file parsers;
* ``download=True`` is the right choice when you want a reusable local raw-file
  cache in addition to the parsed database;
* this guide focuses on the economic StatCan tables only. Environmental
  extensions are intentionally left out here.

Notebook walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`StatCan parser walkthrough <../../notebooks/parsers/statcan/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the StatCan notebook <../../notebooks/parsers/statcan/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/parsers/statcan/walkthrough
