:page-type: Guide
:summary: Turn a matrix into a Plotly figure and inspect the data behind it.

Visualize results
=================

.. container:: mario-companion

   :download:`Download notebook <visualization.ipynb>`

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      fig, data = db.plot(
          matrix="Z", preset="overview", return_data=True,
          auto_open=False, path=False,
      )
      fig.show()

   .. container:: mario-result

      **Result** · An interactive figure and its prepared data. ``path=False``
      skips HTML export; ``auto_open=False`` leaves browser opening to you.

Matrix plots and analysis plots
-------------------------------

.. mario-cards::
   :columns: 2

   .. mario-card:: A matrix
      :icon: chart

      Start with ``db.plot()`` and a preset. Use filters and explicit axes
      when the full table is too large to read.

   .. mario-card:: An analysis
      :icon: paths

      :doc:`Trade analysis <../analysis/supply_chains>` and
      :doc:`structural paths <../analysis/structural_paths>` provide their
      own plotting options alongside the calculated tables.

Focus on one region
-------------------

.. code-block:: python

   fig = db.plot(
       matrix="Z", preset=None, kind="bar",
       x="Sector_from", color="Sector_to",
       filters={"Region_from": ["Reg1"], "Region_to": ["Reg1"]},
       auto_open=False, path=False,
   )
   fig.show()

The ``_from`` fields describe the rows; ``_to`` fields describe the columns.
For a SUT use matrix ``U``, with ``Commodity_from`` and ``Activity_to``.

.. mario-details:: Compare scenarios in the same figure

   Once a second scenario exists:

   .. code-block:: python

      fig = db.plot(
          matrix="Z", scenarios=["alternative"],
          base_scenario="baseline", difference="relative",
          preset="heatmap", auto_open=False, path=False,
      )

   Create it with :doc:`../transformations/apply_shocks`.

See :doc:`db.plot() <../../api_document/mario.Database.plot>` for presets,
axis mappings, filters and export arguments.
