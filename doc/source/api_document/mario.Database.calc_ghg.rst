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

BONSAI HIOT characterization
----------------------------

The built-in BONSAI profile also applies to the native b2 HIOT. It does not read
BONSAI's LCIA workbook. In particular, ``Accelerated CO2, Air | Air`` remains a
separate elementary flow and is excluded from the default GHG aggregate.

The local ``LCIA.xlsx`` checked on 20 October 2026 uses the following nonzero
GWP100 factors. To calculate that characterization explicitly, before filtering
out the original elementary flows::

    db.calc_ghg()  # Creates "GHG AR6 GWP-100".
    bonsai_gwp100 = {
        "Carbon dioxide, fossil | Air": 1.0,
        "Methane, fossil | Air": 29.8,
        "Methane, non-fossil | Air": 27.0,
        "Dinitrogen monoxide | Air": 273.0,
        "Accelerated CO2, Air | Air": 0.00772,
    }
    db.calc_ghg(gwp=bonsai_gwp100, label="GHG BONSAI GWP100")
    db.keep_extensions(["GHG AR6 GWP-100", "GHG BONSAI GWP100"])
    multipliers = db.f  # Two environmental rows in one HIOT solve.

Check these factors against the LCIA workbook accompanying the input export;
they are an example from the inspected files, not a version-independent BONSAI
method. The workbook's UUIDs can be matched to the parser's readable labels
through ``db.info["bonsai"]["satellites"]``. The custom label distinguishes this
BONSAI-specific characterization from MARIO's built-in AR6 GWP100 profile.

Both rows have units of tonnes CO2eq per native product unit. When the product
is ``M_electricity`` in TJ, multiplying either row by 3.6 gives g CO2eq/kWh.
Matching the characterization alone does not guarantee agreement with a saved
footprint from a different source model; see :doc:`mario.parse_bonsai` for the
comparison workflow and the dated local verification.

.. note::

   ``time_horizon`` and ``ipcc_report`` are used only when
   ``Database.calc_ghg(...)`` resolves a built-in ``profile``. In the current
   built-in registry this affects gases such as ``CH4`` and ``N2O``; scalar
   entries such as ``CO2`` and total ``GHG`` remain unchanged. When a custom
   flat ``gwp={...}`` mapping is passed, the method keeps the previous
   behavior and ignores these two arguments.
