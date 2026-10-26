.. raw:: html

   <nav class="explorer-tabs" aria-label="Database explorer">
     <a href="scope.html" aria-current="page">Classifications</a>
     <a href="compare.html">Compare databases</a>
     <a href="analyses.html">Analyses</a>
   </nav>

.. _database-scopes:

Classifications
===============

.. container:: explorer-intro

   Compare regional and sectoral detail across MRIO databases. The list of databases is not exhaustive.

   FIGARO inventories here describe parsed IOT/SUT readings. Local NAM input
   support is documented in :doc:`the FIGARO guide
   </notebooks/parsers/figaro/walkthrough_figaro>`; NAM reporting economies and
   import-origin descriptors are not additional MRIO coverage in these charts.

   .. container:: explorer-feedback

      Found an error, or know a database we should add? Tell us on `GitHub Issues <https://github.com/it-is-me-mario/MARIO/issues>`_.

.. raw:: html

   <div class="explorer-controls" data-scope-controls hidden>
     <nav class="scope-views" data-scope-tabs role="tablist" aria-label="Database scope views">
       <a href="#overview" id="scope-tab-overview" role="tab" aria-controls="overview">
         <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 3v17h17"/><circle cx="9" cy="15" r="1.5"/><circle cx="13" cy="9" r="1.5"/><circle cx="19" cy="5" r="1.5"/></svg>
         <span>Overview</span>
       </a>
       <a href="#geographical-coverage" id="scope-tab-geography" role="tab" aria-controls="geographical-coverage">
         <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3ZM9 3v15M15 6v15"/></svg>
         <span>Geographical scope</span>
       </a>
       <a href="#sectoral-coverage" id="scope-tab-sectors" role="tab" aria-controls="sectoral-coverage">
         <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 10h18M3 15h18M9 4v16M15 4v16"/></svg>
         <span>Sectoral scope</span>
       </a>
       <a href="#environmental-extensions" id="scope-tab-extensions" role="tab" aria-controls="environmental-extensions">
         <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19c9 0 14-5 14-14-9 0-14 5-14 14Zm0 0 8-8"/></svg>
         <span>Extensions</span>
       </a>
     </nav>
   </div>

.. _database-overview:

Overview
--------

Compare region and sector counts. Hover for versions, environmental extensions and licences.

.. raw:: html

   <div class="database-scope-chart" data-database-scope data-root="../../" aria-busy="true">
     <p>Loading database classifications…</p>
   </div>

.. raw:: html

   <p class="scope-license-note"><strong>Non-commercial:</strong> reuse is permitted for non-commercial purposes under the source licence.
   <strong>Restricted:</strong> access or reuse requires specific permission or a dedicated licence, including for some non-commercial uses.</p>

   <details class="coverage-methods"><summary>About the scope chart</summary>
   <p>Markers identify database families; fills indicate environmental data.
   No outline means open use; a dashed outline means non-commercial terms;
   a solid outline means proprietary/restricted access.
   Open use still requires the source attribution and any ShareAlike terms.</p>
   <p>Identical classifications can span releases with different licences. The outline
   shows the most restrictive included terms; hover for release-specific licence links.
   An unclassified licence never counts as open. Parser and indicator availability
   do not determine the licence category. CEDA denotes the proprietary product;
   its set inventory comes from Open CEDA, whose metadata licence is shown separately.</p>
   <p>Regions include individual and aggregate regions. SUT activities and commodities
   are counted separately. Identical counts share a marker across years and releases.</p>
   <p>For parsed databases, environmental data means loaded accounts. Source-only
   profiles follow the documented product and identify parser availability in the hover.
   Separate extensions may not be loaded here. National models are omitted.</p></details>

.. _database-coverage:

Geographical coverage
---------------------

Choose a country or database to explore individual and aggregate regions.

.. mario-geographic-coverage::

:ref:`Download native sets · Excel <database-set-downloads>`

.. raw:: html

   <details class="coverage-methods"><summary>About the geography</summary>
   <p>Global MRIOs include countries without individual regions in aggregates.
   Open CEDA and standard GTAP link to their publishers; GTAP Power links to its
   parsing guide. Eora1 and Eora2 provide scope metadata only: Eora1 links to its
   MARIO parsing guide; Eora2 has no parser. Eora1 26 for 2004 exists at source,
   but is not in the locally checked inventory. GTAP also omits numerical indicators.</p>
   <p>Country names identify database reporting units. Natural Earth map units
   are matched to those identifiers; Somaliland is displayed with Somalia,
   and Palestine retains its own entry. A global coverage flag indicates
   aggregate inclusion even when the exact aggregate membership has not yet
   been documented. National models are omitted.</p>
   <p>EXIOBASE country membership follows the supplied <em>region-classification.xlsx</em>,
   sheet <em>Classification (extended)</em>. The mapping is applied only where
   the parsed region set matches the concordance. Sources:
   <a href="https://github.com/EXIOBASE/00-class">EXIOBASE classifications</a> and
   <a href="https://www.naturalearthdata.com/about/disputed-boundaries-policy/">Natural Earth cartographic policy</a>.</p></details>


.. _sectoral-coverage:

Sectoral coverage
-----------------

Compare **Activities** against **NACE Rev. 2.1**, or **Commodities** against **CPA 2.2**.
Click a cell for native categories and mappings.

.. raw:: html

   <link rel="stylesheet" href="../../_static/sectoral-scope.css">
   <div class="sectoral-scope" data-sectoral-scope data-root="../../" aria-busy="true">
     <p>Loading classification concordances…</p>
   </div>
   <script src="../../_static/sectoral-model.js?v=45aa5a56d92d" defer></script>
   <script src="../../_static/sectoral-scope.js?v=4a9f69126cda" defer></script>

:download:`Download concordances · Excel <../../_static/data/economy/classification-concordances.xlsx>`

.. _database-extensions:

Environmental extensions
------------------------

Compare the satellite accounts loaded for each database, grouped by theme. Click a database
for its native accounts. Employment and economic rows supplied as satellite accounts are included.

.. raw:: html

   <div class="extension-scope" data-extension-scope data-root="../../" aria-busy="true">
     <p>Loading satellite accounts…</p>
   </div>


.. toctree::
   :hidden:

   compare
   analyses
   economy_emissions
