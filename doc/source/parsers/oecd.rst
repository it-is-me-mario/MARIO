OECD
====

MARIO supports three OECD parser families:

* OECD ``ICIO`` csv bundles, including both the regular and extended releases
* OECD national total-table ``IOT`` csv files such as ``ITA2014ttl.csv``
* OECD ``SUT`` tables pulled directly from the official SDMX API


Relevant source links
---------------------

* official OECD ICIO page:
  `OECD inter-country input-output tables <https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html>`_;
* official OECD national IOT page:
  `OECD input-output tables <https://www.oecd.org/en/data/datasets/input-output-tables.html>`_;
* official OECD SUT page:
  `OECD supply and use tables <https://www.oecd.org/en/data/datasets/supply-and-use-tables.html>`_.


Recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_oecd(...) <../api_document/mario.parse_oecd>`


Key arguments
-------------

The key public arguments are:

* ``path``:
  one local OECD file or one directory containing multiple OECD files. 
  Required for ``dataset="ICIO"`` and ``dataset="IOT"``
* ``dataset``:
  choose between ``"ICIO"``, ``"IOT"``, and ``"SUT"``
* ``year``:
  use it when one directory contains more than one candidate file. It is also
  required for ``dataset="SUT"`` because the OECD SDMX pull is annual
* ``country``:
  useful to disambiguate national OECD IOT files and required for
  ``dataset="SUT"``


Notebook walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`OECD parser walkthrough <../notebooks/parsers/oecd/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the OECD notebook <../notebooks/parsers/oecd/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/oecd/walkthrough


Caveats
-------
* The IOT ``dataset`` support only the accounts indicated as "Total table"
