:page-type: Database guide
:summary: Import OECD ICIO, national IOT or supply-use data.

OECD
====

.. container:: mario-companion

   :download:`Download notebook <walkthrough_oecd.ipynb>`

The dataset selector identifies different source families. National IOT and SUT workflows use different inputs and country/year options.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_oecd(path="/path/to/ICIO2022_SML.csv", dataset="ICIO")

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Relevant source pages

   - OECD ICIO page: `Inter-country input-output tables <https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html>`__
   - OECD national IOT page: `Input-output tables <https://www.oecd.org/en/data/datasets/input-output-tables.html>`__
   - OECD SUT page: `Supply and use tables <https://www.oecd.org/en/data/datasets/supply-and-use-tables.html>`__

   MARIO does not download OECD files automatically. For ``ICIO`` and national ``IOT``, the expected workflow is to download the source files manually and then point the parser to the local files. For ``SUT``, MARIO pulls the data directly from the official OECD SDMX API.

.. mario-details:: Key arguments

   The key public arguments are:

   - ``path``: one local OECD file or one directory containing multiple OECD files;
   - ``dataset``: choose ``"ICIO"``, ``"IOT"``, or ``"SUT"``;
   - ``year``: used to disambiguate directories and required for ``dataset="SUT"``;
   - ``country``: used to disambiguate national IOT files and required for ``dataset="SUT"``.

.. mario-details:: Direct file path vs directory path

   Use a **direct file path** when you already know the exact OECD file to parse. This is the simplest workflow and usually means you do not need any further disambiguation.

   Use a **directory path** when you keep several OECD files together. In that case MARIO scans the directory and then uses ``dataset=``, ``year=``, and sometimes ``country=`` to pick the correct candidate.

.. mario-details:: Expected local layouts and caveats

   Typical local layouts are:

   For ``dataset="ICIO"``:

   .. code:: text

      OECD/ICIO/
      ├── Extended/
      │   └── 2022.csv
      └── Regular/
          └── 2022_SML.csv

   For ``dataset="IOT"``:

   .. code:: text

      OECD/IOT/TTL/
      └── ITA2022ttl.csv

   For ``dataset="SUT"``, ``path`` is not required; use ``country=`` and ``year=`` to select the SDMX slice.

   Practical caveats:

   - the ``IOT`` workflow supports only the OECD accounts labeled as total table;
   - in the extended ``ICIO`` release, ``CN1`` and ``CN2`` are aggregated automatically into ``CHN``, and ``MX1`` and ``MX2`` into ``MEX``.

   .. code:: python

      import mario

.. mario-details:: Parse one explicit OECD ICIO csv

   Choose **Regular** (``2022_SML.csv``) or **Extended** (``2022.csv``) and pass the exact local file. Both editions have been parsed and checked for every year from **1995 to 2022** in the Database explorer.

   Extended separates parts of Chinese and Mexican production in its original files. MARIO sums ``CN1``/``CN2`` into ``CHN`` and ``MX1``/``MX2`` into ``MEX``, so both editions expose the same national regions and industry classification after parsing. The downloadable set lists describe these parsed sets.

   For a directory containing several years, point ``path`` to the specific ``Regular`` or ``Extended`` folder and also pass ``year=2022``. Use ``calc_all=False`` when you only need the original matrices and sets.

   The browser sums the ``VA`` row for value added. GDP also includes ``TLS`` on intermediate and final uses; the final-use taxes must be read from the original CSV because MARIO’s ``V`` contains industry columns only. These ICIO files are in nominal million USD and do not include an emissions extension.

   .. code:: python

      db = mario.parse_oecd(
          path="/path/to/2022_SML.csv",
          dataset="ICIO",
      )

      db

.. mario-details:: Parse one national OECD total-table IOT

   Use this when you want one national total table such as ``CZE2014ttl.csv``.

   .. code:: python

      db = mario.parse_oecd(
          path="/path/to/ITA2022ttl.csv",
          dataset="IOT",
      )

      db

.. mario-details:: Parse one OECD SUT directly from the SDMX API

   In principle, this workflow does not require a local ``path``, but it does require ``country=`` and ``year=``.

   At the moment we do **not** show an executable example in the documentation because the official OECD SDMX endpoint can intermittently refuse the request with HTTP errors such as ``403 Forbidden``. When that happens, the issue is upstream of MARIO’s SUT transformation logic and the parse cannot complete.

   For this reason, treat ``dataset="SUT"`` as temporarily unstable in the public docs until the OECD SDMX service becomes reliably accessible again.

   .. code:: python

      db = mario.parse_oecd(
          dataset="SUT",
          country="ITA",
          year=2022,
      )

      db

.. mario-details:: Environmental extensions

   **Warning.** The OECD parser currently exposes the economic tables only.

   ``ICIO``, national ``IOT``, and ``SUT`` tables are therefore **not** parsed as environmentally extended tables in MARIO at the moment.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
