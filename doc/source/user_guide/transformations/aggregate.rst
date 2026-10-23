:page-type: Guide
:summary: Combine native labels into larger groups, using a workbook or a region mapping.

Aggregate a database
====================

.. container:: mario-companion

   :download:`Run the notebook <aggregate.ipynb>`

Choose the mapping first; apply it to a copy while checking the result.

.. mario-cards::
   :columns: 3

   .. mario-card:: Your own groups
      :icon: merge

      Fill the Excel template below. Choose which sets to group.

   .. mario-card:: Regional groups
      :icon: pin

      Use a region mapping or a supported preset such as ``"continent"``.

   .. mario-card:: NACE or CPA groups
      :icon: tag

      :doc:`Prepare a classification aggregation <classification_aggregation>`
      from bundled concordances.

Use a workbook
--------------

.. mario-steps::

   .. mario-step:: 1 · Prepare

      .. code-block:: python

         import mario

         db = mario.load_test("IOT")
         db.get_aggregation_excel(path="aggregation.xlsx")

      Fill the target groups for the sets you want to aggregate.
      :download:`See a filled example <../../_static/data/supporting_files/aggregation_iot_filled.xlsx>`.

   .. mario-step:: 2 · Apply

      .. code-block:: python

         aggregated = db.aggregate(
             "aggregation.xlsx", inplace=False, ignore_nan=True,
         )

      ``ignore_nan=True`` allows unfilled labels to remain unaggregated.
      Aggregation still checks whether the units can be combined.

   .. mario-step:: 3 · Inspect

      .. code-block:: python

         aggregated.get_index("all")
         aggregated.Z

.. mario-details:: Aggregate known regions without a workbook

   On a recognized MRIO such as EXIOBASE:

   .. code-block:: python

      aggregated = db.aggregate(
          io=None, levels="Region", region_aggregation="continent",
          inplace=False,
      )

   Other presets are ``UNregion``, ``EU``, ``OECD``, ``G7`` and ``G20``.
   You may also supply a dictionary, Series or DataFrame. Presets require
   recognizable region identities; the artificial test-region labels do not
   represent real countries.

For parameters and mapping layouts see :doc:`db.aggregate()
<../../api_document/mario.Database.aggregate>`.
