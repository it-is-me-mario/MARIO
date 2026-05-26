mario.Database.calc\_embodied\_net\_imports
============================================

.. currentmodule:: mario

``db.calc_embodied_net_imports(...)`` returns embodied imports minus embodied
exports for the selected indicator.

Positive values indicate net embodied imports; negative values indicate net
embodied exports. When ``aggregate=False``, the output keeps separate
``Intermediate`` and ``Final`` columns.

``indicator``, ``item``, ``scenario``, ``method``, ``clusters``,
``clusters_direction``, ``intermediate``, ``final`` and ``aggregate`` behave
like they do in ``db.calc_trades_content(...)``.

.. automethod:: Database.calc_embodied_net_imports