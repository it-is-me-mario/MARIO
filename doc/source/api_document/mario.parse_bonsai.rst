mario.parse_bonsai
==================

.. currentmodule:: mario

.. autofunction:: parse_bonsai

Native b2 HIOT
--------------

Use ``table="IOT"`` to read BONSAI's final hybrid input-output model::

    db = mario.parse_bonsai("/path/to/HIOT/20260615", table="IOT")
    db.get_index("Sector", region="IT")
    db.calc_ghg()
    db.keep_extensions(["GHG AR6 GWP-100"])
    ghg_per_product_unit = db.f.loc["GHG AR6 GWP-100"]

Keeping only the required environmental rows before requesting ``f`` reduces
the number of right-hand sides in the solve. Retain the original elementary
flows until any additional characterization has been calculated.

The same call accepts a ZIP with one nested release directory. The input bundle
must contain:

* ``extended_size_hiot.b2.pkl``: the native sparse net-supply matrix,
* ``final_demand.b2.csv``: final consumption,
* ``total_elementary_flow_w_iLUC.csv``: absolute direct elementary flows,
  unless ``extensions=False``.

Use a trusted BONSAI export for the native pickle. No precomputed inverse,
terminated inventory or footprint is loaded. The parser does not rebuild Stone
markets or convert the Balanced HSUT. The b2 system already includes iLUC and
capital modelling. Intermediate supply/use CSV exports are not needed.

The reference year comes from nonempty ``time`` values in the elementary flows,
independently of the release directory date. If that metadata is unavailable,
provide it explicitly, for example ``year=2016``. An explicit year must agree
with source time values when present.

Representation and source coverage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Product codes identify Sectors. Activity/product reference pairs, native units
and nonuniform regional classifications remain in ``db.info["bonsai"]`` and
the matrix axes. No Cartesian expansion of regions and products is performed.

For the native net-supply matrix ``T``, MARIO stores ``X = diag(T)`` and
``Z = diag(X) - T``. Thus ``diag(X) - Z`` exactly preserves the original model,
including substitution credits. Direct coefficients use this supplied net
reference production rather than demand-based row totals. Gross reference
supply and self consumption are not separately recoverable from ``T``.
Value-added accounts are zero placeholders; they are not inferred by summing
flows in different physical units.

The final-demand export can refer to products absent from the final HIOT.
``unmatched_final_demand="warn"`` reports and omits those rows, retaining their
full contents in ``db.info["bonsai"]["unmatched_final_demand"]``. Choose
``unmatched_final_demand="raise"`` to reject incomplete coverage. The analogous
``unmatched_extensions`` option applies to elementary-flow activities absent
from the imported model. Source production imbalance is recorded under
``product_balance`` without modifying the model.

An IOT exposes per-unit satellite multipliers as ``f``; the native HSUT exposes
commodity multipliers as ``fc``. The default ``table="SUT"`` and its CSV-based
Balanced import remain unchanged.

Footprint calculation and comparison
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With ``Q = diag(X)``, the imported blocks satisfy

.. math::

   T = Q - Z = (I-z)Q, \qquad e = EQ^{-1},
   \qquad f = e(I-z)^{-1} = ET^{-1}.

Thus MARIO's usual multiplier formula represents the same system as BONSAI's
absolute-emissions calculation. The configured solve obtains ``f`` without
materializing a full inverse. For electricity measured in TJ and emissions in
tonnes, multiply ``f`` by **3.6** to obtain g CO2eq/kWh::

    electricity = db.f.loc[
        "GHG AR6 GWP-100", (slice(None), slice(None), "M_electricity")
    ] * 3.6

``calc_ghg()`` uses MARIO's built-in AR6 GWP100 profile; it does not load BONSAI's
``LCIA.xlsx`` automatically. The local LCIA workbook checked on 20 October 2026
uses the same factors for fossil CO2, fossil/non-fossil methane and N2O, plus
0.00772 for ``Accelerated CO2, Air``. This additional flow is outside the default
MARIO profile. See :doc:`mario.Database.calc_ghg` for an explicit characterization
example, and verify the factors against the workbook for the export being used.

Before comparing with ``ghg_for_all.b2.GWP100.csv``, align region, product and
native unit, and ensure both calculations use the same technosphere, elementary
flows and characterization. Preserve missing nodes; exclude zero reference
values from percentage differences. Signed or near-zero footprints can make
relative differences difficult to interpret.

The directory name ``20260615`` identifies the source folder, not a frozen
snapshot or the reference year. Individual files can be updated within it. File
modification times are useful diagnostics, but are not release identifiers or
proof that inputs belong to the same calculation. Archive the inputs together
and record their checksums when producing a reproducible comparison.

Local verification on 20 October 2026
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The checked native HIOT has 53,789 production nodes. Its representation in MARIO
preserves the sparse source matrix exactly. For all 129 calculated environmental
rows, the maximum relative residual ``norm(f @ T - E) / norm(E)`` was
``1.60e-14`` (evaluated separately for each nonzero environmental row).
This verifies the imported linear system; comparison with a saved footprint
also requires matching source inputs and LCIA factors.

The local matrix's modification date was 20 October, elementary flows were
modified on 19 October, and the saved GWP100 footprint on 15 October. The native
model also contains 1,472 region/product/unit nodes absent from the saved
footprints, while 78 saved nodes are absent from the native model. No separate
HIOT snapshot from 15 October was found in the inspected local HIOT and version
directories. These exports do not form a controlled equivalence benchmark.

For ``M_electricity``, in g CO2eq/kWh:

.. list-table::
   :header-rows: 1
   :widths: 25 25 25 25

   * - Region
     - MARIO AR6 GWP100
     - BONSAI saved
     - Difference
   * - Italy
     - 449.74
     - 435.65
     - +3.23%
   * - Germany
     - 613.36
     - 606.56
     - +1.12%
   * - France
     - 440.16
     - 411.28
     - +7.02%
   * - Canada
     - 264.26
     - 386.30
     - -31.59%
   * - Indonesia
     - 769.59
     - 592.77
     - +29.83%

Across 48 comparable electricity markets the median absolute difference is
3.11%, with 34 markets within 5%. Across 50,846 comparable nonzero saved product
footprints, the median absolute difference is 5.85%. Using the checked BONSAI
LCIA factors changes Italy's result to 449.79 g CO2eq/kWh; its difference from
the saved footprint remains +3.25%.

Download the :download:`verification report
<../notebooks/parsers/bonsai/hiot_validation_20261020.json>` and
:download:`electricity comparison
<../notebooks/parsers/bonsai/electricity_comparison_20261020.csv>`.
