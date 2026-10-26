:page-type: Guide
:summary: Request a quantity; MARIO resolves the dependencies needed to calculate it.

Calculate matrices
==================

.. container:: mario-companion

   :download:`Download notebook <compute_matrices.ipynb>`

Each table format has its own equations. The first examples below use
IOT/SUT; the NAM workflow is described in its own section.

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

NAM account totals and coefficients
-----------------------------------

Start from a parsed NAM database, for example the local FIGARO workflow in
:doc:`/notebooks/parsers/figaro/walkthrough_figaro`:

.. code-block:: python

   totals = nam.resolve_many(["Xa", "Xc", "Xsi_d"])
   coefficients = nam.resolve_many(["u", "cf_d", "rs_dd"])
   plan = nam.explain("cf_d")

``Xa`` sums every authoritative payment made by activity accounts.
``Xsi_d`` does the same for resident income accounts. ``cf_d`` divides
``CF_d`` columns by ``Xsi_d``; it never divides by the subtotal of ``CF_d``.
The coefficient retains the native flow's axes and import descriptors.
The :doc:`NAM calculation reference </reference/api_nam_calculations>`
defines zero and signed accounts and the complete naming convention.

Use ``scenario=...`` on ``resolve`` or ``resolve_many`` for another scenario.
``nam.calc_all()`` without targets assembles ``T`` only; request the desired
totals and coefficients explicitly. ``available_matrices()`` lists registered
names, including results whose inputs may still be missing. NAM does not
register IO inverses, environmental multipliers or a model closure.

The calculation routes and footprint examples below apply to IOT/SUT.

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
