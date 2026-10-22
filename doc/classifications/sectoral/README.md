# Reviewed NACE Rev. 2.1 and CPA 2.2 concordances

## Current contract — 2026-10-11

The full references now contain 651 NACE activity classes and 3,354 CPA product
subcategories. The corrected CPA hierarchy has explicit parents; source file
order is not used as a hierarchy. Activity and product paths are separate.
No economic matrices, numerical allocation weights or fuzzy links are exported.

nxbase owns the source sidecars under `data/sets`: GLORIA/OECD activity members,
FIGARO/WIOD activity definitions, public GTAP definitions, the reviewed EXIOBASE
activity layer, the typed commodity graph and separate product-production
exclusion reviews. New resolvers are `reviewed_activity_correspondence.py` and
`commodity_correspondence.py`. All actual native labels, identities, workbook
parents and source locations are validated against the workbook checksum.

The EXIOBASE activity review retains all 163 native identities, the supplied
legacy industry definitions and complete revision tables, with 94 explicit
current activity reviews. Raw milk includes cattle, sheep and goat farming;
sewerage is separate from water supply; contradictory legacy mineral/food and
extraterritorial/personal-service links are excluded. The EXIOBASE 2 legacy
workbook was supplied locally. Its checksum, original filename and source cells
are retained; the related release-record URL is not a verified public download
URL for that particular legacy workbook. Current overrides are editorial, not
publisher-issued NACE 2.1 concordances.

Workbook parent lineage is context, never a member enumeration. Reviewed scopes
can differ from a retained parent. This task does not rewrite nxbase_sets.xlsx,
materialise SQL or change licensed numerical results. Shared Hybrid activities
reuse the reviewed monetary footprint only after exact identity checks.

CPA routes use complete CPA 2002 → 2008 → 2.1 → 2.2 bridges. FIGARO retains
published CPA 2.1 definitions; WIOD product-code interpretation stays qualified.
EPA CEDA/GLORIA commodity bridges remain qualified binary footprints. Separately
typed producer-origin exclusion reviews prune incompatible broad joins, without
creating product links or asserting exactness of every remaining candidate.
Those review scopes must agree with the current independent activity footprint
or the build fails. Hybrid products use the published 200 SUT → 164 IOT product
correspondence, not activity identities. GTAP and Open CEDA appear only in the
Activities view: their sector/industry vocabularies do not establish a second
native Commodity set. Public CPC and EPA product concordances remain intermediate
sources for the activity lookup; no licensed GTAP numerical data are published.

Unverified categories stay in the native inventory. Seven EXIOBASE products lack
CPA 2002 publisher links; three old CPA codes lack historical revision pairs;
GTAP definitions without CPC codes and EMERGING fine CPA links remain unverified.
ADB/OECD industry IOTs do not supply inferred product vocabularies. EORA has no
verified fine current bridge. A null cell never establishes absence.

After any nxbase workbook/sidecar update, regenerate all snapshots and audit:

```bash
python doc/scripts/snapshot_nxbase_activity.py --nxbase /path/to/nxbase
python doc/scripts/snapshot_nxbase_hybrid.py --nxbase /path/to/nxbase
python doc/scripts/snapshot_nxbase_scope.py --nxbase /path/to/nxbase
python doc/scripts/build_sectoral_scope.py --country-output doc/source/_static/data/economy/country-scope.json
python doc/scripts/audit_classification_scope.py
node --max-old-space-size=8192 doc/scripts/build_classification_concordances.mjs
node --test tests/docs/test_sectoral_scope.cjs tests/docs/test_country_scope.cjs tests/docs/test_reviewed_classifications.cjs
```

Source and workbook hashes prevent stale identities. Official structures and
normalized correspondence pairs are versioned; an upstream classification
revision requires refreshing those tables from their cited sources, preserving
source locations and distinguishing published flags from derived degrees.
Never edit compiled browser JSON manually.

The Excel authoring step requires `@oai/artifact-tool` in Node's module resolution
path (provided by the Codex authoring runtime, not a MARIO dependency) and Python
3 for `stream_classification_rows.py`. The full file contains over one million
cells. Artifact Tool authors the workbook layout, native tables and formulas.
The standard-library OOXML serializer extends those tables with all typed rows,
preserving identifiers, styles, widths, panes and formula caches. This avoids the
monolithic exporter, which exhausted an 8 GiB heap in both full-data attempts.

The compiled graph deduplicates `route_steps`. Product `link_defaults` are stored
per native item; `alternative_steps` retains every ordered alternate path, which
the frontend reconstructs lazily. Country focus exposes the same current NACE
and CPA references. In the Excel, Match IDs resolve through Routes to every
intermediate step and its source. `classification-audit.json` and the root
`CONCORDANCE_REVIEW.md` enumerate all checks, qualifications and native gaps.

## BONSAI native HIOT — added 2026-10-22

`bonsai-native-correspondences.json` snapshots classification facts from the
synced BONSAI bundle: the 1,707 distinct regional HIOT reference-product/process
pairs, descriptions, regional memberships, 1,594 detailed native/NACE records,
1,664 revised CPA 2.1 records and explicit product/market correspondences.
All revised CPA codes validate against the official 2.1 structure; 45 records
are absent from CPA 2008. The 88-category NACE/CPA tables are aggregate
definitions, not the limit of BONSAI's native vocabulary.

The heatmap uses the union of observed regional identities. The classification
overview continues to show Global's 355 sectors, with the regional 355–1,332
range. Global consists of markets and cannot stand for the full productive
classification. Market NACE links are qualified producing-sector footprints;
CPA markets follow only supplied product/market links. A broad anchor for a
detailed child stays context unless it has only one official descendant class.
Only direct definitions of a complete native aggregate enumerate its members.
Capital/carrier identities without a source route remain unverified.

`bonsai-current-reviews.json` contains explicit editorial electricity-definition
reviews. These preserve the surviving official revision routes while excluding
incompatible generation classes and storage services. Mixed biomass/waste
retains both generating-source classes. These reviews are separate from
publisher-issued concordances. No exclusive regional partition is asserted.

The country lookup uses the supplied HIOT reference-product/process pair and
filters by actual regional Sector membership. It does not replace a product
code with an activity code by string substitution. The source matrix is read
only for its axes during snapshotting; no economic calculations or matrix data
are exported.

Refresh the snapshot after a BONSAI classification or HIOT-identity update:

```bash
python doc/scripts/snapshot_bonsai_classifications.py \
  --bonsai /path/to/_bonsai \
  --technosphere /path/to/frozen/extended_size_hiot.b2.pkl
python doc/scripts/build_sectoral_scope.py \
  --country-output doc/source/_static/data/economy/country-scope.json
python doc/scripts/audit_classification_scope.py
python doc/scripts/build_download_metadata.py
node --max-old-space-size=8192 doc/scripts/build_classification_concordances.mjs
node --test tests/docs/test_bonsai_classifications.cjs
```

## Installable concordance API

`build_runtime_concordances.py` invokes the same canonical compiler and writes
compressed metadata under `mario/database_profiles/data/concordances`. These package assets
support `Database.get_concordances` without documentation files, downloads,
nxbase or IO calculations. The default output is `{native_label: [codes]}`;
`details=True` retains source locations, direction, qualification and provenance.

Primary NACE 2.1 and CPA 2.2 results reproduce the reviewed explorer footprints.
Additional editions use explicit route prefixes or official taxonomy bridges.
Reverse/composed bridges remain qualified; no product membership is derived
from an industry. Native parent labels are never expanded into memberships.

The compiled metadata also retain the official NACE 2.1 and CPA 2.2 hierarchies.
`db.get_aggregation(set=..., classification=..., level="section")` prepares
inputs for the existing aggregation API; `level="2 digits"` selects divisions.
All linked codes must collapse to one ancestor to assign a native item.
Unresolved items remain individual (or raise with `unresolved="raise"`), with
reasons and hierarchy sources in each frame's `attrs["concordance"]` report.
Regional domains retain actual region/item pairs. These are reviewable
correspondence-footprint proposals; source qualifications still apply.

`hs2007-exiobase.json` snapshots the original EXIOBASE v3 / HS 2007 workbook
supplied with BONSAI. Exact typed `C_` product aliases join its rows to `EXIO3P`;
unmatched aliases remain excluded. HS codes are validated against UN Comtrade's
2007 description inventory. The source files, checksums, cells and edition are
retained. The API does not substitute HS 2007 for other editions.

Regenerate after changing a classification source:

```bash
python doc/scripts/build_runtime_concordances.py
```

To refresh the HS snapshot as well, pass `--hs /path/to/ex2hs07_1ton.xlsx`
and `--hs-descriptions /path/to/hs3_desc.csv.gz`. The latter is the local
`concordance` port's UN Comtrade description table, not a concordance source.
The source workbook is read only; no source database or coefficients are bundled.

## Historical implementation notes — superseded where the current contract differs

This folder contains normalized **classification metadata**, never economic
matrices. The first documented vocabularies are EXIOBASE 3 monetary industries,
ADB's 35-sector vocabulary and Open CEDA 2024 BEA-based industry descriptors.
The notes below describe the earlier activity-only implementation.

GLORIA v060 also retains all 120 published **ISIC Rev. 4 section anchors**.
`gloria-060-sections.json` preserves the source cell locations, source workbook
checksum, native vocabulary and the complete binary 97-to-120 historical
concordance. It applies to all verified identical annual v060 classifications.
Snapshot it before restoring the README online-only with
`doc/scripts/gloria/sectoral.py`. The public heatmap uses this metadata snapshot,
so refreshing sectoral coverage does not require hydrating economic archives.

The reviewed fine activity layer now lives in nxbase:
`data/sets/activity_correspondences.json` keeps all 120 GLORIA v060 and all 50
OECD ICIO native identities, governed parent references, explicit ISIC members,
current-NACE refinements, relationship precision and sources. GLORIA's detailed
links are **editorial reviews**, not a publisher-supplied detailed concordance.
Published current section anchors and the 97-to-120 descriptors remain evidence.
Qualified overlaps and source-label conflicts are retained, never reported as
exclusive subdivisions. OECD's ISIC ranges come from Table 2 of the official
2025 annex, including 241+2431 versus 242+2432 and 301 versus 302–309.

`nxbase-gloria-icio.json` is the validated static snapshot used by the site. It
records the exact source workbook and correspondence checksums, actual workbook
cell locations, canonical nxbase concepts and every intermediate official route.
There is no activity-to-commodity traversal. Both OECD Regular and Extended use
one column because their native economic sets are identical. GLORIA uses one
v060 activity column across its identical annual sets. Classifications with no
verified route remain null; a reviewed native footprint does not establish a
complete partition of all reference classes.

FIGARO's 64 industries and WIOD 2016's 56 industries now use published NACE
Rev. 2 definitions through `nxbase/data/sets/nace2_activity_correspondences.json`.
The resolver `src/nxbase/sets/nace_activity_correspondence.py` checks each actual
nxbase identity, parent and source code against the explicit definition. The
complete Eurostat revision table links all 615 old classes to 650 current
classes; new class 46.89 has no predecessor and stays unverified. Source split,
merge and overlap qualifications remain attached to every route. These are
classification footprints, not coefficients for allocating economic values.

`nxbase-figaro-wiod.json` records the native definitions, actual workbook cells,
published code memberships and all intermediate revision steps. Source S26 is
Eurostat FIGARO classification metadata with the parsed native CSV identity;
S27 is WIOD's official Appendix Table A1 and retained code/label headers; S29
is the full Eurostat correspondence; S30 is the actual nxbase workbook.
Broad nxbase parents are lineage only: the **published native code** enumerates
the classes. For example WIOD N covers all old section N, whereas FIGARO N77
covers only division 77. WIOD's R_S aggregate explicitly spans two sections.

Identical annual IOT/SUT activity vocabularies share one heatmap column per
family. FIGARO pxp commodities are excluded from NACE coverage. WIOD's current
and previous-year-price IOT descriptions and SUT activity codes retain their
own nxbase identities, readable descriptions and paths in Focus on a country
and downloads, joined by the verified code/label bridge rather than row order.
Documented activity columns are selected by default, except EXIOBASE Hybrid,
which remains available in the database picker because most of its activity
footprint duplicates monetary EXIOBASE.

GTAP 12 standard (65 sectors) and Power (76 sectors) are metadata-only profiles.
Both have 163 published reporting regions, with Power 2023's local MARIO index
verified against the complete public vocabulary. Standard's seven reference
years come from the publisher; Power currently exposes only verified 2023 scope.
An explicit version key (12) keeps Standard and Power coexisting in the latest
country view rather than treating one variant as a newer release.
The local 2017 regional workbook identifies GTAP 11 and is not reused as a GTAP
12 inventory. No economic, GDP, value-added or emissions observations enter the
public browser, its charts or its downloadable workbooks.

`nxbase/data/sets/gtap_activity_correspondences.json` owns the published GTAP
native vocabularies and concordances as a source metadata sidecar. Native GTAP
rows are not yet materialized in the Rosetta workbook or SQL; the existing
nxbase power concepts are used and validated read-only. Refreshing
`snapshot_nxbase_scope.py` also regenerates `nxbase-gtap.json` using
`src/nxbase/sets/gtap_activity_correspondence.py`.

The public GSC3 classification defines some categories through CPC 2.1 and
others through ISIC Rev. 4. Product-defined categories retain explicit
homonymous product and CPC-to-producing-activity bridges, followed by the full
official ISIC4 ↔ NACE2 and NACE2 → NACE2.1 tables. These qualified producer
footprints never imply activity/product identity or allocation weights.
Owner-occupied dwellings (dwe) has no published ISIC concordance and stays
unverified rather than being assigned by its label.

Power's technology correspondences are explicitly editorial reviews of the
published split, not a publisher-supplied detailed NACE concordance. Actual
nxbase power chains retain electricity components, while the technical note's
heat/co-generation scope remains a qualified additional component. These links
are partial and cannot generate 1/k exclusive-subdivision claims. OtherBL is
mixed; TnD combines transmission and distribution. Source S31 is the GTAP
concordance; S32 the current Power definition; S33/S34 the official UN tables;
S35 the actual nxbase workbook; S36 the heat methodology; S37 regional
definitions; S38 the index-only verification. Intermediate flags, row positions
and checksums remain in the downloadable snapshots and CSV.

Refresh public GTAP inventories before rebuilding classifications:

```bash
python doc/scripts/build_gtap_profiles.py
python doc/scripts/snapshot_nxbase_scope.py --nxbase /path/to/nxbase
python doc/scripts/build_sectoral_scope.py \
  --country-output doc/source/_static/data/economy/country-scope.json
```

**Refresh after nxbase updates.** Run both snapshot commands when the workbook
or correspondence decisions change, then rebuild the heatmap and country lookup:

```bash
python doc/scripts/snapshot_nxbase_scope.py --nxbase /path/to/nxbase
python doc/scripts/snapshot_nxbase_activity.py \
  --workbook /path/to/nxbase/data/sets/nxbase_sets.xlsx \
  --pilot doc/classifications/sectoral/activity-pilot.json \
  --output doc/classifications/sectoral/nxbase-activity-refinements.json
python doc/scripts/build_sectoral_scope.py \
  --country-output doc/source/_static/data/economy/country-scope.json
node --test tests/docs/test_sectoral_scope.cjs tests/docs/test_country_scope.cjs
```

The build validates the complete native vocabulary before reusing a route.
Sphinx and the public site use committed JSON, not a live nxbase connection.
None of this requires hydrating GLORIA economic or satellite archives.

- `nace21-structure.json`: all 1,047 official NACE Rev. 2.1 headings, including
  every one of the 651 leaf classes. Source: Eurostat ShowVoc headings; the source
  URL, retrieval date and original SHA-256 are included.
- `activity-pilot.json`: native labels, published cross-classification links,
  their sources and selected connected routes from the three-database
  Classification Explorer pilot. Each intermediate edge retains its source row,
  relationship, partial flags and comments. Only published routes enter the
  heatmap unless a reviewed native-activity containment route supersedes them.
  Proposed nxbase concepts, broad parent-only expansions and editorial
  hypotheses do not enter its numeric colours.
- `nxbase-activity-refinements.json`: actual activity parent chains for the
  twelve EXIOBASE electricity-generation categories, including intermediate
  nxbase concepts, workbook cell ranges and the source workbook checksum.
  Ten technology routes are reviewed against Eurostat's explanatory notes.
  Four non-renewable categories give 1/4 for NACE 35.11; six renewable categories
  give 1/6 for 35.12. These native-activity containment links replace their old
  product/producer correspondence footprint entirely, so renewable technologies
  cannot leak into non-renewable production or steam production via revision
  splits. Other native mappings are unchanged by this focused review.

Snapshot the reviewed nxbase paths from the current workbook (read-only):

**Refresh after nxbase updates.** Changes to `nxbase_sets.xlsx` do not propagate
automatically. Whenever its activity parents or labels change, regenerate this
snapshot, review changed paths and any pending assumptions, then rebuild the
sectoral data. Compare the recorded source SHA-256 with the current workbook
before publishing updated scope mappings. The site and Sphinx build use the
committed JSON snapshot and require no live nxbase installation.

```bash
python doc/scripts/snapshot_nxbase_activity.py \
  --workbook /path/to/nxbase/data/sets/nxbase_sets.xlsx \
  --pilot doc/classifications/sectoral/activity-pilot.json \
  --output doc/classifications/sectoral/nxbase-activity-refinements.json
```

The mixed biomass/waste category and electricity n.e.c. remain separately
listed candidates. Biomass/waste cannot be assumed wholly renewable; nxbase's
fossil anchor for n.e.c. is explicitly an editorial hypothesis. They do not
inflate the confirmed subdivision count. Consequently, 1/4 and 1/6 describe
confirmed native detail, not an assertion of exhaustive partitioning. Their
current parent paths remain inspectable, and the CSV exports them with pending
status, `counted_in_resolution=false` and a blank numeric index.

Regenerate from the repository root:

```bash
python doc/scripts/build_sectoral_scope.py
node --test tests/docs/test_sectoral_scope.cjs
```

The build checks exact native-label sets before sharing a mapping across parsed
profiles. Different classifications retain separate columns even when they have
the same number of categories. Annual monetary EXIOBASE classifications collapse
into one column; ADB's regional variants share their unchanged 35-sector set.
Other activity inventories are available but gray until their leaf concordances
are reviewed. Mixed `Sector` sets with no identified activity/product role are
not assigned a role by guessing.

## Meaning of the colour

The resolution index uses **1/k** when k native categories are linked
exclusively to the same NACE leaf in the complete taxonomy and their selected
routes have no partial-overlap flag. A many-to-many correspondence, or a native
category spanning other NACE classes/sections, is not treated as a subdivision.
For example, EXIOBASE's two native aluminium activities linked exclusively to
NACE 24.42 give 1/2; CEDA's three categories for 28.15 give 1/3.

Otherwise, the value is the largest number of distinct reference classes linked
to a matching native category within the row's original section. Each native
category's section-footprint fraction remains separate: its denominator is that
section's complete leaf-class count. Cross-section links remain explicit.

The three-colour scale uses MARIO cyan at 0, yellow at **10** and orange at
**50+**. It is linear from 0 to 10, then logarithmic to 50; values above 50 have
the same orange, while hover text and CSV retain their exact numeric values.
Missing remains gray, never zero. Scale colours stay fixed while filtering,
zooming or changing the selected databases. A single vertical colourbar shows
Finer than NACE at its lower end and Coarser than NACE at its upper end. The
only key below the heatmap is Concordance unverified. Each leaf remains present;
short sections receive extra display height for their labels. Geometry is not an
economic weight. A clicked cell retains contrasting halo/outline borders, and a
selection message links to its native-sector details below.

Published binary correspondences do not necessarily enumerate exact contents of
a native category. For example, EXIOBASE's product-to-producing-activity route
links paddy rice to mixed farming and support activities as well as growing rice.
These are retained as a *correspondence footprint*, not asserted to be four whole
activities coaggregated in an industry. CEDA uses a producer/activity route
through BEA and NAICS, with partial overlaps preserved. A value of 1 does not
prove one-to-one equivalence or a complete partition. An exact containment-based
resolution score requires additional reviewed extension definitions in nxbase.

The viewer and exported CSV deliberately say **linked classes**, preserve the
route precision and never use these counts to redistribute GDP, value added or
emissions. Unknown is `null`, not zero. No economic allocation weights are inferred.


## EXIOBASE Hybrid activities and the shared monetary classification

`nxbase-exiobase-hybrid.json` retains the actual parent chains of all 164
`EX3h` activities. Their codes/labels are checked against the official Hybrid
3.3.18 identities in `exiobase-hybrid-activities.json` and MARIO's parsed set.
This parent snapshot alone is not the final classification footprint.

`exiobase-monetary-activities.json` retains all 163 industry codes, names and
aliases from the publisher's `exio3class.xlsx`, with the original checksum and
sheet rows. The build verifies code, normalized label and alias in both
publisher classifications before reusing a monetary correspondence. There are
161 common identities. For 149 of them, the existing monetary routes, reference
classes and overlap flags are reused unchanged, with an explicit Hybrid → EX3h
→ monetary classification bridge and both source cell locations. This bridge is
classification metadata, not a new parent link in nxbase.

The twelve electricity-generation activities keep their existing reviewed
nxbase containment routes: ten confirmed categories, plus biomass/waste and
n.e.c. kept pending. Hybrid's two gas activities remain separate from the
combined monetary gas industry. Secondary lead retains its narrower native
label and its own nxbase path to NACE 24.43. Neither exception receives the
monetary aggregate footprint automatically.

The resulting heatmap and country lookup have 162 linked native activities,
two pending generation activities and 648 linked reference classes. The three
unlinked classes remain unverified. Shared broad activities such as beverages,
textiles and hotels/restaurants now use their published correspondence
footprints; they are not reconstructed by expanding an nxbase containment
parent. Published producer/product intermediates inherited from the monetary
routes remain explicitly typed and source-referenced. Queried native and target
sets are activities; no activity/product identity is inferred.

Refresh after nxbase updates, alongside the other snapshots:

```bash
python doc/scripts/snapshot_nxbase_hybrid.py \
  --workbook /path/to/nxbase/data/sets/nxbase_sets.xlsx
python doc/scripts/build_sectoral_scope.py \
  --country-output doc/source/_static/data/economy/country-scope.json
node --test tests/docs/test_sectoral_scope.cjs tests/docs/test_country_scope.cjs
```

Publisher identity snapshots are committed classification metadata, so no
source matrix downloads or annual parsing are required. New classifications
require a reviewed identity snapshot: the build rejects changed vocabularies
or aliases instead of applying the bridge by label similarity. All nxbase
snapshots must record the same workbook checksum before building.
