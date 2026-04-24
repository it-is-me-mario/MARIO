Full International and Global Accounts for Research in input-Output analysis (FIGARO)
=====================================================================================

MARIO parses FIGARO directly from the Eurostat API.

The parser supports both:

* ``SUT`` form;
* ``IOT`` form.

source links
------------

The parser uses the Eurostat Statistics API:

* `Eurostat API introduction <https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction>`_;
* `FIGARO data browser folder <https://ec.europa.eu/eurostat/databrowser/explore/all/naio?lang=en&subtheme=naio.naio_10.naio_10_fcp&display=list&sort=category>`_.

The dataflow suffix depends on the selected year:

* ``2010``-``2013``:
  ``naio_10_fcp_s1``, ``naio_10_fcp_u1``, ``naio_10_fcp_ip1``,
  ``naio_10_fcp_ii1``;
* ``2014``-``2017``:
  ``naio_10_fcp_s2``, ``naio_10_fcp_u2``, ``naio_10_fcp_ip2``,
  ``naio_10_fcp_ii2``;
* ``2018``-``2021``:
  ``naio_10_fcp_s3``, ``naio_10_fcp_u3``, ``naio_10_fcp_ip3``,
  ``naio_10_fcp_ii3``;
* ``2022`` onwards:
  ``naio_10_fcp_s4``, ``naio_10_fcp_u4``, ``naio_10_fcp_ip4``,
  ``naio_10_fcp_ii4``.

recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_figaro(...) <../../api_document/mario.parse_figaro>`

key arguments
-------------

The key public arguments are:

* ``table``:
  choose ``"SUT"`` or ``"IOT"``;
* ``year``:
  required. MARIO uses it to select the correct Eurostat dataflow group;
* ``iot_mode``:
  only relevant for ``table="IOT"``. Use ``"auto"``, ``"product"`` or
  ``"industry"``. ``"auto"`` defaults to product-by-product;
* ``countries``:
  optional country subset using FIGARO country codes, for example
  ``["IT", "ME"]``. If omitted, MARIO parses all available FIGARO countries;
* ``unit``:
  currently ``"MIO_EUR"``.

The old ``path`` argument is deprecated and ignored. FIGARO parsing is now
API-based.

examples
--------

Parse a FIGARO SUT for a small country subset:

.. code-block:: python

   import mario

   db = mario.parse_figaro(
       table="SUT",
       year=2022,
       countries=["IT", "ME"],
       calc_all=False,
   )

Parse the product-by-product IOT:

.. code-block:: python

   db = mario.parse_figaro(
       table="IOT",
       year=2022,
       iot_mode="product",
       countries=["IT", "ME"],
       calc_all=False,
   )

notes
-----

The Eurostat FIGARO API uses ``c_orig`` and ``c_dest`` instead of the local
flat-file ``refArea`` and ``counterpartArea`` fields. MARIO downloads the table
by origin country to avoid Eurostat extraction-size limits, then rebuilds the
MARIO matrices.

For SUTs, ``DOM`` rows in the use table are interpreted as value-added rows.
For IOTs, ``DOM`` rows are interpreted in the same way for the ``V`` matrix.

notebook walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`FIGARO parser walkthrough <../../notebooks/parsers/figaro/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the FIGARO notebook <../../notebooks/parsers/figaro/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/parsers/figaro/walkthrough

caveats
-------

* Full FIGARO tables are large. Use ``countries=`` while developing workflows.
* Eurostat may reject unchunked full-table requests; MARIO chunks requests by
  ``c_orig`` internally.
* For ``table="IOT"``, ``iot_mode="auto"`` defaults to the product-by-product
  dataflow.
