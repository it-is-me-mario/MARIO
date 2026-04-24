CEADS
======

MARIO supports local parsing of selected ``CEADS`` China provincial MRIO
workbooks.

The current backend is intentionally narrow:

* it parses only local Excel workbooks;
* it currently supports only the verified ``2018`` and ``2020`` provincial
  MRIO workbook family;
* it reads only the English table sheet, not the Chinese one;
* it exposes an explicit ``format=`` argument so future CEADS workbook
  families can be added without changing the public API.

Relevant source links
---------------------

* official CEADS data portal:
  `CEADS input-output tables <https://www.ceads.net/data/input_output_tables/>`_;
* data descriptor:
  `China’s Provincial Multi-Regional Input-Output Database for 2018 and 2020 <https://www.nature.com/articles/s41597-025-06543-y>`_;
* dataset DOI:
  `Figshare record 29927291 <https://doi.org/10.6084/m9.figshare.29927291>`_.

Parser Scope
------------

For now, MARIO targets the CEADS provincial MRIO workbook family associated
with the 2018 and 2020 release described in the Scientific Data paper.

That workbook family exposes:

* ``31`` provinces;
* ``42`` sectors;
* one English table sheet named like ``Table_2018_English Version``;
* one ``Sector`` metadata sheet;
* one ``Province`` metadata sheet.

The CEADS portal also lists older provincial MRIO releases such as 2012, 2015,
and 2017. Those historical releases are not automatically assumed to share the
same workbook semantics until they are checked explicitly.

What ``format`` Means
---------------------

``format=`` is the parser-side layout selector. It does not identify the
scientific dataset itself; it identifies the workbook structure that MARIO
knows how to read.

At the moment, MARIO supports:

* ``format="auto"``:
  inspect the workbook and resolve the known layout automatically;
* ``format="ceads_provincial_workbook"``:
  force the currently verified 2018/2020 workbook structure.

Recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_ceads(...) <../api_document/mario.parse_ceads>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  one local workbook or one directory containing one or more CEADS workbooks;
* ``format``:
  workbook layout selector. ``auto`` is the default and currently resolves to
  ``"ceads_provincial_workbook"``;
* ``year``:
  workbook year used to disambiguate one directory containing more than one
  CEADS workbook;
* ``table``:
  currently only ``"IOT"`` is supported.

Expected path structure
-----------------------

``path`` can point to one CEADS workbook or to a directory containing the
verified provincial MRIO workbooks:

.. code-block:: text

   CEADS/
   ├── MRIO 2018.xlsx
   └── MRIO 2020.xlsx

Inside each workbook, MARIO reads the English sheet named like
``Table_<year>_English Version`` and uses the ``Sector`` and ``Province``
metadata sheets for labels. When passing a directory, use ``year=`` to select
the workbook.

Notebook walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`CEADS parser walkthrough <../notebooks/parsers/ceads/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the CEADS notebook <../notebooks/parsers/ceads/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/ceads/walkthrough

Caveats
-------

* MARIO currently parses only the verified CEADS provincial MRIO workbook
  family for 2018 and 2020. Other CEADS workbook families should still be
  treated as unsupported until they are checked explicitly.
* The parser reads only the English table sheet, named like
  ``Table_<year>_English Version``. The Chinese sheet is intentionally not
  used.
* The CEADS workbook contains one explicit imports row. MARIO stores that row
  inside ``V`` as ``Imports``.
* The workbook exposes exports as one aggregate external-use column. MARIO
  therefore stores exports in ``Y`` as one exogenous final-demand category for
  each originating province.
