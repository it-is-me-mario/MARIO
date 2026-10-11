.. raw:: html

   <link rel="stylesheet" href="../../_static/economy-browser.css">
   <nav class="explorer-tabs">
     <a href="browsers.html">Browsers</a>
     <a href="scope.html" aria-current="page">Database scopes</a>
     <a href="analyses.html">Analyses</a>
   </nav>

Database scopes
===============

Explore the geographical and sectoral scope of each database and download its complete
sets: sectors, activities, commodities, satellite accounts and more.

.. container:: explorer-feedback

   Help us improve the explorer: everyone is welcome to report errors in the data,
   concordances or interface on `GitHub Issues <https://github.com/it-is-me-mario/MARIO/issues>`_.

.. _classification-sizes:

Classification sizes
--------------------

Compare MRIO classification sizes, including databases without a MARIO parser
when their coverage is verified from the source. Markers identify database
families; colours indicate whether environmental data are available. Regions
include both individual and aggregate regions. For SUTs,
activities and commodities are counted separately and identified in the hover.
Readings with the same counts are grouped, regardless of year or release.

.. raw:: html

   <link rel="stylesheet" href="../../_static/database-scope.css">
   <div class="database-scope-chart" data-database-scope data-root="../../" aria-busy="true">
     <p>Loading database classifications…</p>
   </div>
   <script src="../../_static/database-scope.js" defer></script>

Colours describe available environmental data. For MARIO readings this means
loaded accounts; for source-only profiles it follows the documented data product.
The hover identifies source-only coverage and parser availability. A database may
offer separate extensions that have not been loaded here. National models are omitted.
Hover for versions and classifications; use the legend to isolate a family or
zoom to separate nearby points.

.. _database-coverage:

Geographical coverage
---------------------

Find the databases that represent a country individually, or explore a database's
geographic coverage by version and year. In global MRIOs, countries without an
individual region are included in aggregate regions.

.. mario-geographic-coverage::

Source-only databases, such as Open CEDA and standard GTAP, link to the publisher
rather than a parsing guide. GTAP Power links to its MARIO parsing guide. Both
GTAP variants contribute public scope and classification metadata; their
licensed numerical indicators are unavailable in the public browser.

Download available set lists in :ref:`Downloadable material <database-set-downloads>`.

.. raw:: html

   <details class="coverage-methods"><summary>About the geography</summary>
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

Choose **Activities** for **NACE Rev. 2.1**, or **Commodities** for **CPA 2.2**.
The heatmap keeps every reference class or product subcategory as a separate row;
section letters provide the overview. Narrow the classification or click a cell
to inspect native categories, intermediate mappings and their sources. Qualified
correspondences describe possible scope; they do not provide allocation weights.

.. raw:: html

   <link rel="stylesheet" href="../../_static/sectoral-scope.css">
   <div class="sectoral-scope" data-sectoral-scope data-root="../../" aria-busy="true">
     <p>Loading classification concordances…</p>
   </div>
   <script src="../../_static/sectoral-model.js?v=45aa5a56d92d" defer></script>
   <script src="../../_static/sectoral-scope.js?v=4a9f69126cda" defer></script>

:download:`Download the complete reviewed concordances · Excel <../../_static/data/economy/classification-concordances.xlsx>`
or read the :download:`concordance audit <../../_static/data/economy/classification-audit.json>`.
