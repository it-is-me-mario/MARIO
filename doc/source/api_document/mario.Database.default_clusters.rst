mario.Database.default\_clusters
================================

.. currentmodule:: mario

.. autoproperty:: Database.default_clusters

Each set's ``"all"`` cluster retains the representation and membership given
by :meth:`~mario.CoreModel.get_index`. Common classifications keep their
existing ordered lists; regional classifications use dictionaries of regional
lists. Geographic Region clusters remain available.

For example, if the commodity domains are ``{"IT": ["C1", "C2"], "DE": ["C1"]}``,
the automatic cluster is::

    db.default_clusters["Commodity"]["all"]
    # {"IT": ["C1", "C2"], "DE": ["C1"]}

Empty regions appear with empty lists. Cluster expansion selects existing
region-item pairs, so ``C2`` is not selected in Germany. Default cluster
generation does not compute matrices. Mutating returned nested lists does not
change the database.

See :doc:`the clusters guide </user_guide/inspection/clusters>` for examples.
