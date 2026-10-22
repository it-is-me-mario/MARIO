mario.Database.calc\_embodied\_exports
=======================================

.. currentmodule:: mario

For trade-content matrix :math:`C` returned by
:doc:`calc_trades_content <mario.Database.calc_trades_content>`:

.. math::

   \mathrm{Exports}_o = \sum_{d\ne o} C_{od}.

Summation is over destination Regions; the same-label domestic entry is
excluded. With ``aggregate=False``, this formula is applied separately to
intermediate and final content.

``db.calc_embodied_exports(...)`` collapses
``db.calc_trades_content(...)`` into embodied export accounts by origin
Region.

For each origin Region, MARIO sums the corresponding trade-content row and
removes the same-label diagonal entry, so domestic content is not counted as an
export. When ``aggregate=False``, the output keeps separate ``Intermediate``
and ``Final`` columns.

``indicator``, ``item``, ``scenario``, ``method``, ``clusters``,
``clusters_direction``, ``intermediate``, ``final`` and ``aggregate`` behave
like they do in ``db.calc_trades_content(...)``.

.. automethod:: Database.calc_embodied_exports