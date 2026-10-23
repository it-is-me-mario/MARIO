mario.Database.calc\_ghg
========================

.. currentmodule:: mario

For the operational steps, see :doc:`Calculate greenhouse gas emissions
<../user_guide/analysis/greenhouse_gases>`.

The aggregate extension is a GWP-weighted sum of matched gas accounts:

.. math::

   E_{\mathrm{GHG},j} = \sum_{g\in G}\mathrm{GWP}_g\,E_{g,j}.

The GWP factors come from the selected profile or explicit ``gwp`` mapping.
The same weighted row sum is applied to final-demand emissions in ``EY``.
The aggregate rows are added to ``E`` and ``EY`` through ``add_extensions``.
Input gas rows
must share one unit. An explicit ``unit`` must match that unit; this operation
does not convert input magnitudes. Unmatched accounts are omitted; if no
accounts match, the calculation raises ``KeyError``.

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
non-fossil methane, and 273 for N2O (``Dinitrogen monoxide | Air``), plus the
BONSAI-specific factor **0.00772** for ``Accelerated CO2, Air | Air`` when
that flow is present. The ``Nitrogen oxides`` (NOx) account is excluded.
Non-fossil CO2 remains a separate
account with factor zero in the aggregate, consistently with the existing
EXIOBASE/GLORIA profiles. This convention does not calculate a net biogenic
carbon balance or characterize resource CO2 uptake. The Balanced bundle has
no fluorinated GHG accounts, so the profile covers its available greenhouse gases.

The conventional gas factors follow the `GHG Protocol table of IPCC GWP values
<https://ghgprotocol.org/sites/default/files/2024-08/Global-Warming-Potential-Values%20%28August%202024%29.pdf>`_.

BONSAI characterization
-----------------------

The built-in profile applies to both Balanced HSUT and native b2 HIOT inputs::

    db.calc_ghg()  # Creates "GHG AR6 GWP-100", including Accelerated CO2.

The additional factor for ``Accelerated CO2, Air | Air`` follows the BONSAI
``LCIA.xlsx`` and its ``load_climate_factors`` / ``calculate_ghg_footprint``
routines checked locally on 21 October 2026. It is a BONSAI modelling convention,
not a general IPCC factor for CO2. The source account remains available after
characterization. No workbook is loaded automatically by MARIO.

Only the checked AR6/GWP100 factor is included for this flow. When it is present,
requesting a different report or horizon without an available factor raises
``ValueError``; provide an explicit ``gwp`` mapping for another characterization.
When the flow is absent, the existing AR4/AR5 factors for the conventional gases
remain available. Source UUIDs and readable labels can be matched through
``db.info["bonsai"]["satellites"]``.

The aggregate retains the input mass unit. HIOT multipliers ``f`` and HSUT
commodity multipliers ``fc`` are expressed per native product unit. Comparisons
with external results require the same source inputs and characterization.

.. note::

   ``time_horizon`` and ``ipcc_report`` are used only when
   ``Database.calc_ghg(...)`` resolves a built-in ``profile``. In the current
   built-in registry this affects gases such as ``CH4`` and ``N2O``; scalar
   entries such as ``CO2`` and total ``GHG`` remain unchanged. When a custom
   flat ``gwp={...}`` mapping is passed, the method keeps the previous
   behavior and ignores these two arguments.
