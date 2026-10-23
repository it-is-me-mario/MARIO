Database comparisons: parsed profiles and original set downloads
===============================================================

This workflow produces release profiles and downloadable original-set lists
from successful local parsing runs. Counts come from the actual reading, rather
than notebook output snapshots, headline figures or declared coverage tables.

One data source, three documentation locations
---------------------------------------------

``source/_static/data/database_profiles.json`` is the committed summary catalogue.
The ``mario_database_profiles`` Sphinx extension reads it to render:

* compact version and region/economic-dimension counts in the parser cards;
* a coverage panel after the import section of each matching source guide;
* the geographic explorer on ``resources/database_coverage`` (displayed as
  Database comparisons; the URL stays compatible), with the compact Excel
  catalogue on ``resources/material`` (Downloadable material).

Counts appear only for parsed profiles. Parser cards and walkthrough panels show
Region, Sector or Activity/Commodity, grouping repeated years while preserving
distinct economic dimensions such as EXIOBASE monetary ixi/pxp. Every workbook
retains its release/year/table context and all original sets, including Satellite
account, Factor of production and Consumption category. A family may have multiple
profiles. Sphinx does not parse databases, make API calls or generate Excel files.

Notebook examples are the parsing recipes
---------------------------------------

Run from the repository root::

    python doc/scripts/database_catalogue.py --prepare
    python doc/scripts/database_catalogue.py --plan

``--prepare`` reads the parser calls in the documentation notebooks using Python's
AST, records their literal options and a call fingerprint, and refreshes
``doc/database_catalogue.recipes.json``. It preserves existing parsed profiles.
It never executes a notebook or parser. An example requiring an in-memory object
(the pymrio bridge) is registered but cannot be run from a path-only JSON job.

``--plan`` lists the recipes while there is no local configuration. Once a local
configuration exists it checks inputs, notebook fingerprints and basic options
without reading a database. Changed examples must be reviewed and the recipes
regenerated. Recipes keep original extension selections: prepare separate jobs
for all available extensions versus a subset, or other table variants.

Inputs remain local
-------------------

Copy ``doc/database_catalogue.example.json`` to
``doc/database_catalogue.local.json`` (gitignored), then supply the paths. Create
one job per release, year, table format, system and extension selection. Use an
explicit label containing that identity, a unique id, and ``expected_table``.
Multiple jobs can reuse a recipe and override its literal parameters. Override
``year``, ``version``, ``system`` etc. to match the actual local release; notebook
example years are not an inventory of the files available on a user's machine.

For API examples, supply a local snapshot path where the parser supports it, or
explicitly opt in with ``--allow-network``. A local run rejects unresolved
``/path/to/`` placeholders and nonexistent input paths, sets supported download
options to false, and forces ``calc_all=False``. It does not execute downloader
cells, plots, transformations or footprint calculations from the notebooks.

Run and inspect the private outputs::

    python doc/scripts/database_catalogue.py --plan --config doc/database_catalogue.local.json
    python doc/scripts/database_catalogue.py --run --config doc/database_catalogue.local.json

Jobs are sequential so large MRIO tables do not coexist in memory. Results live
under the ignored ``Output/database_catalogue/`` directory. ``run-report.json``
records success/failure and diagnostic tracebacks; a failed job does not stop the
remaining jobs. Failures must be investigated in the corresponding walkthrough,
with any fixes made to the notebook/parser before rerunning. Actual local paths
remain in the local config and private diagnostics, not in published metadata.

Each successful job produces ``profile.json`` and ``sets.xlsx``. Their contents:

* Profile: source/release/year/table, parser, notebook/cell/fingerprint, effective
  options, parse time, counts and definitions of what was loaded;
* original sets, one sheet for each set present in the model;
* Region items and Regional counts: associations observed on actual axes, never
  an assumed Cartesian product of all regions and all economic labels;
* Native axes: full original tuples, including regional or sector-specific
  satellite/factor dimensions;
* Units: original unit coordinates and values.

No matrix values are exported. Stored axis metadata are read directly without
copying matrices or triggering derived calculations. Counts of economic labels
are global distinct labels, with the regional counts alongside for heterogeneous
tables. Empty MARIO placeholders are retained and flagged in the workbook, but
excluded from counts of loaded satellite/factor rows. An empty satellite set means no satellite rows were loaded with those
options; it does not prove the source distributes no extensions.

Native regions are not automatically countries. ``database_geography.py`` uses
the committed country registry and explicit source-specific aliases, including
ADB abbreviations and EORA's SDS/SUD codes. EORA ANT/USR remain historical groups,
with no inferred current membership. EXIOBASE 3.11.2 aggregate mappings use
MARIO's bundled region definitions after checking the actual region set,
identifier validity, uniqueness and absence of overlap with individual regions.
The hybrid region set differs and does not inherit that monetary concordance.
Other aggregate memberships and official economic concordances remain separate.
No NACE/CN/EBOPS equivalence is inferred from counts or name similarity.

The geographic explorer offers map and country-list views, an individual-region
country lookup, geographic Version selection and a separate year filter. Versions
with exactly the same native region set share one geographic option even when
economic systems or reference years differ. In the global view the continuous
colorscale counts each database once, using individual regions only. Selecting a
database shows individual and identified aggregate regions as separate categories;
its native aggregate names are also listed when country membership is unavailable.
The country list shows every country with internal scrolling. Lookup names
link to the parsing walkthrough for the selected version. The map has zoom,
reset and drag controls, with its source credit fixed inside the bottom-right
corner. Keyboard and touch controls are also supported.

The compact download table is on Downloadable material. Versions with matching
geography share a heading; economic variants remain distinct unless their native
labels and regional economic associations also match. Identical counts alone
are insufficient. All Excel links retain their reading and extension selection.

``generate_country_map.py`` regenerates the local Natural Earth 1:110m asset,
recording its source URL/hash and the country registry version. Shared boundaries
are deduplicated into one mesh and drawn once at a fixed screen width. Browser rendering
uses local assets only, with country selectors for small territories absent from
the coarse map. Build Sphinx never downloads this asset or reads source datasets.

Add successful profiles to the documentation::

    python doc/scripts/database_catalogue.py --publish
    python -m sphinx -b html doc/source doc/build/html

``--publish`` copies only successes from the latest run to
``_static/data/database_profiles/`` and updates the shared summary catalogue.
Unattempted release profiles remain. An attempted failed refresh removes the
previous public profile/download for that id, avoiding stale counts presented
as the result of a successful rereading. Private error logs are never published.
These are documentation assets, not a deployment command.

Notebook execution and output fixes
-----------------------------------

After validating each parser call, use the existing
``doc/scripts/resolve_notebooks.py`` workflow to rerun the full walkthrough with
the same local inputs. It executes an in-memory copy and copies outputs back while
keeping placeholder paths in public notebook code. The catalogue run is focused
on parsing and sets; it does not certify every later cell in a walkthrough.

Validation during scaffolding uses only packaged IOT/SUT fixtures and temporary
Excel exports. Fixture profiles must never enter the public real-database
catalogue. Once real inputs are supplied, reconcile workbook labels/counts with
MARIO's indexes and original source nomenclatures, and inspect regional variations
and the full selected extension lists before treating a profile as complete.


OneDrive inputs
---------------

Read one selected database/year at a time. Opening a dataless input can trigger
OneDrive's download. After the parser has returned and file handles are closed,
use Finder's OneDrive **Free Up Space** action on that reading's files/folder.
Confirm dataless status and zero allocated blocks before proceeding to the next
large input. This is cache eviction, not deletion of the cloud file. Do not use
unlink, move-to-bin or general directory removal for source datasets. Temporary
ZIP extraction is managed by the parser's temporary-directory context.
Private snapshots and Excel exports suffice for later metadata/geography
refinements; regenerating them does not require downloading source data again.

First real batch (2026-10-08): ADB 74-economy workbook for 2024, EXIOBASE 3.11.2
2024 ixi/pxp, EXIOBASE Hybrid 3.3.18 SUT 2011 (all extensions), and the supplied
Eora26 2017 basic-price bundle. ADB's empty satellite placeholder is flagged as
not loaded. No matching 2024 emission workbook was supplied. Full walkthrough
execution across other versions/years was not part of this batch.

Second real batch (2026-10-08): OECD ICIO Extended 2022 (80 countries + RoW,
50 sectors), FIGARO 2023 product-by-product (49 countries + RoW, 64 sectors;
existing normalized API cache), and EMERGING 2.2 / 2023 with the matching seven
CO2 fuel accounts (245 native regions, 133 sectors). OECD's parser collapses
CN1/CN2 and MX1/MX2 to country totals. The inventories describe MARIO's parsed
sets. EMERGING's ANT and SER retain historical grouping labels; SER is explicitly
Serbia/Montenegro in the author nomenclature, not automatically current Serbia.
The author workbook has exactly the same 245 native region codes as this reading.
TMP maps to TLS following UNSD M49's documented name/code change. Mapping sources
are recorded in JSON and the workbook Profile sheet. Original set labels remain
unchanged. These three source readings were returned to online-only after parsing.
The map palette and aggregate patterns now scale to the number of parsed families.

Geography UI revision (2026-10-08): the header keeps menu links present until
native activation and ignores focusout with no focus destination. The map uses
a deduplicated shared border mesh, a continuous scale for database counts, and
individual/aggregate categories for a single database. Geographic Version groups
ignore economic-system/year differences; the separate year filter only offers
parsed inventory years. Downloadable material now hosts the full set catalogue.

The Hybrid 3.3.18 reading retains five native RoW regions. Its saved native axes
have 48 regions without TW, while the published classification workbook lists
49 with TW. The parser reads these CSV axes directly. Aggregate memberships are
therefore still awaiting a reading-specific concordance; they are not borrowed
from the monetary profile. The model's aggregate names remain visible in the UI.
