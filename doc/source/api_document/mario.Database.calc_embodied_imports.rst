mario.Database.calc\_embodied\_imports
=======================================

.. currentmodule:: mario

For trade-content matrix :math:`C` returned by
:doc:`calc_trades_content <mario.Database.calc_trades_content>`:

.. math::

   \mathrm{Imports}_d = \sum_{o\ne d} C_{od}.

Summation is over origin Regions; the same-label domestic entry is excluded.
With ``aggregate=False``, this formula is applied separately to intermediate
and final content.

``db.calc_embodied_imports(...)`` collapses
``db.calc_trades_content(...)`` into embodied import accounts by destination
Region.

For each destination Region, MARIO sums the corresponding trade-content column
and removes the same-label diagonal entry, so domestic content is not counted
as an import. When ``aggregate=False``, the output keeps separate
``Intermediate`` and ``Final`` columns.

``indicator``, ``item``, ``scenario``, ``method``, ``clusters``,
``clusters_direction``, ``intermediate``, ``final`` and ``aggregate`` behave
like they do in ``db.calc_trades_content(...)``.

.. automethod:: Database.calc_embodied_imports