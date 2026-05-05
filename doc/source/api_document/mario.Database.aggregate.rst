mario.Database.aggregate
========================

.. currentmodule:: mario

Aggregate one or more sets through a workbook, an in-memory mapping, or a
Region preset produced by ``region_aggregation``.

Typical patterns are:

- aggregate multiple sets from a filled Excel workbook;
- aggregate only ``Region`` directly, without creating a workbook first;
- combine a prefilled Region mapping with other workbook-based aggregations.

.. code-block:: python

   aggregated_db = db.aggregate(
	   io=None,
	   levels="Region",
	   region_aggregation="continent",
	   inplace=False,
   )

When both ``io`` and ``region_aggregation`` are provided, MARIO injects the
generated Region mapping only if the workbook or mapping does not already
contain an explicit ``Region`` sheet.

.. automethod:: Database.aggregate