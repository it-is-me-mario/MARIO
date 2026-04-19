BEA
===

MARIO supports local parsing of official ``BEA`` ``SUPPLY-USE`` workbooks.

The current backend is intentionally narrow:

* it parses only the ``SUPPLY-USE`` workbook family;
* it currently supports only ``SUT`` parsing;
* it accepts the official zip bundle, one extracted directory, or one workbook
  path inside that directory;
* it exposes the BEA aggregation ``level`` directly through the public API.

Relevant source links
---------------------

* official BEA input-output page:
  `Industry Input-Output Accounts Data <https://www.bea.gov/industry/input-output-accounts-data>`_;
* interactive guide:
  `Guide to the interactive industry input-output accounts tables <https://www.bea.gov/resources/guide-interactive-industry-input-output-accounts-tables>`_;
* direct supply-use bundle:
  `SUPPLY-USE.zip <https://apps.bea.gov/industry/release/zip/SUPPLY-USE.zip>`_.

Parser Scope
------------

For now, MARIO targets only the official ``SUPPLY-USE`` bundle published by
the ``BEA``. The parser does **not** currently read:

* ``MAKE-USE-IMPORTS (BEFORE REDEFINITIONS)``;
* ``TOTAL AND DOMESTIC REQUIREMENTS``.

The supported public entry point is:

* :doc:`mario.parse_bea(...) <../api_document/mario.parse_bea>`

Supported levels
----------------

``parse_bea`` currently supports three BEA aggregation levels:

.. list-table::
   :header-rows: 1

   * - Level
     - Workbook pair
     - Verified yearly coverage in the current official bundle
   * - ``summary``
     - ``Supply_Summary.xlsx`` + ``Use_Summary.xlsx``
     - ``1997`` to ``2024``
   * - ``sector``
     - ``Supply_Sector.xlsx`` + ``Use_Sector.xlsx``
     - ``1997`` to ``2024``
   * - ``detail``
     - ``Supply_Detail.xlsx`` + ``Use_SUT_Detail.xlsx``
     - ``2007``, ``2012``, ``2017``

How MARIO maps the bundle
-------------------------

The parser reads the bundle as a split-native ``SUT``:

* ``S`` from the domestic-industry block of the BEA ``Supply`` workbook;
* ``U`` and ``Yc`` from the BEA ``Use`` workbook;
* ``Va`` from the use-workbook value-added footer rows;
* ``Vc`` from the supply-workbook commodity-side columns such as imports,
  margins, and product taxes.

This means the parsed table uses a mixed valuation convention:

* supply-side output is read at basic prices;
* use-side flows are read at purchaser prices.

Typical usage
-------------

Direct path to the official zip bundle:

.. code-block:: python

   import mario

   db = mario.parse_bea(
       path="/path/to/SUPPLY-USE.zip",
       year=2024,
       level="summary",
   )

Extracted directory:

.. code-block:: python

   import mario

   db = mario.parse_bea(
       path="/path/to/SUPPLY-USE",
       year=2024,
       level="sector",
   )

One workbook path inside the extracted directory:

.. code-block:: python

   import mario

   db = mario.parse_bea(
       path="/path/to/Supply_Detail.xlsx",
       year=2017,
       level="detail",
   )

Warnings
--------

.. warning::

   MARIO currently parses only the ``SUPPLY-USE`` bundle. The separate
   ``MAKE-USE-IMPORTS (BEFORE REDEFINITIONS)`` and ``TOTAL AND DOMESTIC
   REQUIREMENTS`` releases are not treated as interchangeable inputs.

.. warning::

   The resulting database should be treated as a ``SUT`` with mixed valuation:
   basic-price supply and purchaser-price use.

.. warning::

   ``detail`` coverage in the current official bundle is sparse compared with
   ``summary`` and ``sector``. At the time of verification, only ``2007``,
   ``2012``, and ``2017`` are available in the detailed workbooks.

Notebook Walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`BEA parser walkthrough <../notebooks/parsers/bea/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the BEA notebook <../notebooks/parsers/bea/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/bea/walkthrough
