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

For BONSAI, ``db.calc_ghg()`` auto-detects the built-in profile. Its default
AR6 GWP100 factors are 1 for fossil CO2, 29.8 for fossil methane, 27.0 for
non-fossil methane, and 273 for N2O (``Dinitrogen monoxide | Air``). The
``Nitrogen oxides`` (NOx) account is excluded. Non-fossil CO2 remains a separate
account with factor zero in the aggregate, consistently with the existing
EXIOBASE/GLORIA profiles. This convention does not calculate a net biogenic
carbon balance or characterize resource CO2 uptake. The Balanced bundle has
no fluorinated GHG accounts, so the profile covers its available greenhouse gases.

Factors follow the `GHG Protocol table of IPCC GWP values
<https://ghgprotocol.org/sites/default/files/2024-08/Global-Warming-Potential-Values%20%28August%202024%29.pdf>`_.

.. note::

   ``time_horizon`` and ``ipcc_report`` are used only when
   ``Database.calc_ghg(...)`` resolves a built-in ``profile``. In the current
   built-in registry this affects gases such as ``CH4`` and ``N2O``; scalar
   entries such as ``CO2`` and total ``GHG`` remain unchanged. When a custom
   flat ``gwp={...}`` mapping is passed, the method keeps the previous
   behavior and ignores these two arguments.
