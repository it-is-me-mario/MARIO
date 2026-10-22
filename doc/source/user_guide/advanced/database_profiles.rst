Database profiles and concordances
==================================

Database-specific metadata live together in ``mario/database_profiles``.
The registry identifies each family and connects its native GHG definitions,
parser compute presets and packaged classification concordances.

Inspect a family without downloading or parsing a database::

    import mario

    profiles = mario.get_database_profile()         # Every registered family.
    gloria = mario.get_database_profile("gloria")
    gloria["ghg"]["profiles"]
    gloria["compute"]["parser_presets"]
    gloria["concordances"]["profiles"]

On a parsed database, the same view also includes its metadata, selected GHG
profile and native-set concordance availability::

    profile = db.database_profile
    profile["database"]
    profile["ghg"]["selected_profile"]
    profile["concordances"]["available"]

The returned dictionaries are independent copies. Editing them does not change
registries, settings or model data.

What the three sections mean
----------------------------

* ``ghg``: native account labels, factors, output units and matching rules used
  by ``calc_ghg``. The API defaults are AR6/GWP100; already characterised source
  CO2eq rows retain their original basis. BONSAI's native AR6 profile and the
  explorer's AR5 comparison recipe are explicitly distinct.
* ``compute``: preferences selected by parser, including optional solver
  fallback. These are not current or persisted settings. Use
  ``mario.download_settings()["compute"]`` to inspect the active session.
* ``concordances``: editions, native variants, source URLs, snapshot date and
  actual availability. Support for a classification does not guarantee that
  every native item has a verified link. Unsupported variants retain a reason.

Retrieve item concordances
--------------------------

.. code-block:: python

    db.available_concordances
    db.get_concordances(
        set="Activity", classification="NACE Rev. 2.1",
        item=["Growing wheat", "Growing rice"],
    )
    # {'Growing wheat': ['01.11'], 'Growing rice': ['01.12']}

``item`` accepts one label, several labels, or no filter. ``region=...`` limits
the lookup to actual regional members; otherwise it uses the distinct union.
``details=True`` adds code descriptions, sources, locations, route direction
and qualifications. IOTs use ``Sector``; transformations retain whether its
identities came from Activity or Commodity. BONSAI HIOT also supplies an explicit
reference-product/process association for the activity lookup.

Targets include NACE, ISIC, CPA, CPC and the supplied EXIOBASE product / HS 2007
table, with explicit editions. No industry-to-product memberships are fabricated.
Current NACE 2.1 and CPA 2.2 results match the explorer's reviewed footprints;
other editions follow explicit prefixes or qualified official bridges. Broad
anchors remain broad, and pending proposals remain outside the mapping.
Empty lists mean unverified; **concordance links are not allocation weights**.
See :meth:`~mario.CoreModel.get_concordances` for the complete contract.

Prepare a predefined aggregation
--------------------------------

The same metadata can propose section, division (2 digits), group (3 digits)
or class (4 digits) aggregations. Packaged official hierarchies currently cover
NACE Rev. 2.1 and CPA 2.2; CPA also supports categories and subcategories::

    db.available_aggregations
    mapping = db.get_aggregation(
        set="Activity", classification="NACE Rev. 2.1", level="2 digits",
    )
    mapping["Activity"]                         # Review the proposed targets.
    mapping["Activity"].attrs["concordance"]    # Sources and unresolved items.
    aggregated = db.aggregate(mapping, levels=list(mapping), inplace=False)

An item whose linked codes all belong to one target group is assigned once.
Items crossing groups, lacking verified links or already coarser than the
requested level retain their original labels. ``unresolved="raise"`` instead
requires a unique assignment for every item. Regional memberships remain
regional, and no item is duplicated, split or dropped. Target labels include
the edition, for example ``NACE Rev. 2.1:A``.

These are reviewable groupings of qualified correspondence footprints. Consult
``get_concordances(details=True)`` for the underlying source qualifications;
an unweighted correspondence does not certify complete native containment.
Preparing a mapping leaves the database unchanged; applying it uses the
existing aggregation API and its unit and regional validation.

Maintaining the metadata
------------------------

``registry.py`` owns database identities and references to the three metadata
domains. ``ghg.py``, ``compute.py`` and ``concordances.py`` hold their definitions;
``data/concordances`` contains the compressed, installable explorer snapshots.
Regenerate the latter with ``doc/scripts/build_runtime_concordances.py`` after
updating the canonical classification sources. No IO observations are packaged.

Existing ``mario.ops.ghg.GHG_PROFILES``, ``register_ghg_profile`` and
``mario.settings.parser_profiles.PARSER_COMPUTE_PROFILES`` remain compatible:
they use the same live dictionaries, not duplicate configurations.
