Documentation verification
==========================

For cross-repository site links, verify the public Tutorials and Explorer hosts
and representative paths before merging navigation changes. Their publication
workflows run independently. Verify a tutorial's deployed source manifest against
its canonical repository commit and compare downloaded notebook source cells
with that commit. Preserve the original repository links used in external work.
Check the complete cross-site header at narrow widths, including 320 and 390 px.
Verify dropdown keyboard activation and that the document has no horizontal
overflow with menus closed or open.
Run ``node --test tests/docs/test_external_links.cjs`` when changing link
behaviour. Check navigation between the main site, Tutorials and Explorer in
the browser and confirm that these destinations use the current tab. The shared
``_static/external-links.js`` owns this behaviour; update consumers' pinned theme
revisions after its publication.
Check links across all three sites. Tutorials and Explorer link to the MARIO
library on Latest. Their own version selectors control their local sites.
Read each site's version manifest to verify its own source commits independently.

Run commands from the repository root, using an environment with MARIO and
``doc/docs-requirements.txt`` installed. Use the supported Python version in
the project's packaging configuration. No real database is needed for a
documentation build or the structural checks below.

Build and structural checks
---------------------------

For the versioned publisher, use clean checkouts of the configured refs and a
fresh output directory::

   node --test tests/docs/test_docs_versions.cjs tests/docs/test_external_links.cjs
   python doc/scripts/build_versioned_docs.py --latest-source /path/to/latest --output /tmp/mario-versioned-docs

Both site builds run with strict Sphinx warnings. Check ``docs-versions.json``
against the checkout commits. In a browser, switch a common page and anchor,
then a Gallery-only model page that falls back to the Latest home. Check native
home links with scripts unavailable, Escape and narrow layouts with the selector
open. Download a companion from each channel and check that its guide notice
links back to that channel.
Check the floating selector at the bottom-right before and after scrolling,
including when the header hides, and at the page footer. Its menu opens upward,
stays within a 320 px viewport and supports keyboard activation and Escape.
Check both colour themes and verify that footer links remain accessible.
Check the Latest/Model Gallery selector and retired Preview redirects,
including query strings and anchors. Verify that Latest documents the
released package and that both headers use their source configuration.
Check that Model Gallery contains the approved Latest pages, except
where a source change explicitly removes one. In Model Gallery, Docs and Get
started keep the approved menus from Latest. Check both menus from the
Gallery and from Tutorials and Explorer with Model Gallery selected.
Check that the MARIO logo still opens the MARIO homepage in this channel.
Open the model catalogue from Resources and check its link to the model page.
From Docs → Configuration, open Setup a model from the gallery in the topic sidebar.
Select Model Gallery from a page shared with Latest and check that the
corresponding page and anchor open. On a library page without a counterpart,
verify that the current page stays open with Model Gallery selected. From a
model page, verify that selecting Latest opens its home
page. Exercise Docs, Configuration, Teaching and the model API reference
before switching.
The publisher checks that same-site links and assets throughout the gallery
resolve there, except for links in the version selector. From the Gallery,
open Tutorials and Explorer, follow a link on each site, and return via Docs.
Also select Model Gallery from an open tutorial and an Explorer view and check
that the page, query and anchor are retained. Check that the selector remains
on Gallery until the user chooses another version. Verify the legacy Configuration
redirect, the shared resource images and the model's publication and data links.

Build with warnings treated as errors, then check the built guides::

   python -m sphinx -b html -W --keep-going doc/source /tmp/mario-docs-review
   python doc/scripts/check_documentation.py /tmp/mario-docs-review

Use a new output directory after moving/removing pages or assets. ``-E -a``
rebuilds Sphinx documents but does not delete obsolete published files.

The checker discovers Get started, guide/parser pages and notebook companions from the
source tree. It checks built pages, sidebar membership, local links and anchors,
guide downloads, the shared download list, output-free notebook copies with
source notices, and absence of raw notebook sources. It does not execute examples,
check external URLs or assess scientific correctness and visual quality.
For format/nomenclature changes, also verify IOT/SUT block selection, keyboard
activation and old Nomenclature/technology-assumption URLs with their fragments.
Check regional subheadings inside the productive and final-demand axes, one
symbol per matrix, and structural zeros at their origin/destination coordinates.
In single-region mode, change import representation, external trade resolution
and import classification. Check import-row partitions, foreign origins inside
the classification, export-partner annotations and the active row definitions.
``tests/docs/test_table_configurations.py`` checks the generated layouts.
Run ``node tests/docs/test_table_formats.cjs`` to check selector combinations,
dynamic row definitions, regional-scope changes and import-matrix anchors.

Run existing tests relevant to the change. For public APIs or notebook downloads::

   python -m pytest tests/docs/test_api_reference_docs.py
   python -m pytest tests/docs/test_downloads.py

For database profiles, concordances or aggregation, use the matching tests in
``tests/core/test_database_profiles.py``, ``tests/api/test_concordances.py`` and
``tests/api/test_classification_aggregation.py``. Explorer changes also have
Python and Node checks under ``tests/docs/``; select the affected component.
Do not rerun every real database for a wording-only edit.

Example verification
--------------------

For national SUT import parsers, compare ``U + IMP_a`` and ``Yc + IMP_Y``
cell by cell against the source total-use workbooks. Check imported rows against
the official import-use table, and verify both product and activity balances
before and after aggregation. Published income hierarchies require disjoint
components: including both value-added subtotals and their parts can pass a
shape-only parser test while invalidating the model. Retain source rounding
differences explicitly and include a coefficient reset and accounting/export
round trip in the integration check.

* Execute changed minimal examples against packaged IOT/SUT fixtures where
  possible. Check outputs, units and axes, not just absence of exceptions.
* Export separate-import models with reversed productive axes in flow and
  coefficient modes. After Excel, text and Parquet reloads, calculate prices
  and import coefficients to verify that import columns follow the economic
  blocks' normalized order. ``tests/ops/test_import_representation.py`` covers
  these round trips.
* For ``to_cvxlab()``, run ``tests/api/test_to_cvxlab.py`` with CVXLab installed.
  Exercise its actual template APIs and reload the generated workbooks into
  CVXLab's database. Check copied-set dependency order, existing attributes and
  unmapped data, several scenarios, incomplete coordinates, repeated calls and
  rollback after a file-replacement failure. Exercise shared target tables for
  use/final demand, imports and factors/extensions, including multiple scenarios
  and conflicting source coordinates. Execute the companion with its
  downloaded settings workbook beside it. The split-model bridge has separate
  Excel/CSV integration checks in the add-sector tests.
* For an installable model, install into an isolated environment and open the
  workspace outside the source checkout. Check the pinned installation and a
  development ref, fetch the declared data, and verify that the documented
  YAML change and Python override give the same result.
* Source-specific calls need the stated release, files and options. When those
  inputs are unavailable, check signatures and data requirements and explicitly
  report that full execution was not performed.
* For locally supplied EXIOBASE MRSUT bundles, compare all four matrices' row
  and column labels, order and units with the supported layout. Verify imported
  cells against the source, including the supply transpose. Treat ``meta.json``
  ``vers`` as a revision date; use supplier confirmation for a release absent
  from the payload. Keep local parser support separate from the public download
  registry and parsed-release catalogue.
* Check that notebook variables are defined in execution order and selectors
  match the intended source. Retain portable paths and input/licence guidance.
* After scientific changes, reconcile affected equations, examples, figures and
  captions. State characterization, allocation and numerical limits where relevant.
  For comparisons across modelling packages, match classifications, units and
  the treatment of zero-output nodes when checking equations and executed
  outputs. Inspect the recipes of technologies assigned positive production
  after a zero-output reference. Verify the receiving package's actual input
  files and model execution as well as the independent equation calculation.
* For regional footprints, verify producer and consumer attribution on a small
  cross-border example; a conserved global total can hide incorrect geography.
  For SUT regional extraction, check use-side and supply-side imports
  independently, including direct final-demand imports and nonzero ``Ya``.
  Exercise unequal supplier shares and co-production when attributing imports
  to producers; verify each source cell, both native monetary balances and
  unchanged domestic environmental accounts. Keep sparse-path checks separate
  from numerical comparisons so a unified matrix cannot hide a memory regression.
  For IOT and SUT import accounts, aggregate the productive classification alone
  and verify the row classifier in both production and final-demand factor
  blocks. Exercise total foreign sourcing and explicit source regions. Preserve
  factors with empty classification levels, including Excel round trips with
  the declared matrix layouts. Canonicalize missing MultiIndex components in
  scalar/groupby references before label alignment: pandas can encode the same
  missing component either as a level member or as a missing code.
  Include import-only classifier labels and geographic presets for explicit
  origins. Check that descriptor mappings do not add endogenous nodes and that
  the stored Region aggregation map includes only the modeled source regions.
  Inspect the combined DataFrame view before aggregation and verify its factor
  and final-demand cells without changing live matrix indexes or row ordering.
  For chained scenario workflows, execute the sequence through transformations
  that consume only the baseline or discard other scenarios, and check that
  earlier updates survive.
  For separate-import configurations, compare prices, production and domestic
  environmental accounts with the combined representation. Exercise both flow
  and coefficient resets, SUT-to-IOT methods, scenario copies, the combined
  display and monetary balance diagnostics. Round-trip native imports through
  Excel and matrix/flat text and Parquet, retaining their structural manifests,
  descriptors and technology assumptions. Use the pinned pandas dependency
  when checking flat reconstruction and copy-on-write behaviour.
  ``tests/docs/test_workflow_examples.py`` executes the affected RST recipes
  and notebook calculations on small accounting/scenario fixtures. Run it
  when changing those examples; source-database and live-provider runs remain
  separate checks.
* For supply-mix recipe estimation, check unequal donor outputs, receiving-region
  domestic/import shares and the no-purchases fallback independently. Verify
  both intermediate and direct coefficients, SUT commodity-to-activity routing,
  sparse storage and unchanged source scenarios. Exercise more than one newly
  activated producer in reversed update order; donor weights and sourcing must
  come from the pre-update scenario, not earlier imputed columns.

* For REX3, verify nested economic/GHG version folders and explicit companion
  selectors, including the requested year and country-sector label alignment.
  Check MATLAB orientation against source cells, coefficient-to-flow GHG
  reconstruction using complete output, and absolute LULUCF on a zero-output
  sector. Keep the detailed GHG sum separate from the overlapping native
  aggregate. Saved notebook outputs document a previous run, not a current
  integration test; rerun a full real bundle when it is locally available.
  ``scripts/benchmark_rex3_ghg.py`` streams an independent source benchmark
  before database construction; inspect country-sector diagnostics as well as
  global totals. Compare imported blocks with the oriented source cells to
  distinguish source imbalances from import errors. Verify that native direct
  household climate impacts remain in ``EY`` and are not silently included
  in the detailed source aggregate, whose first five ``EY`` rows are zero.

For FIGARO E3, compare matrix and flat-file economic blocks cell by cell,
including signed primary inputs and direct final-demand adjustments. Match
extension columns by codes after trimming source whitespace; their final-demand
order differs from the economic tables. Test gas-mass versus characterised
CO2eq choices, separate EDU/OCC estimates, all energy indicators, conflicting
browser copies, and product-extension allocation on unequal industry outputs.
Nonzero extensions on zero-output industries must remain in native industry
accounts or cause an explicit allocation error, never disappear.
Verify model solvability separately from import: inspect sparse Leontief
systems for closed unit-feedback components and confirm the strict public
inverse rejects them before allocating a dense identity. A solve-based preset
does not establish nonsingularity. Keep source loops and undefined results
explicit rather than silently changing flows or applying a pseudoinverse.

If partial calculations are offered, exercise the public multiplier target
on the source files, verify the undefined-node mask and residual of the
independent subsystem, and confirm that full inverse requests still fail.
Inspect construction-code export precision before attributing a singularity
to rounding; the existence of an unrounded export path is not evidence that
its data is available or nonsingular.

When a parser applies a source-specific correction, test its exact node and
structural guards, the uncorrected opt-out, and both matrix representations.
Verify changed cells against the raw import, retained absolute accounts and
output references, and the reported balance gap. Pin required output
references before eager calculations, for both Database and ModelState.
Check full inverses against the corrected operator and confirm that opting
out restores the original failure. Such a correction is not evidence that
the unmodified source is invertible or that its producer accounts reconcile
with native final-demand footprints.

Rendered review
---------------

Serve the built site locally::

   python doc/scripts/serve_preview.py /tmp/mario-docs-review --port 8765

Open ``http://127.0.0.1:8765``. For affected pages:

* Reach the feature through its topic menu, then follow its API/example links.
* Inspect desktop and narrow layouts. Check heading hierarchy, code overflow,
  tables, figures and the visibility of prerequisites and interpretation limits.
* Open disclosures with mouse and keyboard; test deep links into them.
* Download a companion and confirm it is the intended notebook. For changes to
  download cleaning, inspect code, source notices and removal of saved results.

A local build is not an online deployment. Report the preview location and
verification limits accurately; publishing is a separate task.
