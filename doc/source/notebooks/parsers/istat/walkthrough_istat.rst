:page-type: Database guide
:summary: Import Italian national supply-use and input-output tables.

ISTAT
=====

.. container:: mario-companion

   :download:`Download notebook <walkthrough_istat.ipynb>`

This example downloads the selected edition. Choose the table, valuation and industry or product system before comparing results.
See :func:`mario.parse_istat` for the complete parser signature.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_istat(
          path="istat_cache", year=2022, table="IOT", iot_mode="product",
          download=True, edition="latest",
      )

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Relevant source page

   - Official ISTAT tag page: `ISTAT sistema input-output <https://www.istat.it/tag/sistema-input-output/>`__

   This parser targets the official ISTAT release bundles, not arbitrary spreadsheets with a similar shape.

.. mario-details:: Key arguments

   The key public arguments are:

   - ``path``: local workbook, extracted release directory, release zip, or cache directory;
   - ``year``: reference year to select from the ISTAT release;
   - ``table``: choose ``"IOT"`` or ``"SUT"``;
   - ``iot_mode``: for ``IOT``, either ``"product"`` or ``"industry"``;
   - ``level``: for ``SUT``, either ``"63"`` or ``"20"``;
   - ``price``: for ``SUT``, either ``"current"`` or ``"pyp"``;
   - ``valuation``: for ``SUT``, either ``"basic"`` or ``"purchaser"``;
   - ``import_representation``: for basic-price SUT, choose total imports in factor accounts or native imports by commodity;
   - ``extensions``: optionally add ``"emissions"``, ``"employment"`` and/or ``"energy"`` to the 63-branch SUT;
   - ``download``: when ``True``, MARIO downloads the official release before parsing it;
   - ``edition`` and ``page_url``: downloader selectors for the official ISTAT release page.

.. mario-details:: `IOT` versus `SUT`

   Use ``table="IOT"`` when you want the symmetric representation with ``Z``, ``Y``, and ``V``.

   Use ``table="SUT"`` when you want the native split structure with ``S``, ``U``, ``Yc``, ``Ya``, ``Va``, and ``Vc``.

   For ``IOT``, the key selector is ``iot_mode=``. For ``SUT``, the key selectors are ``level=``, ``price=``, and ``valuation=``.

.. mario-details:: Workbook, extracted directory, or zip archive

   For ``IOT``, passing the workbook directly is often the simplest workflow.

   For ``SUT``, passing the extracted release directory or the release zip is usually more convenient, because MARIO resolves the required workbook triplet from the official file names.

.. mario-details:: Download workflow

   If you already have the official release locally, point the parser to the workbook, directory, or zip file.

   If you want MARIO to fetch the official release first, use ``download=True`` together with a cache directory in ``path``.

.. mario-details:: Expected local release layout

   Typical local structure:

   .. code:: text

      ISTAT/
      ├── input_output_2015_2020.zip
      ├── input_output_2020_2022.zip
      └── extracted_release/
          ├── *.xlsx
          └── *.xls

   For local parsing, the workbook names and sheets must come from the official ISTAT release. For ``download=True``, ``path`` is the cache directory where MARIO stores the downloaded archive and extracted files. The direct helper is ``mario.download_istat_io(...)``.

   .. code:: python

      import mario

.. mario-details:: Parse one local `IOT` workbook

   This is the simplest ``IOT`` workflow. If you haven’t downloaded it, you can indicate a folder path and download=True

   .. code:: python

      db = mario.parse_istat(
          path="/path/to/IOT",
          year=2022,
          table="IOT",
          iot_mode="product",
          download=True,
          edition="latest",
      )

.. mario-details:: Parse one `SUT` release

   The ``SUT`` workflow needs the structural selectors explicitly.

   .. code:: python

      db = mario.parse_istat(
          path="/path/to/SUT",
          year=2022,
          table="SUT",
          level="63",
          price="current",
          valuation="basic",
          download=True,
          edition="latest",
      )

      db

.. mario-details:: First inspection

   Once the release is parsed, the normal MARIO inspection helpers work exactly as for the other parsers.

   .. code:: python

      db.table_type

   .. code:: python

      db.activities

   .. code:: python

      db.units

.. mario-details:: Caveats

   - the parser expects the official ISTAT workbook and release naming conventions;
   - ``SUT`` parsing has more structural selectors than ``IOT``, so explicit arguments are usually the better choice;
   - ``download=True`` is optional, but it is often the cleanest workflow when you want a stable local archive of the release.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.

Separate SUT imports by product
-------------------------------

The official ``IMPORT`` workbook records imported products by purchasing
activity and final-demand category. Select native import accounts directly
when parsing this already single-region table:

.. code-block:: python

   db = mario.parse_istat(
       "istat_cache", year=2022, table="SUT", level="63",
       price="current", valuation="basic", import_representation="separate",
       download=True, edition="2020-2022",
   )
   imported_intermediates = db.query("IMP_a")
   imported_final_demand = db.query("IMP_Y")

``IMP_a`` and ``IMP_Y`` have one row per imported commodity, with no origin
country detail. ``U`` and ``Yc`` contain domestic uses after subtracting the
corresponding imported cells. ``IMP_c`` is zero. All monetary flows are in
millions of euros. Aggregation maps domestic and imported commodity rows
together. Do not call ``to_single_region()`` on this national table.

The default ``import_representation="factor-accounts"`` retains total imported
supply by product in ``Vc`` and total uses in ``U`` and ``Yc``. It is a
different accounting layout from allocating imported uses to ``IMP_a`` and
``IMP_Y``. Parse the source again to choose that layout. Once separated,
:meth:`db.to_import_representation() <mario.Database.to_import_representation>`
can combine those same imported-use accounts with the factors and restore them.
Separate parsing currently requires SUT at basic prices; IOT and purchaser-price
requests are rejected before downloading.

SUT income rows contain disjoint value-added components, excluding the published
subtotals and the wages already included in employee compensation. A reduced
workbook without the full decomposition uses total value added instead.
``VY`` retains product taxes and the published final-demand accounting
adjustments. These adjustments are separate from domestic and imported product
uses. Published rounding differences are retained rather than balanced by an
unreported correction. Without ``extensions``, the zero satellite placeholder
is not an emissions inventory.

See :doc:`separate import accounts </user_guide/transformations/import_accounts>`
and :doc:`exports to CVXLab </user_guide/inspection/to_cvxlab>` for coefficients,
aggregation and exports.

Add emissions, employment and energy
------------------------------------

Select satellite groups while parsing the native 63-branch SUT, then aggregate
the productive classifications as usual:

.. code-block:: python

   db = mario.parse_istat(
       path="istat_cache", year=2022, table="SUT", level="63",
       valuation="basic", import_representation="separate",
       extensions=["emissions", "employment", "energy"],
       download=True, edition="2020-2022",
   )
   activity_accounts = db.query("Ea")
   household_accounts = db.query("EY")
   greenhouse_gases = activity_accounts.loc["AEA | GHG"]
   provenance = db.info["istat_extensions"]

``extensions=None`` is the default and leaves the monetary workflow unchanged.
A single group name or ``"all"`` is also accepted. Selected accounts must exist
for the requested year. They align by native activity codes with NACE Rev. 2
A64; ISTAT's table contains 63 branches because it excludes extraterritorial
organisations (section U). No statistical allocation to products is needed:
activity flows populate ``Ea`` and ``Ec`` remains zero. This option currently
requires ``table="SUT", level="63"``. Aggregate afterwards for a coarser model.

.. list-table:: Optional satellite groups
   :header-rows: 1
   :widths: 15 50 35

   * - Selection
     - Source and rows
     - Units
   * - ``emissions``
     - `Air emissions accounts (AEA) <https://ec.europa.eu/eurostat/databrowser/view/env_ac_ainah_r2/default/table?lang=en>`_:
       24 indicators, labelled ``AEA | <airpol code>``
     - Tonnes of the substance or the indicator's equivalent
   * - ``employment``
     - `National accounts employment <https://ec.europa.eu/eurostat/databrowser/view/nama_10_a64_e/default/table?lang=en>`_:
       ``Employment | Total`` (domestic concept); hours from the ISTAT USE workbook
     - Persons and hours, converted from source thousands
   * - ``energy``
     - `Physical energy flow accounts (PEFA) <https://ec.europa.eu/eurostat/databrowser/view/env_ac_pefa04/default/table?lang=en>`_:
       ``Energy | Net domestic energy use`` (``NETDOM_EUSE``)
     - TJ

AEA and PEFA follow the national-accounts residence principle. Their direct
household totals go into ``EY`` under household final consumption; the
household-purpose breakdowns are not added again. Employment has no direct
household final-demand account. These are domestic direct accounts, without
the emissions or energy embodied in imports.

Keep overlapping indicators separate: ``AEA | GHG`` already expresses total
greenhouse gases in ``t CO2-eq``; do not sum it with its gas components or their
equivalent versions. Other characterised rows retain ``t SO2-eq`` or
``t NMVOC-eq`` as appropriate. PEFA imports net domestic energy use, rather
than summing production and intermediate energy flows through transformations.
Coefficients calculated from these accounts use the SUT monetary denominator,
which is millions of euros; they are not automatically per euro.

Cache and source vintages
~~~~~~~~~~~~~~~~~~~~~~~~~

With ``download=True``, missing Eurostat snapshots are saved in
``istat_cache/extensions/`` alongside the monetary release cache. For a local
zip or workbook, the extension cache is beside that file. Subsequent calls
with ``download=False`` use these snapshots without network access; keep the
workbooks and extension cache together for reproducibility.
``overwrite_download=True`` refreshes selected snapshots only when downloading,
and validates their required observations before replacing previous files.

Missing, confidential or non-finite required observations cause an explicit
error. They are never treated as zero. Source update dates, retrieval times,
queries, native-code mappings and observation flags are recorded in
``db.info["istat_extensions"]`` (or ``state.metadata.extra["istat_extensions"]``
for ``model="ModelState"``). Later revisions of the satellite sources can
differ from the monetary workbook's vintage even when their reference year
matches. ``edition`` selects the monetary release, not a historical Eurostat
revision; archive the cache to retain an exact snapshot.

See the official metadata for
`AEA <https://ec.europa.eu/eurostat/cache/metadata/en/env_ac_ainah_r2_sims.htm>`_,
`employment <https://ec.europa.eu/eurostat/cache/metadata/EN/nama_10_pe_esms_it.htm>`_
and `PEFA <https://ec.europa.eu/eurostat/cache/metadata/en/env_pefa_sims.htm>`_.
