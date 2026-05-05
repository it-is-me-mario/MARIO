mario.Database.get\_aggregation\_excel
======================================

.. currentmodule:: mario

Create an aggregation workbook for one or more sets.

Use ``region_aggregation`` when you want MARIO to prefill the ``Region`` sheet
for you. This is useful both for region-only aggregation and for mixed
workflows where you want to aggregate ``Region`` together with other sets such
as ``Sector``.

.. code-block:: python

   db.get_aggregation_excel(
	   path="/path/to/exiobase_region_template.xlsx",
	   levels=["Sector"],
	   region_aggregation="continent",
	   overwrite=True,
   )

The resulting workbook contains a prefilled ``Region`` sheet and leaves the
other requested sheets empty for manual editing.

.. automethod:: Database.get_aggregation_excel