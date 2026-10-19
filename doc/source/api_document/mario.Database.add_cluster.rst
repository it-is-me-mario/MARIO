mario.Database.add\_cluster
===========================

.. currentmodule:: mario

.. automethod:: Database.add_cluster

``members`` accepts a regional mapping when the set is regional, for example
``db.add_cluster("Activity", "selected", {"IT": ["A2"]})``. List shorthand is
also accepted and intersected with each region's domain. Existing clusters
are retained; the named cluster is replaced as a complete definition. See
:doc:`mario.Database.set_clusters` for validation and omitted-region semantics.
