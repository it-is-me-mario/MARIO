mario.Database.plot
===================

.. currentmodule:: mario

.. automethod:: Database.plot

Totals on stacked bars
----------------------

Use ``show_totals=True`` to display one total above each stacked column,
without labels on its individual segments. Totals use the segments displayed
after filtering, aggregation and ``top_n`` selection::

    fig = database.plot(
        matrix="E", x="Item_to", color="Region",
        filters={"Item_from": ["GHG AR6 GWP-100"]},
        category_orders={"Item_to": database.sectors},
        show_totals=True, totals_format=".3s",
        title="E | direct GHG emissions",
        path="results/E_totals.html", auto_open=False,
    )

``totals_format`` accepts Plotly/D3 number formats: ``".3s"`` gives compact
labels and ``",.0f"`` shows whole numbers. If ``text`` or ``text_auto`` is also
provided, only total labels are shown. Faceted bar plots are supported; animated
plots and grouped/overlaid bars are not. With signed segments, labels report
the net total and sit outside the stack.
