:page-type: Guide
:summary: Request a quantity; MARIO resolves the dependencies needed to calculate it.

Calculate matrices
==================

.. container:: mario-companion

   :download:`Download notebook <compute_matrices.ipynb>`

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      footprint = db.query("f")

   .. container:: mario-result

      **Result** · A DataFrame of total satellite footprints per unit of sector
      output. Rows are satellite accounts; columns identify region and sector.

Choose the quantity
-------------------

.. list-table::
   :header-rows: 1
   :widths: 45 25 30

   * - Quantity
     - IOT
     - SUT
   * - Production
     - ``X``
     - ``Xa``, ``Xc``
   * - Direct technical coefficients
     - ``z``
     - ``u``, ``s``
   * - Total satellite footprint coefficients
     - ``f``
     - ``fa``, ``fc``

Use the :doc:`matrix catalogue <../../reference/api_resolvable_matrices>` for
all definitions and axes. In a hybrid model, each output keeps its native unit.

Calculate several targets
-------------------------

.. code-block:: python

   db.calc_all(["X", "z", "f"])
   db.list_matrices(scenario="baseline")

By default, the runtime stores the requested targets. Dependencies may be
calculated internally without being retained as extra matrices.

.. mario-details:: Work on another scenario

   .. code-block:: python

      db.clone_scenario("baseline", "alternative")
      alternative = db.query("f", scenarios="alternative")

   See :doc:`../transformations/apply_shocks` to change that scenario.

.. mario-details:: Choose a calculation route for one request

   .. code-block:: python

      result = db.resolve(
          "f",
          force_rewrite=True,
          compute_options=mario.ComputeOptions(
              planning_override="prefer_direct_targets",
          ),
      )

   Direct solves can avoid constructing a full inverse. Asking for the inverse
   itself still requires its output storage. Read :doc:`../advanced/compute_settings`
   for memory, solver selection, singular systems and session-wide defaults.

For a combined climate indicator, :doc:`characterize the gases
<../analysis/greenhouse_gases>` before selecting the GHG row of ``f``.
