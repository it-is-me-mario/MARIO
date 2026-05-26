mario.Database.calc\_spa
========================

.. currentmodule:: mario

``db.calc_spa(...)`` runs a first demand-driven structural path analysis for one
indicator, one scenario, and one selected bundle of final demand.

The method is currently available only for IOT tables. It combines the direct
coefficient row for ``indicator`` with the ``z`` coefficient matrix and the
selected columns of ``Y`` to enumerate ordered upstream paths up to a chosen
depth.

Use ``item`` to focus the final-demand bundle on one sector, and
``final_demand_region`` or ``final_demand_category`` to keep only the relevant
final-demand columns. The output is a dataframe sorted by absolute contribution
and includes path shares relative to the full footprint of the selected bundle.

Like ``db.calc_trades(...)``, ``db.calc_spa(...)`` can also render one built-in
plot with ``show_plot=True`` and export it with ``save_plot=...`` or
``path=...``. Use ``plot="paths"`` for the default horizontal bar chart of the
reported paths, ``plot="sankey"`` for a network-style view of the same ranked
paths, or ``plot="depth"`` for an integrated summary of the footprint by
upstream depth.

.. automethod:: Database.calc_spa