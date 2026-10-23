Computation settings
====================

Compute settings control how MARIO obtains a result: whether it builds an
inverse matrix, which solver it uses and how it handles singular systems.
Inspect the active configuration with:

.. code-block:: python

   import mario

   mario.download_settings()["compute"]

These settings apply to every database in the current Python process or
notebook kernel. They affect subsequent calculations; changing them does not
recalculate results already stored in a database.

What each setting does
----------------------

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

Inverse or solve?
-----------------

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

A practical configuration
-------------------------

For a large database, configure the session after parsing:

.. code-block:: python

   mario.set_compute_method("solve")
   mario.set_linear_solver("scipy")
   mario.set_linear_strategy("direct")
   mario.set_singular_policy("raise")

For UMFPACK, install ``scikit-umfpack`` and SuiteSparse, then select
``mario.set_linear_solver("umfpack")``. It supports ``direct`` or ``auto``;
``iterative`` requires SciPy and is an option when factorization memory is
too costly. Its convergence and speed depend on the particular system.

**BONSAI, GLORIA and EMERGING already select solve/direct presets during
parsing**, preferring UMFPACK and falling back to SciPy if it cannot be imported.
BONSAI selects ``partial``; GLORIA and EMERGING select ``raise``. Other parsers
leave active settings unchanged. Apply any manual changes after parsing.
See :doc:`../../reference/api_settings_methods` for installation instructions,
model sizes, presets and saving defaults for future sessions.

To inspect a parser's preferences before parsing, use
``mario.get_database_profile("gloria")["compute"]["parser_presets"]``.
This describes the preferred backend and fallback; it is not the active session
configuration returned by ``mario.download_settings()["compute"]``.
See :doc:`database_profiles` for the complete metadata view.

Use partial results deliberately
--------------------------------

``partial`` requires ``solve`` with ``direct`` or ``auto``. It preserves the
source model and marks affected coefficients as NaN; it does not repair a
singular model or define a unique solution for the full system. Explicit
inverse requests still fail for singular systems.

When summing returned pandas objects, preserve undefined values with
``skipna=False``. Otherwise pandas can silently omit NaN from a total.

Override one calculation
------------------------

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
