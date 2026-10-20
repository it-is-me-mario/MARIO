mario.Database.calc\_ghg
========================

.. currentmodule:: mario

.. automethod:: Database.calc_ghg

The new account is added to each existing scenario using that scenario's
environmental values. Economic blocks remain unchanged. In a native SUT,
``Ea``, ``Ec`` and ``EY`` can be characterized directly without constructing
the unified ``E``, ``Z`` or ``z`` views.

Already materialized environmental coefficients, multipliers and footprints
receive the weighted row directly; no missing matrices or linear systems are
computed by this method. Custom operator caches depending on changed blocks
are discarded for on-demand recalculation.

.. note::

   ``time_horizon`` and ``ipcc_report`` are used only when
   ``Database.calc_ghg(...)`` resolves a built-in ``profile``. In the current
   built-in registry this affects gases such as ``CH4`` and ``N2O``; scalar
   entries such as ``CO2`` and total ``GHG`` remain unchanged. When a custom
   flat ``gwp={...}`` mapping is passed, the method keeps the previous
   behavior and ignores these two arguments.
