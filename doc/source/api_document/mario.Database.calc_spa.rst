mario.Database.calc\_spa
========================

:doc:`Structural path analysis </user_guide/analysis/structural_paths>` provides a task guide and a minimal example.

.. currentmodule:: mario

Let :math:`d` be the selected direct indicator row and :math:`y` be ``Y``
summed over the selected final-demand columns after filtering items.
The full footprint and an individual path contribution are:

.. math::

   H = d(I-z)^{-1}y, \qquad
   P_{i_k\to\cdots\to i_0\to\alpha}
   = d_{i_k}\!\left(\prod_{r=1}^{k}z_{i_r i_{r-1}}\right)Y_{i_0\alpha}.

Here :math:`\alpha` is one selected final-demand column and depth :math:`k`
counts upstream coefficient steps. At depth zero the empty product is one,
giving :math:`d_{i_0}Y_{i_0\alpha}`. ``share_of_total`` divides each signed
contribution by :math:`H`. When :math:`H=0`, it uses the sum of reported
contributions as the denominator; if that is also zero, shares are zero.

When the spectral radius of :math:`z` is less than one,
:math:`H=\sum_{k=0}^{\infty}dz^ky`. Reported paths are limited by ``max_depth``,
``cutoff`` and ``top_n``, so their sum need not equal :math:`H`.
The cutoff is applied to a path before expanding it.

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
