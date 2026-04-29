Dev guide
=========

This section is for contributors, maintainers, and advanced users who want to
understand how MARIO is organized internally.

The goal is not only to explain how to change the code, but also to explain
how the main subsystems fit together: where parsing stops, where compute logic
starts, how scenarios and matrices are stored, and which modules own high-level
operations such as plotting, export, aggregation, or shocks.

If you are trying to read the codebase efficiently, start with:

* :doc:`architecture_overview` for the package layout and the main execution
   boundaries;
* :doc:`parsers` for the ingestion path from raw sources to ``Database``;
* :doc:`compute_layer` for the catalog/resolver/formula model used to build
   matrices on demand.

.. toctree::
   :maxdepth: 1

   architecture_overview
   parsers
   compute_layer
   adding_new_matrices
   testing_strategy
   realdata_fixtures
   documentation
   ../resources/changelog
