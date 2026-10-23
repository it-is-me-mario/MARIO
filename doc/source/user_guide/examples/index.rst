:summary: Follow complete workflows and download the notebooks to adapt them.

Examples
========

These examples combine multiple MARIO operations. Each states the source
inputs it needs; real database files must be obtained separately. Download
the notebook from its page to run the workflow locally.

.. mario-cards::
   :columns: 2
   :links:

   .. mario-card:: :doc:`Import and inspect BONSAI <bonsai>`
      :icon: parsers

      Read a Balanced HSUT and a native HIOT, then inspect their regions,
      product units and import diagnostics.

   .. mario-card:: :doc:`Compare GHG footprints <compare_ghg>`
      :icon: cloud

      Characterize EXIOBASE, EORA26 and ADB, harmonize regional totals and
      compare the results graphically.

   .. mario-card:: :doc:`Trace a supply chain <../advanced/supply_chain_analyses>`
      :icon: chain

      Connect structural indicators, bilateral trade and embodied impacts
      across EXIOBASE years.

   .. mario-card:: :doc:`Find structural paths <../advanced/structural_path_analysis>`
      :icon: paths

      Trace the paths from German final demand to a selected environmental
      impact in EXIOBASE.

For a single operation, use the corresponding guide under Data sources,
Calculations and analysis, or Transformations and scenarios. Other guide
notebooks and Excel templates are also available in
:doc:`Downloadable material <../../resources/material>`.

.. toctree::
   :hidden:

   bonsai
   compare_ghg
   ../advanced/supply_chain_analyses
   ../advanced/structural_path_analysis
