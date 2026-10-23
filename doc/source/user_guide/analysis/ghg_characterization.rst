:page-type: Explanation
:summary: Understand the characterization recipe, units and accounting boundary behind a GHG result.

GHG characterization and footprints
====================================

Gas characterization
--------------------

For each producing node, MARIO multiplies the matched gas accounts by their
characterization factors and sums them:

.. math::

   E_{\mathrm{GHG},j} = \sum_{g \in G} \mathrm{GWP}_g E_{g,j}.

The same operation applies to direct final-demand emissions in ``EY`` and to
the native environmental blocks of a SUT. Existing environmental coefficients
and footprint matrices receive the weighted row too. Missing footprint
matrices are calculated when requested.

Only matching accounts enter the result. Missing gases are not estimated.
All matched accounts must share a unit; the method does not convert their
magnitudes. For example, kilograms of each gas produce a result interpreted
as kilograms of CO2-equivalent.

Built-in GHG profiles
---------------------

A built-in profile connects source account labels to factors. The profile
is selected from source/name metadata unless explicitly supplied. Inspect it
with :doc:`database profiles <../advanced/database_profiles>`.

The API defaults to AR6 and a 100-year horizon. Those arguments select factors
where the profile stores multiple reports or horizons. A scalar factor is
unchanged. In particular, an already characterized source CO2eq total keeps
its original characterization; a new output label does not recharacterize it.

BONSAI's recipe includes a factor of **0.00772** for
``Accelerated CO2, Air | Air`` when present. This is a BONSAI modelling
convention checked for AR6/GWP100, not a general IPCC factor for CO2.
The conventional factors and the available alternatives are documented in
:doc:`db.calc_ghg() <../../api_document/mario.Database.calc_ghg>`.

Supply your own factors
------------------------

Pass exact account labels and the factors appropriate to your assessment.
For example, **only if these are your source labels**, this mapping represents
the listed conventional AR6/GWP100 gas factors:

.. code-block:: python

    factors = {
        "CO2 - combustion - air": 1.0,
        "CH4 - combustion - air": 29.8,
        "N2O - combustion - air": 273.0,
    }
    characterized = db.calc_ghg(
        gwp=factors, label="GHG selected combustion accounts", inplace=False,
    )

This example covers those three accounts only. Include other relevant source
accounts explicitly. With ``gwp=...``, report and horizon arguments do not
modify the supplied factors; preserve the factor mapping with your results.

Supply-chain footprints
-----------------------

On an IOT, direct emission coefficients ``e`` describe emissions per unit of
output. The per-unit footprint includes the supply chain:

.. math::

   f = e\,(I-z)^{-1}.

MARIO can obtain the same result by solving a linear system rather than
materializing the inverse. See :doc:`computation settings <../advanced/compute_settings>`.
For a SUT, use the native activity and commodity quantities, including ``fc``
for commodity footprints; see the
:doc:`matrix catalogue <../../reference/api_resolvable_matrices>`.

A multiplier is not a national total. Production-based and consumption-based
totals also require the appropriate activity or demand aggregation and treatment
of direct final-demand emissions. The
:doc:`comparison example <../examples/compare_ghg>` makes those choices explicit.

Cross-database comparisons
--------------------------

Record the source release and reference year, account coverage, actual factors,
units and accounting boundary. The Explorer's published comparison recipes
can differ from ``calc_ghg()`` defaults: selecting the same report name alone
does not guarantee identical account coverage or factors.

Return to :doc:`Calculate greenhouse gas emissions <greenhouse_gases>` for
the operational steps.
