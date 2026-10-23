:page-type: Guide
:summary: Calculate each region’s output shares for a selected group of sectors.

Inspect production mixes
========================

**Requires an IOT.** Select sectors with comparable production units.

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      mix = db.get_mix(["Agriculture", "Services"])
      mix["Reg1"]

   .. container:: mario-result

      **Result** · ``{region: {sector: share}}``. Each region's selected output
      is normalized by its bundle total. The mapping is also stored in ``db.mix``.

.. mario-cards::
   :columns: 2

   .. mario-card:: Inspect a model
      :icon: chart

      ``get_mix()`` reads production ``X``. It describes the shares already
      represented in the selected scenario.

   .. mario-card:: Change a model
      :icon: bolt

      :doc:`Update electricity mixes <../advanced/electricity_mix>` to apply
      new supply or trade shares, including supported external providers.

.. mario-details:: Electricity and region-specific sectors

   For a supported electricity classification, use
   ``db.get_mix("electricity")`` to select its generation bundle.
   With region-specific classifications, only sectors present in a region
   appear in that region's result. A region with no selected sectors returns
   ``{}``; a zero-production bundle returns zero shares.

**Check what the output represents.** In a transformed hybrid IOT, shares of
reference-product output can differ from a historical physical generation mix,
particularly where by-products have no independent nodes. Align units, scope
and CHP treatment before comparing against an electricity statistics source.

Full interface: :doc:`db.get_mix() <../../api_document/mario.Database.get_mix>`.
