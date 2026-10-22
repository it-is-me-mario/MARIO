mario.CoreModel.get_concordances
================================

.. currentmodule:: mario

.. automethod:: CoreModel.get_concordances

For a parsed GLORIA SUT, retrieve all native activity links, or select items::

    db.get_concordances(set="Activity", classification="NACE Rev. 2.1")
    db.get_concordances(
        set="Activity",
        classification="NACE Rev. 2",
        item=["Growing wheat", "Growing rice"],
        region="ITA",
    )
    # {'Growing wheat': ['01.11'], 'Growing rice': ['01.12']}

The region label must match the parsed database. Omitting ``region`` uses the
distinct union, rather than claiming that every item exists in every region.
``item`` always selects current native labels; a label not in that set raises
``WrongInput``. Renamed, aggregated or newly added labels without a bundled
identity return an empty list. An empty result does not establish absence.

Discover the editions available for this database before querying::

    db.available_concordances
    db.get_concordances(set="Commodity", classification="CPA 2.2")
    db.get_concordances(
        set="Commodity", classification="CPC 2.1", item="Growing wheat"
    )

Targets currently include NACE 2.1/2/1.1, ISIC 4/3.1, CPA 2.2/2.1/2008/2002,
CPC 2.1 and HS 2007. Availability and coverage vary by database and native
variant. ``NACE``, ``CPA``, ``ISIC``, ``CPC`` and ``HS`` are documented aliases
for NACE 2.1, CPA 2.2, ISIC 4, CPC 2.1 and HS 2007 respectively. HS 2022 is
not silently substituted with HS 2007. The HS 2007 supplement covers EXIOBASE
products with an explicit supplied alias correspondence; absent aliases remain
unverified. No product memberships are inferred from industry classifications.

For IOTs, ``set="Sector"`` uses the native side: activity for industry-by-industry
tables, commodity for product-by-product tables. MARIO's SUT→IOT transformations
retain this distinction. ``Activity`` and ``Commodity`` may select compatible
IOT projections. BONSAI HIOT additionally supplies an explicit reference-product
to process association: ``set="Activity"`` or a NACE target follows that bridge,
retaining actual Sector labels as dictionary keys.

Retrieve the evidence when interpreting a many-to-many result::

    result = db.get_concordances(
        set="Activity", classification="NACE Rev. 2", item="Growing wheat",
        details=True,
    )
    result["Growing wheat"]["codes"]
    result["Growing wheat"]["matches"]["01.11"]["routes"]
    result["Growing wheat"]["sources"]

The current NACE 2.1 and CPA 2.2 results reproduce the explorer's reviewed
footprints. Additional editions follow explicit route prefixes or compose
official classification bridges. Composed and reverse routes are marked
``partial`` with their traversal direction: they are qualified correspondences,
not proof of exact native scope. A supplied broad anchor is returned only at
its own classification level; it does not enumerate possible descendant classes.
Workbook parents and pending editorial proposals never supply memberships.

These are **correspondences, not numerical allocation weights**. A code list
can be many-to-many; equal division among its entries is not justified by the
mapping. Results use packaged metadata and require neither a network request
nor calculation of an input–output inverse.
