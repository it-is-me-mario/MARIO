Inspection and calculations
===========================

Once a table is parsed, these guides show how to look inside the *database*,
compute the *matrices* you need, plot them, customise their labels and export
the result.

.. mario-cards::
   :columns: 2
   :links:

   .. mario-card:: :doc:`Basic inspections <basic_inspections>`
      :kicker: db.query
      :icon: table-search

      Look inside a parsed database: sets, labels, matrices and searches, on an
      IOT and on a SUT.

   .. mario-card:: :doc:`Compute matrices <compute_matrices>`
      :kicker: db.calc_all
      :icon: compute

      Calculate the matrices that are not stored yet and choose how MARIO
      computes them.

   .. mario-card:: :doc:`Visualization workflows <visualization>`
      :kicker: db.plot
      :icon: chart

      Plot matrices and results with one entry point, from quick presets to full
      Plotly Express mappings.

   .. mario-card:: :doc:`Custom matrices and indices labels <custom_labels_and_aliases>`
      :kicker: mario.upload_settings
      :icon: tag

      Rename matrices and set aliases through the MARIO settings, and see how the
      API follows.

   .. mario-card:: :doc:`Exporting <export_and_roundtrip>`
      :kicker: db.to_excel
      :icon: export

      Write a database to Excel, CSV and Parquet, and read the output layouts.

.. toctree::
   :hidden:

   basic_inspections
   compute_matrices
   visualization
   custom_labels_and_aliases
   export_and_roundtrip
