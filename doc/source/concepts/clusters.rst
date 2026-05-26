Clusters
========

In MARIO, a cluster is a named group of labels inside one set.
Clusters are useful when multiple workflows need to reuse the same grouping
logic without rewriting the member lists every time.

At the moment, MARIO auto-generates default clusters only for the
``Region`` set. The same API already accepts user-defined clusters for any
set, and automatic coverage for additional sets can be extended in future
releases.

What Clusters Mean
------------------

Clusters and aggregations are related, but they are not the same thing.

- A cluster is a reusable named group such as ``EU`` or
  ``continent:Europe``.
- An aggregation is a one-to-one mapping from each original label to one
  target label.

This distinction matters because shock and sector-addition helpers can reuse
clusters as selection shortcuts, while ``Database.aggregate(...)`` needs a
deterministic aggregation index for every label that will be collapsed.

Inspect Default and Available Clusters
--------------------------------------

Default clusters are generated on demand from the database coverage and then
merged with any user-defined clusters you store on the database.

.. code-block:: python

   import mario

   db = mario.parse_exiobase(
       path="/path/to/IOT_2024_ixi.zip",
       table="IOT",
       unit="Monetary",
   )

   db.default_clusters["Region"].keys()
   db.available_clusters["Region"]["EU"]

``db.default_clusters`` returns only the automatically generated definitions.
``db.available_clusters`` returns the effective definitions after merging the
defaults with the clusters saved via ``db.set_clusters(...)``.

Add Custom Clusters
-------------------

You can persist your own groups with ``Database.set_clusters(...)`` and they
will become part of ``available_clusters``.

.. code-block:: python

   db.set_clusters(
       {
           "Region": {
               "Europe custom": ["AUT", "BEL", "DEU", "FRA", "ITA"],
           },
           "Sector": {
               "Energy": [
                   "Electricity",
                   "Gas",
                   "Steam and air conditioning supply",
               ],
           },
       }
   )

   db.available_clusters["Sector"]["Energy"]

Set names can be passed using the usual MARIO aliases. Cluster members must
still be valid labels for the selected set.

Use Clusters for Region Aggregation
-----------------------------------

The new ``region_aggregation`` argument builds a Region aggregation index from
the same regional coverage logic used to derive default region clusters.
This is the recommended path when you want to aggregate regions without first
editing an Excel workbook by hand.

.. code-block:: python

   by_continent = db.aggregate(
       io=None,
       levels="Region",
       region_aggregation="continent",
       inplace=False,
   )

   by_continent.get_index("Region")

Preset rely values on the `country_converter package <https://github.com/IndEcol/country_converter>`_.
The currently supported by ``region_aggregation`` are:

- ``continent``
- ``UNregion``
- ``EU``
- ``OECD``
- ``G7``
- ``G20``

You can also pass an explicit mapping, a pandas ``Series`` or a pandas
``DataFrame`` when you need fully custom Region targets.

Country Coverage Workbook
-------------------------

The default regional coverage is backed by the packaged country coverage
workbook used by MARIO at runtime. It helps resolve source-specific region
codes to ISO3 labels before assigning default region groups.

Download the :download:`Country_coverage workbook </_static/data/supporting_files/Country_coverage.xlsx>`

For a complete workbook-based workflow, see
:doc:`../user_guide/transformations/aggregate`.