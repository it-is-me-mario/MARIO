Full International and Global Accounts for Research in input-Output analysis (FIGARO)
=====================================================================================

MARIO supports local parsing of FIGARO flat files in both:

* ``SUT`` form;
* ``IOT`` form.

The parser is intentionally file-based: download the FIGARO files yourself,
keep them in one local directory, and then point MARIO to that directory.

Relevant source links
---------------------

The current parser is based on the public CIRCABC FIGARO libraries referenced
by MARIO:

* supply files:
  `CIRCABC supply library <https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/library/651e74b4-ff35-445b-9427-5b3ed9ec5ca9?p=1&n=10&sort=name_ASC>`_;
* use files:
  `CIRCABC use library <https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/library/093bfbed-142f-47c8-a151-d9fd3f95a507?p=1&n=10&sort=name_ASC>`_;
* product-by-product IOT files:
  `CIRCABC pxp IOT library <https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/library/93e9d3f7-54ab-47e9-8b40-ae4ac6faf7b5?p=1&n=10&sort=modified_DESC>`_;
* industry-by-industry IOT files:
  `CIRCABC ixi IOT library <https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/library/50d2f89f-ea50-4c8d-969e-cf3ad6b43750?p=1&n=10&sort=modified_DESC>`_.

Recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_figaro(...) <../api_document/mario.parse_figaro>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  local directory containing the FIGARO flat files;
* ``table``:
  choose ``"SUT"`` or ``"IOT"``;
* ``year``:
  use it when the selected directory contains more than one FIGARO year;
* ``iot_mode``:
  only relevant for ``table="IOT"``. Use ``"auto"``, ``"product"`` or
  ``"industry"``.

Expected path structure
-----------------------

``path`` must point to one directory containing the downloaded FIGARO bundles
or their extracted CSV files:

.. code-block:: text

   FIGARO/
   ├── supply/
   │   └── *.csv
   ├── use/
   │   └── *.csv
   └── iot/
       └── *.csv

Passing one single ``.zip`` or ``.csv`` file is not supported by the current
backend. Keep all files for the selected table and year under the same local
directory and select the year with ``year=``.

Download workflow
-----------------

Automatic FIGARO download is intentionally not supported.

In practice, the workflow is:

1. download the relevant FIGARO flat files from CIRCABC;
2. place the ``.zip`` bundles or extracted ``.csv`` files in one local folder;
3. pass that folder to ``mario.parse_figaro(...)``.

Notebook walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`FIGARO parser walkthrough <../notebooks/parsers/figaro/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the FIGARO notebook <../notebooks/parsers/figaro/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/figaro/walkthrough

Caveats
-------

* FIGARO parsing expects a local directory. Passing one single ``.zip`` or
  ``.csv`` file is not supported by the current backend.
* For ``table="IOT"``, ``iot_mode`` can be ``auto``, ``product``, or
  ``industry``. When both IOT variants are present and ``iot_mode="auto"``,
  MARIO defaults to the product-by-product file.
