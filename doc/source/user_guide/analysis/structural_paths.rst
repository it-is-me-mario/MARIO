:page-type: Guide
:summary: Identify the supply-chain paths contributing to a selected final-demand footprint.

Structural path analysis
========================

**Requires an IOT and one scenario.** Choose a satellite account, a factor of
production or ``"total value added"`` as the indicator.

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      paths = db.calc_spa(
          indicator="CO2", item="Agriculture",
          final_demand_region="Reg1",
          max_depth=3, cutoff=0.0, top_n=10,
      )
      paths[["path", "depth", "contribution", "share_of_total"]]

   .. container:: mario-result

      **Result** · One row per reported path, ranked by absolute contribution.
      ``paths.attrs`` contains the total footprint and reported coverage.

Path contributions
------------------

.. container:: mario-flow

   **Upstream supplier** → **Producing sector** → **Final demand**

The row's ``contribution`` is the selected indicator generated at the upstream
end of that path. ``depth=0`` is the producing sector's direct contribution;
each additional depth adds one upstream transaction.

Depth and pruning
-----------------

.. mario-cards::
   :columns: 3

   .. mario-card:: Depth
      :kicker: max_depth

      Number of upstream rounds. More depth can create many more paths.

   .. mario-card:: Threshold
      :kicker: cutoff

      Absolute contribution in the indicator's unit. Paths below it are neither
      retained nor expanded.

   .. mario-card:: Displayed paths
      :kicker: top_n

      Number of rows returned **after** traversal. It does not limit traversal
      time. ``None`` returns all retained paths.

Footprint coverage
------------------

.. code-block:: python

   paths.attrs["total_footprint"]
   paths.attrs["reported_contribution"]
   paths.attrs["coverage_share"]

**The reported paths are a partial decomposition.** Depth, pruning and
``top_n`` can omit contributions. A small contribution at one node can also
prune important upstream contributions; coverage is not an error bound.
Direct final-demand emissions in ``EY`` are outside this production-chain
expansion. Signed flows can cause cancellation, so shares need not behave
like percentages of a positive total.

.. mario-details:: Show or save a plot

   .. code-block:: python

      paths = db.calc_spa(
          indicator="CO2", item="Agriculture",
          final_demand_region="Reg1", max_depth=3, top_n=10,
          plot="sankey", show_plot=True,
      )

   Choose ``"paths"`` for ranked paths, ``"sankey"`` for their network or
   ``"depth"`` for totals by depth. Pass ``save_plot="spa.html"`` to save
   a figure. Setting ``plot`` alone does not build it.

.. mario-details:: What is being expanded?

   The analysis expands :math:`e(I-z)^{-1}y` into
   :math:`ey + ezy + ez^2y + \cdots`, where ``y`` is the selected final-demand
   bundle. The infinite series converges when the spectral radius of ``z``
   is less than one. An item's selector filters the rows of ``Y``; region and category
   selectors filter its columns. When ``item`` is omitted, sector units must
   be homogeneous. The current implementation accepts one IOT scenario at a time.

Follow the :doc:`EXIOBASE motor-vehicles example <../advanced/structural_path_analysis>`
for a real-data workflow. All arguments: :doc:`db.calc_spa()
<../../api_document/mario.Database.calc_spa>`.
