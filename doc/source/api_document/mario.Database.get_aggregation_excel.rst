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

Regional classifications
------------------------

Common classifications retain the historical label index and one
``Aggregation`` column. When ``get_index(set_name)`` returns a regional
dictionary, its sheet instead has three columns:

.. list-table:: Example Activity sheet
   :header-rows: 1

   * - Regions
     - Item
     - Aggregation
   * - IT, FR
     - A
     - Industry
   * - IT, FR
     - B
     - Industry
   * - GB
     - A
     - Services
   * - GB
     - C
     - Services

Regions share rows only when their **complete sets of labels** are identical;
label order does not matter. A label appearing in two different classifications
has separate rows for those groups. Regions with unique classifications are
included as groups of one, so their activities and commodities can still be
aggregated. Empty regional classifications have no item rows. The grouping is
computed independently for each set, including regional consumption categories.

For a nonuniform database, the ``Region`` sheet has ``Regions``, ``Region`` and
``Aggregation`` columns. It includes only groups of at least two regions whose
classifications match across **every regional set**. The first column displays
each compatibility group. Regions omitted from this sheet remain in the
database unchanged. The sheet can be empty when no regions are compatible.

``Regions`` cells contain comma-separated region labels. Labels containing a
comma or double quote are CSV-quoted automatically. These are literal string
comparisons, with no inferred semantic harmonization.

.. automethod:: Database.get_aggregation_excel
