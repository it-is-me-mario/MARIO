Visualization
=============

Visualization in MARIO is centered on one plotting engine:
:doc:`db.plot(...) <../api_document/mario.Database.plot>`.

Use it in two ways:

* simple workflow: choose a matrix and a ``preset`` such as ``"overview"`` or
  ``"composition"``;
* advanced workflow: pass explicit Plotly Express mappings such as ``x=``,
  ``color=``, ``facet_col=`` and ``animation_frame=``.

To look at a whole matrix, use ``preset="heatmap"``: the matrix is drawn as
it is stored, with rows and columns in their original order. Add
``log_color=True`` when a few large entries, such as the diagonal of ``Z``,
would flatten everything else, and ``color_clip=(0.05, 0.995)`` to soften
outliers. Combine it with ``filters`` to draw one block, for example
``filters={"Region_from": ["DE"], "Region_to": ["IT"]}``.

.. code-block:: python

   db.plot(matrix="Z", preset="heatmap", log_color=True, color_clip=(0.05, 0.995))

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
