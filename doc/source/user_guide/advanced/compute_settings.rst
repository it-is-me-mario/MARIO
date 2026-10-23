:page-type: Guide
:summary: Control the calculation route, numerical solver and handling of singular systems.

Computation settings
====================

.. container:: mario-recipe

   .. code-block:: python

      import mario

      mario.download_settings()["compute"]

   .. container:: mario-result

      **Result** · The active configuration for this Python process.
      Settings apply to subsequent calculations across all databases;
      changing them does not recalculate stored results.

Choose the calculation route
----------------------------

.. mario-cards::
   :columns: 3

   .. mario-card:: Solve
      :kicker: compute_method="solve"

      Solve for requested targets. Useful for large models when a full
      inverse is unnecessary.

   .. mario-card:: Inverse
      :kicker: compute_method="inverse"

      Build and reuse an explicit inverse. Its storage must fit in memory.

   .. mario-card:: Auto
      :kicker: compute_method="auto"

      Choose using an estimated memory cost. The estimate is a heuristic,
      not a limit on RAM use.

Configure a large model
-----------------------

Apply manual choices **after parsing**, because some parsers select presets.

.. code-block:: python

   mario.set_compute_method("solve")
   mario.set_linear_solver("scipy")
   mario.set_linear_strategy("direct")
   mario.set_singular_policy("raise")

BONSAI, GLORIA and EMERGING already prefer solve/direct with optional UMFPACK
and a SciPy fallback. **BONSAI selects partial singular results**; GLORIA and
EMERGING select raise. Other parsers leave the active settings unchanged.

Install optional UMFPACK
------------------------

For calculations on the full BONSAI, GLORIA or EMERGING database:

.. code-block:: sh

   conda install -c conda-forge scikit-umfpack

With pip, install SuiteSparse using your system package manager first, then
run ``python -m pip install "mariopy[umfpack]"``. Pip does not install
SuiteSparse. Select ``mario.set_linear_solver("umfpack")`` to use it explicitly.

.. mario-details:: Settings and built-in defaults

   .. list-table:: Built-in defaults, before saved settings or parser presets
      :header-rows: 1
      :widths: 27 16 57

      * - Setting
        - Default
        - Meaning
      * - ``compute_method``
        - ``"inverse"``
        - ``inverse`` builds an explicit Leontief inverse; ``solve`` prefers
          solving for the requested result; ``auto`` chooses using a memory estimate.
      * - ``linear_solver``
        - ``"scipy"``
        - Numerical backend for solve-based calculations: SciPy or optional UMFPACK.
      * - ``linear_strategy``
        - ``"auto"``
        - ``direct`` factorizes a sparse system; ``iterative`` solves by successive
          approximations; ``auto`` chooses using system size and the number of
          vectors to solve. UMFPACK always uses direct factorization.
      * - ``singular_policy``
        - ``"raise"``
        - ``raise`` rejects a detected singular system; ``partial`` returns only
          independently determined coefficients, with NaN elsewhere and a warning.
      * - ``auto_w_memory_fraction``
        - ``0.25``
        - Fraction of total physical RAM used as the threshold for automatic choices.
      * - ``auto_w_overhead_factor``
        - ``3.0``
        - Multiplier on the estimated size of one dense inverse, allowing for
          working copies in the automatic memory estimate.

.. mario-details:: Equivalent equations, different memory use

   For example, an IOT multiplier satisfies ``f = e (I-z)^-1``. The ``inverse``
   path constructs ``w = (I-z)^-1`` and multiplies by it. The ``solve`` path
   solves ``f (I-z) = e`` directly. Both represent the same model; their memory
   use and numerical rounding can differ. The same distinction applies to the
   corresponding SUT calculations.

   Use ``solve`` for large models when you need a few indicators or results.
   An explicit inverse can be useful when the inverse itself is needed and fits
   in memory. Requesting ``db.w`` still asks for the full inverse, even with
   ``compute_method="solve"``. Sparse factorization and the requested outputs
   also consume memory: ``solve`` is not a fixed RAM limit.

   With ``auto``, MARIO estimates inverse memory as ``8 * n**2 * overhead_factor``
   bytes and compares it with the configured fraction of total physical RAM.
   This is a heuristic, not a measurement of currently free RAM or a benchmark.

.. mario-details:: Partial results from singular systems

   ``partial`` requires ``solve`` with ``direct`` or ``auto``. It preserves the
   source model and marks affected coefficients as NaN; it does not repair a
   singular model or define a unique solution for the full system. Explicit
   inverse requests still fail for singular systems.

   When summing returned pandas objects, preserve undefined values with
   ``skipna=False``. Otherwise pandas can silently omit NaN from a total.

.. mario-details:: Override one calculation and inspect solver decisions

   Use ``ComputeOptions`` to override the session for one request:

   .. code-block:: python

      f = db.resolve(
          "f",
          compute_options=mario.ComputeOptions(
              backend_override="sparse_direct",
              singular_policy="raise",
          ),
      )

   This selects the solve/direct path using the active solver, without changing
   session defaults. Cached results are reused: ``force_rewrite=True`` recomputes
   the requested block, while other cached intermediates can still be reused.
   For comparisons of complete calculation paths, use fresh imports with the
   same inputs.

   Keep ``calc_all=False`` when importing a large database and request only the
   matrices needed for the analysis. To inspect solver decisions, enable
   ``mario.set_log_verbosity("debug")`` before the calculation.

See :doc:`../../reference/api_settings_methods` for saving defaults and
:doc:`database_profiles` for preferences packaged by source.
