:page-type: Explanation
:summary: Understand which hierarchy groups can be assigned and how uncertain correspondences are reported.

How classification groups are assigned
=======================================

A correspondence links a native item to one or more classification codes.
An aggregation proposal follows the official hierarchy above those codes.
Each native item receives one target; the proposal never splits its values
between several groups.

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

When linked codes span multiple groups
--------------------------------------

Several linked classes can collapse to one ancestor. The packaged GLORIA
release 060 correspondence links ``Fishing`` to classes in divisions 01 and
03. Both belong to NACE section A: a section proposal assigns it to A; a
division proposal retains ``Fishing`` individually.

The native name alone does not override the supplied correspondence. Even a
unique ancestor retains the source's partial-overlap qualifications. Inspect
``db.get_concordances(..., details=True)`` for source evidence. The
correspondences do not supply allocation weights.

.. list-table::
   :header-rows: 1
   :widths: 43 27 30

   * - Correspondence
     - Target
     - Report reason
   * - All codes have one ancestor at the requested level
     - Ancestor group
     - Resolved
   * - Codes have several ancestors at that level
     - Original label
     - ``multiple_groups``
   * - No verified correspondence
     - Original label
     - ``unverified``
   * - Codes are too broad to identify that level
     - Original label
     - ``coarser_than_level``

The default ``unresolved="keep"`` retains those original labels. Use
``unresolved="raise"`` when every item must receive a hierarchy group.

The report and its counts
--------------------------

For a mapping frame, ``frame.attrs["concordance"]`` records the edition,
level, metadata date, hierarchy source, group descriptions and unresolved
items. ``assigned_items`` counts distinct native labels assigned to a group,
not region/item pairs, production or emissions.

A unique code is not proof of full economic containment. Review the source
qualifications and resulting groups before applying them to your analysis.

Units and table representation
-------------------------------

The existing aggregation checks apply when the mapping is used. Different
units cannot be summed into one group. A CPA group for hybrid commodities can
therefore be rejected if its members have different units. The ``unresolved``
option handles classification uncertainty, not unit conversion.

On an IOT, use ``set="Sector"`` and a classification compatible with its native
identities. BONSAI's HIOT Activity projection returns a ``"Sector"`` mapping:
it groups the product table and does not construct an industry-by-industry IOT.

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

Return to :doc:`Aggregate by classification <classification_aggregation>`
for the preparation, review and application steps.
