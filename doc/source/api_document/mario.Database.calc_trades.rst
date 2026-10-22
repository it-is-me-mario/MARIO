mario.Database.calc\_trades
===========================

.. currentmodule:: mario

For intermediate and final trade components:

.. math::

   T_{od} = T_{od}^{\mathrm{int}} + T_{od}^{\mathrm{fin}}, \qquad
   T_{od}^{(B)} = \sum_{i\in o}\sum_{j\in d} B_{ij}.

The sums include only selected items and existing nodes. For IOT,
:math:`B=Z` gives intermediate trade and :math:`B=Y` gives final trade.
For Isard SUT, these are ``U`` and ``Yc``. Chenery-Moses SUT uses one
supply-side sum from ``S``, selecting commodity columns; it is not split
into intermediate and final components. Rows identify origin Regions and
columns identify destinations. Domestic entries are retained.

``db.calc_trades(...)`` aggregates one sector or commodity into a
region-by-region trade matrix.

When ``item`` is omitted, MARIO aggregates all sectors or commodities together,
but only when they share one common unit of measure. Hybrid or otherwise
heterogeneous unit layouts still require an explicit ``item``.

For IOT tables it uses ``Z`` for intermediate trade and ``Y`` for final demand.
For SUT tables it uses ``U`` for intermediate trade and ``Yc`` for final
demand when the table follows the Isard format.

A code is accepted when it exists in at least one region. Only existing
region-item pairs contribute: the calculation does not create missing commodity
or activity nodes. The returned matrix includes all database regions on both
axes. In an Isard SUT, regions without the selected commodity have a zero origin
row but can still import it. Regions with no relevant flows remain as zero rows
and columns. Regional final-demand classifications may differ in size or be
empty.

Sparse transaction blocks are summed without converting them to dense arrays.
Only the small region-by-region result is made dense. Native SUT supply blocks
are used to detect the trade format when no unified ``Z``/``z`` is already
materialized.

For Chenery-Moses SUT tables, commodity trade is aggregated from ``S`` instead.
Because that trade is stored as one supply-side flow matrix, MARIO currently
supports only the aggregate case with ``intermediate=True``, ``final=True`` and
``aggregate=True``.

When both ``intermediate=True`` and ``final=True``, the default is
``aggregate=True``, so the returned dataframe is the sum of intermediate and
final trade. Use ``aggregate=False`` to keep the two components separate under a
column MultiIndex.

Use ``total=True`` to add row and column totals.

Use ``clusters=...`` to aggregate the Region dimension before totals and
plotting. This accepts Region aggregation presets such as ``'continent'`` and
explicit mappings such as ``{'EU': ['FR', 'DE', 'IT']}``.

These clusters sum the trade result; they do not aggregate the database itself
or change its regional classifications.

Use ``clusters_direction='origin'`` to aggregate only the origin Regions,
``'destination'`` to aggregate only the destination Regions, or ``'both'`` to
aggregate both axes. The default is ``'both'``.

Use ``scenario='all'`` to calculate the same trade matrix for every available
scenario on the database. In that case ``db.calc_trades(...)`` returns a
dictionary ``{scenario: dataframe}`` instead of a single dataframe.

Use ``show_plot=True`` to also build and display a region-by-region heatmap
while still returning the trade matrix.

Use ``exclude_domestic_from_plot=True`` to hide same-label origin-destination
pairs from that heatmap without changing the returned trade matrix.

When more than one scenario is plotted together, MARIO builds one animated
heatmap with a scenario slider.

Use ``save_plot=...`` to write that heatmap to an HTML file. The older
``path=...`` argument is still accepted as a backward-compatible alias. When
``save_plot`` is provided, MARIO saves the plot without displaying it. When the
path ends in ``.html`` or ``.htm``, MARIO writes HTML; for image extensions
such as ``.png`` or ``.svg``, it uses Plotly image export.

Use ``title=...`` to override the heatmap title. The heatmap colorbar uses the
unit of the selected item instead of the generic ``sum of Value`` label.

.. automethod:: Database.calc_trades
