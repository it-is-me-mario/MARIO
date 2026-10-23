:page-type: Guide
:summary: Find labels, inspect scenarios and retrieve the matrices you need.

Inspect and query a database
============================

.. container:: mario-companion

   :download:`Run the notebook <basic_inspections.ipynb>`

Start with the packaged IOT; use your parsed ``db`` in the same calls.

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      sectors = db.get_index("Sector")
      production = db.query("X", scenarios="baseline")

   .. container:: mario-result

      **Result** · ``sectors`` is a list of native labels; ``production`` is a
      pandas DataFrame indexed by region and sector.

Find your way around
--------------------

.. mario-cards::
   :columns: 2

   .. mario-card:: Labels and sets
      :icon: tag

      ``db.sets`` lists the sets. ``db.get_index("all")`` returns their members.
      Use ``db.search("Agr")`` to find labels without knowing their exact spelling.

   .. mario-card:: Scenarios and matrices
      :icon: table-search

      ``db.scenarios`` lists the scenarios.
      ``db.list_matrices(scenario="baseline")`` shows what is stored.
      ``db.available_matrices()`` lists quantities the runtime can resolve.

Read data
---------

.. code-block:: python

   Z = db.Z                          # Baseline transactions.
   e = db.query("e")                 # Calculate if missing.
   selected = Z.loc[("Reg1", "Sector", "Agriculture")]

Dotted access and ``query()`` can trigger a calculation. They are more than
lookups of already stored matrices. See :doc:`compute_matrices` for control
over requested targets and scenarios.

.. mario-details:: SUTs: activities and commodities

   .. code-block:: python

      sut = mario.load_test("SUT")
      activities = sut.get_index("Activity")
      commodities = sut.get_index("Commodity")
      use = sut.query("U")
      commodity_output = sut.query("Xc")

   The inspection pattern stays the same; SUTs have separate activity and
   commodity sets and split matrix blocks. See :doc:`../../get_started/table_formats`.

.. mario-details:: BONSAI and other regional classifications

   When membership varies by region, ``get_index()`` returns
   ``{region: [members]}``. Ask for one region or the union explicitly:

   .. code-block:: python

      local = db.get_index("Sector", region="IT")
      union = db.get_index("Sector", flat=True)

   These calls require a database containing ``IT``. A label in the union need
   not exist in every region. ``search()`` accepts the same selectors.

Continue with :doc:`classification concordances <concordances>` or
:doc:`exporting your model <export_and_roundtrip>`.
