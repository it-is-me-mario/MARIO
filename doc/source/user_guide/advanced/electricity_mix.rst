:page-type: Guide
:summary: Change generation shares and bilateral sourcing with explicit mappings or provider data.

Update electricity mixes
========================

.. container:: mario-companion

   :download:`Download notebook <electricity_mix.ipynb>`

Use a model with separate generation technologies, such as a supported
EXIOBASE layout or EMERGING-E. Supply and trade shares answer different questions.

.. mario-cards::
   :columns: 2

   .. mario-card:: How is electricity produced?
      :icon: bolt

      ``update_supply_mix()`` changes generation shares. The ``"electricity"``
      preset uses EMBER fuel groups.

   .. mario-card:: Where does it come from?
      :icon: chain

      ``update_trade_mix()`` changes sourcing by destination. Its electricity
      preset uses ENTSO-E scheduled commercial exchanges.

Update a generation mix
-----------------------

With a supported model already parsed as ``db``:

.. container:: mario-recipe

   .. code-block:: python

      db.update_supply_mix(
          "electricity", scenario="updated_mix", clone_from="baseline",
      )

   .. container:: mario-result

      **Result** · A scenario using the packaged provider snapshot. On an IOT,
      the selected generation bundle is redistributed across ``z`` and ``Y``.
      On a supported SUT, generation commodities are combined and activity
      market shares are updated in ``s``.

The provider groups are coarser than native technologies. MARIO redistributes
within each group using its existing internal composition. This does not
independently estimate every technology's historical share.

.. mario-details:: Inspect the resulting IOT mix

   .. code-block:: python

      mix = db.get_mix("electricity", scenario="updated_mix")

   See :doc:`../analysis/production_mix` for units and the distinction between
   reference-product output and physical generation, including CHP by-products.

.. mario-details:: Use live provider data for a selected year

   Register the provider key in your environment, then configure the session:

   .. code-block:: python

      import os
      import mario

      mario.set_api_keys(ember=os.environ["EMBER_API_KEY"])
      db.update_supply_mix(
          "electricity", scenario="updated_mix", year=2023, api_key="ember",
      )

   Without an explicit live-provider selection, the packaged snapshot is used.
   Uncovered regions or regions with no positive generation remain unchanged.
   A missing year can fall back to the nearest available observation; check
   the log before treating the result as a uniform-year update.

.. mario-details:: Separate generation and trade in an Isard SUT

   Promote ``updated_mix`` to the baseline of a separate database, then pool
   the shared electricity commodity. ``pool_trade()`` operates on the baseline
   and discards other scenarios; promoting first keeps the generation update.

   .. code-block:: python

      pooled_db = db.build_new_instance("updated_mix")
      pooled_db.pool_trade("electricity")
      pooled = pooled_db.meta.pooled_trade_map["electricity"]
      pooled_db.update_trade_mix(
          "electricity", items=pooled["supply"], commodities=pooled["need"],
          level="Activity", scenario="trade_mix", clone_from="baseline",
          fill_uncovered_domestic=False,
      )

   The pool adds a pass-through activity and a need commodity per region.
   ``pooled_db`` retains the updated generation mix; its ``trade_mix`` scenario
   adds the sourcing update. Generation and sourcing occupy separate
   market-share columns. The original ``db`` remains available for comparison.
   This example uses the packaged ENTSO-E snapshot and keeps uncovered regions'
   sourcing. Its net commercial exchanges are not physical cross-border flows.

   .. figure:: ../../_static/images/pool_trade.png
      :alt: Electricity pooling separates the supply and need markets in a SUT.

      The supply activity connects production to each destination's need market.

.. mario-details:: Explicit mappings and destination filters

   Supply accepts ``{region: {label: share}}``; trade accepts
   ``{destination: {origin: share}}``. Use ``rescale=True`` when the supplied
   totals need normalization. See the APIs for item and column selectors.

   On a Chenery–Moses SUT, a producer's technology appears in multiple
   destination markets. Keep ``column_regions=None`` to update all of them;
   a domestic-only filter would leave exported production on the old mix.

Full interfaces: :doc:`update_supply_mix <../../api_document/mario.Database.update_supply_mix>`,
:doc:`pool_trade <../../api_document/mario.Database.pool_trade>` and
:doc:`update_trade_mix <../../api_document/mario.Database.update_trade_mix>`.
