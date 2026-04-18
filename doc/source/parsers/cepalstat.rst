CEPALSTAT
=========

MARIO supports local parsing of selected CEPALSTAT ``COU`` and ``MIP`` bundles
distributed through the official ECLAC repository.

The repository is not published in one uniform technical format, so the parser
works through layout-family detection rather than one single workbook template.
At the moment MARIO supports:

* ``SUT`` integrated offer/use workbooks, such as Colombia;
* ``SUT`` two-sheet workbooks, such as Argentina;
* ``SUT`` split offer/demand workbooks, such as Brazil;
* ``SUT`` multi-cuadro workbooks, such as Chile;
* ``IOT`` direct symmetric matrix workbooks, such as Dominican Republic and
  Guatemala;
* ``IOT`` cuadro workbooks, such as Colombia;
* ``IOT`` symmetric workbooks, such as Argentina;
* ``IOT`` demand-at-basic-prices workbooks, such as Brazil;
* ``IOT`` matrix workbooks, such as Chile.

For this source, the most useful documentation format is a notebook-driven one:
this landing page stays short, while one practical notebook covers bundle
selection, ``table=``, ``year=``, ``country=``, ``iot_mode=``, and the main
parser caveats by family.

Relevant source links
---------------------

* official CEPALSTAT repository:
  `Repository of supply and use tables and input-output tables in Latin America and the Caribbean <https://statistics.cepal.org/repository/cou-mip/index.html?lang=en>`_;
* ECLAC presentation note for the repository:
  `ECLAC Statistics Division presents the repository <https://www.cepal.org/en/notes/eclac-statistics-division-presents-repository-supply-and-use-tables-and-input-output-tables>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_cepalstat(...) <../api_document/mario.parse_cepalstat>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  one local CEPALSTAT workbook, zip bundle, or one directory containing
  multiple bundles;
* ``table``:
  choose between ``"SUT"`` and ``"IOT"``;
* ``year``:
  use it when one bundle contains multiple yearly workbooks or when one
  directory contains more than one candidate file;
* ``country``:
  useful to disambiguate directories containing several country bundles;
* ``iot_mode``:
  only relevant for ``table="IOT"``. Use ``"pxp"``, ``"axa"``, or ``"auto"``.
  Some bundles expose both representations, while others expose only one.

Typical usage
-------------

Direct path to one CEPALSTAT SUT bundle:

.. code-block:: python

   import mario

   db = mario.parse_cepalstat(
       path="/path/to/COL_COU_2023.zip",
       table="SUT",
       year=2019,
   )

Direct path to one CEPALSTAT IOT bundle:

.. code-block:: python

   import mario

   db = mario.parse_cepalstat(
       path="/path/to/DOM_MIP_2012.zip",
       table="IOT",
       iot_mode="pxp",
   )

Directory containing multiple CEPALSTAT bundles:

.. code-block:: python

   import mario

   db = mario.parse_cepalstat(
       path="/path/to/cepalstat_directory",
       table="IOT",
       country="ARG",
       year=1997,
       iot_mode="auto",
   )

Caveats
-------

* CEPALSTAT is currently a local-file parser only; MARIO does not provide a
  downloader for this source;
* not every repository family is implemented yet; unsupported families are
  rejected explicitly;
* some bundles expose only one matrix representation even if ``iot_mode`` is
  set differently;
* some families do not expose the same level of detail on the factor side:
  for example, some Argentina ``SUT`` bundles only expose aggregate value
  added, while some Brazil ``IOT`` bundles require a residual value-added
  reconstruction.

Notebook Walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`CEPALSTAT parser walkthrough <../notebooks/parsers/cepalstat/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the CEPALSTAT notebook <../notebooks/parsers/cepalstat/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/cepalstat/walkthrough
