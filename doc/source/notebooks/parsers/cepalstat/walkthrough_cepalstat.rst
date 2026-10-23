:page-type: Database guide
:summary: Import supported national supply-use and input-output releases.

CEPALSTAT
=========

.. container:: mario-companion

   :download:`Download notebook <walkthrough_cepalstat.ipynb>`

This parser is beta: supported file families and years differ by country. Select the observation year within the source release.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_cepalstat(path="/path/to/COL_COU_2023.zip", table="SUT", year=2019)

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Relevant source page

   - Official CEPALSTAT repository: `Repository of supply and use tables and input-output tables in Latin America and the Caribbean <https://statistics.cepal.org/repository/cou-mip/index.html?lang=en>`__

   MARIO does not provide an automatic downloader for this source. The expected workflow is to parse local files that you already downloaded from the repository.

.. mario-details:: Expected path structure

   ``path`` can point either to one downloaded CEPALSTAT bundle archive or to a directory collecting multiple bundle archives.

   Typical direct-file inputs look like:

   .. code:: text

      /path/to/COL_COU_2023.zip
      /path/to/DOM_MIP_2012.zip

   When you want MARIO to select from a local directory, a practical layout is:

   .. code:: text

      cepalstat_directory/
      |-- ARG_COU_2020.zip
      |-- BRA_COU_2020.zip
      |-- COL_COU_2023.zip
      |-- DOM_MIP_2012.zip
      `-- CHI_MIP_2020.zip

   MARIO does not require every country bundle to follow one identical internal workbook engineering, but it does expect CEPALSTAT-style bundle names and local files that you already downloaded from the repository.

.. mario-details:: Supported layout families

   CEPALSTAT is not technically uniform, so MARIO resolves a set of supported families behind the same public API.

   Current ``SUT`` support includes:

   - integrated offer/use workbooks such as Colombia;
   - two-sheet workbooks such as Argentina;
   - split offer/demand workbooks such as Brazil;
   - multi-cuadro workbooks such as Chile.

   Current ``IOT`` support includes:

   - direct matrix workbooks such as Dominican Republic and Guatemala;
   - cuadro workbooks such as Colombia;
   - symmetric workbooks such as Argentina;
   - demand-at-basic-prices workbooks such as Brazil;
   - matrix workbooks such as Chile.

   .. code:: python

      import mario

.. mario-details:: Parse one SUT bundle directly

   Use ``year=`` when the bundle contains more than one annual workbook or when the workbook itself exposes more than one reference year.

   .. code:: python

      db = mario.parse_cepalstat(
          path="/path/to/COL_COU_2023.zip",
          table="SUT",
          year=2019,
      )

      db

.. mario-details:: Parse one IOT bundle directly

   Use ``iot_mode=`` when the bundle exposes both ``PxP`` and ``AxA``, or set ``iot_mode="auto"`` when the workbook family should decide automatically.

   .. code:: python

      db = mario.parse_cepalstat(
          path="/path/to/DOM_MIP_2012.zip",
          table="IOT",
          iot_mode="pxp",
          calc_all=False,
      )

      db

.. mario-details:: Parse from one directory containing multiple bundles

   When ``path`` points to a directory, ``country=`` and ``year=`` are the main selectors. This is useful when the local CEPALSTAT folder contains many countries and vintages.

   .. code:: python

      db = mario.parse_cepalstat(
          path="/path/to/cepalstat_directory",
          table="IOT",
          country="ARG",
          year=1997,
          iot_mode="auto",
          calc_all=False,
      )

      db

.. mario-details:: Warnings you should expect

   Some CEPALSTAT families require controlled fallbacks. Typical examples are:

   - the offer and use product sets differ slightly, so MARIO keeps the common intersection and warns;
   - some ``SUT`` families expose only aggregate value added rather than the full breakdown;
   - some ``IOT`` families do not expose explicit factor rows, so MARIO reconstructs aggregate value added residually and warns.

   These warnings are informative: they mark real differences in the source layout, not parser noise.

.. mario-details:: Practical recommendation

   For CEPALSTAT, start by validating one country family at a time. The repository is coherent at the metadata level, but the actual workbook engineering differs a lot across countries and vintages. If you are building reproducible ingestion scripts, keep the source file names and years explicit rather than relying on broad directory parsing when avoidable.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
