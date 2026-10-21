****************
Release History
****************

All notable changes to MARIO, newest first. Versions match the ``mariopy``
package on PyPI, and dates are its publication dates.

Unreleased
----------

* ``parse_bonsai(table="IOT")`` reads native b2 HIOT directories or ZIP bundles,
  preserving sparse net-supply matrices, hybrid product units, nonuniform
  regional sectors and source diagonal normalization. It imports final demand
  and direct elementary flows, reports unmatched source rows and leaves the
  existing Balanced HSUT parser as the default. No Stone reconstruction or
  precomputed inverse is required.
* BONSAI documentation explains the equivalence between native ``E T^-1`` and
  MARIO's ``e (I-z)^-1`` multipliers, electricity unit conversion, explicit
  BONSAI LCIA characterization and comparison of matching source exports.
  The executed walkthrough limits the HIOT solve to the required GHG rows. A dated local
  verification records source checksums, numerical residuals and discrepancies
  against older saved footprints; file modification dates are distinguished
  from release identifiers.
* ``get_index`` preserves complete Factor of production and Satellite account
  lists when custom extension layouts contain global scopes outside the Region
  set. GTAP global accounts are no longer discarded by regional-view inference;
  extension axes composed entirely of database regions retain regional views.
* ``to_iot`` converts native SUT blocks on their observed regional nodes, using
  sparse products for B/D and batched supply solves for A/C instead of dense
  diagonals, unified SUT views or inverses. B/D retain activity final demand and
  both Activity/Commodity accounts, including allocation to direct final uses.
  A/C require square, nonsingular supply and zero ``Ya``. Undefined zero-output
  allocation raises an error naming the nodes; no pseudoinverse or data repair
  is applied. Common dense cases retain their formulas, API and storage.
* ``is_isard`` reads native ``U`` when no unified source is already cached and
  sums sparse flows directly by regional labels, including unequal regional
  domains and different row/column region orderings. No unified view is built.
* ``to_chenery_moses`` transforms native SUT blocks using sparse allocation
  matrices instead of dense diagonals and unified ``Z`` views. Regional
  Activity memberships are preserved and only observed destination Commodity
  markets are added. ``Ya`` and activity/direct final-demand accounts are
  retained; Commodity accounts follow destination shares with conserved totals.
  Unselected scenarios are zero-extended when new market axes are needed.
  Undefined zero-net sourcing raises an error without data adjustments.
  Common dense tables retain their output storage and API.
* ``pool_trade`` explicitly rejects region-specific Activity, Commodity or
  Consumption category classifications before copying or querying the model.
  The transformation for common regional classifications is unchanged.
* ``to_pymrio`` explicitly rejects region-specific Sector or Consumption
  category classifications before querying matrices, instead of failing later
  while expanding units. Common regional classifications retain their existing
  export behavior. SUT-to-IOT conversion remains a separate operation.
* ``update_supply_mix`` and ``update_trade_mix`` accept nonuniform regional
  classifications, validate actual region-item pairs and retain sparse storage.
  Missing explicitly requested origins raise an error even at zero weight;
  destinations may import an item without a local node. Column filters select
  existing columns only, and explicit commodity aggregation maps existing
  regional occurrences without adding production nodes. Common classifications
  retain their API, bundle totals and scenario behavior.
* ``calc_linkages`` supports sparse flow blocks and nonuniform regional
  classifications without constructing full inverse views. Regional reductions
  use actual production nodes; exact self effects are subtracted without
  modifying sparse arrays. Detected singular Ghosh/Leontief components raise
  an error naming their nodes, without exclusions or data corrections. Common
  dense tables retain their existing result layout and normalization.
* Total and upstream trade-content breakdowns project regional trade vectors
  through the IOT/SUT coefficient system without constructing an inverse or an
  exploded multiplier. SUT results retain both Activity and Commodity
  contributors and their legacy ordering; upstream subtracts the direct vector
  contribution. Sparse flow inputs retain sparse output and use the same
  projection for collapsed totals. Large iterative solves apply split
  coefficients as an operator, and exact proportional trade vectors share a
  solve. Nonconverged results raise an error.
* Direct trade-content breakdowns weight actual flow entries without building a
  dense contributor diagonal. Sparse inputs produce zero-fill sparse results,
  retaining the contributor index and zero rows. Region clusters are applied
  before expanding the output; contributors retain their original regional
  labels. Dense inputs keep the existing dense output format.
* ``calc_trades_content`` resolves only the indicator rows required by its
  method: direct coefficients for ``direct``, total multipliers for ``total``,
  and both for ``upstream``. Total contributor breakdowns no longer load or
  construct an unused direct diagonal. Results, indicator units and accounting
  formulas remain unchanged.
* ``calc_trades`` accepts sector/commodity codes from regional classifications
  and sums actual region-item pairs. All database regions remain in its output,
  including zero rows and destinations without a local commodity node. Sparse
  flow blocks remain sparse until reduced to regional totals, including weighted
  sums. SUT supply-format checks read native ``S`` when no unified view is
  materialized, avoiding construction of ``Z`` just to choose the trade path.
* Database equality compares the members of every region for nonuniform sets,
  detecting different regional classifications even when region names and the
  global label union match. Index order remains irrelevant, common lists keep
  their previous behavior, and equality retains its historical index-only scope.
* Aggregation workbooks group regions by each complete regional classification.
  Nonuniform sets use ``Regions``, ``Item`` and ``Aggregation`` columns, including
  single-region groups. The Region sheet lists only regions with compatible
  classifications across all regional sets; omitted regions remain unchanged.
  Geographic mergers across incompatible string sets are rejected. Readers,
  sparse aggregation and unit checks support regional mappings, while common
  classifications retain the legacy workbook format.
* Regional sets retain region-to-list mappings in automatic ``all`` and user
  clusters. Definitions are validated per region-code pair; list shorthand is
  intersected with each region's domain. Common sets keep their existing list
  clusters. Shock expansion selects actual nodes, including in split SUT and
  legacy workbooks, and preserves sparse coefficient updates. Excel templates
  use union picklists and inspect sparse blocks without densifying them.
* ``search`` searches regional member lists and returns matches grouped by
  region for nonuniform sets, omitting regions with no matches. ``region=...``
  and ``flat=True`` select one region or a distinct global union. Common
  classifications retain list results; global searches remain grouped by set.
* Database summaries show the minimum and maximum member count per region for
  regional index dictionaries, including regions with no members. Common
  classifications retain their existing scalar counts.
* ``get_index`` keeps ordered lists for common regional classifications and
  returns dictionaries of regional lists for nonuniform sets. ``region=...``
  selects one region and ``flat=True`` explicitly requests the union of labels.
* Add ``mario.parse_bonsai`` for Balanced hybrid supply-use ZIPs and extracted
  directories. Imports preserve native units, regional trade and direct final
  demand extensions in sparse blocks, with explicit unmatched-flow diagnostics.

v1.3.1
------

*Released 2026-10-19.*

Session settings and matrix aliases
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Settings changes apply to the current Python process by default.
  ``upload_settings``, ``reset_settings`` and the compute-setting helpers no
  longer rewrite the installed package.
* ``upload_settings(..., persist=True)`` explicitly saves validated user
  defaults that new sessions load automatically. ``get_settings_path()``
  exposes the profile location; ``MARIO_CONFIG_DIR`` selects a separate
  profile for a project or environment. Writes are atomic, and invalid
  saved profiles produce a warning and fall back to built-in defaults.
* ``reset_settings()`` temporarily restores built-in defaults in the current
  session. ``reset_settings(persist=True)`` also removes the saved profile.
  Neither operation changes the settings of already initialized kernels.
  The settings guide, API reference and custom-labels notebook now explain
  temporary aliases, optional persistence and both reset modes.
* Internal matrix identifiers remain canonical (``E``, ``EY``, ``F``, etc.).
  Configured names such as ``R``, ``Ry`` and ``Re`` are resolved at the API
  boundary. Changing or resetting settings after loading a database therefore
  preserves its matrices, including through aggregation, scenario resets,
  region extraction, copying and SUT-to-IOT conversion.
* Invalid settings are rejected before changing the active configuration,
  including unknown keys, non-string matrix labels, duplicate or reserved
  names and invalid compute options. Surrounding whitespace is normalized.
* Resetting settings restores the same ``inverse`` compute default used by a
  fresh installation, instead of unexpectedly switching it to ``auto``.

EXIOBASE downloads
~~~~~~~~~~~~~~~~~~

* Fixed interrupted monetary EXIOBASE downloads, including the 3.11.2
  ``ixi`` and ``pxp`` archives: partial files are retained under ``.part``
  and resumed with HTTP range requests, with up to six attempts per call.
* Zenodo downloads now verify the published file size and checksum before
  reusing an archive or extracting it. Truncated or corrupted cached archives
  are recovered instead of being silently reused as complete downloads.
* Failed ZIP extraction removes the incomplete destination directory so a
  subsequent call can retry extraction.
* Documented the explicit 3.11.2 download call and expanded regression coverage
  for both systems, interrupted transfers and cached archives. Support for the
  3.11.2 release itself was introduced in MARIO 1.2.0.

GHG accounts and aggregation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``Database.calc_ghg`` preserves the existing row and column axis names of
  ``E`` and ``EY``, as well as satellite-account unit index names. Plot filters
  such as ``Item_from`` and sector mappings such as ``Item_to`` remain valid
  after adding the GHG indicator.
* Aggregated set lists retain the first occurrence order in their aggregation
  mappings instead of passing through an unordered set. Reusing
  ``database.sectors`` in plot ``category_orders`` now gives a stable order.
* Matrix block specifications resolve configured aliases back to their
  canonical catalog entries. Aggregation no longer fails with
  ``No block specification is known for 'R'`` when ``E`` is renamed to ``R``.
* Aggregation preserves canonical matrix keys and access through active
  aliases, including when settings change in an existing Python session.
* Split SUT aggregation resolves renamed unified source blocks before
  building their ordering, avoiding invalid keyword arguments such as ``R``
  when extracting native satellite blocks from the renamed ``E`` view.
* ``add_extensions`` and ``calc_ghg`` accept canonical and configured matrix
  names consistently, including renamed ``E``, ``EY``, ``e``, ``V`` and ``v``.
  Adding the GHG indicator no longer rejects ``E`` when the active name is
  ``R`` or loses the renamed final-demand block.
* ``to_single_region`` and ``to_region_subset`` preserve access through
  the current matrix aliases after ``upload_settings`` in the same session.
  ``E`` and ``EY`` remain available for subsequent aggregation,
  avoiding a false missing-data cycle between ``E`` and ``e``.
* Eurostat IOT and SUT parsers label their three-level axes as
  ``Region``, ``Level`` and ``Item``. Sector aggregation now reduces the
  numeric matrices as requested, and plots expose ``Sector_from`` and
  ``Sector_to`` instead of anonymous ``row_1``/``column_1`` fields.
* ``Database.plot`` uses the same matrix-name validation as ``query``.
  Both canonical names and configured aliases are accepted, such as
  ``E``/``R``, ``F``/``Re`` and ``z``/``A``.

Stacked-bar totals
~~~~~~~~~~~~~~~~~~

* ``Database.plot`` adds the keyword-only ``show_totals=True`` option to show
  one total label per stacked bar and suppress segment labels. Totals respect
  filters, aggregation, ``top_n`` selection and facet panels. ``totals_format``
  controls their Plotly/D3 number format (default ``".3s"``); signed stacks
  display net totals. Animated, grouped and overlaid bars are not supported.
  The default plotting behaviour is unchanged.

v1.3.0
------

*Released 2026-10-12.*

Plotting API
~~~~~~~~~~~~

* ``Database.plot`` adds ``log_color`` and ``color_clip`` for matrix
  heatmaps. ``log_color=True`` uses log10 colours, leaves zeros blank and
  rejects negative values; ``color_clip=(low, high)`` clips colour values
  to the requested quantiles without changing the data. These options
  require a heatmap without facets or animation and are keyword-only;
  existing positional arguments retain their original positions.
* ``preset="heatmap"`` now preserves the complete matrix row and column
  axes and their original order by default. Supply ``x`` and ``heatmap_y``
  explicitly to retain a custom pivot. This fixes heatmaps that previously
  collapsed rows onto column labels.

Parser fixes
~~~~~~~~~~~~

* ``parse_adb`` preserves global ``E`` and ``EY`` totals when the emissions
  extension contains additional economies: where both global tables have
  ``RoW`` and all economic regions are covered, those extra economies are
  aggregated into the economic table's ``RoW`` and recorded in metadata.
* ``parse_emerging`` corrects MATLAB v7.3 transaction-matrix orientation
  during sparse loading and reads HDF5 chunks without repeatedly
  decompressing the same columns.
* ``parse_wiod`` retains published signed factor and tax rows on domestic
  final uses in ``VY`` for international SUTs using
  ``row_mode="external_account"``.
* ``parse_figaro`` supports Eurostat supply dataflows with a single
  ``geo`` dimension, assigning domestic supply to the same region on
  both matrix axes.
* ``parse_exiobase`` and ``parse_exiobase_3`` recognize official 3.8.2
  archives whose metadata incorrectly reports ``v3.81`` when the dataset
  name is ``exio382_ntnu``.

Add-sector workflow
~~~~~~~~~~~~~~~~~~~

* ``Database.add_sectors(split=True)`` now loads the workbook's split-support
  sheets before validating and generating CVXLab inputs. Empty legacy sheets
  missing newer columns are accepted without discarding data.

Distribution
~~~~~~~~~~~~

* Source archives now include the changelog and omit documentation website
  assets. The complete documentation source remains in the Git repository.

Documentation
~~~~~~~~~~~~~

* Redesigned the documentation and navigation around an MRIO Data explorer
  for indicators, database scope and analyses. Its reviewed data now include
  GLORIA v060 annual readings for 2001--2025; 2024--2025 are publisher forecasts.
  EXIOBASE GHG indicators use EDGAR-compatible AR5 GWP100 for
  mass-reported gases; monetary HFC/PFC retain source values, and Hybrid
  remains a three-gas subtotal.
* Updated parser walkthroughs, source-licence notes and the public parser API
  reference. Native-set inventories and reproducible downloads accompany the
  explorer.

v1.2.0
------

*Released 2026-10-06.*

EXIOBASE 3.11.2
~~~~~~~~~~~~~~~~

* Added download and parsing support for the official EXIOBASE 3.11.2 IOT
  release on Zenodo (record ``23039074``), including both ``ixi`` and ``pxp``
  systems for 1995--2024.
* Added explicit discovery of the new ``deforestation`` environmental
  extension alongside the other split EXIOBASE satellite accounts.
* Updated the monetary EXIOBASE walkthrough with a 3.10.2--3.11.2 comparison,
  source-year versus now-cast coverage, and guidance on the populated 2024
  CO2 combustion rows.

Packaging
~~~~~~~~~

* Supported Python versions are declared as 3.11 to 3.13
  (``python_requires=">=3.11,<3.14"``): the pinned ``numpy==2.1.1`` has no
  Python 3.14 wheels.

v1.1.1
------

*Released 2026-07-30.*

GTAP parser rewrite
~~~~~~~~~~~~~~~~~~~~

* The GTAP Power MRIO parser was rebuilt around a record-scatter assembly
  engine shared by the csv and gdx backends: records are mapped onto integer
  axis positions and accumulated directly into dense blocks, so the build cost
  scales with the number of records instead of the size of the cartesian label
  space. The full GTAP 2023 csv bundle (~7 GB, ~140M records) parses
  end-to-end in about 80 seconds where the previous implementation ran for
  20+ minutes before failing; csv reading prefers the multithreaded pyarrow
  engine and logs per-file progress.
* Fixed csv parsing failures and silent distortions on recent GTAP exports:
  duplicated record keys (several GDX symbols flattened into one csv file) now
  sum instead of raising ``cannot handle a non-unique multi-index``; the
  spurious all-zero ``EMI_0_*`` satellite rows are no longer produced; E and
  EY expose one dense, aligned satellite row set matching the gdx backend
  semantics.
* Output- and value-added-based emission accounts, which the csv export
  encodes with the ``SRC="TOT"`` placeholder, are now captured as domestic
  satellite rows of the destination region (e.g. ``EMI_CH4_dms_QO``) instead
  of being silently dropped -- previously about one third of the emission
  record mass in the GTAP 2023 csv bundle was lost. Satellite record mass the
  parser cannot attribute is now reported with a parser warning.

Optional GTAP structured row layouts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``parse_gtap`` gained an opt-in ``matrix_layouts`` argument, e.g.
  ``{"V": ("Region", "Sector"), "E": ("Region", "Sector")}``: factor and
  satellite rows are exposed as a semantic ``(Region, Sector, item)``
  MultiIndex instead of the flat string names, and the matching block
  specifications are registered on the database. Values are identical to the
  flat parse -- only the index representation changes. Row families without a
  region or sector of their own (PTAX, VAAD/VTAX endowments, ETAX, DTAX/ITAX,
  domestic satellite accounts) carry the ``"TOTAL"`` sentinel on the levels
  that do not apply; the sentinel is not part of the Region/Sector sets and
  passes through aggregation untouched. The default keeps the historical flat
  rows unchanged.
* The gdx backend requires the GAMS Python API in the active environment; the
  pip package ``gamsapi[transfer]`` is sufficient to read GDX bundles.

v1.1.0
------

*Released 2026-07-26.* It includes the trade-mix changes prepared as 1.0.4,
which was never published.

Add sectors: value added and inventory handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``Database.add_sectors`` gained ``VA_fix`` and ``accept_non_unitary_sum``.
  ``VA_fix=True`` warns about database factor-of-production rows missing from
  the workbook inventories before slice filling and augments the missing
  factors of production from the parent sectors. ``accept_non_unitary_sum=True``
  accepts inventory sheets whose factor/sector rows do not sum to 1: sheets
  summing to 0 are skipped entirely, other non-unitary inventories proceed with
  a warning instead of raising.
* ``read_add_sectors_excel`` now reads grouped inventory sheets from multiple
  sheets in a single call and accepts ``split=True/False``; the add-sector
  workbook input loader was moved to ``mario/ops/add_sector_workbook.py``.
* Total output and flow computations are corrected after inserting a new sector
  column, and the value-added block ``V`` is now zero-masked as well.
* ``add_sectors`` runs inside a stage-aware error handler that reports which
  step failed, and restores the source per-matrix axis level names dropped by
  the engine's positional groupbys (so downstream ops such as
  ``update_supply_mix`` that rely on named index levels keep working).

Sector split workflow
~~~~~~~~~~~~~~~~~~~~~~~

* Reworked the sector-split routine used by ``add_sectors(split=True)``:
  zeroes stay zeroes, small digits are cleaned, incompatible exogenous data and
  exclusions are validated, factor-of-production clusters are allowed, and the
  split routine is invoked only when needed. Disaggregation optimization
  problems are built faster and the split-constraint formulation was improved.
  A new ``residue`` threshold zeroes out small positive CVXLab input values, and
  the split no longer overwrites an existing output folder.

RAS balancing
~~~~~~~~~~~~~~

* Added a RAS balancing API for IOT databases. ``Database.ras(target_rows,
  target_cols, ...)`` rebalances the flow matrix ``z`` of a scenario to the
  given row and column margins with the biproportional RAS algorithm
  (``tol``/``max_iter`` controls, ``inplace``/``calc_all`` options), backed by
  the reusable ``mario.ops.ras`` helper.

Settings
~~~~~~~~

* The default ``compute.compute_method`` changed from ``auto`` to ``inverse``.

Shock scenarios
~~~~~~~~~~~~~~~

* ``Database.shock_calc`` gained a ``base_scenario`` parameter (default: the
  baseline) so a shock can be built on top of any existing scenario instead of
  always starting from the baseline. All shock readers (``z``/``Y``/``e``/``v``
  and the SUT split readers) now read their base blocks from the selected
  scenario.
* Added a ``Type='Supply mix N'`` shock (with ``N`` from 1 to 10) to the ``z``
  and ``Y`` shock sheets. Rows sharing the same ``(Region_from, 'Supply mix N')``
  describe one regional bundle: their ``Sector_from`` entries are the mix members
  and ``Value`` their shares, while ``Region_to``/``Sector_to`` select the buyer
  columns to rewrite (``all`` targets every column). ``shock_calc`` groups the
  rows and applies ``Database.update_supply_mix_iot`` on top of the shocked
  scenario, redistributing the bundle while preserving each selected column
  total. Shares are used as given when they sum to 1 (±1%) and otherwise
  rescaled with a warning. IOT only.
* ``get_shock_excel`` now extends the picklists on the ``z``/``Y`` sheets with
  the ``Supply mix 1`` … ``Supply mix 10`` options, covers 100 shock rows with
  data validation, drops the unused ``main`` sheet and hides the auxiliary
  ``indeces`` sheet.

Electricity supply mix update
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Added ``Database.update_supply_mix_iot`` (with the ``update_mix_iot`` alias)
  to overwrite the electricity generation mix of an IOT database across the
  ``z`` and ``Y`` blocks of one scenario, together with ``Database.get_mix`` to
  read back a sector bundle's production mix. It works for any IOT database that
  exposes a disaggregated power sector (currently EXIOBASE and EMERGING-E): the
  ``"electricity"`` mode derives shares from EMBER generation data for the
  requested ``year``, aggregating to the compatible EMBER fuel groups and
  redistributing them with each group's current internal composition. Aggregate
  regions (built-in EXIOBASE Rest-of-World regions or user aggregations) are
  resolved to their member countries automatically, and an explicit
  ``region -> {sector: share}`` mapping is also accepted. Documented under a new
  user-guide page.
* ``update_supply_mix_iot`` gained ``column_regions``/``column_sectors``
  selectors to restrict the coefficient redistribution to a subset of
  buyer/demand columns (default: all columns). The operation stays matricial —
  the selected columns are rewritten, the others keep their original
  coefficients.

Supply mix on SUT databases
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Generalized the supply-mix update to SUT databases through the new
  ``Database.update_supply_mix`` (``update_supply_mix_iot`` and
  ``update_mix_iot`` remain as IOT-only aliases). The share labels select the
  behaviour, with ``level='Activity'``/``'Commodity'`` available to
  disambiguate labels existing in both classifications:

  * **Commodity mixes** redistribute the commodity bundle rows across the use
    block ``u`` and the final-demand block ``Yc``, exactly like the IOT case,
    with ``column_regions``/``column_sectors`` (buyer activities) selectors.
  * **Activity mixes (market shares)** rewrite the supply block ``s`` on the
    commodity columns selected by the new required ``commodities=...``
    argument. The shares are rescaled onto the combined market share currently
    held by the listed activities, so producers outside the bundle (e.g.
    by-product suppliers of the same commodity) keep their share untouched.

* Added the ``aggregate_commodity={'new commodity': [existing commodities]}``
  argument: the mapping is structurally aggregated (through ``aggregate``)
  before the mix update so that several activities compete on one shared
  commodity market. The aggregation affects the whole database, not only the
  selected scenario.
* ``update_supply_mix("electricity")`` now works on SUT databases: MARIO
  aggregates the disaggregated electricity commodities into one shared
  ``electricity`` commodity using the packaged profile (extended with the
  EXIOBASE product-side aliases) and rewrites the market shares of the
  generation activities with the EMBER-derived mix, keeping transmission and
  distribution commodities separate.
* ``Type='Supply mix N'`` shock rows are now applied on SUT workbooks too:
  ``u``/``Yc`` sheets author commodity mixes and the ``s`` sheet authors
  market-share mixes (``Commodity_to`` must name the target commodity there;
  ``all`` is rejected). ``get_shock_excel`` extends the ``u``/``s``/``Yc``
  picklists with the ``Supply mix 1`` … ``Supply mix 10`` options. Supply-mix
  rows on the legacy unified ``z``/``Y`` sheets or on the ``Ya`` sheet of one
  SUT workbook — previously ignored silently — now emit one warning.
* Documented the supply-mix shock type in the shock-analyses user-guide page
  and extended the electricity supply mix page with the SUT workflow.

Trade mixes
~~~~~~~~~~~~

* Added ``Database.update_trade_mix``, the dual of ``update_supply_mix``: it
  redistributes one traded item across its **origin regions** inside the
  columns of each destination market (``destination -> {origin: share}``),
  preserving every selected column total. Origins that are not listed keep
  their share, so partial sourcing updates are well defined. The rewritten
  blocks follow the table layout: ``z``/``Y`` on IOT, ``u``/``Yc`` on Isard
  SUTs (Commodity level) and the ``s`` market-share columns selected by
  ``commodities=...`` on pooled/Chenery-Moses SUTs (Activity level, with
  ``level=`` available to disambiguate). Applying one destination-level mix to
  every buyer column imposes the Chenery-Moses uniform-sourcing hypothesis on
  an Isard table; ``column_sectors`` keeps selected buyers on their original
  sourcing, and the docs spell out the same caveat for technology mixes on
  Chenery-Moses tables (where ``column_regions`` restrictions would decouple
  the domestic mix from the exported one).
* Added ``Database.pool_trade(commodities, supply_suffix=" - supply",
  need_suffix=" - need")``: a structural transformation that pools the trade
  of selected commodities behind one pass-through layer (one
  ``"{c} - supply"`` activity and one ``"{c} - need"`` commodity per region).
  Buyers are rewired onto the domestic need commodity keeping their totals,
  and the supply block routes each destination market to the origin
  pass-through activities with the bilateral flows observed on the Isard use
  side — so the pooled table preserves destination-level trade totals exactly
  and the initial ``s`` market shares equal the observed origin shares.
  Technology and trade mixes then live in two separate ``s`` columns and can
  be updated independently. The pooled pairs are recorded on
  ``meta.pooled_trade_map``; like other structural transforms, the pooling
  rebuilds the baseline and drops other scenarios with one warning.
* Added the ``Type='Trade mix N'`` shock family: rows sharing the same
  ``(item, Region_to, 'Trade mix N')`` triple form one destination mix, with
  ``Region_from`` carrying the origins and ``Value`` their shares
  (``Region_to='all'`` is rejected). IOT workbooks author them on the ``z``/``Y``
  sheets, SUT workbooks on ``u``/``Yc`` (Isard sourcing) and ``s`` (pooled
  market shares, with a mandatory ``Commodity_to``). The template picklists
  now offer both mix families through the hidden ``indeces`` sheet, working
  around Excel's 255-character limit on inline validation lists.
* Added the "Update trade mixes" user-guide page covering
  ``update_trade_mix``, ``pool_trade``, the Chenery-Moses uniformity caveats
  and the Excel route.
* Both mix methods gained one ``column_categories`` selector restricting the
  final-demand redistribution (``Y`` on IOT, ``Yc`` on SUT commodity mixes) to
  selected consumption categories. The ``Consumption category_to`` field of
  the ``Y``/``Yc`` shock sheets — previously ignored for mix rows — now feeds
  that selector.
* ``update_supply_mix("electricity")`` now recognises databases whose labels
  carry the plain EMBER group names (``Coal``, ``Wind``, ``Other Renewables``,
  ...), such as tables aggregated to the EMBER technology resolution, and
  ``ember_path`` accepts the raw EMBER ``yearly_full_release_long_format.csv``
  download directly (reduced on the fly with the same filters used to build
  the packaged snapshot).

GHG aggregation
~~~~~~~~~~~~~~~

* ``Database.calc_ghg`` now names the aggregated satellite account after its GWP
  basis when ``label`` is omitted: built-in profiles yield
  ``"GHG {ipcc_report} GWP-{time_horizon}"`` (e.g. ``"GHG AR6 GWP-100"``), while
  custom ``gwp=...`` mappings keep the plain ``"GHG"`` label. Pass ``label=...``
  to override. This changes the previous default label ``"GHG"`` for built-in
  profiles.

Plotting
~~~~~~~~

* Plot helpers no longer fail when the inline Jupyter rendering backend is
  unavailable: the figure HTML is always written to disk first, and inline
  display errors are downgraded to one warning. ``nbformat>=5.10.4`` (required
  by Plotly for notebook rendering) is now installed by default.

v1.0.3
------

*Released 2026-07-02.*

EMERGING-E parser
~~~~~~~~~~~~~~~~~

* Extended ``parse_emerging`` with the ``variant="E"`` EMERGING-E bundle, which
  parses the power-disaggregated table (146 sectors, with electricity split into
  14 generation sub-sectors) directly from ``EMERGING_E_<year>.mat``. MARIO
  auto-detects a sibling label workbook and otherwise falls back to a packaged
  EMERGING-E sector classification (use ``labels_path=`` to override detection).
* Added CO2 projection for EMERGING-E: when only a standard EMERGING
  ``EMERGING_CO2_<year>`` companion is available, MARIO projects the 7 fuel rows
  of the aggregated ``electricity`` sector onto the EMERGING-E generation
  sub-sectors through a fixed fuel-to-technology mapping. Pass ``co2_path=`` to
  point at a specific companion file.

Matrix-specific export
~~~~~~~~~~~~~~~~~~~~~~~~

* Added ``Database.export(matrices, scenarios=..., format="csv"|"txt"|"parquet",
  split="scenario"|"matrix", include_meta=False, **meta_overrides)`` to write
  selected matrices as flat long-format files with ``Scenario``, ``Matrix``,
  ``Unit`` and ``Value`` columns. Flow matrices carry the numerator unit while
  coefficient and exploded (``f_ex``, ``m_ex``, ``p_ex`` and SUT variants)
  matrices carry the ``numerator/denominator`` unit ratio. Files can be split
  one-per-scenario or one-per-matrix, an optional metadata header is written
  (one row per scenario, or parquet schema key/value metadata), and
  ``release_date`` and other metadata fields can be supplied at export time.
  A ``filters`` argument restricts the exported rows to selected axis labels,
  e.g. ``filters={"Satellite account": ["CO2"]}`` to export only the CO2
  footprint rows; keys may be suffixed with ``"_from"``/``"_to"`` to target a
  single side. When splitting one-per-matrix, a flow and its coefficient
  (``Z``/``z``) no longer collide on case-insensitive filesystems: the
  coefficient token is doubled (``zz``).

v1.0.2
------

*Released 2026-06-14.*

Packaging and installation
~~~~~~~~~~~~~~~~~~~~~~~~~~

* Installed Parquet support by default by shipping the package with the
  required dependency out of the box, refreshed the installation guidance,
  refined optional-dependency messaging, and added package-metadata regression
  coverage. Resolved issue `#142 <https://github.com/it-is-me-mario/MARIO/issues/142>`__.
* Declared ``python_requires=">=3.11"`` in the package metadata.

SUT scenarios and native matrix workflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Extended SUT scenario updates so unified ``Z``, ``Y`` and ``E`` inputs are
  accepted directly and normalized through the shared ordering logic, with
  dedicated regression tests for the new update paths. Resolved issue
  `#144 <https://github.com/it-is-me-mario/MARIO/issues/144>`__.
* Switched SUT export and parser roundtrips to native SUT blocks instead of
  legacy unified IOT-style matrices, while preserving backward-compatible
  parsing of historical TXT, Parquet and Excel layouts. Resolved issue
  `#146 <https://github.com/it-is-me-mario/MARIO/issues/146>`__.

Parser and export roundtrip fixes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Fixed ``coefficients``-mode parsing of native SUT and special-layout IOT
  bundles from TXT and Parquet, which raised ``KeyError: 'Z'`` because the
  index builders only looked up the upper-case flow matrix name.
* Fixed the explicit SUT Excel export so productive columns are written in the
  same commodity-first order as the rows, allowing workbooks with overlapping
  ``Activity``/``Commodity`` item labels to round-trip correctly.
* Fixed flat TXT/CSV parsing of standard IOT bundles, which raised
  ``ValueError: not enough values to unpack`` due to an inconsistent parser
  return signature.
* Added a full export/parse roundtrip test matrix covering the ``standard`` and
  ``special`` layouts across Excel, TXT and Parquet in both ``flows`` and
  ``coefficients`` modes.

v1.0.1
------

*Released 2026-06-13.*

Core calculations and regional subsets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Added exploded price-contribution accessors for the price index workflow:
  ``p_ex`` / ``p_ex_all`` for IOT databases and ``pa_ex`` / ``pa_ex_all`` plus
  ``pc_ex`` / ``pc_ex_all`` for SUT activity- and commodity-side
  contributions.
* Expanded ``Database.to_region_subset(...)`` and ``to_single_region(...)``
  with sectorized external-trade layouts via
  ``externalized_trade_layout="sectorized"`` and the shorthand trade modes
  ``"by_sector"`` and ``"by_region_and_sector"``.
* Fixed IOT sectorized subset export so ``to_excel(...)`` writes a coherent
  explicit special-layout workbook, including aligned ``VY`` rows and public
  ``Region/Sector`` plus ``Region/Consumption category`` axes without legacy
  ``Level`` markers.
* Added an explicit ``NotImplementable`` guard for SUT
  ``to_region_subset(...)`` calls that request custom ``trade_mode`` or
  non-legacy externalized-trade layouts, while preserving the standard legacy
  subset workflow for SUT tables.

Parquet and packaging
~~~~~~~~~~~~~~~~~~~~~

* Made ``pyarrow>=17`` an explicit optional dependency for Parquet parsing,
  export and storage workflows, added clearer runtime guidance when Parquet
  support is unavailable, and exposed a dedicated ``mariopy[parquet]`` extra.
* Hardened PyPI packaging metadata by sanitizing ``README.rst`` raw-directive
  blocks before publishing it as the package long description and by declaring
  the ``text/x-rst`` content type explicitly in ``setup.py``.

Documentation
~~~~~~~~~~~~~

* Added installation guidance for optional Parquet support and refreshed the
  README setup instructions.
* Reworked API-reference navigation and expanded the shock-workflow and
  transformation documentation, including doc-build warning fixes and notebook
  metadata cleanup for the published docs.

v1.0.0
------

*Released 2026-06-03.*

Architecture and public API
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Reorganized MARIO around clearer ``api``, ``compute``, ``ops``, ``parsers``,
  ``views``, ``storage`` and ``internal`` modules.
* Moved most legacy logic out of ``core`` and ``tools`` and consolidated the
  public surface around ``Database``.
* Added support for renamed baseline scenarios, more ergonomic matrix/index
  inspection helpers, and template-based custom database authoring workflows.
* Added a unified ``Database.plot(...)`` workflow backed by Plotly Express and
  kept the historical plotting helpers as deprecated compatibility wrappers.
* Added exploded multiplier and footprint accessors on ``CoreModel`` through
  ``f_ex``, ``fa_ex``, ``fc_ex``, ``m_ex``, ``ma_ex``, ``mc_ex`` and the
  corresponding ``*_all`` convenience properties.
* Added a more explicit compute layer with planner, resolver, primitives,
  formula modules and dependency graph utilities.
* Added trade-analysis APIs, trade-content plotting, parser-based scenario
  import workflows, and default shock clusters with automatic region mapping.
* Configured MARIO to default to ``INFO`` logging on import while preserving
  explicit ``set_log_verbosity(...)`` overrides.

Parsing and export
~~~~~~~~~~~~~~~~~~

* Added ``matrix_layout`` as a backward-compatible alias for
  ``matrix_layouts`` in Excel parsing entry points and reject ambiguous calls
  that pass both names at once.
* Unified Excel, TXT and Parquet parsing through a shared parser-state flow.
* Added native flat TXT/Parquet export and matching re-import support.
* Introduced ``matrix_layouts`` support for richer IOT and SUT layouts,
  including cases where ``V`` and ``E`` carry additional ``Region`` and
  ``Sector``/``Activity`` levels.
* Preserved legacy public axes for historical workbooks while allowing newer
  explicit layouts without forcing ``Level`` markers back into exports.
* Added structural ``tech_assumption`` support for SUT parsing with
  ``industry-based`` / ``product-based`` modes, including automatic fallback to
  ``industry-based`` for non-square SUT tables.
* Expanded direct parser coverage with BEA supply-use, CEADS, CEPALSTAT,
  USEEIO and GLORIA support, and improved parser robustness for FIGARO,
  OECD ICIO, EMERGING bundles and zip-based imports.

Add sectors and structural operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Refactored ``add_sectors`` around a workbook-driven workflow with a single
  template format.
* Added CVXLab-backed ``split=True`` support for IOT workflows, including a
  packaged ``Split_sectors`` model template.
* Improved ``add_sectors`` compatibility with explicit IOT layouts where
  ``V``/``E`` do not follow the old ``Region/Level/Item`` convention.
* Added overwrite protection to ``get_add_sectors_excel(...)`` and
  ``get_inventory_sheets(...)`` so existing files and inventory sheets are not
  replaced unless ``overwrite=True`` is passed explicitly.

Aggregation and transforms
~~~~~~~~~~~~~~~~~~~~~~~~~~

* Made aggregation robust to layout-aware ``V`` and ``E`` blocks without
  breaking the legacy public surface.
* Changed ``aggregate(...)`` to default to ``calc_all=False`` and hardened
  sparse export paths, including a fix for sparse ``to_parquet(...)`` output.
* Added a default ``zero_output_epsilon`` fallback during aggregation so
  zero-output items with non-zero stored coefficients do not lose their
  reconstructed ``z``/``v``/``e`` columns after aggregation.
* Added ``VY`` as a first-class factor-of-production final-demand block across
  MARIO.
* Kept transformation utilities in the new ``ops`` layout and aligned them with
  the refactored parser/database flow.
* Added SUT-native structural assumption management, including a public
  ``change_assumption(...)`` workflow and table-aware reset operations that now
  preserve split SUT blocks instead of rebuilding unified placeholders first.

Compute and SUT semantics
~~~~~~~~~~~~~~~~~~~~~~~~~

* Added product-based SUT support to the compute layer, including the public
  matrix ``c`` and the corresponding supply-side formulas alongside the
  historical industry-based path.
* Made SUT technology assumptions a first-class database property that is
  stored in metadata, shown in database summaries, preserved by test fixtures,
  and cleared when transforming SUT databases into IOT form.
* Added ``Database.calc_ghg(...)`` with built-in EXIOBASE, EORA, GLORIA and
  EMERGING profiles, plus improved metadata matching and satellite-account
  aggregation.
* Added SUT-specific Ghosh formulas alongside the refactored supply-side
  compute path.
* Introduced sparse-aware helper routines for shared compute operations such as
  row/column sums, matrix-matrix products, and matrix-vector products, and
  routed more IOT/SUT formulas through those helpers instead of direct
  pandas/NumPy calls.

Parsers and downloaders
~~~~~~~~~~~~~~~~~~~~~~~

* Added or rewrote direct parsers for Eurostat SDMX, FIGARO, OECD ICIO, WIOD,
  ADB MRIO, EMERGING, EORA, GTAP, StatCan and EXIOBASE IOT/SUT/hybrid data.
* Separated raw-data download utilities from parser-side logic and exposed a
  cleaner downloader surface.

Testing and documentation
~~~~~~~~~~~~~~~~~~~~~~~~~

* Greatly expanded the automated test suite across compute, parser, export,
  downloader and add-sectors workflows.
* Added focused regression coverage and API reference pages for exploded
  matrices and the new plotting workflow.
* Added vendored real-data workbook fixtures for IOT and SUT plus aggregation
  templates, with roundtrip tests for Excel, TXT and Parquet exports.
* Added pandas 3 compatibility fixes, parser coverage reporting, and broader
  parser/developer documentation refreshes across the user guide and README.
* Added a visualization user-guide notebook for ``db.plot(...)`` and updated
  notebook resolution so published docs persist HTML Plotly output instead of
  unsupported ``application/vnd.plotly.v1+json`` payloads.
* Removed GTAP and CEPALSTAT pages from the published documentation while
  keeping their parser implementations in the package.
* Rewrote and expanded developer-facing documentation, tutorials and parser
  development guidance.

Requirements
~~~~~~~~~~~~

* MARIO now requires pandas 3 (``pandas==3.0.2``) and therefore Python 3.11
  or later. ``xlsxwriter`` and ``openpyxl`` are pinned to 3.2.9 and 3.1.5;
  ``numpy`` stays at 2.1.1.
* New runtime dependencies: ``pint``, ``scipy``, ``h5py``, ``pyxlsb``,
  ``country_converter`` and ``cvxlab`` (for ``add_sectors(split=True)``).

v0.3.5
------

*Released 2025-01-31.*

Parsers
~~~~~~~

* Added ``parse_oecd(path, year)`` for OECD ICIO tables and
  ``parse_exiobase_3_9_4(path)`` for EXIOBASE 3.9.4. Both read the source
  with pymrio and convert the result with ``parse_from_pymrio``
  (`#126 <https://github.com/it-is-me-mario/MARIO/pull/126>`__).
* ``parse_exiobase`` accepts ``version="3.9.4"`` and now uses it by default.
  Pass ``version="3.8.2"`` or ``"3.8.1"`` to read older archives.

Documentation
~~~~~~~~~~~~~

* Added a tutorial on the pymrio-based parsers and an API page for
  ``parse_oecd``.

v0.3.4
------

*Released 2024-10-30.*

Parsing
~~~~~~~

* Recent pandas versions read the label ``"None"`` as a missing value. Index
  labels that pandas reads as NaN, or that are ``"-"``, are now restored to the
  string ``"None"`` when parsing Excel and TXT files and when reading
  aggregation workbooks. Duplicated labels are not checked.
* Parsing raises an error naming the matrices that contain NaN values.
* ``parse_eora`` checks that the requested ``table`` matches the single-region
  file, including SUT files requested as IOT.
* Fixed the extension check of the hybrid EXIOBASE parser and clarified parser
  error messages.

Export
~~~~~~

* ``to_txt`` writes the units file to both the flows and the coefficients
  folders (`#114 <https://github.com/it-is-me-mario/MARIO/issues/114>`__).
* ``to_excel`` and ``to_txt`` always write units: their ``units`` argument was
  removed. At least one of ``flows`` and ``coefficients`` must be ``True``.
* Fixed the metadata path written by ``to_excel(include_meta=True)``.

Removed
~~~~~~~

* ``parse_eurostat_sut`` now raises an error. It depended on table layouts
  produced by the Eurostat web interface
  (`#115 <https://github.com/it-is-me-mario/MARIO/issues/115>`__). Rearrange
  such tables into the MARIO format, as in ``test_SUT_standard.xlsx`` under
  ``mario/test``, or install ``mariopy==0.3.3``.

Requirements
~~~~~~~~~~~~

* Pinned ``pandas==2.2.3``, ``numpy==2.1.1``, ``xlsxwriter==3.2.0`` and
  ``openpyxl==3.1.0``, and raised IPython to ``>=8.27.0``. ``plotly``,
  ``tabulate`` and ``pyyaml`` are unpinned.

v0.3.3
------

*Released 2024-09-26.*

Fixes
~~~~~

* ``to_excel(flows=True)`` wrote ``Y`` in place of ``EY``, repeating rows in
  the exported workbook
  (`#107 <https://github.com/it-is-me-mario/MARIO/issues/107>`__).
* ``download_figaro`` uses the new Eurostat download links
  (`#108 <https://github.com/it-is-me-mario/MARIO/issues/108>`__). Files
  from the new links were not tested with ``parse_FIGARO_SUT`` at release.

v0.3.2
------

*Released 2024-06-29.*

Fixes
~~~~~

* Fixed installation from PyPI: the ``mario.settings`` package and its YAML
  files were missing from the distribution, so ``import mario`` failed
  (`#103 <https://github.com/it-is-me-mario/MARIO/pull/103>`__).

v0.3.1
------

*Released 2024-06-29.*

Fixes
~~~~~

* ``parse_FIGARO_SUT`` swapped the supply and use tables and built ``Z`` with
  the wrong shape
  (`#102 <https://github.com/it-is-me-mario/MARIO/pull/102>`__).

v0.3.0
------

*Released 2024-06-27.*

Settings and nomenclature
~~~~~~~~~~~~~~~~~~~~~~~~~

* Added ``mario.settings``: a ``settings.yaml`` file maps MARIO's matrix
  names and index levels to user-defined names. ``download_settings``,
  ``upload_settings`` and ``reset_settings`` manage the file; ``Nomenclature``
  and ``Index`` expose the active names
  (`#76 <https://github.com/it-is-me-mario/MARIO/issues/76>`__,
  `#80 <https://github.com/it-is-me-mario/MARIO/pull/80>`__).
* Exported the ``IOT`` and ``SUT`` table-type constants.

Table transformations
~~~~~~~~~~~~~~~~~~~~~

* Added ``Database.to_chenery_moses`` to convert an Isard SUT into a
  Chenery-Moses SUT, moving trade from the use table to the supply table.
  ``is_isard`` and ``is_chenerymoses`` report the current form
  (`#90 <https://github.com/it-is-me-mario/MARIO/pull/90>`__).

Data templates
~~~~~~~~~~~~~~

* Added ``DataTemplate`` and ``MatrixBuilder`` to build empty IOT or SUT
  databases from lists of regions, sectors and other sets
  (`#71 <https://github.com/it-is-me-mario/MARIO/issues/71>`__).

FIGARO
~~~~~~

* Added ``download_figaro(table, year, path)`` and ``parse_FIGARO_SUT``.
  The parser reads the supply-use tables; environmental extensions are not
  parsed (`#95 <https://github.com/it-is-me-mario/MARIO/pull/95>`__).

Add sectors
~~~~~~~~~~~

* Rewrote ``add_sectors`` for readability and speed, with unit tests. Empty
  input sheets are accepted, and a missing unit of measure raises an error
  naming the item.

Compatibility
~~~~~~~~~~~~~

* Removed the upper bounds on pandas and xlsxwriter and fixed the pandas
  deprecations they exposed (``DataFrame.append``, ``groupby(axis=...)``)
  (`#31 <https://github.com/it-is-me-mario/MARIO/issues/31>`__).
  ``pyyaml`` is a new dependency. Irrelevant openpyxl warnings are filtered.

Fixes
~~~~~

* ``parse_exiobase`` failed on the hybrid EXIOBASE folder when a year was
  passed; the hybrid table has a fixed year (2011)
  (`#66 <https://github.com/it-is-me-mario/MARIO/issues/66>`__).

Removed
~~~~~~~

* ``Database.reset_to_backup``, ``Database.set_solver`` and
  ``CoreModel.is_productive``.

Documentation
~~~~~~~~~~~~~

* New tutorials on parsers, table transformations and ``add_extensions``, a
  new documentation theme, and an updated ReadTheDocs configuration.

v0.2.2
------

*Released 2023-09-16.*

Downloads
~~~~~~~~~

* Added ``download_hybrid_exiobase(path)`` and exposed the pymrio download
  functions ``download_eora26``, ``download_exiobase1``,
  ``download_exiobase2``, ``download_exiobase3``, ``download_oecd`` and
  ``download_wiod2013`` from ``mario``.

Documentation
~~~~~~~~~~~~~

* The README lists pymrio as a dependency and describes the test suite.
  ``CITATION.cff`` was removed.

v0.2.1
------

*Released 2023-05-30.*

Fixes
~~~~~

* ``aggregate`` checked only the baseline for missing matrices, failing on
  databases with several scenarios.

Requirements
~~~~~~~~~~~~

* Pinned ``pandas<=1.3.5``: newer pandas releases broke MARIO. The
  installation guide explains how to avoid the conflict.

Documentation
~~~~~~~~~~~~~

* Added ``CITATION.cff`` and refreshed the documentation.

v0.2.0
------

*Released 2023-05-04.* The release was tagged ``v2.0.0`` in git by mistake;
the package version is 0.2.0. The ``v2.0.0-doi`` pre-release archives it on
Zenodo.

Breaking changes
~~~~~~~~~~~~~~~~

* ``Database.sut_to_iot`` was renamed ``Database.to_iot``
  (`#16 <https://github.com/it-is-me-mario/MARIO/issues/16>`__).
* ``parse_from_txt`` and ``parse_from_excel`` no longer default to
  ``mode="flows"``: ``mode`` is required
  (`#40 <https://github.com/it-is-me-mario/MARIO/issues/40>`__).
* ``parse_eurostat`` was replaced by ``parse_eurostat_sut``, rewritten for the
  new Eurostat table layout and with checks on the downloaded files
  (`#8 <https://github.com/it-is-me-mario/MARIO/issues/8>`__).
* ``parse_eora`` takes a required ``table`` argument and can read
  single-region SUTs.
* The licence changed from CC BY-NC-SA 4.0 to GNU GPL v3.0.

pymrio integration
~~~~~~~~~~~~~~~~~~

* Added ``Database.to_pymrio`` and ``parse_from_pymrio`` to convert databases
  to and from pymrio ``IOSystem`` objects
  (`#14 <https://github.com/it-is-me-mario/MARIO/pull/14>`__). pymrio is a new
  dependency.

Parsers
~~~~~~~

* Added ``parse_exiobase``, one entry point for the EXIOBASE IOT, SUT and
  hybrid tables (`#36 <https://github.com/it-is-me-mario/MARIO/issues/36>`__).
* Added ``hybrid_sut_exiobase`` for the CSV release of hybrid EXIOBASE on
  Zenodo, much faster to read than the Excel files
  (`#37 <https://github.com/it-is-me-mario/MARIO/issues/37>`__).

Database API
~~~~~~~~~~~~

* Added ``Database.query`` to extract matrices without the nested output of
  ``get_data`` (`#33 <https://github.com/it-is-me-mario/MARIO/issues/33>`__).
* ``search`` gained ``ignore_case``
  (`#27 <https://github.com/it-is-me-mario/MARIO/issues/27>`__).
* ``to_excel`` and ``to_txt`` gained ``include_meta`` to save the metadata as
  ``metadata.json``.
* ``get_aggregation_excel`` and aggregation tables reject items that are not
  in the database; missing items stay unaggregated.
* ``backup`` moved from ``Database`` to ``CoreModel``.

Fixes
~~~~~

* Backward linkages summed rows instead of columns. ``plot_linkages`` also got
  a fixed legend title and clearer hover values
  (`#43 <https://github.com/it-is-me-mario/MARIO/issues/43>`__).
* ``parse_from_txt`` failed with ``mode="coefficients"`` because ``to_txt``
  and the parser used different separators
  (`#47 <https://github.com/it-is-me-mario/MARIO/issues/47>`__).
* Index and column level names are kept after transformations such as
  ``to_iot`` and ``aggregate``
  (`#11 <https://github.com/it-is-me-mario/MARIO/issues/11>`__).
* ``calc_all`` raises ``WrongInput`` for an unknown scenario instead of
  treating it as a matrix name
  (`#30 <https://github.com/it-is-me-mario/MARIO/issues/30>`__).
* ``add_extensions`` failed with ``inplace=False``, and checked ``EY`` even
  when adding ``V`` rows. Fixed the unit check of aggregations.
* ``f_dis`` is no longer computed as a database matrix; ``calc_f_dis`` remains
  available.

Testing and documentation
~~~~~~~~~~~~~~~~~~~~~~~~~

* Added the first unit test suite and a CI workflow.
* Documented the pymrio integration and the new API functions.

v0.1.0
------

*Released 2021-11-01.* First public release, by Mohammad Amin Tahavori,
Lorenzo Rinaldi and Nicolò Golinucci at Politecnico di Milano.

* ``Database`` class for single- and multi-regional, monetary and hybrid
  input-output and supply-use tables, with scenarios.
* Parsers for EXIOBASE 3 IOT (``parse_exiobase_3``), EXIOBASE SUT
  (``parse_exiobase_sut``), EORA (``parse_eora``) and Eurostat
  (``parse_eurostat``), and for user tables in Excel or TXT
  (``parse_from_excel``, ``parse_from_txt``).
* Aggregation, SUT-to-IOT conversion, single-region extraction, new
  extensions (``add_extensions``) and new sectors (``add_sectors``) through
  Excel templates.
* Shock and sensitivity analysis from Excel templates (``shock_calc``),
  linkages, GDP and balance checks.
* ``calc_*`` functions for every IO matrix, Plotly plots (``plot_matrix``,
  ``plot_gdp``, ``plot_linkages``, ``plot_bubble``), and export to Excel and
  TXT.

The ``v0.1.0`` git tag (2021-12-29) also holds these changes, which reached
PyPI with 0.2.0:

* Added ``calc_f_dis``, footprints split by origin region and sector.
* The price index ``p`` can be plotted, also for SUTs, and plots of ``X``
  for SUTs were fixed.
* ``plot_gdp`` gained ``drop_reg``, ``title`` and the ``"specific footprint"``
  and ``"absolute footprint"`` extension values.
* Databases can be compared with ``==``.
* ``parse_exiobase_sut`` reads units as ``EUR`` instead of ``M EUR``.
