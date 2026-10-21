Benchmark documentation assets
==============================

The Database explorer pages (Classifications, Browser and Analyses) embed committed snapshots
and HTML fragments generated from local data.
The Sphinx build does not run a parser, query nxbase, or depend on a neighbouring
checkout of the eNextGen site or paper repository.

Regenerate the fragments from the root of the MARIO repository::

    python doc/scripts/generate_benchmark_assets.py

The script also refreshes the geographic catalogue profiles from
``doc/source/_static/data/parser_coverage.json``. These are declared catalogue
entries, not verified region sets from parsed tables. Equal lists across years
are coalesced; release versions and table formats remain separate. No sector,
activity, commodity or satellite count is inferred from the catalogue.

Electricity data and chart drawing code are adapted from
``eNextHub/electricity-carbon-footprint``, ``blogpost/``:

- ``query_nxbase.py`` / ``data/figure2.json``: country comparison (699 observations).
- ``query_figure1.py`` / ``data/figure1.json``: technology comparison (3,582 observations).
- ``charts/figure1.template.html`` and ``charts/figure2.template.html``: SVG charts,
  filters, statistics, fullscreen and raster export.

Reference: Citterio, C., Golinucci, N., Rinaldi, L., Rocco, M.V. (2026),
Carbon intensity of electricity: a systematic methodological and quantitative
review, Journal of Industrial Ecology, https://doi.org/10.1007/s44498-026-00148-3.
Blogpost: https://enextgen.it/en/analyses/electricity-carbon-footprint/.
Source code: https://github.com/eNextHub/electricity-carbon-footprint/tree/enextgen_blogpost.

The author-created comparison figures and pipeline are attributed under
CC BY 4.0. Third-party values remain subject to their source-specific terms;
the local files contain the comparison snapshot, not full source databases.
The source repository and blogpost document redistribution limits.

This is the locally available blogpost snapshot imported on 2026-10-08. It
includes nxsut 3.0, and is not an exact reconstruction of the article's original
figures. Country data retain source, comparison year, scope, method and geography.
The technology snapshot retains source, technology, scope and value but omits
country and year per observation. Its caption therefore does not claim a shared
EU27+US or country-year sample. Pooled boxplots do not balance sources by their
number of observations or weight values by generation.

Changes to the chart code for MARIO: theme variables and logo, enabled country
selector, filtered-observation CSV exports, consistent filtering of table
columns and country medians when sources are hidden, local snapshot wording,
and technology grouping labelled "Other technologies" rather than treating
biomass and waste as uniformly low-carbon.

When updating the electricity snapshots, regenerate them in the analysis
repository, copy them to ``doc/source/_static/data/benchmarks/``, update the
method notes and this provenance record, and rerun the asset generator. Retain
source/version/year/units where available. Review any changes to source terms.

BONSAI supplement (2026-10-21)
-----------------------------

``build_bonsai_explorer.py`` publishes the native b2 HIOT classification,
original-set workbook, country-specific memberships, producer GHG totals and
electricity-generation observations from a frozen local audit. The original
699 country-comparison observations remain unchanged: BONSAI appears only in
the technology comparison, as requested. The technology supplement contains
588 observations (294 direct and 294 life-cycle), reference year 2016, with
the source update timestamp displayed separately: 21 October 2026, Europe/Rome.

The audit retains the 53,750-node HIOT, elementary flows including iLUC,
BONSAI LCIA workbook, input SHA-256 hashes and cached MARIO multipliers. The
same-input dimensional and normalized solves agree to a relative L2 error of
5.83e-16 for GWP100, without partial results. The exporter verifies the hashes,
characterisation factors, cached multiplier alignment, production units and
product/activity pairings. It uses actual native generation products, not the
``M_electricity`` market footprint. The reviewed mapping is recorded alongside
each observation; notably POWP is Oil and POWO is Tide and wave. Individual
countries contribute available technologies; Global and RoW are excluded.

Regenerate from local frozen inputs and the supplied native descriptions::

    python doc/scripts/build_bonsai_explorer.py /path/to/bonsai_equivalence_20261021 --classification /path/to/classification.csv
    python doc/scripts/build_extension_scope.py
    python doc/scripts/generate_benchmark_assets.py

The source folder label ``20260615`` is not an immutable release or the
reference year. Frozen HIOT inputs are dated 2026-10-21 14:47:27 and elementary
flows 15:06:22 Europe/Rome; the LCIA workbook retains its own timestamp/hash.
Only metadata and derived indicators are committed, never source matrices.
The additional results retain BONSAI attribution and are not part of the
article/blogpost snapshot. Data-specific reuse terms are recorded as unclassified;
the repository's MIT software licence is not used as a data licence.

The classification overview uses 355 sectors from the native Global block,
while its hover explains the 355–1,332 regional range. The native union of
1,707 distinct sector labels and all regional memberships remain in the set
download. Fine NACE/CPA correspondences are unverified, so those cells remain
unclassified. GDP and value added are unavailable, rather than published as
zeros from MARIO placeholders. The indicator snapshot provides producer GHG
totals with BONSAI GWP100 (AR6 plus Accelerated CO2), with no separate final-demand
emission observations; it does not claim an identical basis to the AR5 reference.

Next data step: read the releases provided by Lorenzo through MARIO, export
their original sets and units into per-release Excel workbooks, and replace
the catalogue-only view with verified geographic and classification profiles.
Country coverage, aggregate membership and model-region counts must remain
distinct; heterogeneous regional classifications need region-to-item records.


Parsed release profiles are managed separately by
``doc/scripts/database_catalogue.py``. See ``database_catalogue.rst`` for the
notebook-derived recipe registry, local inputs, original-set Excel export and
shared counts in parser cards/walkthroughs. The geographic catalogue above
remains a folded reference view, separate from parsed release counts.


The geographic view uses ``geography-concordances.json`` to distinguish global
MRIO coverage from national BEA/USEEIO scope. Exact EXIOBASE memberships were
reviewed against the supplied ``region-classification.xlsx``, sheet
``Classification (extended)`` (250 reporting identifiers, reviewed 2026-10-09).
Apply this concordance only when the complete native region set matches; Hybrid
omits Taiwan as an individual region and therefore retains only the global
coverage fallback until its own exact membership is documented. Do not infer
which specific RoW contains a country from a global flag. The set downloads
retain their original extraction metadata and native sets.

Natural Earth's SOL geometry is assigned to the SOM reporting unit. PSE is
retained independently. This is a database identifier concordance, not a list of
sovereign states. Both map widgets draw selection outlines above their border
mesh, including every polygon belonging to the selected reporting identifier.
