.. Internal development archive; not part of the published user documentation.

BONSAI regional-index method diagnosis
======================================

This is a development snapshot from 2026-10-19, after the first regional
``get_index`` change. It identifies the next adaptations; it does not claim
that all MARIO methods support BONSAI yet.

The summary regression has since been fixed: regional sets display
``from X to Y per region``, counting the members of each regional list and
including empty regions. Common classifications retain scalar counts.
``search`` has also been adapted: it searches inside the regional lists and
groups matches by region, with explicit union and region selectors. See
:doc:`/api_document/mario.CoreModel.search` for examples. The tables and
downloadable snapshot below record the initial diagnosis before these fixes;
rerun the ``repr`` and ``search`` probes to check the updated behavior.
Cluster handling has also been adapted. Regional sets now retain dictionaries
of regional lists in automatic ``all`` and user clusters. Validation checks
each region-code pair, and list shorthand is intersected with each regional
domain. Common sets keep their previous list clusters. Shock expansion uses
actual nodes and supports sparse updates; Excel picklists use observed code
unions without discarding the stored regional definitions. See
:doc:`/api_document/mario.Database.set_clusters` for this contract. The
initial snapshot below predates these adaptations as well.

Aggregation has since been adapted too. Regional template sheets group regions
by their entire label sets and include groups of one. Readers expand those rows
to real region-item pairs, retaining omitted nodes. Geographic mergers now
require matching string sets across all regional classifications, including
consumption categories. Region presets obey the same check; the unrestricted
``WORLD`` probe below is now expected to be rejected for a nonuniform database.
Aggregation also caches axis mappings and handles sparse zero-output column
replacement. See :doc:`/api_document/mario.Database.get_aggregation_excel`
and :doc:`/api_document/mario.Database.aggregate`. Historical outcomes below
remain unchanged as a record of the initial diagnosis.

On Balanced 20260615, exact label comparison produces 50 separate Activity
classifications and 50 separate Commodity classifications. Consequently the
current Region template has headers only: no original regions meet the merge
criterion. The item sheets still contain all 51,356 activity pairs and 53,400
commodity pairs, while shared final-demand classifications reduce to 13 rows
covering 267 regional category pairs. Regional item aggregation can be applied
first; a new template then reflects any classifications made identical by
those explicit mappings.

Database equality now compares the members of each region for regional sets.
The same region keys and global code union are insufficient for equality.
Ordering of regions and labels remains irrelevant, and common lists retain
their previous comparison behavior. Equality continues to compare logical
indexes rather than matrix values or units. The equality failure in the initial
snapshot below therefore predates this correction.

``calc_trades`` has also been adapted to regional classifications. Code
validation uses the observed union, while flow selection uses actual matrix
pairs. Sparse blocks reduce directly to regional totals and all database regions
remain in the output, including regions without a selected origin node or final
demand. Native supply-format detection avoids constructing a unified ``Z`` view.
Historical trade failures below predate this change; trade-content calculations
still require separate validation of their coefficients and multipliers.
On the complete Balanced bundle, the 50-by-50 trade result for ``C_TLAND_ALL``
matches independent COO sums of both ``U`` and ``Yc``. Four regions without that
commodity have zero origin rows, and no unified ``Z`` or ``z`` is materialized.

Trade-content indicator loading now follows the selected method: ``direct``
requests only direct coefficients, ``total`` resolves total multipliers, and
``upstream`` requires both. Total contributor breakdowns no longer construct an
unused direct diagonal. Direct contributor breakdowns have also been adapted:
actual flow entries are weighted without a square diagonal,
and sparse inputs retain sparse output with the existing contributor index and
zero rows. Region clusters are applied before output expansion, retaining each
contributor's original labels. Total/upstream breakdowns now project the trade
vectors through the native coefficient system too, retaining Activity and
Commodity contributors without constructing an inverse or exploded multiplier.
Upstream subtracts direct contributions at vector level. Sparse collapsed
totals use the same projected calculation, while dense collapsed totals retain
their existing multiplier path. Large iterative solves apply the split system
as an operator rather than forming its coefficient product.
Existing coefficient and multiplier formulas are unchanged; in particular Isard
SUT direct content remains based on ``ec``/``vc``.
On the complete Balanced bundle, direct content was checked against independent
weighted COO sums of ``U`` and ``Yc`` with queries limited to ``ec``, ``U`` and
``Yc``. No total multiplier or inverse was materialized. The imported ``Ec`` is
zero, so nonzero numerical checks for all three methods use small models.
The direct contributor breakdown has also been checked on the complete bundle:
its sparse 2,670,000-by-50 result preserves the 53,400 actual contributor nodes
and sums to the collapsed result. A one-region trade cluster preserves those
contributor labels. Neither check constructs a direct diagonal or an inverse.
Total and upstream breakdowns were also checked on the complete bundle for
``M_Artis`` and the first satellite account (standing wood). Their sparse
5,237,800-by-50 outputs contain all 104,756 actual Activity/Commodity nodes per
trade origin and nonzero contributions from ``Ea``. They agree with collapsed
totals and satisfy ``total - direct = upstream`` after label alignment. This
does not change the meaning of Isard direct content: it still uses ``ec``/``vc``.

``calc_linkages`` has since been adapted to sparse coefficient systems and real
regional nodes, including exact diagonal exclusion. Its historical SparseArray
assignment failure below is fixed. Small invertible models retain the legacy
values and output layout. On the complete Balanced bundle, a generic
strong-component singularity check instead identifies two four-node Ghosh
components in Taiwan (``Beany`` and ``Eggs_ggs``). The method reports their actual
nodes and raises an error before requesting inverse views. No source values or
regional memberships are changed and no nodes are excluded. Turning off
diagonal exclusion does not resolve this singularity. See
:doc:`/api_document/mario.Database.calc_linkages`.

Inspection on 2026-10-20 identified an important qualification: the two Taiwan
market Commodity nodes explicitly have mass balance disabled in the source
classification. Their supplied quantities differ from ``U + Yc``. MARIO's
current demand-based ``Xc`` creates singular Leontief blocks too, whereas the
corresponding reference-supply-minus-use blocks used by the BONSAI HIOT
construction are nonsingular. Thus this is a limitation of applying the current
output convention to these unbalanced HSUT nodes, not proof that BONSAI's
published HIOT is singular. See ``taiwan_output_normalization_20261020.json``
for the source quantities and independent two-by-two determinant checks. A
change to the HSUT output convention requires an explicit mathematical policy;
the solver neither changes source flows nor silently substitutes a solution.

``update_supply_mix`` and ``update_trade_mix`` have also been adapted. Supply
labels are validated in their specified region, while every trade item must
exist in every explicitly listed origin, including zero-weight origins. Missing
pairs raise an error rather than being created or silently removed from the
weights. A destination may import an item without a local node for that item.
Column filters apply to actual buyer, market and final-demand columns. Sparse
updates preserve storage, bundle column totals, unselected rows and other
scenarios. Level inference can distinguish labels by their regional memberships;
ambiguity within the requested regions still requires an explicit level.
Explicit commodity aggregation maps the observed region-code pairs only. The
historical mix failures below predate these changes.
On the complete Balanced bundle, Activity and Commodity supply mixes and a
Commodity trade mix were checked against independent sparse sums. The checks
preserve unselected entries and actual axes and reject absent regional pairs.
``M_Artis`` is present on both classifications in the selected origins, so that
trade example specifies ``level="Commodity"`` explicitly.

``to_pymrio`` now reports nonuniform Sector or Consumption category
classifications as unsupported before requesting matrices or creating an
``IOSystem``. Common regional classifications retain their existing export
path. Flattening original region-item identities into a single-region model
would be a separate representation change; the exporter does not perform it.
Direct SUT export still requires a SUT-to-IOT conversion first. The historical
``to_iot("B").to_pymrio()`` shape error below is replaced by this explicit
capability error. SUT-to-IOT conversion is handled independently, as described
in the follow-up below.

``pool_trade`` is also explicitly unsupported when Activity, Commodity or
Consumption category classifications differ between regions. It raises
``NotImplementable`` before copying or querying the model, including with
``inplace=False``. This is a format restriction rather than a BONSAI-specific
check; pooling for common classifications retains its existing behavior.
The historical unknown-label or missing-node errors below are replaced by
this capability error. Regional pooling is deferred until it is needed.

``to_chenery_moses`` has since been rewritten around native flow blocks and
sparse origin-to-destination allocation matrices. It preserves Activity nodes
and matches Commodity codes by exact strings. Existing Commodity nodes remain;
additional destination markets are created only for observed nonzero use or
final-demand flows. ``Ya``, activity accounts and direct final-demand accounts
are preserved. Supply and Commodity accounts are distributed to destination
markets while retaining their row totals. Unselected scenarios are zero-extended
on new shared market axes, preserving existing flows. Undefined zero-net trade
shares raise an error, and unused source commodities retain their original
supply/accounts without balancing adjustments.
On the complete Balanced 20260615 bundle, ``Ya`` is entirely zero, the 51,356
Activity nodes remain unchanged, and 8,125 observed import markets expand the
Commodity axis from 53,400 to 61,525 nodes. Independent sparse checks preserve
use/final-demand totals by Commodity code and buyer, Activity supply totals and
account totals. The transformation requests no unified ``Z``/``Y`` views,
diagonal matrices or inverse systems. Common dense cases retain dense output
blocks. The historical transformation failure below predates these changes.

``is_isard`` now mirrors the native supply-format check: it reuses an already
cached unified source, otherwise reads native ``U``. Sparse regional sums use
actual origin/destination names rather than assuming the same regional order
or rectangular memberships. The complete Balanced table is detected as Isard
without building ``Z`` or ``z``. The historical resource limit below predates
this correction.

``to_iot`` now operates on native blocks too. B/D use sparse products and retain
the actual Commodity/Activity nodes as IOT Sectors, respectively. They preserve
nonzero ``Ya`` by allocating eliminated flows and accounts to both intermediate
and final uses. Activity and Commodity accounts are both retained; ``EY`` and
``VY`` include accounts allocated to direct final uses. A/C use bounded batches
of supply solves and require square, nonsingular supply and zero ``Ya``. No
dense diagonal or inverse is constructed, and singular or undefined allocations
raise explicit errors without pseudoinverses, balancing or source-data repairs.
Dense common tables retain their storage and classical zero-``Ya`` formulas.
Conversion still uses the baseline and drops other scenarios, as before.

On the complete Balanced 20260615 bundle:

* D completes with 51,356 observed Activity/Sector nodes, 267 final-demand
  columns and 2,679,945 nonzero transactions in sparse ``Z``. Independent checks
  retain original Activity output, account totals, units and regional membership,
  and verify sampled output rows against commodity-by-commodity allocations.
  The source blocks remain unchanged. The 21 original zero-output activities
  remain zero-output sectors, including their original inputs/accounts; this
  conversion does not assert or repair source balance.
* B raises ``WrongInput`` for nine Activity nodes with zero output and nonzero
  inputs/accounts. Six are ``A_MA_INCI_no_recov`` in DE, GB, HU, IT, NL and RO;
  the others are ``A_CHEM`` in TW, ``A_BKBP`` in WF and ``A_Hempd`` in WM.
  Allocating their inputs/emissions over products would require undefined
  shares. They are neither silently discarded nor moved to an invented sink.
* A/C raise ``NotImplementable`` because the original supply has 51,356 Activity
  rows and 53,400 Commodity columns. Regional nonuniformity alone is not a
  restriction: square, invertible nonuniform examples are covered separately.

Small tests also verify B/D final-demand impacts against the original split
linear system with nonzero ``Ya`` and both sides' accounts, and all four methods
against their dense classical formulas. These are conversion checks, not a
claim that all downstream IOT operations scale to a complete BONSAI IOT.

Index contract
--------------

``get_index(name)`` returns the existing ordered list when every region has
the same members, or ``{region: [members]}`` when memberships differ. Equal
counts are insufficient. Each set is evaluated independently::

    db.get_index("Activity")                # Regional dictionary on BONSAI.
    db.get_index("Activity", region="IT")   # List of 1,177 activities.
    db.get_index("Activity", flat=True)     # List of 1,585 distinct codes.

Regional membership comes from materialized matrix axes. The implementation
does not create missing region-item combinations. Stored logical indexes and
the internal ``ModelState.get_index`` remain in their previous representation
at this stage. See :doc:`/api_document/mario.CoreModel.get_index`.

Scope and comparison
--------------------

The diagnosis compares each operation on independent database copies with
the new getter and with the previous getter attached to the copy. Everything
else, including sparse blocks and input data, is identical. This isolates
getter regressions from existing limitations.

* **37 probes on a small balanced BONSAI-format bundle**, imported through
  ``parse_bonsai``. It has unequal activity, commodity and final-demand
  classifications in two regions, including nodes with zero flows.
* **12 probes on the complete Balanced 20260615 ZIP**, reference year 2016:
  50 regions, 51,356 activity nodes, 53,400 commodity nodes and 267
  final-demand nodes. Activity, commodity and consumption-category views
  are dictionaries; Region, Factor of production and Satellite account
  remain lists. ``Global`` has no final-demand members.

.. list-table:: Probe outcomes
   :header-rows: 1
   :widths: 50 25 25

   * - Outcome
     - Small bundle
     - Complete bundle
   * - Passed with both getters
     - 16
     - 3
   * - New getter regression
     - 11
     - 5
   * - Existing limitation or incorrect result
     - 8
     - 2
   * - Both fail, but the failure changes
     - 2
     - 0
   * - Time budget exceeded
     - 0
     - 2

The full-size activity aggregation also rejects valid labels with the new
getter, but the old-getter comparison exceeds its time budget, so that row
is counted as a resource limit. Counts refer to individual calls, not to a
guarantee for every option of a method.

New regressions
---------------

.. list-table:: Calls that succeeded with the previous getter on the small bundle
   :header-rows: 1
   :widths: 34 66

   * - Operation
     - Observed failure and cause
   * - ``str(db)`` / ``repr(db)``
     - Counts dictionary keys, reporting regions as activities or commodities.
       Reproduced on the complete bundle.
   * - ``search``
     - Searches region keys and misses an existing activity code. Reproduced
       on the complete bundle.
   * - ``default_clusters``
     - The ``all`` activity cluster contains region keys instead of activities.
       Reproduced on the complete bundle.
   * - ``set_clusters``
     - Membership validation compares an activity with dictionary keys and
       rejects it. Reproduced on the complete bundle.
   * - ``get_aggregation_excel``
     - Silently writes region names in the Activity sheet. Reproduced on the
       complete bundle.
   * - ``aggregate`` with an identity activity mapping
     - ``read_aggregated_index`` rejects valid activity labels when validating
       against the dictionary.
   * - ``calc_trades`` and ``calc_trades_content``
     - Reject a valid commodity because their validators compare it with
       region keys.
   * - ``get_shock_excel``
     - Calls ``extend`` on a dictionary.
   * - ``update_supply_mix`` and ``update_trade_mix``
     - Treat regional dictionaries as global lists and reject valid labels.

Other failures and limitations
------------------------------

.. list-table:: Problems that changing the getter alone does not resolve
   :header-rows: 1
   :widths: 34 66

   * - Operation
     - Diagnosis
   * - Database equality
     - Returns equal after regional activity memberships change while the
       global union stays the same. The old getter compares global unions;
       the new path compares region keys. Neither checks region-item pairs.
   * - ``calc_linkages``
     - Attempts unsupported in-place assignment into a pandas SparseArray
       with either getter.
   * - ``shock_calc`` for ``u``
     - The new getter rejects a valid commodity; the old getter proceeds
       until an unsupported SparseArray assignment. Both issues need work.
   * - ``pool_trade``
     - The new getter rejects a commodity. With the old getter it requests
       that commodity in a region where the node does not exist.
   * - ``to_chenery_moses``
     - Fails with an axis-length mismatch with either getter. Its rectangular
       region-by-item construction is incompatible with unequal memberships.
   * - ``to_iot("B").to_pymrio()``
     - The exporter tiles the global unit table once per region, producing
       more rows than the actual IOT nodes.
   * - ``is_balanced`` and ``to_region_subset``
     - Explicitly reject hybrid tables. These are existing restrictions,
       not evidence of a regional-index regression.
   * - ``to_pymrio`` directly on the HSUT
     - Explicitly requires an IOT.
   * - ``calc_ghg`` without explicit factors
     - No automatic BONSAI profile exists. Explicit diagnostic factors work.

On the complete bundle, region aggregation to ``WORLD`` fails with a sparse
assignment error in ``_clear_zero_output_sut_flow_overrides`` with both getters,
although it succeeds on the small bundle. The failing operation tries to clear
columns of zero-output activities through ``block.loc[:, impacted] = 0.0``.
Identity activity aggregation with the old getter and ``is_isard`` with both
getters exceed the 45-second per-call budget. They are not reported as
successful or as proven functional failures. In activity aggregation,
``_aggregate_legacy_axis`` repeatedly rebuilds the same mapping inside its
label loop. ``is_isard`` first constructs a unified ``Z`` view instead of
inspecting the existing split ``U`` block directly.

Calls that completed
--------------------

On the complete bundle, index access, native ``get_data`` and calculation of
``Xa``/``Xc`` complete with both getters. The independent release integration
test also checks all published product supply/use totals and regional counts.

On the small bundle, coefficient and footprint calculations, ``is_isard``,
extension-template generation, ``add_extensions``, the empty add-sectors
template, ``to_iot("B")``, a ``Yc`` bar plot and explicit-factor GHG calculation
complete. Regional aggregation to ``WORLD`` preserves totals in the checked
blocks. These calculation probes primarily establish structural compatibility;
they do not validate economic or environmental results.

Excel, CSV and Parquet roundtrips preserve regional memberships and numerical
values in the checked blocks. Their final-demand axes can change layout or
order: this also happens with the previous getter. Thus these are semantic
roundtrip checks, not exact pandas-axis identity checks.

Full-size inverses, dense exports, plots, shocks and footprints are not run.
Actual sector insertion and CVXLab optimization are not exercised: they need
a filled inventory workbook or a specified optimization problem.

Next implementation steps
-------------------------

1. Adapt shared selection and validation helpers to distinguish an explicit
   global union from valid region-item pairs. Fix summaries, search, clusters
   and workbook templates using that distinction.
2. Adapt aggregation mappings and validation, retaining only existing nodes
   and checking units. Remove repeated mapping construction and handle sparse
   zero-output updates. Test identity, item and region aggregation with value
   and membership checks before relying on the complete database.
3. Adapt trade operations, shocks and transformations, including their
   sparse writes and assumptions about equal regional dimensions. Compare
   regional memberships in database equality and preserve them in exports.

Replacing every internal use with ``flat=True`` would hide missing regional
nodes; only operations whose semantics require a global union should use it.

Reproduce
---------

From a source checkout in the MARIO development environment::

    PYTHONPATH=. python scripts/diagnose_bonsai_methods.py \
        --path /path/to/Balanced/20260615.zip \
        --output /tmp/bonsai-methods.json

Omit ``--path`` for the small bundle only. ``--methods`` selects specific
probes, ``--append`` replaces those results in an existing report, and
``--timeout`` changes the per-operation POSIX time budget. Reports are saved
after each completed comparison. All inputs are read-only; each operation
uses a copy and temporary output files.

The recorded environment is Python 3.13.14, pandas 3.0.2 and NumPy 2.1.1.
The :download:`raw diagnosis <bonsai_methods_20261019.json>` includes individual
calls, exception sites, timings and dataset counts.
