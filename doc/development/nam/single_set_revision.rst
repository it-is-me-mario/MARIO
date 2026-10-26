.. Internal design revision; not part of the published manual.

NAM revision: one accounting set per block axis
===============================================

This page records the implemented single-set revision (runtime schema and
native workbook version 2). Account coefficients and the national FIGARO SUT/IOT
projection are implemented; general conversion recipes remain proposals.

Agreed constraints
------------------

* Each elementary accounting block has exactly one accounting set on its rows
  and one on its columns. A union of several sets is not an acceptable terminal
  domain. Reference economy and observed partner/product descriptors remain
  explicit roles in ``matrix_layouts``.
* Institutional income and capital remain distinct sets. Resident and
  nonresident sets also remain distinct; they cannot be combined into a single
  block under an ``income`` or ``capital`` union.
* The complete NAM view has the same account list and order on both axes.
  This does not require symmetric values or transpose relationships between
  opposite flow blocks. ``T`` is the composite view of the whole system, rather
  than an elementary block obeying the single-set rule.
* Use a single residual set, ``Other accounts`` (proposed ID ``other``, short
  alias ``o``), for statistical discrepancies and source-specific routing that
  do not fit the main economic sets. Their identity, type, signs and observed
  flows must be retained as distinct items; do not create a set per residual
  account or collapse the items into a single ``Other`` balance.
* Regrouping classifications is not economic aggregation or elimination of
  accounts. Distinct source routing nodes must not be summed, removed or
  confused with aggregate control totals.
* A block covers the full membership of each of its two sets, including
  legitimate zero rows and columns, as already required for the tax blocks.

Consequences for the block catalogue
------------------------------------

For illustration, with ``d`` for resident/domestic and ``f`` for nonresident,
the current ``RI`` needs two blocks: income-resident by factor and
income-nonresident by factor. The current ``RS`` needs four set pairs:

.. list-table:: Saving flows, illustrative names
   :header-rows: 1
   :widths: 20 40 40

   * - Name
     - Rows
     - Columns
   * - ``RS_dd``
     - Resident capital sectors
     - Resident income sectors
   * - ``RS_df``
     - Resident capital sectors
     - Nonresident income sectors
   * - ``RS_fd``
     - Nonresident capital sectors
     - Resident income sectors
   * - ``RS_ff``
     - Nonresident capital sectors
     - Nonresident income sectors

These names are registered in the runtime contract. The same reasoning
applies to distributive flows, financial transactions, imports and exports.
For example, an import block cannot join investment-category destinations and
institutional-capital destinations on a single axis. Capital-account results
such as ``B9`` also need separate resident/nonresident presentations.

Consolidating several source sets into one broader logical set can instead
merge blocks with the same resulting set pair. For example, fixed investment,
inventories and acquisitions of nonproduced assets may share a broader capital
acquisition block while retaining item types. The revised registry must give
each authoritative cell one owner and preserve exclusive import authority.

``Other accounts`` appears on both axes of the complete NAM. Blocks involving
it use the full declared membership, including zero items. An Other-by-Other
block records observed links between residual accounts. If regrouping creates
several source flow families with the same ordered set pair, consolidate them
into one authoritative block and retain the family/type on the items and in
source metadata; named selections must not become duplicate native payments.

Implemented regrouping
-------------------------------

The following source placements preserve the economic role and item type.

.. list-table:: Placement in broader logical sets
   :header-rows: 1
   :widths: 26 34 40

   * - Current distinction
     - Host set
     - Meaning to retain
   * - Distribution and capital transfers
     - Distributive transactions
     - Distinguish current transfers from capital transfers.
   * - Fixed assets, other investment and nonproduced assets
     - Non-financial assets
     - Distinguish fixed assets, inventories, valuables and nonproduced assets.
   * - Statistical adjustment
     - Other accounts
     - ``B9FX9`` remains an observed discrepancy, outside financial instrument
       transactions and the computed financial-side ``B9``.
   * - Investment demand and allocation pools
     - Other accounts
     - Retain ``P51G`` and ``B8_S1`` as distinct routing nodes, respectively a
       demand pool and a saving-allocation pool. Neither is an asset type.
       ``B8_S1`` is not interchangeable with the zero institutional ``S1`` control.
   * - External trade clearing
     - External trade account (``tr``), separate from Other
     - Retain ``P7`` and ``P33`` as explicit trade-clearing nodes. A nonresident
       institutional item such as source ``S2`` retains its institutional
       accounting role instead of moving to Other just because it is foreign.

Short aliases should keep existing MARIO conventions where the meaning is
unchanged: ``r``, ``a``, ``c``, ``f`` and ``n``. New aliases and block names
follow the chosen logical sets. The institutional convention is
``si_d`` / ``si_f`` for income and ``sc_d`` / ``sc_f`` for capital; these are
accepted by the NAM API.
The residual set uses the proposed alias ``o``; its item metadata identifies
discrepancies and investment routing without a fourth account index level.
Trade clearing remains in the separate ``tr`` set.

Implementation and verification scope
-------------------------------------

The runtime and development catalogues, FIGARO adapter, financial results,
summary, aliases, template and export/reload contract use the same set pairs.
``T`` uses the full square accounting view. ``B9_d`` and ``B9_f`` are separate
financial results, not additional native flows. The workbook version is 2;
version 1 is rejected with instructions to reparse the original FIGARO source
or regenerate the template. Existing workbooks are not silently rewritten.

The diagram is generated as a square set-by-set registry. Verify every retained
FIGARO cell and native block through export/reload, along with item types,
legitimate zeros, missing-data states and exclusive import authority.
