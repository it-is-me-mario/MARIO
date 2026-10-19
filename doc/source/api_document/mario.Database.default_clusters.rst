mario.Database.default\_clusters
================================

.. currentmodule:: mario

.. autoproperty:: Database.default_clusters

Each set's ``"all"`` cluster is an ordered list of distinct observed codes,
including when :meth:`~mario.CoreModel.get_index` returns regional lists in a
dictionary. The order follows ``get_index(set_name, flat=True)``. Common
classifications retain their previous lists, and geographic Region clusters
remain available.

For example, if the commodity domains are ``{"IT": ["C1", "C2"], "DE": ["C1"]}``,
the automatic cluster is::

    db.default_clusters["Commodity"]["all"]
    # ["C1", "C2"]

This union does not imply that ``C2`` exists in Germany. Regional membership
is still given by ``db.get_index("Commodity", region="DE")``. Default cluster
generation does not create region-item pairs or compute matrices. Mutating
the returned clusters does not change the database.
