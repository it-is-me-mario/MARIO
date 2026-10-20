mario.Database.calc\_trades\_content
====================================

.. currentmodule:: mario

Let :math:`t_{od}` be the vector of selected traded flows from origin
``o`` to destination ``d``, grouped by production node. With direct indicator
row :math:`d` and total multiplier row :math:`q`, the three methods compute:

.. math::

   C_{od}^{\mathrm{direct}} = d\,t_{od}, \qquad
   C_{od}^{\mathrm{total}} = q\,t_{od}, \qquad
   C_{od}^{\mathrm{upstream}} = (q-d)\,t_{od}.

For IOT, :math:`d=e_k` or :math:`v_h` and :math:`q=d\,w`.
For Isard SUT, :math:`d=e_{c,k}` or :math:`v_{c,h}` and :math:`q` is the
corresponding row of ``fc`` or ``mc``. Chenery-Moses SUT uses activity-side
direct rows and ``fa`` / ``ma`` instead. Upstream removes the direct content
of the traded production nodes while retaining their suppliers' contributions.

For IOT, the contributor vector returned by ``breakdown=True`` is:

.. math::

   c_{od}^{\mathrm{total}} = \operatorname{diag}(d)\,w\,t_{od}, \qquad
   c_{od}^{\mathrm{direct}} = \operatorname{diag}(d)\,t_{od}.

For Isard SUT it is:

.. math::

   c_{od}^{\mathrm{total}} = \begin{bmatrix}
     \operatorname{diag}(d_a)\,s\,w_{cc}\,t_{od} \\
     \operatorname{diag}(d_c)\,w_{cc}\,t_{od}
   \end{bmatrix}, \qquad
   c_{od}^{\mathrm{direct}} = \begin{bmatrix}0\\
     \operatorname{diag}(d_c)\,t_{od}\end{bmatrix}.

For Chenery-Moses SUT, the total blocks are
:math:`\operatorname{diag}(d_a)w_{aa}t_{od}` and
:math:`\operatorname{diag}(d_c)w_{ca}t_{od}`; only the activity block contributes
to the direct vector. In all cases, upstream is total minus direct, and
summing contributor entries gives :math:`C_{od}`.

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