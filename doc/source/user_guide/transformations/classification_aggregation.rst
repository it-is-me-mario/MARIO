Aggregating by classification
=============================

``db.get_aggregation(...)`` prepares a native-item-to-group mapping;
``db.aggregate(...)`` applies it to the model. The groups follow the official
hierarchy above the codes returned by :doc:`../inspection/concordances`.

**Preparing a mapping leaves the database unchanged.** Applying it with
``inplace=False`` returns an aggregated copy. Each native item has one target;
no item is divided between groups.

Choose an edition and a hierarchy level
---------------------------------------

.. code-block:: python

    db.available_aggregations

Hierarchy presets currently cover **NACE Rev. 2.1** and **CPA 2.2**, for native
variants with corresponding metadata. A NACE Rev. 2 or HS 2007 concordance alone
does not provide a hierarchy aggregation preset for that edition.

.. list-table:: Levels and example ancestors
   :header-rows: 1
   :widths: 24 20 28 28

   * - ``level``
     - Alias
     - NACE Rev. 2.1 example
     - CPA 2.2 example
   * - ``"section"``
     - —
     - ``A``
     - ``A``
   * - ``"division"``
     - ``"2 digits"``
     - ``01``
     - ``01``
   * - ``"group"``
     - ``"3 digits"``
     - ``01.1``
     - ``01.1``
   * - ``"class"``
     - ``"4 digits"``
     - ``01.11``
     - ``01.11``
   * - ``"category"``
     - ``"5 digits"``
     - Unavailable
     - ``01.11.1``
   * - ``"subcategory"``
     - ``"6 digits"``
     - Unavailable
     - ``01.11.11``

``classification`` chooses the system **and edition**; ``level`` chooses a
level within it. ``level="2 digits"`` does not mean NACE Rev. 2. The default
level is ``"section"``. Native-set and edition defaults follow
``get_concordances``; explicit arguments make the intended grouping clear.

Prepare and inspect the mapping
-------------------------------

These examples use a **GLORIA release 060 SUT**, already parsed as ``db``.
Prepare the Activity aggregation into NACE divisions:

.. code-block:: python

    mapping = db.get_aggregation(
        set="Activity", classification="NACE Rev. 2.1", level="2 digits",
    )
    frame = mapping["Activity"]
    frame.loc[["Growing wheat", "Growing rice", "Fishing"], "Aggregation"].to_dict()
    # {'Growing wheat': 'NACE Rev. 2.1:01',
    #  'Growing rice': 'NACE Rev. 2.1:01',
    #  'Fishing': 'Fishing'}

The result is ``{set_name: DataFrame}``. Its ``Aggregation`` column gives one
target for every current item. Labels include the edition, for example
``NACE Rev. 2.1:01``; descriptions are in the report. Unlike
``get_concordances``, this method prepares the complete selected set and has
no ``item`` or ``region`` filter.

Several linked classes can collapse to one ancestor. The packaged GLORIA
correspondence links ``Fishing`` to classes in divisions 01 and 03. Both
belong to section A: the section proposal assigns Fishing to A, while the
division proposal retains Fishing individually. The native name alone does
not override the supplied correspondence.

.. list-table:: Decision for each native item
   :header-rows: 1
   :widths: 48 30 22

   * - Linked codes
     - Target
     - Report reason
   * - All have one ancestor at the requested level
     - That ancestor group
     - Resolved
   * - Have several ancestors at that level
     - Original label
     - ``multiple_groups``
   * - No verified correspondence
     - Original label
     - ``unverified``
   * - Cannot reach the requested level, including a supplied broader code
     - Original label
     - ``coarser_than_level``

Read the report before applying
-------------------------------

.. code-block:: python

    report = frame.attrs["concordance"]
    report["classification"]          # 'NACE Rev. 2.1'
    report["level"]                   # 'division'
    report["groups"]["NACE Rev. 2.1:01"]  # Code and description.
    report["unresolved"]["Fishing"]["groups"]  # ['01', '03']
    report["hierarchy_source"]        # Official hierarchy source record.
    report["as_of"]                   # Metadata snapshot date.

    import pandas as pd

    unresolved_items = pd.DataFrame.from_dict(report["unresolved"], orient="index")

The default ``unresolved="keep"`` retains unresolved items individually, so
the result can mix standard groups and original labels.
``report["assigned_items"]`` counts distinct native labels assigned to a group,
not region/item pairs, output or emissions.

To require a group for every item:

.. code-block:: python

    strict_mapping = db.get_aggregation(
        set="Activity", classification="NACE Rev. 2.1", level="division",
        unresolved="raise",
    )
    # Raises WrongInput if any native item remains unresolved.

A unique group still inherits the source's partial-overlap qualifications.
Use ``db.get_concordances(..., details=True)`` to inspect the original evidence.
Equal division among several linked codes is not justified by these metadata.

Apply the reviewed mapping
--------------------------

.. code-block:: python

    aggregated = db.aggregate(
        io=mapping, levels=list(mapping), inplace=False,
    )

This aggregates **Activity only**. Commodity and Region keep their existing
classifications; the result remains a SUT. To prepare both productive sides:

.. code-block:: python

    both_sides = {
        **db.get_aggregation(set="Activity", classification="NACE Rev. 2.1", level="section"),
        **db.get_aggregation(set="Commodity", classification="CPA 2.2", level="section"),
    }
    aggregated_both = db.aggregate(both_sides, levels=list(both_sides), inplace=False)

On an IOT, choose ``set="Sector"`` and an edition compatible with its native
identities. A BONSAI HIOT Activity projection still returns a ``"Sector"``
mapping and aggregates the product table; it does not construct an
industry-by-industry IOT.

The existing aggregation checks apply. Different units cannot be summed into
one group. A proposed CPA group for hybrid commodities can therefore be rejected
at application if it mixes units. ``unresolved="keep"`` handles classification
uncertainty, not unit conversion.

Regional classifications and provenance
---------------------------------------

Common classifications have one row per native label. Regional classifications,
including BONSAI's varying domains, have a ``(Region, Item)`` index with only
existing pairs. Pass this whole mapping to ``aggregate`` without flattening
the index. Geographic aggregation is separate; see :doc:`aggregate` for Region
mappings and compatibility rules.

Keep the input mapping and report with your results. After aggregation,
``get_concordances`` sees new labels and does not reconstruct original
membership. The report lives in the DataFrame's ``attrs``; exporting its rows
to CSV or Excel does not automatically preserve that report.

For all parameters, see :meth:`~mario.CoreModel.get_aggregation` and
:meth:`~mario.Database.aggregate`.
