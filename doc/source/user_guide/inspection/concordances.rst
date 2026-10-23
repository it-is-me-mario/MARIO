Classification concordances
===========================

``db.get_concordances(...)`` returns the classification codes linked to native
items in a parsed database. For example, GLORIA's native activity
``"Growing wheat"`` links to NACE Rev. 2.1 class ``"01.11"``.
The lookup uses the packaged metadata shared with the Database explorer.
It leaves the model unchanged and needs no downloads or matrix calculations.

A **native item** is a label in your model. A **classification** is the target
system and edition, such as NACE Rev. 2.1. The output keeps native labels as
keys and returns target codes as strings, preserving leading zeros.

Choose the native set and target edition
----------------------------------------

.. code-block:: python

    db.table_type
    db.sets
    db.available_concordances

.. list-table:: Which set to query
   :header-rows: 1
   :widths: 25 25 50

   * - Model
     - ``set``
     - Target normally describes
   * - SUT
     - ``"Activity"``
     - Activities: NACE or ISIC
   * - SUT
     - ``"Commodity"``
     - Products: CPA, CPC or the supplied HS correspondence
   * - IOT
     - ``"Sector"``
     - The native side: activities for industry-by-industry, products for
       product-by-product

For a SUT, omitting ``set`` selects Activity; for an IOT, it selects Sector.
The default target is NACE Rev. 2.1 for activity identities and CPA 2.2 for
commodity identities. Use explicit editions in reproducible analyses.

.. list-table:: Recognised targets; availability depends on the native variant
   :header-rows: 1
   :widths: 18 60 22

   * - System
     - Explicit editions
     - Short alias selects
   * - NACE
     - ``"NACE Rev. 2.1"``, ``"NACE Rev. 2"``, ``"NACE Rev. 1.1"``
     - ``"NACE"`` → 2.1
   * - ISIC
     - ``"ISIC Rev. 4"``, ``"ISIC Rev. 3.1"``
     - ``"ISIC"`` → 4
   * - CPA
     - ``"CPA 2.2"``, ``"CPA 2.1"``, ``"CPA 2008"``, ``"CPA 2002"``
     - ``"CPA"`` → 2.2
   * - CPC
     - ``"CPC 2.1"``
     - ``"CPC"`` → 2.1
   * - HS
     - ``"HS 2007"``
     - ``"HS"`` → 2007

HS 2007 comes from the supplied EXIOBASE product correspondence and its
explicit product bridges. A request for HS 2022 raises ``WrongInput``.
An available activity concordance does not establish a product concordance.

Retrieve one item, several items or the full set
------------------------------------------------

These examples use a **GLORIA release 060 SUT**, already parsed as ``db``.
Native labels vary across databases; inspect yours with
``db.get_index("Activity", flat=True)``.

.. code-block:: python

    db.get_concordances(
        set="Activity", classification="NACE Rev. 2.1", item="Growing wheat",
    )
    # {'Growing wheat': ['01.11']}

    db.get_concordances(
        set="Activity", classification="NACE Rev. 2.1",
        item=["Growing wheat", "Growing rice"],
    )
    # {'Growing wheat': ['01.11'], 'Growing rice': ['01.12']}

    all_activity_links = db.get_concordances(
        set="Activity", classification="NACE Rev. 2.1",
    )

``item`` filters native labels, not target codes. Omitting it includes the full
current set. Repeated labels appear once; dictionary order follows the request.
A requested label absent from the selected set raises ``WrongInput``.

On an EXIOBASE monetary SUT parsed as ``exio``, query products instead:

.. code-block:: python

    exio.get_concordances(
        set="Commodity", classification="HS 2007", item="Wheat",
    )
    # {'Wheat': ['100110', '100190']}

Regional classifications and IOTs
---------------------------------

Without ``region``, a lookup uses the distinct union of native labels across
regions. This does not mean every label exists in every region. Restrict the
lookup using a region code returned by the model:

.. code-block:: python

    region = db.get_index("Region")[0]
    labels = db.get_index("Activity", region=region)
    regional_links = db.get_concordances(
        set="Activity", classification="NACE Rev. 2.1",
        region=region, item=labels[:2],
    )

This matters for BONSAI, whose regional classifications vary. Requesting an
item absent from the chosen region raises ``WrongInput`` even if another
region contains it.

On an IOT, ``set="Activity"`` or ``set="Commodity"`` is accepted only when
compatible with its native Sector identities. SUT-to-IOT conversions retain
which side became Sector. BONSAI HIOT also has an explicit reference-product/
process association: an Activity query or a NACE target can follow that bridge.
Keys remain the actual HIOT Sector labels; this lookup does not convert the
product table into an industry table.

Read descriptions and evidence
------------------------------

.. code-block:: python

    detail = db.get_concordances(
        set="Activity", classification="NACE Rev. 2.1",
        item="Growing wheat", details=True,
    )["Growing wheat"]

    detail["codes"]                        # ['01.11']
    detail["matches"]["01.11"]["name"]      # Target description.
    detail["matches"]["01.11"]["routes"]    # Steps and source locations.
    detail["sources"]                      # Publisher and source records.
    detail["profile"]                      # Selected native variant.
    detail["as_of"]                        # Packaged metadata snapshot date.

A route records steps, source locations and qualifications, with traversal
direction for composed bridges. Current NACE 2.1 and CPA 2.2 links reproduce
the explorer's reviewed code lists. Other editions use explicit route prefixes
or compose official bridges; composed routes are marked ``partial``. Supplied
broad anchors stay at their supplied level.

Here a **correspondence footprint** is the set of classes linked by the source.
It can include partial overlaps; it does not assert that the entire native
item is exactly partitioned into those classes. Several codes supply no rule
for dividing output or emissions among them. Consult route qualifications
when using those links to interpret economic or environmental results.

Missing links and unavailable queries
-------------------------------------

.. list-table:: Interpret an empty or detailed result
   :header-rows: 1
   :widths: 30 70

   * - Result or ``status``
     - Meaning
   * - ``[]`` in the simple output
     - The current native label has no verified link in this lookup.
       A label absent from the model instead raises ``WrongInput``.
   * - ``"mapped"``
     - At least one route exists; source qualifications still apply.
   * - ``"unverified"``
     - Native identity recognised, but no link to this target.
   * - ``"unknown_native_identity"``
     - No bundled identity recognised; possible after renaming, adding or
       aggregating items.
   * - ``"ambiguous_identity"``
     - The label matches several bundled identities.

Unknown families, unsupported native variants, unavailable target editions and
invalid items or regions raise ``WrongInput``. Inspect
``db.database_profile["concordances"]`` for family support and variant reasons.
Missing links are not filled by fuzzy matching.

To group these codes into sections or divisions, continue with
:doc:`../transformations/classification_aggregation`.
