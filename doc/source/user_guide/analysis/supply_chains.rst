:page-type: Guide
:summary: Measure bilateral trade, its embodied impacts and the regions contributing to them.

Trade and supply-chain analysis
===============================

Start with a traded item. IOTs use a sector; SUTs use a commodity.

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      trade = db.calc_trades(item="Agriculture")
      carbon = db.calc_trades_content(
          indicator="CO2", item="Agriculture", method="total",
      )

   .. container:: mario-result

      **Result** · Two region-by-region DataFrames: traded output in the item's
      unit, and embodied CO2 in the indicator's unit. Rows are origins; columns
      are destinations. Domestic flows are included.

Choose the question
-------------------

.. list-table::
   :header-rows: 1
   :widths: 44 56

   * - Question
     - Method
   * - How much is traded?
     - :doc:`calc_trades <../../api_document/mario.Database.calc_trades>`
   * - What impacts are embodied in that trade?
     - :doc:`calc_trades_content <../../api_document/mario.Database.calc_trades_content>`
   * - Which producers contribute to those impacts?
     - ``calc_trades_content(..., breakdown=True)``
   * - How concentrated are impact contributors?
     - :doc:`calc_trades_concentration <../../api_document/mario.Database.calc_trades_concentration>`
   * - What share depends on selected regions?
     - :doc:`calc_trades_exposure <../../api_document/mario.Database.calc_trades_exposure>`

Concentration is an HHI of **absolute contributor-region shares**. Exposure
is the share of absolute content attributable to selected contributor regions.
Both require an ``indicator``; they summarize the embodied-content breakdown.

.. mario-cards::
   :columns: 3

   .. mario-card:: Direct
      :kicker: method="direct"

      Impacts at the traded item's producer.

   .. mario-card:: Total
      :kicker: method="total"

      Direct and upstream impacts together.

   .. mario-card:: Upstream
      :kicker: method="upstream"

      The indirect part of the total.

**Embodied trade is not a consumption footprint.** Summing intermediate and
final trade across supply-chain stages can count the same upstream impact
multiple times. Use the returned tables to describe the selected transactions.

.. mario-details:: Separate final and intermediate transactions

   .. code-block:: python

      components = db.calc_trades(item="Agriculture", aggregate=False)
      final_only = db.calc_trades(item="Agriculture", intermediate=False)

   ``aggregate=False`` retains separate ``Intermediate`` and ``Final`` column
   groups. ``total=True`` adds a Total row and column. Omit ``item`` only when
   the combined items have homogeneous units.

.. mario-details:: Inspect the contributing producers

   .. code-block:: python

      contributors = db.calc_trades_content(
          indicator="CO2", item="Agriculture",
          method="total", breakdown=True,
      )

   Rows retain the origin and contributor levels. ``breakdown=True`` cannot
   be combined with ``total=True``.

.. mario-details:: Structural linkages

   .. code-block:: python

      linkages = db.calc_linkages(scenario="baseline")

   :doc:`db.calc_linkages() <../../api_document/mario.Database.calc_linkages>`
   measures forward and backward relationships in the production structure.
   It answers a different question from the quantities crossing a trade link.

Follow the :doc:`multi-year EXIOBASE case <../advanced/supply_chain_analyses>`
or :doc:`trace individual structural paths <structural_paths>`.
