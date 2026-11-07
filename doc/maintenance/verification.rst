Documentation verification
==========================

Run commands from the repository root, using an environment with MARIO and
``doc/docs-requirements.txt`` installed. Use the supported Python version in
the project's packaging configuration. No real database is needed for a
documentation build or the structural checks below.

Build and structural checks
---------------------------

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

* Execute changed minimal examples against packaged IOT/SUT fixtures where
  possible. Check outputs, units and axes, not just absence of exceptions.
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
* For regional footprints, verify producer and consumer attribution on a small
  cross-border example; a conserved global total can hide incorrect geography.
  For chained scenario workflows, execute the sequence through transformations
  that consume only the baseline or discard other scenarios, and check that
  earlier updates survive.
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
