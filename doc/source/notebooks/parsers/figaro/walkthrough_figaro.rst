:page-type: Database guide
:summary: Import FIGARO IOT/SUT from the API or national accounting matrices from local files.

FIGARO
======

.. container:: mario-companion

   :download:`Download notebook <walkthrough_figaro.ipynb>`

:func:`mario.parse_figaro` has two input routes: local source files for
``table="NAM"`` and Eurostat API/cache data for ``table="IOT"`` or ``"SUT"``.
``path`` means a source file in the first route and an API cache directory in
the second. Select the route for the data you have.
The inventory panel summarizes IOT/SUT readings; NAM memberships come from
the selected local ledger.

Local national accounting matrices
----------------------------------

Download the FIGARO-NAM CSV release or a national workbook from `Eurostat's NAM releases
<https://ec.europa.eu/eurostat/web/experimental-statistics/national-accounting-matrices-figaro>`__
and pass the local file to :func:`mario.parse_figaro`:

.. code-block:: python

   import mario

   nam = mario.parse_figaro("FIGARO_NAM_2023.csv", table="NAM", countries="IT")
   nam.U
   nam.MU
   nam.info["figaro_nam"]

The result is a NAM database containing the selected national ledger,
institutional and financial accounts, and observed bilateral import detail.
Eurostat publishes FIGARO-NAM as experimental statistics; its
`methodological note <https://ec.europa.eu/eurostat/en/web/products-statistical-working-papers/w/ks-01-25-050>`__
describes compilation of the national accounts. Availability in MARIO refers
to the source layouts described here, not an assumed annual release schedule.

The published CSV contains all countries in long form with columns
``base,ctr,Set_i,m,Set_j,value``. Select **exactly one** reference economy with
``countries="IT"`` (or ``["IT"]``). Omitting the selection or requesting several
countries raises an error. The reader streams the file in chunks and retains
only the selected ledger: ``m`` identifies the reporting economy, while foreign
``ctr`` rows supply its bilateral product-use imports. Export totals come from
the national ``S2`` account; outgoing bilateral rows are not added again.

This CSV is a sparse publication: omitted entries mean zero within the supported
FIGARO-NAM classification. The source adapter retains complete account sets,
including wholly zero accounts; this does not change the native NAM rule that
unavailable blocks differ from declared zero. ``base`` supplies the year and
values use the release's million-euro units and FIGARO-NAM valuation.

A national workbook remains supported:

.. code-block:: python

   nam = mario.parse_figaro("FIGARO_NAM_IT_2023.xlsx", table="NAM")

The workbook path reads the T02 square ledger and appended bilateral
product-use detail and verifies the workbook's unit/valuation labels.
Both input formats check reference economy/year, one owner for every nonzero
square cell, import-detail reconciliation and reconstruction of the square
from native blocks. They preserve the investment routing nodes ``P51G``/``B8_S1`` and the observed
``P7``/``P33`` trade-clearing accounts. ``P7–S2`` settlements retain their
source value without an inferred origin/product allocation. ``B9FX9`` stays
in ``Other accounts``, through ``O_sc_d``/``O_sc_f``. Imports remain in the
separate ``External trade account`` set. These checks do not establish a model
closure or a SUT valuation bridge.

Check the import audit
~~~~~~~~~~~~~~~~~~~~~~

For one reporting economy, inspect reconstruction and the source account
imbalance separately:

.. code-block:: python

   audit = nam.info["figaro_nam"]
   audit["source_reconciled"]
   audit["max_cell_reconstruction_error"]
   audit["max_source_account_imbalance"]
   audit["external_settlements"]

Reconstruction compares the native MARIO blocks with the original source
cells. It does not certify equal receipts and payments for each account.
``max_source_account_imbalance`` reports that separate source diagnostic in
million EUR; no balancing operation is applied. Audit fields refer to the
original import and are not refreshed when you later edit a scenario.

Other local input forms
~~~~~~~~~~~~~~~~~~~~~~~

``year=`` is optional for NAM; when supplied it must match the source.
``path`` can also be a list of local workbooks or a directory of
national XLSX files or T02 worksheet CSV exports retaining their metadata
and header rows. Pass a published all-country CSV as a **single file**, separate
from workbooks or releases for other years. Arbitrary long-form CSV schemas are
not accepted.
All selected national ledgers must share one reference period and each
reference economy must occur once. ``countries=`` selects reporting economies,
not import partners. For example:

.. code-block:: python

   nam = mario.parse_figaro(
       ["FIGARO_NAM_IT_2023.xlsx", "FIGARO_NAM_FR_2023.xlsx"], table="NAM",
   )
   nam.get_index("Region")

This retains independent national ledgers; it does not consolidate trade and
external accounts into an interregional system. NAM reads local data and
does not use the IOT/SUT API cache or assume NAM SDMX availability.

NAM account totals and coefficients can then be requested with
``nam.resolve_many(["Xa", "Xsi_d", "u", "cf_d"])``; the coefficients use
full paying-account totals and preserve the import descriptors.
See :doc:`the NAM calculation reference </reference/api_nam_calculations>`
for signed zero-total accounts and the distinction from model closure.

For several workbook ledgers, the combined audit keeps a ``sources`` list
with one audit per economy; ``reference_economies`` identifies the reporting
economies. Each retains its own external accounts. Neither additional
import origins nor nonresident ``S2`` items become extra reporting economies.

.. mario-details:: Read FIGARO item codes

   The source defines item codes; MARIO defines the accounting sets and block
   names. Source descriptions and their normalized set/item identities are
   retained in ``nam.info["figaro_nam"]["source_accounts"]`` for a single
   economy, and under each entry in ``sources`` for multiple ledgers.

   .. list-table::
      :header-rows: 1
      :widths: 28 72

      * - Source code
        - Meaning and normalization
      * - ``S11``, ``S12``, ``S13``, ``S14``, ``S15``
        - Non-financial corporations, financial corporations, general government,
          households and non-profit institutions serving households: resident
          income-sector members.
      * - ``S2``
        - Rest of the world in the nonresident income set.
      * - ``B8_S11`` … ``B8_S15``, ``B8_S2``
        - The same sector members in resident/nonresident capital sets;
          normalized items are ``S11`` … ``S15`` and ``S2`` there.
      * - ``D21X31``, ``D29X39``
        - Taxes less subsidies on products, and other taxes less subsidies
          on production, in the tax set.
      * - ``D4``, ``D5``, ``D61``, ``D62``, ``D7``, ``D8``, ``D9``
        - Distributive transactions, including property income, current income/
          wealth taxes, social contributions/benefits, other transfers, pension
          adjustments and capital transfers. Item types distinguish their roles.
      * - ``N1…``, ``P52``, ``P53``, ``NP``
        - Nonfinancial asset categories, inventories, valuables and nonproduced
          assets. They describe assets, separately from the products purchased.
      * - ``F1`` … ``F8`` and their subdivisions
        - Financial instruments: gold/SDRs, currency/deposits, debt securities,
          loans, equity/fund shares, insurance/pensions/guarantees, derivatives
          and other receivables/payables. These are transaction flows, not
          end-of-period asset stocks.
      * - ``P7``, ``P33``
        - Import and resident-household-consumption-abroad clearing accounts,
          in the dedicated external trade set.

   The investment-routing nodes ``B8_S1``/``P51G`` and discrepancy ``B9FX9``
   remain distinct Other items. Source controls ``S1``/``B9`` are omitted from
   the normalized square only after their rows and columns are verified zero;
   their audit entries are retained. ``B9_d``/``B9_f`` are calculated
   financial-side results, not those source controls.

.. mario-details:: Common input problems

   * A bulk CSV needs exactly one explicit ``countries`` selection and one
     source file. Do not mix annual bulk CSVs or a bulk file with national
     workbooks in the same input directory.
   * A T02 worksheet export must retain its metadata, account headers, square
     and appended import-detail rows. A CSV containing only the square is
     insufficient for that reader.
   * Unknown account codes, duplicate observations, missing values and
     unexplained import-detail differences raise errors rather than being
     discarded or silently reclassified. Sparse omitted observations have
     zero semantics only in the supported published bulk format.
   * Read an exported MARIO workbook with
     ``mario.parse_from_excel(..., table="NAM", mode="flows")``.
     Read the original FIGARO workbook with ``mario.parse_figaro(..., table="NAM")``.

See :doc:`the NAM format guide </get_started/table_formats/nam>` for the
account sets, native layouts, supported operations, templates and Excel
round trips, and :doc:`the parser reference </api_document/mario.parse_figaro>`
for arguments. :doc:`The NAM interface </reference/api_nam_database>` gives
the supported inspection and update methods. The accompanying notebook
contains independent local NAM and API IOT/SUT sections; run the section
matching your input files.

IOT and SUT API import
----------------------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_figaro(table="SUT", year=2022, path="figaro_cache")

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

The following options describe the IOT/SUT API route.

.. mario-details:: Source links

   - `FIGARO data and releases <https://ec.europa.eu/eurostat/web/esa-supply-use-input-tables/database>`__
   - `FIGARO methodology and classifications <https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_fcp_esms.htm>`__
   - `Eurostat Statistics API <https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction>`__
   - `Eurostat reuse terms <https://ec.europa.eu/eurostat/help/copyright-notice>`__

   FIGARO IOT values are in **million EUR at current basic prices**. Products follow CPA 2.1 and activities NACE Rev.2. Browser monetary values are converted to current USD using same-year exchange rates. Derived calculations must credit Eurostat; Eurostat is not responsible for these calculations.

.. mario-details:: Dataflow groups

   The parser selects the dataflow suffix from ``year``:

   - ``2010``-``2013``: ``s1``, ``u1``, ``ip1``, ``ii1``
   - ``2014``-``2017``: ``s2``, ``u2``, ``ip2``, ``ii2``
   - ``2018``-``2021``: ``s3``, ``u3``, ``ip3``, ``ii3``
   - ``2022`` onwards: ``s4``, ``u4``, ``ip4``, ``ii4``

   For example, a 2022 SUT uses ``naio_10_fcp_s4`` and ``naio_10_fcp_u4``.

   Supply flows use a single ``geo`` dimension: MARIO places domestic production on the same region on both axes of ``S``. Use and IOT flows retain their origin and destination dimensions.

.. mario-details:: Key arguments

   - ``table``: choose ``"SUT"`` or ``"IOT"``.
   - ``year``: reference year, required; this is separate from the dataset edition.
   - ``path``: optional directory of normalized API-cache CSVs and JSON sidecars. Matching caches are reused; missing requests are downloaded into that directory.
   - ``countries``: optional FIGARO country-code selection; keep it consistent with the cached request. A subset is not a complete global MRIO.
   - ``iot_mode``: ``"product"`` → ``pxp``; ``"industry"`` → ``ixi``; ``"auto"`` defaults to product. This is an IOT system, separate from table format.
   - ``unit``: Eurostat monetary unit, currently ``"MIO_EUR"``.

.. mario-details:: Local caches and API requests

   MARIO checks ``path=`` for a matching cache before calling the API. The cache key includes the dataflow, year, monetary unit, country selection and factor-row selection; keep the original cache filenames. ``path`` is a cache directory, not a single CSV path.

   Without a matching cache, MARIO chunks requests by ``c_orig`` to respect Eurostat extraction limits. Full tables are large, so country subsets can help during development; they do not replace the full global parse used in the browser.

   The DOM/W2 rows supply the factor matrix ``V``. For GDP, sum D1 + D29X39 + B2A3G and add net product taxes D21X31 on **intermediate and final uses**. The IOT parser retains intermediate taxes in ``V``; the browser independently reads final-use taxes from the same source cache. Residence-purchase adjustment rows are excluded from this income calculation.

   .. code:: python

      import mario

.. mario-details:: Parse a FIGARO SUT

   Point ``path`` to the directory containing matching supply and use API caches. If either cache is absent, MARIO downloads that request.

   .. code:: python

      db_sut = mario.parse_figaro(
          table="SUT",
          year=2022,
          path="/path/to/figaro/sut_directory"
      )

      db_sut

   .. code:: python

      db_sut

.. mario-details:: Parse a FIGARO IOT

   The local series uses ``iot_mode="product"`` (pxp). Change ``year`` and select its cache directory to read another annual table. ``industry`` (ixi) is supported by MARIO but is not present in the supplied local IOT inventory.

   .. code:: python

      db_iot = mario.parse_figaro(
          table="IOT",
          year=2022,
          iot_mode="product",
          path="/path/to/figaro/iot_directory",
          calc_all=False,
      )

      db_iot

.. mario-details:: First inspection

   Once parsed, the result is a standard MARIO database.

   .. code:: python

      db_sut.get_index("Region")[:5]

   .. code:: python

      db_sut.get_index("Activity")[:5]

   .. code:: python

      db_sut.get_index("Commodity")[:5]

.. mario-details:: Practical notes

   - ``ip1``–``ip4`` and ``ii1``–``ii4`` partition reference years; their suffixes are not database versions.
   - Preserve cache filenames and the original country selection. ``countries=`` changes the request key.
   - The public browser groups identical native sets into one Excel inventory; equal coverage does not mean equal annual values.
   - No GHG indicator is inferred from monetary factors or MARIO placeholder extension rows. Environmental accounts require separate source files.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
