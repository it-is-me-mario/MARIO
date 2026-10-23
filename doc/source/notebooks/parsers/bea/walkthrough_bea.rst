:page-type: Database guide
:summary: Import US supply-use tables from a local BEA workbook.

BEA
===

.. container:: mario-companion

   :download:`Run the notebook <walkthrough_bea.ipynb>`

Select the reporting year and aggregation level. Detail-level tables are available for benchmark years.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_bea(path="/path/to/SUPPLY-USE.xlsx", year=2024, level="summary")

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Where the files come from

   Relevant official pages:

   - `Industry Input-Output Accounts Data <https://www.bea.gov/industry/input-output-accounts-data>`__
   - `Guide to the interactive industry input-output accounts tables <https://www.bea.gov/resources/guide-interactive-industry-input-output-accounts-tables>`__
   - `Direct ``SUPPLY-USE.zip`` bundle <https://apps.bea.gov/industry/release/zip/SUPPLY-USE.zip>`__

   MARIO currently supports only the ``SUPPLY-USE`` bundle. It does not yet parse:

   - ``MAKE-USE-IMPORTS (BEFORE REDEFINITIONS)``
   - ``TOTAL AND DOMESTIC REQUIREMENTS``

.. mario-details:: Supported levels and years

   The parser currently supports three aggregation levels:

   - ``summary``: ``1997`` to ``2024``
   - ``sector``: ``1997`` to ``2024``
   - ``detail``: ``2007``, ``2012``, ``2017``

   These ranges were verified directly on the current official workbook bundle.

.. mario-details:: Accepted path inputs

   ``parse_bea(...)`` accepts any of these:

   - the official ``SUPPLY-USE.zip``
   - one extracted directory containing the BEA workbooks
   - one workbook path inside that directory

   In all cases you still provide:

   - ``year=``
   - ``level=``

.. mario-details:: Expected extracted structure and matrix mapping

   Typical extracted ``SUPPLY-USE`` bundle:

   .. code:: text

      SUPPLY-USE/
      ├── Supply_Summary.xlsx
      ├── Use_Summary.xlsx
      ├── Supply_Sector.xlsx
      ├── Use_Sector.xlsx
      ├── Supply_Detail.xlsx
      └── Use_SUT_Detail.xlsx

   ``level=`` selects the workbook pair and ``year=`` selects one year inside that pair.

   MARIO reads the bundle as a split-native ``SUT``: ``S`` from the domestic-industry block of the supply workbook, ``U`` and ``Yc`` from the use workbook, ``Va`` from the use-workbook footer rows, and ``Vc`` from the supply-side columns such as imports, margins, and product taxes. The result should therefore be treated as a mixed-valuation ``SUT``: basic-price supply and purchaser-price use.

   .. code:: python

      import mario

   .. code:: python

      db = mario.parse_bea(
          path="/path/to/SUPPLY-USE",
          year=2024,
          level="summary",
      )

      db

   .. code:: python

      db = mario.parse_bea(
          path="/path/to/SUPPLY-USE",
          year=2024,
          level="sector",
      )

   .. code:: python

      db = mario.parse_bea(
          path="/path/to/SUPPLY-USE",
          year=2017,
          level="detail",
      )

.. mario-details:: What the parser builds

   MARIO reads the BEA bundle as a split-native ``SUT``:

   - ``S`` from the BEA ``Supply`` workbook
   - ``U`` and ``Yc`` from the BEA ``Use`` workbook
   - ``Va`` from the use-workbook footer rows
   - ``Vc`` from the supply-workbook commodity-side columns for imports, CIF/FOB adjustments, trade and transport margins, and product taxes

   This is therefore a mixed-valuation table:

   - supply is read at basic prices
   - use is read at purchaser prices

   .. code:: python

      base = db["baseline"]
      for name in ["S", "U", "Yc", "Va", "Vc"]:
          print(name, base[name].shape)

.. mario-details:: Caveats

   - ``table="SUT"`` is the only supported mode right now.
   - The parser does not yet expose the separate ``MAKE-USE-IMPORTS (BEFORE REDEFINITIONS)`` bundle.
   - The parser does not treat ``TOTAL AND DOMESTIC REQUIREMENTS`` as raw database inputs.
   - ``detail`` coverage is much narrower than ``summary`` and ``sector`` in the current official release.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
