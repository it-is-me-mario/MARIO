:page-type: Database guide
:summary: Import FIGARO input-output, supply-use and national accounting tables.

FIGARO
======

.. container:: mario-companion

   :download:`Download notebook <walkthrough_figaro.ipynb>`

Use :func:`mario.parse_figaro` to read Eurostat's FIGARO tables. Choose the
table format for your analysis: an **IOT** for sector transactions, a **SUT**
for separate activities and products, or a **NAM** to follow production,
institutional income, capital and financial transactions together.

IOT and SUT inputs come from the Eurostat API, with optional local caching.
NAM inputs are downloaded separately and read from local files. The source
inventory below covers IOT/SUT; NAM memberships are read from the selected
national ledger.

Choose a table
--------------

.. mario-switch::
   :label: FIGARO table format
   :hint: Choose a format to see its inputs and import call.

   .. mario-switch-option:: figaro-iot
      :badge: IOT
      :title: Input-output table
      :text: Product-by-product or industry-by-industry, from the API or cache.

   .. mario-switch-option:: figaro-sut
      :badge: SUT
      :title: Supply-use table
      :text: Separate activities and commodities, from the API or cache.

   .. mario-switch-option:: figaro-nam
      :badge: NAM
      :title: National accounting matrix
      :text: A national ledger, from a local CSV release or XLSX workbook.

For IOT/SUT, ``path`` is a **cache directory**: matching cached requests are
reused and missing requests are downloaded. A first import can download a
large table. Add ``countries=["IT", "FR"]`` to request a smaller country
subset; this does not constitute a complete global system.

.. _figaro-iot:
.. _iot-and-sut-api-import:

Import an IOT
-------------

Choose a reference year and an IOT system. ``iot_mode="product"`` reads the
product-by-product table; use ``"industry"`` for industry-by-industry.

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_figaro(
          table="IOT", year=2023, iot_mode="product",
          path="figaro_cache/iot_product",
      )

   .. container:: mario-result

      **Result** · An IOT with transactions ``Z``, final demand ``Y`` and
      factors ``V``. Products or industries occupy the ``Sector`` set,
      according to ``iot_mode``.

.. _figaro-sut:

Import a SUT
------------

The parser reads the matching supply and use dataflows for the requested year.
Both API responses are cached in the same directory.

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_figaro(
          table="SUT", year=2023, path="figaro_cache/sut",
      )

   .. container:: mario-result

      **Result** · A SUT with separate ``Activity`` and ``Commodity`` sets,
      supply ``S``, intermediate use ``U``, final demand ``Yc``/``Ya`` and
      factors ``Va``/``Vc``/``VY``.

.. _figaro-nam:
.. _local-national-accounting-matrices:

Import a NAM
------------

Download a CSV release or a national workbook from
`Eurostat's FIGARO-NAM releases
<https://ec.europa.eu/eurostat/web/experimental-statistics/national-accounting-matrices-figaro>`__.
For the all-country CSV, select **exactly one reporting economy** explicitly:

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_figaro(
          "FIGARO_NAM_2023.csv", table="NAM", countries="IT",
      )

   .. container:: mario-result

      **Result** · A national ledger with production, institutional and
      financial accounts. Import blocks retain observed origin/product
      detail. The reference year is read from the file.

Here ``path`` is a **source file**. No API request is made. ``countries``
selects the reporting economy, while foreign import origins remain descriptors
of that ledger. Eurostat publishes FIGARO-NAM as experimental statistics.
Source reconciliation checks reproduction of the ledger; it reports account
imbalance separately and does not choose a model closure.

.. _other-local-input-forms:

.. mario-details:: National workbooks and several reporting economies

   A national XLSX workbook needs no country selection:

   .. code-block:: python

      db = mario.parse_figaro("FIGARO_NAM_IT_2023.xlsx", table="NAM")

   The reader uses worksheet ``T02`` with its metadata, account headers,
   square ledger and appended bilateral import detail. T02 CSV worksheet
   exports retaining that structure are also accepted.

   Pass a list of national workbooks, or a directory containing them, to
   retain several independent ledgers:

   .. code-block:: python

      db = mario.parse_figaro(
          ["FIGARO_NAM_IT_2023.xlsx", "FIGARO_NAM_FR_2023.xlsx"], table="NAM",
      )

   The ledgers must share a reference year and each reporting economy must
   occur once. This does not consolidate them into an interregional system.
   ``countries`` can select reporting economies from the supplied workbooks;
   ``year`` can check their source period. Pass an all-country bulk CSV as
   one file, separately from workbooks or other releases.

Inspect the imported model
--------------------------

For any format, inspect its sets, regions and units before calculating:

.. code-block:: python

   db.get_index("all")
   db.get_index("Region")
   db.units

Evaluating ``db`` also shows the table format, scenarios and set sizes.
IOT/SUT regions identify the economies represented in the production system;
NAM regions identify the reporting national ledgers, including their external
accounts.

Continue with :doc:`database inspection </user_guide/inspection/basic_inspections>`
and :doc:`matrix calculations </user_guide/inspection/compute_matrices>`.
The format guides explain the relevant sets and equations:
:doc:`IOT </get_started/table_formats/iot>`,
:doc:`SUT </get_started/table_formats/sut>` and
:doc:`NAM </get_started/table_formats/nam>`.

A FIGARO-NAM can also produce a national SUT or IOT with ``db.to_sut()`` or
``db.to_iot(method="B")``. See the
:doc:`NAM conversion guide </user_guide/transformations/nam_to_sut>` for its
account mapping, import aggregation and scenario handling. A projected NAM
and a separately published SUT need not share the same source revision.

.. _inputs-and-options:

Source conventions and checks
-----------------------------

Values use **million EUR**. IOT/SUT products follow CPA 2.1 and activities
NACE Rev. 2; IOT values are at current basic prices. NAM inputs retain the
FIGARO-NAM valuation, with workbook unit/valuation labels checked on import.
The reference year and publication edition are separate: record the actual
source files or cache metadata when comparing releases.

These inputs provide economic accounts. MARIO's placeholder satellite rows
are not measured environmental data; emissions require separate sources.

.. mario-details:: IOT/SUT API requests and caches

   ``year`` is required. ``iot_mode="auto"`` defaults to the product IOT;
   it does not choose the table format. The supported monetary ``unit`` is
   ``"MIO_EUR"``. See the :doc:`parser reference
   </api_document/mario.parse_figaro>` for all arguments.

   The cache key includes dataflow, year, unit, country selection and
   factor-row selection. Keep the generated CSV filenames and JSON sidecars.
   Without a matching cache, requests are chunked by origin country to
   respect Eurostat extraction limits.

   The dataflow suffix is selected from the reference year:

   * 2010–2013: ``s1``, ``u1``, ``ip1``, ``ii1``.
   * 2014–2017: ``s2``, ``u2``, ``ip2``, ``ii2``.
   * 2018–2021: ``s3``, ``u3``, ``ip3``, ``ii3``.
   * 2022 onwards: ``s4``, ``u4``, ``ip4``, ``ii4``.

   For example, a 2023 SUT uses ``naio_10_fcp_s4`` and
   ``naio_10_fcp_u4``. These suffixes partition reference years; they do not
   identify publication editions. Supply has one ``geo`` dimension, placed
   on both axes of ``S``; use and IOT flows retain origin and destination.

   Domestic factor rows populate ``V`` for an IOT and ``Va`` for a SUT.
   GDP requires D1 + D29X39 + B2A3G plus net product taxes D21X31 on
   intermediate **and final** uses. The IOT ``V`` contains intermediate
   taxes only; retain the source cache for final-use taxes. Residence-purchase
   adjustment rows are excluded from this income calculation.

.. _check-the-import-audit:

.. mario-details:: NAM source checks and audit

   The published bulk CSV uses ``base,ctr,Set_i,m,Set_j,value``. ``base``
   supplies the year, ``m`` the reporting economy and foreign ``ctr`` rows
   its bilateral imports. The reader streams the selected ledger in chunks.
   Exports use national ``S2`` totals, without adding outgoing bilateral
   rows again. Omitted observations mean zero within the supported source
   classification, including wholly zero accounts.

   Both CSV and workbook readers check source identities, ownership of
   nonzero square cells, import-detail reconciliation and reconstruction
   of the ledger. Unknown codes, duplicate observations, missing values and
   unexplained import-detail differences raise errors.

   For a single reporting economy:

   .. code-block:: python

      audit = db.info["figaro_nam"]
      audit["source_reconciled"]
      audit["max_cell_reconstruction_error"]
      audit["max_source_account_imbalance"]

   Reconstruction checks source reproduction, separately from account
   balance. No balancing is applied and no model closure is selected. Audit
   fields describe the original import; they do not certify later scenario
   edits. With several ledgers, ``sources`` contains the per-economy audits.

   ``source_accounts`` retains source descriptions and their MARIO set/item
   identities; ``external_settlements`` records settlements without inferred
   origin/product allocations. See the :doc:`NAM format guide
   </get_started/table_formats/nam>` for trade accounts, investment routing
   and native layouts. Read MARIO's own exported NAM workbook with
   ``mario.parse_from_excel(..., table="NAM", mode="flows")``.

Source links
------------

* `FIGARO data and releases <https://ec.europa.eu/eurostat/web/esa-supply-use-input-tables/database>`__
  and `methodology/classifications <https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_fcp_esms.htm>`__.
* `Eurostat Statistics API <https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction>`__.
* `FIGARO-NAM releases <https://ec.europa.eu/eurostat/web/experimental-statistics/national-accounting-matrices-figaro>`__
  and `methodological note <https://ec.europa.eu/eurostat/en/web/products-statistical-working-papers/w/ks-01-25-050>`__.
* `Eurostat reuse terms <https://ec.europa.eu/eurostat/help/copyright-notice>`__.
  Credit Eurostat for derived calculations; Eurostat is not responsible for them.
