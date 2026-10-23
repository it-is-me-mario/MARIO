:page-type: Guide
:summary: Save named groups of labels and reuse them in selections and scenarios.

.. _concept-clusters:

Work with clusters
==================

A **cluster** is a named group of members of one set. Store a selection once,
then reuse it in workflows that accept clusters, such as shocks or sector additions.

Create a cluster
----------------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      sectors = db.get_index("Sector")
      db.set_clusters({"Sector": {"Selected sectors": sectors[:2]}})
      selected = db.available_clusters["Sector"]["Selected sectors"]

   .. container:: mario-result

      **Result** · A reusable named selection containing the first two native
      sector labels. This call does not change the table's dimensions or values.

Set names accept the usual aliases; members must exist in the chosen set.
See :doc:`db.set_clusters() </api_document/mario.Database.set_clusters>` for
validation and replacement options.

Default and saved groups
------------------------

.. mario-cards::
   :columns: 2

   .. mario-card:: Generated regional groups
      :kicker: db.default_clusters

      On recognized region labels, MARIO derives groups such as continents
      and EU membership. Default groups are generated only for ``Region``;
      their members depend on the database's coverage.

   .. mario-card:: All available groups
      :kicker: db.available_clusters

      Combines generated defaults with the groups you have saved.
      You can define your own clusters for other sets, such as Sector.

For example, on a parsed EXIOBASE database:

.. code-block:: python

   db.default_clusters["Region"].keys()
   eu_members = db.available_clusters["Region"]["EU"]

The artificial region labels in the packaged test table do not identify
countries and cannot provide this geographic example.

Clusters and aggregation
------------------------

A cluster records a reusable selection. **Aggregation changes the table** and
needs one target group for each original member being mapped.

The :doc:`aggregation guide <../transformations/aggregate>` explains how to
use regional presets (``continent``, ``UNregion``, ``EU``, ``OECD``, ``G7``, ``G20``)
or a custom mapping. Region presets share the coverage logic used by default
clusters; selecting a cluster alone does not aggregate anything.

Continue with :doc:`shocks <../transformations/apply_shocks>` or
:doc:`db.available_clusters </api_document/mario.Database.available_clusters>`.
