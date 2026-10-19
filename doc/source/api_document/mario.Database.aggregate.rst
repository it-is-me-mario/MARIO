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

Regional item mappings use the original region and item as their source key,
even when regions are aggregated in the same operation. Mapped rows and columns
are summed over actual nodes, retaining sparse storage and regional differences
in the resulting classifications. Unit compatibility checks still apply.

Regions can be merged only when their complete label sets match across all
regional classifications. This restriction also applies to Region presets and
in-memory inputs, independently of what the Excel template displays. Comparisons
use literal labels; MARIO does not infer equivalence between different labels.

.. automethod:: Database.aggregate
