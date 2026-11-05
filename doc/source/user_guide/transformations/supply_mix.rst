:page-type: Guide
:summary: Change any production bundle and estimate recipes for newly activated producers.

Update supply mixes
===================

Use :meth:`~mario.Database.update_supply_mix` with explicit shares to change
any bundle of sectors, commodities or activities. Labels must already exist
in the specified region. With the packaged IOT example:

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      db.update_supply_mix(
          {"Reg1": {"Industry": 0.7, "Services": 0.3}},
          scenario="new_mix", clone_from="baseline",
          recipe_regions="Reg2",
      )

   .. container:: mario-result

      **Result** · A new scenario with a 70/30 split of the selected regional
      bundle for every buyer. Newly activated producers with empty recipes
      receive estimates from Reg2 when that region produces the same item.

The shares redistribute the combined rows of the selected bundle, preserving
its total for each buyer. Other members of the classification keep their
shares. Pass ``rescale=True`` for weights that do not sum to one.

Choose the table layout
-----------------------

* **IOT:** sector shares rewrite rows of ``z`` and ``Y``.
* **SUT commodity mix:** commodity shares rewrite rows of ``u`` and ``Yc``.
  Pass ``level="Commodity"`` if the labels also identify activities.
* **SUT activity mix:** activity shares rewrite rows of ``s``. Specify the
  market with ``commodities=...`` and, if needed, ``level="Activity"``.
  Producers outside the selected bundle retain their market shares.

``column_regions``, ``column_sectors`` and ``column_categories`` restrict the
buyers affected by the redistribution. Activity mixes select commodity
columns with ``commodities`` instead. These selectors do not restrict the
input recipe of a newly activated producer: its full column must be usable.

Estimate missing recipes
------------------------

By default, a producer with zero output before the update and an entirely
zero intermediate-input column receives an estimated recipe when the mix
gives it demand. An existing nonzero recipe is retained. The estimate uses
the selected scenario immediately before the update, including earlier shocks.

For each input, MARIO sums requirements across supplying regions before
averaging donors of the same output item. Donor weights are proportional to
their output. It then distributes that total input coefficient over supplying
regions using the receiving country's purchases of that input: intermediate
use plus final demand, including domestic supply. Negative net purchases are
excluded from the sourcing shares. If no purchases exist, the supplying-region
split falls back to the magnitudes of the donors' averaged input coefficients.

For example, donor input requirements of 0.2 and 0.6 with outputs of 100 and
300 give a total requirement of 0.5. If the receiving country buys that input
25% domestically and 75% from another country, its estimated coefficients
are 0.125 and 0.375, regardless of where the donors buy their inputs.

Entirely empty direct-emissions and value-added columns use the same donor
weights. On an IOT these are ``e`` and ``v``; on SUT activities they are ``ea``
and ``va``. SUT commodity mixes also fill empty ``ec`` and ``vc`` columns. A
missing SUT supply column is estimated from donors' activity shares and assigned
to domestic activities with the same labels; those activities must already
exist. Their empty use recipes are then filled. MARIO records donor choices
in the database's metadata history.

These estimates assume transferable technology and comparable output units.
They do not estimate country-specific efficiency, emissions controls, prices
or factor shares. Review the donor choice for your application. If no eligible
donor exists, MARIO raises an error before writing the proposed mix. To retain
empty recipes deliberately, pass ``fill_missing_recipes=False``.

Choose donor regions
--------------------

``recipe_regions=None`` (the default) or ``"global"`` uses all other regions
with positive output of the same item. A region or list restricts every
missing recipe. Use a mapping for individual receiving-region/item pairs:

.. code-block:: python

   db.update_supply_mix(
       {"Reg1": {"Industry": 0.7, "Services": 0.3}},
       scenario="regional_recipe", clone_from="baseline",
       recipe_regions={
           ("Reg1", "Industry"): ["Reg2"],
       },
   )

Unspecified pairs use global donors. Explicit donors must have positive
pre-update output of the requested item. On SUT commodity mixes, a commodity
override is also used for its producers unless an activity override exists.
If several commodities share an inactive activity, specify an activity
override when their commodity donor selections differ.

For an interactive session, set ``recipe_regions="prompt"``. MARIO asks for
donors for each missing recipe and lists the eligible regions. Enter one
region, comma-separated regions, or press Enter to use all eligible donors.
Mapping values can also be ``"prompt"`` for selected pairs. Use explicit
mappings for unattended scripts and reproducible notebooks.

See :doc:`../advanced/electricity_mix` for the electricity preset and its
downloadable notebook. The same recipe estimation applies to that preset.
Use :meth:`~mario.Database.update_trade_mix` to change sourcing shares directly.
The :doc:`API reference <../../api_document/mario.Database.update_supply_mix>`
documents all selectors and SUT trade-layout constraints.
