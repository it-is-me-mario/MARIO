:page-type: Guide
:summary: Find labels, inspect scenarios and retrieve the matrices you need.

Inspect and query a database
============================

.. container:: mario-companion

   :download:`Download notebook <basic_inspections.ipynb>`

Start with the packaged IOT; the same query pattern applies to parsed IOT/SUT
databases. For NAM, use the dedicated section below.

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      sectors = db.get_index("Sector")
      production = db.query("X", scenarios="baseline")

   .. container:: mario-result

      **Result** · ``sectors`` is a list of native labels; ``production`` is a
      pandas DataFrame indexed by region and sector.

Sets, labels and scenarios
--------------------------

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
      ``db.available_matrices()`` lists registered names. A registered result
      can be calculated only when its required inputs are available.

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
   commodity sets and split matrix blocks. See :doc:`../../get_started/table_formats/sut`.

Inspect a NAM
-------------

After :doc:`importing FIGARO-NAM </notebooks/parsers/figaro/walkthrough_figaro>`,
inspect its sets and request data through the NAM resolver:

.. code-block:: python

   nam.sets
   residents = nam.get_index("si_d")
   stored = nam.list_matrices()
   registered = nam.available_matrices()
   consumption = nam.get_block("CF_d")
   coefficients = nam.resolve("cf_d")
   axes = nam.get_block_spec("MU")

``CF_d`` receives consumption funding on rows and records the paying resident
income sectors on columns. ``get_block`` reads available data without
calculating it; ``resolve`` calculates a registered result when needed.
An unavailable flow is absent from ``list_matrices()``, even though its name
exists in the catalogue. ``has_matrix`` tests availability in that scenario,
not whether every dependency of an uncomputed result can be resolved.

National axes use ``Region / Set / Item``. FIGARO import rows also retain
``origin_region`` and ``imported_commodity``; those origins are not extra
reporting economies. ``nam.units`` is a dictionary of currency, scale and
period. NAM does not implement ``query`` or ``search``; use ``get_index``
and pandas selection on returned frames. See :doc:`/reference/api_nam_database`
for exact signatures and :doc:`compute_matrices` for coefficients.

.. mario-details:: BONSAI and other regional classifications

   When membership varies by region, ``get_index()`` returns
   ``{region: [members]}``. Ask for one region or the union explicitly:

   .. code-block:: python

      local = db.get_index("Sector", region="IT")
      union = db.get_index("Sector", flat=True)

   These calls require a database containing ``IT``. A label in the union need
   not exist in every region. ``search()`` accepts the same selectors.

Continue with :doc:`named groups <clusters>`, :doc:`classification concordances <concordances>` or
:doc:`exporting your model <export_and_roundtrip>`.
