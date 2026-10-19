BONSAI regional-index method diagnosis
======================================

This is a development snapshot from 2026-10-19, after the first regional
``get_index`` change. It identifies the next adaptations; it does not claim
that all MARIO methods support BONSAI yet.

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
at this stage. See :doc:`../../api_document/mario.CoreModel.get_index`.

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
