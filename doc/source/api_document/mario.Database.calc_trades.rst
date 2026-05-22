mario.Database.calc\_trades
===========================

.. currentmodule:: mario

``db.calc_trades(...)`` aggregates one sector or commodity into a
region-by-region trade matrix.

For IOT tables it uses ``Z`` for intermediate trade and ``Y`` for final demand.
For SUT tables it uses ``U`` for intermediate trade and ``Yc`` for final
demand.

When both ``intermediate=True`` and ``final=True``, the default is
``aggregate=True``, so the returned dataframe is the sum of intermediate and
final trade. Use ``aggregate=False`` to keep the two components separate under a
column MultiIndex.

Use ``total=True`` to add row and column totals.

Use ``show_plot=True`` to also build and display a region-by-region heatmap
while still returning the trade matrix.

Use ``save_plot=...`` to write that heatmap to an HTML file. The older
``path=...`` argument is still accepted as a backward-compatible alias. When
``save_plot`` is provided, MARIO saves the plot without displaying it. When the
path ends in ``.html`` or ``.htm``, MARIO writes HTML; for image extensions
such as ``.png`` or ``.svg``, it uses Plotly image export.

Use ``title=...`` to override the heatmap title. The heatmap colorbar uses the
unit of the selected item instead of the generic ``sum of Value`` label.

.. automethod:: Database.calc_trades