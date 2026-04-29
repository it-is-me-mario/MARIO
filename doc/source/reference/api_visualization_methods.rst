Visualization
=============

Visualization in MARIO is centered on one plotting engine:
:doc:`db.plot(...) <../api_document/mario.Database.plot>`.

Use it in two ways:

* simple workflow: choose a matrix and a ``preset`` such as ``"overview"`` or
  ``"composition"``;
* advanced workflow: pass explicit Plotly Express mappings such as ``x=``,
  ``color=``, ``facet_col=`` and ``animation_frame=``.

The historical methods are still available as deprecated wrappers for backward
compatibility, but new code should use ``db.plot(...)`` directly.

Unified Plot API
----------------

.. list-table::
   :header-rows: 1

   * - Method
     - Purpose
   * - :doc:`db.plot(...) <../api_document/mario.Database.plot>`
     - Single interactive plotting entrypoint for matrices or pre-built dataframes.


Legacy Wrappers
---------------

These wrappers now delegate to ``db.plot(...)`` and emit a deprecation warning.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.Database.plot
   ../api_document/mario.Database.plot_matrix
   ../api_document/mario.Database.plot_gdp
   ../api_document/mario.Database.plot_linkages
   ../api_document/mario.Database.plot_bubble
