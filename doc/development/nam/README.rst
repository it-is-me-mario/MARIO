.. Internal implementation contract; not part of the published manual.

NAM format: data contract and implementation plan
=================================================

The native flow core, local FIGARO adapter and version 2 Excel template/I/O
implement the `single-set revision <single_set_revision.rst>`_. Each native
block has exactly one accounting set per axis. There are distinct resident
and nonresident income and capital sets; no elementary axis is their union.
The complete square ``T`` is a composite view and uses the identical ordered
account list on both axes. Values need not be symmetric.

Canonical structural definitions are in ``mario/model/nam_schema.json``.
The development `catalogue.json <catalogue.json>`_ must match its sets,
domains, block roles and import authority. Its generated `catalogue.rst
<catalogue.rst>`_ also records implemented account normalization and future conversion policies.
``implemented: false`` refers to that complete modelling proposal; flow
inspection, updates, scenarios, account totals, coefficients and native I/O
are implemented. Matrix symbols
are MARIO conventions, not universal NAM nomenclature.

Identity and geography
-----------------------

An accounting node is **Region / Set / Item**. Item labels are arbitrary;
FIGARO codes are interpreted only by its source adapter. Short names, set IDs
and display labels resolve to the same set. Matching item strings across
income and capital does not identify the same account. Memberships can differ
by reporting economy; do not create an unconditional Region-by-Item product.
Each block covers its complete two sets, including legitimate zero members.

Region identifies the economy reporting the national accounts. Nonresidents
are relative to that economy, not necessarily individually identified foreign
partners. Institutional rest-of-world codes such as ``S2`` belong to the
appropriate nonresident income/capital sets. They are distinct from trade
clearing nodes such as ``P7``/``P33`` in ``External trade account`` (``tr``).
Imports do not belong to ``Other accounts``.

Observed origin, destination and imported product are descriptor roles in
``matrix_layouts``. They can add native index levels without changing the
three-level account identity or inventing a fourth Account level. Retain the
richer native blocks when projecting them into ``T``. Unknown descriptors use
an explicit source marker, not inferred partner allocations.

Multiple files represent independent reporting economies with observed partner
detail. They are not a consolidated interregional NAM. Interregional
consolidation must distinguish each member's transactions with members and
nonmembers; summing S2 accounts does not achieve it.

Consolidated logical sets
-------------------------

Nonfinancial assets (``nf``) retain fixed assets, inventories, valuables and
nonproduced assets as typed items. Distributive transactions (``d``) retain
current and capital transfers. Other accounts (``o``) retain miscellaneous
adjustments and source-specific investment routing as distinct items; this is
regrouping, not economic aggregation or elimination of source nodes.

For FIGARO, ``B8_S1`` (saving-allocation pool), ``P51G`` (investment demand
pool) and ``B9FX9`` (observed discrepancy) belong to Other. ``B8_S1`` is a
nonzero routing account, not the zero ``S1`` institutional control. The
``IK_d``/``IK_f`` → ``O_nf`` → ``O_o`` → ``C_o`` chain preserves investment
ownership, asset allocation, pool linkage and product purchases respectively.
``M_o`` retains imported purchases through the demand pool. These margins do
not determine a joint product-by-asset-by-investor table.

One authoritative native block owns each registered ordered set pair. Blocks
involving Other contain all its items; opposite directions are separate
blocks. Item ``kind``, source code and description remain in immutable schema
metadata and editable workbook account columns. Source-specific routing must
not be removed or added again under duplicate flow aliases.

Authority, units and balances
------------------------------

Columns pay and rows receive. Store observed monetary flows, including signed
financial transactions, with currency, scale, period and valuation provenance.
Unavailable data differs from declared zero. ``T`` requires every active flow
domain to be supplied or explicitly declared zero. An empty set pair does not
require a fictitious observation. Availability is not balance certification.

Import authority is exclusive: ``use_imports`` has domestic product uses plus
``MU``, ``MY``, ``Minv``, ``M_o`` and ``Mcap_d``/``Mcap_f``; ``supply_imports``
has total uses plus product-side ``MS``. An alternative representation may be
a derived view only. Never count both. A shape does not choose a behavioural
allocation model or establish a valuation bridge.

``B9_d`` and ``B9_f`` calculate financial-side net lending from their own
``AF``/``LF`` input pairs, retaining resident/nonresident sets separately.
They are outputs, not native payments. Source ``B9FX9`` remains observed in
``O_sc_d``/``O_sc_f``, outside financial instruments and computed net lending.
Reconciliation to the nonfinancial capital account remains future work. Do not
infer unavailable finance from an otherwise balanced nonfinancial chain.

Local FIGARO source audit
--------------------------

The adapter reads T02 XLSX/CSV worksheets and the published all-country bulk
CSV. Bulk input requires one explicit country: ``m`` selects the national
ledger and foreign ``ctr`` rows supply import detail. Outgoing bilateral rows
are not added to national export totals. It streams chunks and checks duplicate
keys across the selection. ``figaro_nam_accounts.csv`` owns the complete source
classification and descriptions; omitted sparse observations are zeros within
that source contract, including whole zero accounts. Native unavailable data
retains its separate meaning.
It detects source signatures rather than relying only on fixed coordinates,
checks reference economy/year and units, separates square ledger and bilateral
product-use rows, and verifies the zero S1/B9 controls before excluding them.
Every retained square cell has one native owner. Unknown nonzero set pairs,
nonzero controls and unexplained differences between P7 and bilateral detail
fail explicitly. P7–S2 settlements remain observed without invented origin or
product allocation. The native square is checked cell by cell against source.

Portable synthetic fixtures cover routing, discrepancies, CSV/XLSX and multiple
reporting economies. A real local source must also be reconciled and exported,
then reloaded with all native blocks, ``T``, descriptors and item metadata
compared. A grand total alone cannot detect attribution errors. Local NAM
input does not imply availability through the existing IOT/SUT SDMX transport.

Persistence and unsupported operations
---------------------------------------

Native workbook version 2 preserves scenario parents, local records, account
identities, item metadata, layouts, descriptors, units, coverage and source
audit. Derived caches are rebuilt. Version 1 uses incompatible domains and
block names: reject it explicitly and request regeneration/reparsing from the
original source; do not silently rewrite user-edited workbooks.

Changing native inputs invalidates derived results in descendant scenarios.
Direct dataframe construction, aggregation, closure, inverses
and ``to_sut`` remain unimplemented. Unsupported IO operations fail explicitly.

Remaining modelling work
--------------------------

The next target is a nonmutating open-national-SUT projection from native
blocks, preserving scenarios, trade representation and provenance. Review each
block's valuation and item types before deciding SUT targets. Investment,
nonproduced assets, capital transfers and financial assets cannot all become
newly produced product demand. Product/activity balances, import totals and
GDP require reconciliation before a conversion can be certified.

Coefficient names are lowercase source-flow names. Each set has an ``X``
vector named from its short name, containing full outgoing account totals.
Native layouts are retained when columns are normalized by these totals. A paying
account's budget includes all relevant blocks, not just one column sum.
Zero-denominator accounts with nonzero signed flows have undefined
normalization. Do not use epsilon or infer missing observations from balances.
Accounting shares do not supply closure rules or justify an IO inverse.

Aggregation must act on the declared sets and descriptors, then recompute
results. Income and capital maps remain separate unless a future explicit
shared institutional mapping is requested. Never apply mappings solely by
matching item strings across sets. Interregional consolidation and FIDELIO
behavioural equations remain separate later tasks.

Verification and maintenance
-----------------------------

Follow ``doc/maintenance/README.rst`` for guides, APIs, companions and generated
assets. ``python doc/scripts/check_nam_spec.py --write`` regenerates the internal
catalogue; run without ``--write`` to check it. This standard-library checker
validates structure, authority and runtime agreement, not economic correctness.

``tests/core/test_nam_core.py`` and ``tests/parsers/test_nam.py`` cover the core
and portable I/O. Run affected compute, API, IOT/SUT parser and documentation
regressions as listed in the maintenance KB. SUT conversion calls remain proposals; account-total and coefficient examples
are executable.

Reference
----------

The `UN national accounts tables
<https://unstats.un.org/unsd/econstats/national-accounts/data/madt>`_
use Rest of the world (S.2) for nonresident relationships with residents.
Eurostat's `FIGARO-NAM methodology
<https://ec.europa.eu/eurostat/documents/3888793/22644316/KS-01-25-050-EN-N.pdf/fafcf924-7491-dc42-5905-8b807a4c2230?t=1764748194426>`_
supplies the source accounting context. MARIO's sets, symbols and future
conversion policies are implementation choices.
