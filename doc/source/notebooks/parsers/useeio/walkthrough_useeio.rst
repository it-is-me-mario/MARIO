:page-type: Database guide
:summary: Import the supported USEEIO workbook families as supply-use tables.

USEEIO
======

.. container:: mario-companion

   :download:`Download notebook <walkthrough_useeio.ipynb>`

Workbook release labels and economic source years can differ. These models are imported as SUTs, with commodity-side satellite accounts.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_useeio(path="/path/to/USEEIOv2.5-yellowthroat-22.xlsx", format="auto")

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Relevant source pages

   - Data.gov catalog page: `USEEIO v2.5 models <https://catalog.data.gov/dataset/useeio-v2-5-models>`__
   - EPA model page: `USEEIO models <https://www.epa.gov/land-research/us-environmentally-extended-input-output-useeio-models>`__
   - EPA technical page: `USEEIO technical content <https://www.epa.gov/land-research/us-environmentally-extended-input-output-useeio-technical-content>`__
   - Framework and workbook format reference: `USEPA/useeior <https://github.com/USEPA/useeior>`__

   MARIO does not download USEEIO workbooks automatically. The expected workflow is to download one workbook manually and then point the parser to that local file.

.. mario-details:: What MARIO currently parses

   The current backend is intentionally narrow:

   - it parses the local Excel workbook export;
   - it currently supports only the verified ``v2.5`` workbook structure;
   - it does **not** parse the full ``useeior`` build framework directly.

   This is why the parser exposes an explicit ``format=`` argument even though only one format is supported today.

.. mario-details:: What the main model aliases mean

   The official ``USEPA/USEEIO`` model registry distinguishes model **aliases** such as ``yellowthroat``, ``kingbird``, or ``catbird``. These aliases describe the **content** of the model, not the workbook layout.

   For the currently relevant national ``v2.5`` families:

   - ``yellowthroat``: BEA Summary 2017, GLORIA-backed, with GHG and material-footprint extensions;
   - ``waxwing``: BEA Detail 2017, GLORIA-backed, with GHG and material-footprint extensions;
   - ``kingbird``: BEA Summary 2017, EXIOBASE-backed, with GHG extensions;
   - ``kinglet``: BEA Detail 2017, EXIOBASE-backed, with GHG extensions;
   - ``oriole``: BEA Summary 2017, CEDA-backed, with GHG extensions;
   - ``catbird``: BEA Detail 2017, CEDA-backed, with GHG extensions.

   The current MARIO parser targets these national workbook exports, not the ``StateEEIO`` families that are listed in the same upstream registry.

   One caution from the upstream registry: ``USEEIO v2.5-waxwing-22`` is marked as deprecated because it was published with an incorrect extension and replaced upstream by ``v2.5.1-waxwing-22``.

.. mario-details:: What `format` means

   ``format=`` is a **parser-side** selector. It tells MARIO what workbook organization it should expect.

   So:

   - ``yellowthroat`` and ``kingbird`` are different models;
   - but they can still share the same parser ``format`` if their workbook tabs and matrix semantics are organized in the same way.

   Today the parser supports:

   - ``format="auto"``: inspect the workbook and resolve the known layout automatically;
   - ``format="v2.5_workbook"``: force the currently verified workbook structure.

   For this verified format, MARIO expects the workbook to expose the standard ``useeior`` export components such as ``V``, ``U``, ``B``, ``q``, ``commodities_meta``, ``final_demand_meta``, and ``value_added_meta``.

.. mario-details:: Key arguments and workbook layout

   Key public arguments:

   - ``path``: one local ``USEEIO*.xlsx`` workbook or one directory containing one workbook;
   - ``format``: use ``"auto"`` or ``"v2.5_workbook"``;
   - ``table``: currently only ``"SUT"`` is supported.

   Typical local layout:

   .. code:: text

      USEEIO/
      ├── USEEIOv2.5-yellowthroat-22.xlsx
      ├── USEEIOv2.5-kingbird-22.xlsx
      └── USEEIOv2.5-catbird-22.xlsx

   Inside the workbook, MARIO expects the ``useeior`` export sheets such as ``V``, ``U``, ``B``, ``q``, ``commodities_meta``, ``final_demand_meta``, and ``value_added_meta``. The workbook release label can differ from the internal IO year stored in the parsed metadata.

   .. code:: python

      import mario

.. mario-details:: Parse one explicit workbook

   Use this when you already know the exact workbook you want to ingest.

   .. code:: python

      db = mario.parse_useeio(
          path="/path/to/USEEIOv2.5-yellowthroat-22.xlsx",
          format="auto",
      )

.. mario-details:: Pin the workbook format explicitly

   If you want to be strict and avoid ``auto`` detection, pin the verified format directly.

   .. code:: python

      db = mario.parse_useeio(
          path="/path/to/USEEIOv2.5-waxwing-22.xlsx",
          format="v2.5_workbook",
      )

.. mario-details:: Parse from a directory

   You can also point the parser to a directory, but only when that directory contains a single workbook.

   .. code:: python

      db = mario.parse_useeio(
          path="/path/to/USEEIO",
          model_alias="yellowthroat",
          release_year=2022,
      )

.. mario-details:: Why MARIO parses USEEIO as a SUT

   For the verified workbook family, the structure is closer to a split-native ``SUT`` than to a symmetric ``IOT``:

   - ``V`` is the make matrix;
   - ``U`` contains the use block plus final demand columns and value-added rows;
   - ``B`` is a direct environmental coefficient matrix;
   - ``q`` provides the commodity-output vector used to reconstruct direct environmental flows.

   So the parser returns the native ``S``, ``U``, ``Yc``, ``Va``, ``Ec``, … blocks rather than forcing a symmetric ``IOT`` interpretation.

.. mario-details:: Commodity-side environmental extension

   One important detail of the verified ``v2.5`` workbook layout is that ``B`` is aligned with the **commodity** axis. Because of that, MARIO reconstructs the direct extension on the commodity side:

   - ``Ec = B * q``

   This is deliberate. For this workbook family, ``Ec`` is the correct direct extension block, while ``Ea`` stays zero-filled.

.. mario-details:: Release year versus internal IO year

   Some USEEIO workbooks expose a release label that differs from the internal IO year used by the model. MARIO stores the **internal IO year** in the parsed database metadata.

   So if a workbook is labelled like ``...-22.xlsx`` but the internal economic base year is ``2017``, MARIO will record ``2017`` as ``db.meta.year``.

   .. code:: python

      db.meta.name, db.meta.year, db.meta.price

.. mario-details:: Current limitations

   - only the verified ``v2.5_workbook`` format is supported;
   - there is no MARIO downloader yet;
   - the parser targets the workbook export, not the full ``useeior`` framework pipeline.

   That is also why keeping ``format=`` explicit is useful: it leaves room for future workbook families without pretending they are already supported.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
