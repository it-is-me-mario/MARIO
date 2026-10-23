:page-type: Guide
:summary: Inspect the GHG definitions, compute preferences and classifications packaged for a source.

Database profiles
=================

.. container:: mario-recipe

   .. code-block:: python

      import mario

      profile = mario.get_database_profile("gloria")
      profile.keys()

   .. container:: mario-result

      **Result** · An offline metadata dictionary. No database files are
      downloaded or parsed, and no settings are changed.

Family and model profiles
-------------------------

.. mario-cards::
   :columns: 2

   .. mario-card:: Before importing
      :icon: parsers

      :doc:`mario.get_database_profile() <../../api_document/mario.get_database_profile>`
      with a family name shows its bundled variants. Omit the name to list families.

   .. mario-card:: After importing
      :icon: table-search

      :doc:`db.database_profile <../../api_document/mario.CoreModel.database_profile>`
      adds the current model's metadata, selected GHG profile and available
      classifications.

Profile contents
----------------

.. list-table::
   :header-rows: 1
   :widths: 24 40 36

   * - Section
     - Contains
     - Next action
   * - ``ghg``
     - Native accounts, factors and profile selection
     - :doc:`Calculate GHG <../analysis/greenhouse_gases>`
   * - ``compute``
     - Parser preferences for numerical calculations
     - :doc:`Configure calculations <compute_settings>`
   * - ``concordances``
     - Variants, target editions, sources and hierarchy levels
     - :doc:`db.get_concordances() <../inspection/concordances>` or
       :doc:`db.get_aggregation() <../transformations/classification_aggregation>`

**Family support is not model availability.** A family can have concordances
while the imported release has none. On a parsed model, inspect:

.. code-block:: python

   profile = db.database_profile
   profile["concordances"]["available"]
   profile["concordances"]["unavailable_reason"]

.. mario-details:: GHG profile selection and existing CO2eq totals

   ``ghg["selected_profile"]`` follows source/name metadata. It does not check
   that all configured gas accounts exist, or record an explicit override
   made in a previous ``calc_ghg(profile=...)`` call.

   API defaults are AR6/GWP100. Already characterized CO2eq totals keep their
   original factors; selecting another report does not reconstruct their gases.
   BONSAI's default AR6 recipe also differs from the explorer's AR5 comparison.

.. mario-details:: Preferred solver versus active session settings

   ``compute["parser_presets"]`` describes a parser's preferred settings.
   The current configuration is ``mario.download_settings()["compute"]``.

   BONSAI, GLORIA and EMERGING prefer solve/direct with optional UMFPACK and
   a SciPy fallback. An empty preset leaves the session unchanged.
   Apply manual overrides after parsing.

.. mario-details:: Versions, provenance and copies

   Definitions are packaged with MARIO. ``as_of`` describes the classification
   metadata snapshot, not the economic reference year or a fresh online query.
   Available editions can still have incomplete coverage at item level.

   Returned dictionaries are independent copies. Editing them does not change
   settings, register GHG profiles or update the packaged concordances.
   Availability is independent across sections: a source may support GHG
   characterization but have no bundled classification mapping, or vice versa.
