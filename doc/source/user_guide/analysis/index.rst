:summary: Calculate matrices and indicators, then inspect and explain their results.

Calculations and analysis
==========================

Start from an imported database. Request the quantities needed for your
analysis; MARIO resolves their dependencies.

NAM supports account totals and account-normalized coefficients through
:doc:`Calculate matrices <../inspection/compute_matrices>` and the
:doc:`NAM calculation reference </reference/api_nam_calculations>`.
The footprint, supply-chain, path, production-mix and plotting workflows
below currently apply to IOT/SUT; NAM does not yet select a model closure.

.. toctree::
   :hidden:

   ../inspection/compute_matrices
   greenhouse_gases
   ghg_characterization
   supply_chains
   structural_paths
   production_mix
   ../inspection/visualization

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - I want to
     - Guide
   * - Calculate output, coefficients or footprint matrices
     - :doc:`Calculate matrices <../inspection/compute_matrices>`
   * - Combine gas accounts into a GHG indicator
     - :doc:`Calculate greenhouse gas emissions <greenhouse_gases>`
   * - Understand the GHG indicator and its units
     - :doc:`GHG characterization and footprints <ghg_characterization>`
   * - Measure trade and embodied supply-chain content
     - :doc:`Trade and supply-chain analysis <supply_chains>`
   * - Identify individual upstream paths
     - :doc:`Structural path analysis <structural_paths>`
   * - Read regional production shares
     - :doc:`Inspect production mixes <production_mix>`
   * - Plot a matrix or a prepared result
     - :doc:`Visualize results <../inspection/visualization>`

Worked examples
---------------

The :doc:`Examples <../examples/index>` collection connects these operations
in complete analyses:

* :doc:`Trace a supply chain <../advanced/supply_chain_analyses>` through
  structural indicators, bilateral trade and embodied impacts.
* :doc:`Find structural paths <../advanced/structural_path_analysis>` from
  final demand to an environmental impact.
* :doc:`Compare GHG footprints across databases <../examples/compare_ghg>`
  with explicit source versions, characterization and unit harmonization.

For numerical methods, memory use and solver selection, see
:doc:`Computation settings <../advanced/compute_settings>`.
The :doc:`matrix catalogue <../../reference/api_resolvable_matrices>` lists
available quantities, definitions and axes.
