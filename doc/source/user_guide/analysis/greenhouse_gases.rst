:page-type: Guide
:summary: Combine the gas accounts in your database into a GHG indicator and retrieve its footprint.

Calculate greenhouse gas emissions
===================================

.. container:: mario-guide-facts

   **You need:** a parsed database with environmental accounts and a supported
   GHG profile, or an explicit mapping of accounts to characterization factors.

   **You obtain:** an additional satellite account in CO2-equivalent terms.
   The default built-in basis is **AR6 / GWP100** where the profile provides
   those factors. Already characterized source totals retain their source basis.

Check the source profile
-------------------------

For a known database family, inspect the profile selected from its metadata
and the accounts actually present:

.. code-block:: python

    profile = db.database_profile["ghg"]
    profile["selected_profile"]
    db.get_index("Satellite account")

The selected profile identifies a matching recipe; it does not certify that
all gases are available in the imported file. If the family has no built-in
profile, use the explicit-factor route in
:doc:`GHG characterization <ghg_characterization>`.

Create the GHG account
----------------------

On a freshly parsed model whose source profile provides AR6/GWP100 factors:

.. code-block:: python

    db.calc_ghg(ipcc_report="AR6", time_horizon=100)
    ghg = "GHG AR6 GWP-100"
    db.units["Satellite account"].loc[ghg]

**Result:** ``GHG AR6 GWP-100`` is added to the satellite accounts in every
existing scenario. The source gas accounts remain available. The aggregate
uses their shared mass unit, now interpreted as CO2-equivalent mass.

The call modifies ``db`` and returns ``None``. To keep the original model,
use ``characterized = db.calc_ghg(inplace=False)`` instead, then continue with
``characterized``. Choose one of these routes; adding the same account twice
raises an error.

Retrieve emissions and footprints
----------------------------------

Choose the representation of your model:

.. mario-switch::
   :label: GHG results by table format
   :hint: Choose IOT or SUT to see the relevant environmental matrices.

   .. mario-switch-option:: ghg-iot
      :badge: IOT
      :title: Sector results
      :text: Direct emissions and per-unit supply-chain footprints.

   .. mario-switch-option:: ghg-sut
      :badge: SUT
      :title: Activity and commodity results
      :text: Separate native emission blocks and commodity footprints.

.. _ghg-iot:

IOT results
~~~~~~~~~~~~

.. code-block:: python

    db.calc_all(["f"])
    direct_emissions = db.E.loc[ghg]
    per_unit_footprint = db.f.loc[ghg]

``E`` contains direct emissions by producing sector. ``f`` includes upstream
requirements per unit of sector output. Its denominator follows the database's
native monetary or physical unit.

.. _ghg-sut:

SUT results
~~~~~~~~~~~~

.. code-block:: python

    db.calc_all(["fc"])
    activity_emissions = db.Ea.loc[ghg]
    commodity_emissions = db.Ec.loc[ghg]
    per_unit_footprint = db.fc.loc[ghg]

``Ea`` and ``Ec`` retain activity-side and commodity-side emissions.
``fc`` gives the footprint per native commodity unit.

Check what the indicator represents
------------------------------------

``calc_ghg()`` characterizes available accounts. Retrieving a missing footprint
matrix is the separate calculation shown above. Direct final-demand emissions
in ``EY`` are characterized too; they must be considered when constructing
complete production- or consumption-based totals.

For BONSAI, the built-in AR6/GWP100 profile also includes its specific
``Accelerated CO2`` factor. Other characterization choices require an explicit
factor for that flow when present. For sources that supply an already
characterized CO2eq total, choosing ``ipcc_report`` does not reconstruct the
underlying gases. Read :doc:`GHG characterization and footprints <ghg_characterization>`
before comparing results across sources or reports.

If the calculation fails
------------------------

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Situation
     - What to check
   * - No profile can be selected
     - Inspect the source metadata; supply a supported ``profile`` or an explicit ``gwp`` mapping.
   * - No gas accounts match
     - Check that extensions were imported and that their labels match the selected recipe.
   * - Input accounts have different units
     - Harmonize their magnitudes and units before characterization. The ``unit`` argument does not convert values.
   * - The GHG label already exists
     - Reuse that account, start from the uncharacterized model, or choose a distinct label for another indicator.

See :doc:`db.calc_ghg() <../../api_document/mario.Database.calc_ghg>` for every
argument, or follow the complete :doc:`cross-database comparison
<../examples/compare_ghg>`.
