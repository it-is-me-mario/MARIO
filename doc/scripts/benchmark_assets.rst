Benchmark documentation assets
==============================

The Database comparisons and Analyses & benchmarks pages embed committed HTML
fragments generated from local data.
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
