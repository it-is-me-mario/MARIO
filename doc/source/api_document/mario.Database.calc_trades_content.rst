mario.Database.calc\_trades\_content
====================================

.. currentmodule:: mario

``db.calc_trades_content(...)`` calculates the indicator content embodied in
region-by-region trade.

Accepted ``indicator`` values are:

* one row from ``Satellite account``
* one row from ``Factor of production``
* ``"total value added"``

Use ``method='direct'`` for direct coefficients only, ``'total'`` for direct
plus upstream effects, or ``'upstream'`` for the indirect share only.

Use ``breakdown=True`` to return contributor-level content tables instead of a
collapsed Region-by-Region total. In that case MARIO keeps the trade pair while
decomposing the content across the contributing production nodes. Summing the
breakdown over contributor levels reconstructs the corresponding collapsed
``db.calc_trades_content(...)`` result for the same ``method``.

For IOT tables, MARIO uses ``e`` and ``v`` for direct content, and ``f`` and
``m`` for total content. With ``breakdown=True``, MARIO uses the direct row
itself for ``method='direct'`` and the exploded matrices ``f_ex`` or ``m_ex``
for ``'total'`` and ``'upstream'``.

For Isard SUT tables, MARIO uses commodity-side coefficients and multipliers:
``ec`` and ``vc`` for direct content, and ``fc`` and ``mc`` for total content.
With ``breakdown=True``, MARIO uses commodity-side exploded totals built from
``fc_ex`` and ``mc_ex``.

For Chenery-Moses SUT tables, commodity trade is aggregated from ``S`` and the
content weights are taken from the activity side instead: ``ea`` and ``va``
for direct content, and ``fa`` and ``ma`` for total content. Because that
trade is stored as one supply-side flow matrix, MARIO currently supports only
the aggregate case with ``intermediate=True``, ``final=True`` and
``aggregate=True``.

``item``, ``scenario``, ``clusters``, ``clusters_direction``, ``intermediate``,
``final``, ``aggregate`` and ``total`` behave like they do in
``db.calc_trades(...)``.

When ``breakdown=True``, Region clustering still applies to the trade axes, but
plotting and ``total=True`` are not currently supported.

Use ``show_plot=True`` to also build and display a region-by-region heatmap
while still returning the trade-content matrix.

When more than one scenario is plotted together, MARIO builds one animated
heatmap with a scenario slider.

Use ``save_plot=...`` to write that heatmap to HTML or image files. The older
``path=...`` argument is still accepted as a backward-compatible alias. When
``save_plot`` is provided, MARIO saves the plot without displaying it.

Use ``title=...`` to override the heatmap title. The heatmap colorbar uses the
unit of the selected indicator.

.. automethod:: Database.calc_trades_content