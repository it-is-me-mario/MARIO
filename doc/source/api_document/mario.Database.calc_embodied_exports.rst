mario.Database.calc\_embodied\_exports
=======================================

.. currentmodule:: mario

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