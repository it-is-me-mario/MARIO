mario.parse_bonsai
==================

.. currentmodule:: mario

For input files and an import example, see the :doc:`BONSAI guide
<../user_guide/parsers/bonsai>`.

.. autofunction:: parse_bonsai

Native b2 HIOT
--------------

Use ``table="IOT"`` to read BONSAI's final hybrid input-output model::

    db = mario.parse_bonsai("/path/to/HIOT/20260615", table="IOT")
    db.get_index("Sector", region="IT")
    db.units["Sector"].head()
    db.info["bonsai"]

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

Further calculations
~~~~~~~~~~~~~~~~~~~~

With ``Q = diag(X)``, the imported blocks satisfy

.. math::

   T = Q - Z = (I-z)Q, \qquad e = EQ^{-1},
   \qquad f = e(I-z)^{-1} = ET^{-1}.

MARIO's usual multiplier formula therefore represents the native system.
The configured solve obtains the requested multipliers without materializing
a full inverse. Units follow the elementary-flow and product units in the
source. Keep ``calc_all=False`` and request only the matrices needed for an
analysis. See :doc:`../reference/api_resolvable_matrices` for available calculations and
:doc:`mario.Database.calc_ghg` for greenhouse-gas characterization.

The directory name ``20260615`` identifies the source folder, not a frozen
snapshot or the reference year. Individual files can be updated within it.
Archive inputs together and record their checksums for reproducible analyses.
