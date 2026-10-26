:page-type: Explanation
:summary: Import and inspect national accounting matrices with separate income, capital and trade accounts.

.. _concept-nams:

National Accounting Matrices
============================

:doc:`Table formats <../table_formats>` / :doc:`IOT <iot>` · :doc:`SUT <sut>` · **NAM**

A NAM connects **production, income, consumption, capital and financial
accounts** in one accounting system. It keeps the activity/commodity
distinction of a SUT and follows income through institutional sectors to
consumption, saving and investment.

A NAM is an accounting dataset. A model built from it must additionally
specify endogenous accounts, exogenous inputs and behavioural equations.
MARIO preserves and normalizes the accounts; it does not select those rules.

Structure and native matrices
-----------------------------

Select a block to see its definition and exact sets. Rows receive payments;
columns pay. The diagram uses the same accounting sets, in the same order,
on both axes. Column headers show short names and full set names vertically. Use the
**Flows / Coefficients** switch to see the lowercase coefficient names and
their softer block colours.
It uses FIGARO's
**use-side import** representation; select a block for its full set names.

.. raw:: html
   :file: ../_generated/nam_structure.html

Follow ``Va_f`` from activities to factors, then ``RI_d`` to institutional income
accounts. ``CF_d`` funds consumption; ``RS_dd`` transfers saving from resident income
to resident capital accounts. ``IK_d`` records acquisitions of nonfinancial
assets by resident sectors. ``Yc_inv`` records products by nonfinancial-asset
category when the source provides that breakdown. FIGARO instead supplies
fixed-investment product purchases through a separate demand pool.

.. container:: mario-format-note

   **Every native block has one set on each axis.** Resident income,
   nonresident income, resident capital and nonresident capital are four
   distinct sets. A sector can have the same item code in different sets.
   ``T`` combines all sets into the complete square view. A dash means no
   registered block for that set pair in this representation; it is not a
   measured zero. Financial and institutional payments need not be symmetric.

Inspect a NAM
-------------

Import one country from a local FIGARO-NAM CSV release with :func:`mario.parse_figaro`:

.. container:: mario-recipe

   .. code-block:: python

      import mario

      nam = mario.parse_figaro("FIGARO_NAM_2023.csv", table="NAM", countries="IT")
      nam.get_index("Region")
      nam.U
      nam.MU
      nam.T

   .. container:: mario-result

      A MARIO ``Database`` with native flows, observed import detail and a
      three-level national accounting view. The year is read from the file.

The published all-country CSV requires exactly one explicit country selection.
It reads that national ledger and its bilateral imports in chunks. National
XLSX workbooks are also supported with
``mario.parse_figaro("FIGARO_NAM_IT_2023.xlsx", table="NAM")``. See the
:doc:`FIGARO source guide </notebooks/parsers/figaro/walkthrough_figaro>` for
CSV fields, sparse-zero semantics and input variants.

Evaluate ``nam`` or call ``print(nam)`` to see its name, table type, scenarios
and set counts, as for IOT/SUT. Region counts refer to reporting economies;
import origins are separate descriptors. If national memberships differ,
set sizes are reported as a range per region rather than a pooled total.

The current NAM interface supports flow inspection, native block updates,
scenario cloning, account totals, account-normalized coefficients, financial-side
``B9_d``/``B9_f`` and Excel export/reload. NAM aggregation, model closure,
inverses and ``to_sut`` are not implemented yet. The
:doc:`NAM database reference </reference/api_nam_database>` lists supported
methods and their signatures. Other inherited IO operations raise an explicit
error.

Indices
-------

``T`` has **Region / Set / Item** on both axes. Rows receive payments;
columns pay. Region means the economy reporting its national accounts,
including its external accounts. It is distinct from a product's origin or
an export partner. Several reporting economies can coexist without becoming
a consolidated interregional system.

Income and capital remain separate sets even when they have identical sector
members: ``(IT, resident income, S14)`` and ``(IT, resident capital, S14)``
identify different accounts. This is why the national view needs three index
levels, without an additional Account level. A matching set order on both
axes does not imply a symmetric matrix of payments.

Income and capital use separate institutional sets. ``S14`` can appear in
both; its identity includes its set. The rest of the world is conventionally
coded ``S.2`` in national accounts (``S2`` in FIGARO), but MARIO requires no
particular item spelling. Residency and accounting role belong to the set.
``P7`` and ``P33`` in FIGARO are trade-clearing accounts, not institutional
sector codes; they use a separate set.

.. raw:: html
   :file: ../_generated/nam_indices.html

Use :meth:`nam.get_index() <mario.CoreModel.get_index>` with a short name, set ID or display
label, for example ``nam.get_index("si_d")`` for resident income sectors. Members can differ between reporting economies. The :doc:`set reference
</reference/api_indices>` lists all IDs and labels; the :doc:`matrix reference
</reference/api_resolvable_matrices>` lists their block domains and roles.

Account totals and coefficients
--------------------------------

Every accounting set has a total vector named ``X`` plus its short name:
``Xa``, ``Xc``, ``Xf``, ``Xsi_d``, ``Xsc_d`` and so on. ``X`` combines all
account totals. Each vector has accounting nodes on rows and one column named
``production``, following the IOT/SUT vector convention. For institutional,
financial and other sets it represents total account expenditure. In a
balanced NAM this equals total receipts; it is not universally production.
Adding totals across all sets counts successive stages of the same income
circulation and is not a GDP measure.

For a native flow ``F``, its coefficient is named ``F.lower()`` and uses the
**full total of its column account**, including all outgoing native blocks:

.. math::

   X_j = \sum_i T_{ij}, \qquad f_{ij}=F_{ij}/X_j.

For example, ``u = U / Xa`` columnwise and ``cf_d = CF_d / Xsi_d``.
Normalizing ``CF_d`` by its own column sum is not the NAM coefficient definition.
``t`` is the coefficient view of the complete ``T``. These are accounting
shares; registering them does not select endogenous accounts or create a model
closure or an inverse.

.. code-block:: python

   totals = nam.resolve_many(["Xa", "Xc", "Xsi_d"])
   coefficients = nam.resolve_many(["u", "cf_d", "rs_dd"])
   nam.explain("cf_d")

An entirely inactive zero account has zero coefficients. A zero total with
nonzero signed payments is undefined and raises an error identifying the
accounts; no epsilon or implicit missing-data replacement is used. Financial
coefficients can be negative or exceed one. Each total requires complete
outgoing coverage of its own set; unrelated missing accounts need not block it.
Native descriptors are retained when dividing their columns by the matching
account total.

See :doc:`the NAM calculation reference </reference/api_nam_calculations>`
for naming, dependencies and examples. IOT/SUT names have their own equations:
SUT ``s`` can depend on IT/PT, whereas NAM ``s`` is always ``S / Xc``.

Native blocks and detail
------------------------

Native flows are authoritative. ``T`` projects their accounting nodes into a
square view; it does not replace the richer blocks or add to their totals.

.. mario-details:: Complete matrix names, roles and default sets

   .. raw:: html
      :file: ../_generated/nam_matrices.html

   ``T`` is an accounting view and ``B9_d``/``B9_f`` are calculated results; neither is
   an additional payment block. Account totals and coefficients are also derived
   from the authoritative flows. Flow/coefficient pairs follow the uppercase/
   lowercase convention; views and results have explicit registry roles.
   See the :doc:`matrix reference
   </reference/api_resolvable_matrices>` for the shared catalogue.

For FIGARO, the import blocks ``MU``, ``MY``, ``Minv``, ``M_o`` and
``Mcap_d``/``Mcap_f`` retain
``Region / origin_region / imported_commodity / Set / Item`` on their rows.
Their accounting set is **External trade account** (``tr``), containing
``P7`` and ``P33``. Import origins and products are descriptors in
``matrix_layouts``. ``Unspecified`` marks unobserved descriptors, including
those of ``P33``; it is not an extra reporting economy.

**Other accounts** (``o``) contains FIGARO's investment routing nodes
``B8_S1`` and ``P51G``, and its observed discrepancy ``B9FX9``. It keeps these
as separate items with ``kind``, source code and description metadata.
It does not contain imports or institutional sectors. Nonfinancial assets
(``nf``) include fixed assets, inventories, valuables and nonproduced assets,
with their types retained. Distributive transactions (``d``) include current
and capital transfers, also distinguished by item type.

FIGARO's fixed-investment chain is ``IK_d``/``IK_f`` (assets by investor),
``O_nf`` (allocation pool by asset), ``O_o`` (demand pool by allocation pool)
and ``C_o`` (products by demand pool). ``M_o`` records imports paid by that
pool. These preserve the observed margins without inventing a joint
product-by-asset-by-investor table. ``Yc_cap_d``/``Yc_cap_f`` and
``Mcap_d``/``Mcap_f`` support sources with direct capital-sector destinations.
Every block involving ``o`` includes all its declared items, including zeros.

``AF_d`` and ``LF_d`` contain resident financial transactions; ``AF_f`` and
``LF_f`` cover nonresidents. ``B9_d`` and ``B9_f`` compute net financial asset
acquisitions minus net liability incurrence for their respective capital sets.
FIGARO's ``B9FX9`` stays in ``O_sc_d``/``O_sc_f`` as an observed discrepancy,
outside the financial instrument set and outside the calculated results.
Reconciliation against the nonfinancial account remains a separate task.

Matrix names are MARIO conventions, not universal NAM symbols. The suffixes
``d`` and ``f`` distinguish resident/domestic and nonresident/foreign sets;
for two institutional axes they follow row then column order, as in
``RS_df``. ``Va_f``/``Vc_f`` retain ``f`` for factors, while ``T`` prefixes
identify tax or transfer families. Use the declared domains and descriptions
to interpret a block; letter case alone does not determine its role.

Missing data and import authority
---------------------------------

Each block records ``observed``, ``declared_zero``, ``unavailable`` or
``derived``. Missing data cannot be replaced by implicit zeros. ``T`` requires
every active flow domain to be supplied or explicitly known to be zero.
Availability and reproduction of a source table do not certify its valuation
bridge or the economic assumptions of a model.

``use_imports`` records domestic product uses and imports by user through
``MU``, ``MY``, ``Minv``, ``M_o`` and ``Mcap_d``/``Mcap_f``. ``supply_imports`` records total product
uses and imports by product through ``MS``. Only one representation is
authoritative. The FIGARO adapter uses ``use_imports`` and retains the
observed bilateral detail. A shape alone does not select an allocation model.

Create and fill a template
--------------------------

:func:`mario.write_parse_template` accepts explicit national memberships:

.. code-block:: python

   mario.write_parse_template(
       "nam_template.xlsx",
       table="NAM",
       sets={"IT": {"commodity": ["Goods", "Services"],
                     "activity": ["Industry", "Services"]}},
       units={"currency": "EUR", "scale": 1_000_000, "period": 2023},
       representation="use_imports",
   )

The workbook contains editable native blocks and a ``matrix_layouts`` registry.
Follow a block's link to its values, fill the complete numeric block including
zeros as numeric values, then change its presence to ``observed``. Excel
formulas are not accepted as observed inputs. Initial blanks mean
``unavailable``. Use ``declared_zero`` only for a block known to be entirely
zero; ``block_states={"U": "declared_zero"}`` can declare that when creating
a template. Keep account identities and registry ranges consistent.
The ``accounts`` sheet includes editable ``kind`` and ``description`` columns
and JSON metadata for other item attributes. Supply them programmatically with
``item_metadata={"IT": {"nf": {"Machinery": {"kind": "fixed_asset"}}}}``
when the corresponding item is declared in ``sets``.

.. code-block:: python

   nam = mario.parse_from_excel("nam_template.xlsx", table="NAM", mode="flows")

Save and update flows
----------------------

.. code-block:: python

   nam.to_excel("nam_native.xlsx")
   restored = mario.parse_from_excel("nam_native.xlsx", table="NAM", mode="flows")

The native workbook preserves reference economies, set-scoped items,
descriptors, item types/descriptions, block states, units, source audit and
scenario inheritance. Derived view, account-total, coefficient and financial-result caches are rebuilt from native inputs. For programmatic
updates, retrieve an independent frame and write it through
:meth:`nam.set_block() <mario.CoreModel.set_block>`; ``nam.matrices`` exposes
read-only snapshots. Changing an input invalidates derived results.

The native workbook uses format version 2. Earlier version 1 workbooks use
different sets and block names and are rejected explicitly. Reparse the original
FIGARO file or regenerate the template with this version; keep any manual
edits for review when transferring values to the revised blocks.

Continue with the :doc:`FIGARO source guide
</notebooks/parsers/figaro/walkthrough_figaro>` for local input signatures,
source checks and multi-country selection.
