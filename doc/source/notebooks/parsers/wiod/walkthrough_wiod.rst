:page-type: Database guide
:summary: Import WIOD world or national input-output and supply-use tables.

WIOD
====

.. container:: mario-companion

   :download:`Run the notebook <walkthrough_wiod.ipynb>`

Use the matching workbook family and valuation. SUT, national and previous-year-price workbooks follow separate branches.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_wiod(path="/path/to/WIOT2014_Nov16_ROW.xlsb", table="IOT")

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Table conventions

   Current IOTs and international SUTs are in **million US dollars at current prices**. PYP IOTs use **previous-year prices and previous-year US dollars**; they are not comparable directly with current-price World Bank GDP. For international SUTs, ``row_mode="external_account"`` preserves ROW imports in ``Va`` and ``VY``; ROW is not an endogenous Region and a complete World total is unavailable.

   The optional Socio-Economic Accounts include employment and capital. They are not environmental accounts and do not provide GHG. Their source covers the individual countries; ROW extension entries are placeholders. SUT factor accounts include ROW imports alongside the published factors. GDP is value added at basic prices plus net product taxes on intermediate and final uses, including the published ``VY`` tax row for SUTs.

   The examples for national tables remain below as parser documentation; national files are outside this multiregional browser inventory.

.. mario-details:: Relevant source pages

   - Official WIOD 2016 release page: `GGDC WIOD 2016 release <https://www.rug.nl/ggdc/valuechain/wiod/wiod-2016-release?lang=en>`__
   - MRIO IOT, current prices: `Dataverse 199104 <https://dataverse.nl/api/access/datafile/199104>`__
   - MRIO IOT, previous-year prices: `Dataverse 199102 <https://dataverse.nl/api/access/datafile/199102>`__
   - MRIO international SUT: `Dataverse 199100 <https://dataverse.nl/api/access/datafile/199100>`__
   - National IOT bundle: `Dataverse 199099 <https://dataverse.nl/api/access/datafile/199099>`__
   - National SUT bundle: `Dataverse 199096 <https://dataverse.nl/api/access/datafile/199096>`__
   - Socio-economic accounts: `Dataverse 199095 <https://dataverse.nl/api/access/datafile/199095>`__

.. mario-details:: Key arguments

   The key public arguments are:

   - ``path``: one workbook or one directory containing multiple WIOD workbooks;
   - ``table``: choose ``"IOT"`` or ``"SUT"``;
   - ``year``: used to disambiguate directories and mandatory for national workbooks with multi-year content;
   - ``country``: useful when one directory contains multiple national workbooks;
   - ``add_extensions``: optional path to ``Socio_Economic_Accounts.xlsx``;
   - ``row_mode``: only relevant for the international ``SUT`` workbook.

.. mario-details:: Direct file path vs directory path

   Use a **direct workbook path** when you already know the exact file to parse. This is the simplest case and often means you do not need ``year=`` or ``country=``.

   Use a **directory path** when you keep several WIOD files together. In that case MARIO scans the directory and then uses ``table=``, ``year=``, and optionally ``country=`` to pick the correct file.

.. mario-details:: Example local layouts and caveats

   Typical extracted layout:

   .. code:: text

      WIOD/
      ├── WIOTS_in_EXCEL/
      │   └── WIOT2014_Nov16_ROW.xlsb
      ├── WIOTS_PYP_in_EXCEL/
      │   └── WIOT2014_PYP_Nov16_ROW.xlsb
      ├── NIOTS/
      │   └── ITA_NIOT_nov16.xlsx
      ├── SUT_national/
      │   └── ITA_SUT_nov16.xlsx
      ├── SUT_international/
      │   └── intsut14_nov16.xlsb
      └── Socio_Economic_Accounts.xlsx

   National ``IOT`` and ``SUT`` workbooks contain multiple years in one file, so ``year=`` is mandatory for those inputs. For the international ``SUT``, ``row_mode="external_account"`` is the recommended mode because ``ROW`` is not published as a complete endogenous economy.

   .. code:: python

      import mario

.. mario-details:: Optional download step

   MARIO provides dedicated WIOD download helpers instead of one generic downloader for every asset.

   .. code:: python

      mario.download_wiod2016(
          path="/path/to/wiod",
          table="IOT",
      )

      mario.download_wiod2016_iot_pyp("/path/to/wiod_pyp")
      mario.download_wiod2016_national_iot("/path/to/wiod_national_iot")
      mario.download_wiod2016_national_sut("/path/to/wiod_national_sut")
      mario.download_wiod2016_socioeconomic_accounts("/path/to/wiod_extensions")

.. mario-details:: Parse one explicit MRIO IOT workbook

   Use this when you want to point MARIO to one specific WIOD multiregional IOT file.

   .. code:: python

      db = mario.parse_wiod(
          path="/path/to/WIOT2014_Nov16_ROW.xlsb",
          table="IOT",
      )

   .. code:: python

      db

.. mario-details:: Parse one explicit MRIO IOT workbook in previous-year prices

   The ``_PYP`` variant is selected from the filename directly. No extra parser flag is needed.

   .. code:: python

      db = mario.parse_wiod(
          path="/path/to/WIOT2014_PYP_Nov16_ROW.xlsb",
          table="IOT",
      )

.. mario-details:: Parse one international SUT workbook

   This is the source where the treatment of ``ROW`` matters. With ``row_mode="external_account"``, MARIO also preserves the published factor rows on domestic final uses in ``VY``, including signed taxes and adjustments.

   .. code:: python

      db = mario.parse_wiod(
          path="/path/to/intsut14_nov16.xlsb",
          table="SUT",
          row_mode="external_account",
      )

.. mario-details:: Parse one national IOT workbook

   National WIOD ``IOT`` workbooks contain multiple years in one workbook, so ``year=`` is required.

   .. code:: python

      db = mario.parse_wiod(
          path="/path/to/ITA_NIOT_nov16.xlsx",
          table="IOT",
          year=2014,
      )

.. mario-details:: Parse one national SUT workbook

   National WIOD ``SUT`` workbooks also require ``year=``.

   .. code:: python

      db = mario.parse_wiod(
          path="/path/to/ITA_SUT_nov16.xlsx",
          table="SUT",
          year=2014,
      )

.. mario-details:: Parse from a directory containing multiple WIOD files

   This is the important case when you keep several WIOD files together. Use ``year=`` to select the year and ``country=`` when the directory contains multiple national workbooks.

   .. code:: python

      db = mario.parse_wiod(
          path="/path/to/wiod_directory",
          table="SUT",
          country="ITA",
          year=2014,
      )

.. mario-details:: Add socio-economic extensions

   When ``add_extensions=`` is provided, MARIO imports ``Socio_Economic_Accounts.xlsx`` as satellite extensions.

   - for ``IOT``, they populate ``E``;
   - for ``SUT``, they populate ``Ea`` and keep ``Ec`` zero-filled.

   .. code:: python

      db = mario.parse_wiod(
          path="/path/to/WIOT2014_Nov16_ROW.xlsb",
          table="IOT",
          add_extensions="/path/to/Socio_Economic_Accounts.xlsx",
      )

.. mario-details:: Warnings to expect

   Typical parser warnings or important notes are:

   - unreadable ``.xlsb`` files stored as cloud placeholders instead of real local files;
   - ambiguous directory selections when ``year=`` or ``country=`` is missing;
   - notes in ``db.meta_history`` when the international ``SUT`` parser reclassifies ``ROW`` under ``row_mode="external_account"``.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
