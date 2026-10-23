mario.Database.set\_clusters
============================

.. currentmodule:: mario

.. automethod:: Database.set_clusters

For a common classification, define each cluster as a list of labels::

    db.set_clusters({"Activity": {"selected": ["A1", "A2"]}})

Special case: regional classifications
--------------------------------------

Cluster definitions follow the shape of the corresponding set. For regional
activity domains ``{"IT": ["A1", "A2"], "DE": ["A1", "A3"]}``, use::

    db.set_clusters({
        "Activity": {
            "selected": {"IT": ["A2"], "DE": ["A3"]},
            "Italy only": {"IT": ["A1"]},
        }
    })

Each region-code pair is validated. ``{"IT": ["A3"]}`` is rejected even though
``A3`` exists in Germany. Unknown regions and codes are rejected before the
stored clusters change. An omitted region selects no members; a same-named
explicit definition replaces the complete earlier cluster, without filling
omitted regions from it.

A list remains accepted as shorthand on regional sets::

    db.set_clusters({"Activity": {"shared selection": ["A1", "A2"]}})
    db.clusters["Activity"]["shared selection"]
    # {"IT": ["A1", "A2"], "DE": ["A1"]}

The shorthand is intersected with each region's domain, including empty
lists where no supplied code exists. Codes absent from the entire domain are
rejected. Common/global sets retain the existing list representation. Set
aliases and legacy keyword payloads are supported. Nested input/output lists
are copied independently.

Shock expansion respects these regional definitions for activity, commodity,
sector and final-demand axes. It selects actual matrix nodes, never a padded
region-by-item grid. A literal code absent from all selected regions is an
error; a regional cluster with no members in those regions selects nothing.

See :doc:`the clusters guide </user_guide/inspection/clusters>` for examples.
