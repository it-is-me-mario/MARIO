mario.Database.calc\_trades\_concentration
===========================================

.. currentmodule:: mario

``db.calc_trades_concentration(...)`` calculates a concentration
indicator for embodied trade content.

This first implementation returns the Herfindahl-Hirschman index (HHI) computed
from the absolute contributor-Region shares behind
``db.calc_trades_content(..., breakdown=True)``.

The output keeps the same trade axes as ``db.calc_trades_content(...)`` after
collapsing contributor detail: rows are origin Regions and columns are
destination Regions. When ``aggregate=False``, the output keeps the same
``Intermediate`` / ``Final`` column split.

``indicator``, ``item``, ``scenario``, ``method``, ``clusters``,
``clusters_direction``, ``intermediate``, ``final`` and ``aggregate`` behave
like they do in ``db.calc_trades_content(...)``.

The older name ``db.calc_trades_content_concentration(...)`` is still accepted
as a deprecated alias.

.. automethod:: Database.calc_trades_concentration