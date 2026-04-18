WIOD
====

MARIO supports local parsing of the WIOD 2016 Excel workbooks distributed on
the official GGDC release page.

The parser currently supports:

* multiregional ``IOT`` workbooks in current prices;
* multiregional ``IOT`` workbooks in previous-year prices (``_PYP``);
* multiregional international ``SUT`` workbooks;
* national ``IOT`` workbooks;
* national ``SUT`` workbooks;
* optional socio-economic accounts imported through ``add_extensions=...``.

For this source, the most useful documentation format is a notebook-driven one:
this landing page stays short, while one practical notebook covers where to
download the files, direct-file versus directory parsing, ``year=``,
``country=``, ``add_extensions=``, the WIOD download helpers, and the
difference between ``MRIO`` and national workflows.

Relevant source links
---------------------

* official WIOD 2016 release page:
  `GGDC WIOD 2016 release <https://www.rug.nl/ggdc/valuechain/wiod/wiod-2016-release?lang=en>`_;
* MRIO IOT, current prices:
  `Dataverse 199104 <https://dataverse.nl/api/access/datafile/199104>`_;
* MRIO IOT, previous-year prices:
  `Dataverse 199102 <https://dataverse.nl/api/access/datafile/199102>`_;
* MRIO international SUT:
  `Dataverse 199100 <https://dataverse.nl/api/access/datafile/199100>`_;
* national IOT bundle:
  `Dataverse 199099 <https://dataverse.nl/api/access/datafile/199099>`_;
* national SUT bundle:
  `Dataverse 199096 <https://dataverse.nl/api/access/datafile/199096>`_;
* socio-economic accounts:
  `Dataverse 199095 <https://dataverse.nl/api/access/datafile/199095>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_wiod(...) <../api_document/mario.parse_wiod>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  one WIOD workbook or one directory containing multiple WIOD workbooks;
* ``table``:
  choose ``"IOT"`` or ``"SUT"``;
* ``year``:
  use it when one directory contains multiple candidate files. For national
  WIOD workbooks it is mandatory, because one workbook contains multiple years;
* ``country``:
  useful when one directory contains multiple national workbooks;
* ``add_extensions``:
  optional path to ``Socio_Economic_Accounts.xlsx``. When passed, MARIO
  imports the socio-economic extensions into ``E`` for IOTs and into ``Ea``
  for SUTs;
* ``row_mode``:
  only relevant for the international WIOD ``SUT`` workbook. Use
  ``"external_account"`` to remove ``ROW`` from the endogenous region set and
  reclassify those flows into ``Va`` and ``VY``. Use ``"legacy_region"`` to
  keep the previous parser behaviour.

Download workflow
-----------------

Automatic download is available:

* ``mario.download_wiod2016(...)``
* ``mario.download_wiod2016_iot_pyp(...)``
* ``mario.download_wiod2016_national_iot(...)``
* ``mario.download_wiod2016_national_sut(...)``
* ``mario.download_wiod2016_socioeconomic_accounts(...)``

Typical usage
-------------

Direct path to one multiregional IOT workbook:

.. code-block:: python

   import mario

   db = mario.parse_wiod(
       path="/path/to/WIOT2014_Nov16_ROW.xlsb",
       table="IOT",
   )

Directory containing multiple national workbooks:

.. code-block:: python

   import mario

   db = mario.parse_wiod(
       path="/path/to/wiod_national_directory",
       table="SUT",
       country="ITA",
       year=2014,
   )

Socio-economic accounts:

.. code-block:: python

   import mario

   db = mario.parse_wiod(
       path="/path/to/WIOT2014_PYP_Nov16_ROW.xlsb",
       table="IOT",
       add_extensions="/path/to/Socio_Economic_Accounts.xlsx",
   )

Warnings
--------

.. warning::

   The international WIOD ``SUT`` workbook does not provide a fully endogenous
   ``ROW`` economy. In the source file, ``ROW`` appears only on the commodity
   origin side of the ``USE`` table, not as a complete region with supply,
   value added, and final demand.

.. warning::

   Because of that source structure, the international ``SUT`` parser exposes
   two modes:

   * ``row_mode="external_account"``:
     the default and recommended mode. ``ROW`` is removed from the endogenous
     region set and reclassified as an external account through ``Va`` and
     ``VY``;
   * ``row_mode="legacy_region"``:
     the previous parser behaviour, kept for backward compatibility.

.. warning::

   The international ``SUT`` treatment should still be considered under
   investigation. The parser now makes the modelling choice explicit, but the
   underlying WIOD source does not uniquely identify a complete endogenous
   ``ROW`` region.

Notebook Walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`WIOD parser walkthrough <../notebooks/parsers/wiod/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the WIOD notebook <../notebooks/parsers/wiod/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/wiod/walkthrough
