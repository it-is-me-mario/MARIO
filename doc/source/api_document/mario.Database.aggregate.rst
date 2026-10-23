mario.Database.aggregate
========================

.. currentmodule:: mario

Aggregate one or more sets through a workbook, an in-memory mapping, or a
Region preset produced by ``region_aggregation``.

Typical patterns are:

- aggregate multiple sets from a filled Excel workbook;
- aggregate only ``Region`` directly, without creating a workbook first;
- combine a prefilled Region mapping with other workbook-based aggregations.
- apply a NACE or CPA mapping prepared by
  :meth:`~mario.CoreModel.get_aggregation`, as shown in
  :doc:`Aggregating by classification <../user_guide/transformations/classification_aggregation>`.

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

.. note::

   For :ref:`regional classifications <regional-classifications>`, item mappings
   use the original region and item as their source key, even when regions are
   aggregated in the same operation. Only existing nodes are aggregated, and
   unit compatibility checks still apply.

   Regions can be merged only when their complete label sets match across all
   regional classifications. This also applies to Region presets and in-memory
   inputs. Comparisons use literal labels; MARIO does not infer equivalence
   between different labels. See :doc:`mario.Database.get_aggregation_excel`
   for the corresponding workbook layout.

.. automethod:: Database.aggregate
