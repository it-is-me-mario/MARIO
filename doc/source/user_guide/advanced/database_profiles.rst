Database profiles
=================

A database profile describes the GHG accounts, parser compute preferences and
classification correspondences bundled for one database family. Inspect it
before importing a database, or identify the definitions applicable to an
existing ``db``.

Use :doc:`mario.get_database_profile() <../../api_document/mario.get_database_profile>` to inspect a family and
:doc:`db.database_profile <../../api_document/mario.CoreModel.database_profile>` to inspect a parsed model.

.. list-table:: Choose the operation
   :header-rows: 1
   :widths: 32 40 28

   * - You want to
     - Use
     - Result
   * - Inspect metadata for a family
     - :doc:`mario.get_database_profile() <../../api_document/mario.get_database_profile>` with ``"gloria"``
     - Metadata dictionary
   * - Inspect metadata for a parsed model
     - :doc:`db.database_profile <../../api_document/mario.CoreModel.database_profile>`
     - Metadata dictionary with model availability
   * - Find classification codes for native items
     - :doc:`db.get_concordances() <../inspection/concordances>`
     - ``{native_item: [codes]}``
   * - Prepare NACE sections or divisions
     - :doc:`db.get_aggregation() <../transformations/classification_aggregation>`
     - Mapping ready for ``db.aggregate``

These inspection and preparation methods leave matrices and settings unchanged.
``db.aggregate(...)`` is the separate operation that applies an aggregation.

Inspect a family before parsing
-------------------------------

Call :doc:`mario.get_database_profile() <../../api_document/mario.get_database_profile>` with a family name, or omit the argument
to list all registered families:

.. code-block:: python

    import mario

    families = mario.get_database_profile()
    list(families)  # Registered database family identifiers.

    gloria = mario.get_database_profile("gloria")
    gloria["ghg"]["profiles"]["gloria"]
    gloria["compute"]["parser_presets"]["gloria"]
    gloria["concordances"]["classifications"]

No source database is downloaded or parsed. This view lists all bundled
variants: for example, ``"exiobase"`` includes monetary and hybrid definitions.
It does not select a variant or check the accounts in a particular file.

Inspect a parsed database
-------------------------

For a model already imported with a MARIO parser, read
:doc:`db.database_profile <../../api_document/mario.CoreModel.database_profile>`. It returns the same dictionary as
calling :doc:`mario.get_database_profile() <../../api_document/mario.get_database_profile>` with that model:

.. code-block:: python

    profile = db.database_profile
    profile["database"]                         # Source, year, table, version.
    profile["ghg"]["selected_profile"]          # Autodetected GHG profile ID.
    profile["concordances"]["available"]        # Editions by current native set.
    profile["concordances"]["unavailable_reason"]

MARIO uses source metadata and native identities to select a mapped variant.
The bundled GLORIA concordances, for example, cover release 060. A model that
declares release 057 has no available concordance for that variant; the reason
explains the mismatch. Unknown database families raise ``WrongInput``.

``concordances["supported"]`` describes the **family**. It can be ``True`` even
when the current model's variant is unsupported. Check ``available`` and
``unavailable_reason`` for the model itself. In a family-only query, model
metadata, selected GHG profile and native-set availability are ``None``.

Read the three metadata sections
--------------------------------

GHG definitions
~~~~~~~~~~~~~~~

``ghg["profiles"]`` holds native account labels, characterisation factors,
matching rules and units used by :meth:`~mario.Database.calc_ghg`.
``selected_profile`` is autodetected from the model's source/name. It does not
record the last explicit ``calc_ghg(profile=...)`` call or verify that every
configured gas account is present.

The API defaults are AR6/GWP100. Already characterised source CO2eq rows,
such as those used by ADB and EMERGING, retain their original characterisation
when multiplied by their scalar factor. Changing ``ipcc_report`` does not
recharacterise those source totals. BONSAI's default AR6 profile also differs
from the documentation explorer's AR5 comparison recipe.
See :doc:`../analysis/greenhouse_gases` for calculations and
:doc:`../../api_document/mario.Database.calc_ghg` for the BONSAI-specific factor.

Compute preferences
~~~~~~~~~~~~~~~~~~~

``compute["parser_presets"]`` describes preferences selected by a successful
parser. BONSAI, GLORIA and EMERGING prefer solve/direct with optional UMFPACK
and a SciPy fallback when UMFPACK cannot be imported. The actual active solver
can therefore differ from the preferred solver in the profile.

Inspect the current session separately:

.. code-block:: python

    preferred = mario.get_database_profile("gloria")["compute"]["parser_presets"]
    active = mario.download_settings()["compute"]

An empty ``parser_presets`` dictionary means that the parser leaves active
settings unchanged. It does not mean the model has no computation settings.
Settings apply to all databases in the current Python process. Apply manual
overrides after parsing; see :doc:`compute_settings` for options and persistence.

Concordance metadata
~~~~~~~~~~~~~~~~~~~~

``concordances`` lists native variants, target editions, source URLs and the
snapshot date (``as_of``). The date describes the packaged classification
metadata, not the economic database's reference year or the latest query.
``profiles`` records bundled releases and native variants; ``classifications``
also lists the available hierarchy aggregation levels.

A listed edition has a supported correspondence route. Coverage can still be
incomplete for individual items. See :doc:`../inspection/concordances` to read
code lists, missing links and source qualifications, then
:doc:`../transformations/classification_aggregation` to prepare an aggregation.

Availability is independent across sections. EORA has a built-in GHG profile
and no bundled native concordance; FIGARO has bundled concordances and no
built-in GHG profile.

Copies and updates
------------------

Returned dictionaries are independent copies. Editing ``profile["compute"]``
does not configure the solver; use the computation settings API. Editing
``profile["ghg"]`` does not register a profile; use
``mario.ops.ghg.register_ghg_profile`` or pass an explicit ``gwp`` mapping.

Definitions are packaged with MARIO and queried offline. Updating source files
outside the package does not refresh the bundled snapshot automatically. The
legacy GHG and parser-profile import paths remain compatible and refer to the
same live registries as ``mario.database_profiles``.
